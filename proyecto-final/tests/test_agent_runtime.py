import importlib
import itertools
import json
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from pydantic import Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class ModeloFalso(GenericFakeChatModel):
    """Modelo de chat con respuestas predefinidas que registra los mensajes recibidos."""

    llamadas: list = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.llamadas.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def modelo(*respuestas):
    return ModeloFalso(messages=iter(respuestas))


def herramienta(nombre, resultado=None, error=None):
    argumentos = {}

    @tool(nombre)
    def _herramienta(sku: str = "") -> dict:
        """Herramienta de prueba."""
        argumentos["sku"] = sku
        if error:
            raise error
        return resultado or {"ok": True, "codigo": "OK"}

    return _herramienta, argumentos


def cargar_agente():
    # Se sustituye rag para no cargar modelos ni el índice vectorial.
    previos = {nombre: sys.modules.get(nombre) for nombre in ("agent", "tools", "rag")}
    sys.modules["rag"] = ModuleType("rag")
    sys.modules.pop("tools", None)
    sys.modules.pop("agent", None)
    try:
        return importlib.import_module("agent")
    finally:
        for nombre, previo in previos.items():
            if previo is None:
                sys.modules.pop(nombre, None)
            else:
                sys.modules[nombre] = previo


agent_module = cargar_agente()


class TestAgentRuntime(unittest.TestCase):
    def setUp(self):
        parche = patch.object(agent_module, "registrar_evento")
        self.registrar = parche.start()
        self.addCleanup(parche.stop)

    def construir_agente(self, llm, tools=(), max_llamadas_modelo=4):
        return agent_module.IrisAgent(
            session_id="test-session",
            llm=llm,
            tools=list(tools),
            max_llamadas_modelo=max_llamadas_modelo,
        )

    def test_respuesta_directa_no_invoca_tools(self):
        llm = modelo(AIMessage(content="¡Hola! Estoy bien, gracias."))
        agent = self.construir_agente(llm)

        result = agent.responder("Hola, ¿cómo estás?")

        self.assertTrue(result["ok"])
        self.assertEqual(result["respuesta"], "¡Hola! Estoy bien, gracias.")
        self.assertEqual(result["eventos"], [])
        self.assertEqual(len(llm.llamadas), 1)

    def test_respuesta_en_bloques_omite_firma_y_metadata(self):
        llm = modelo(
            AIMessage(
                content=[
                    {
                        "type": "text",
                        "text": "Tienes 30 días calendario para solicitar una devolución.",
                        "extras": {"signature": "firma-interna"},
                    },
                    {"type": "image", "url": "dato-interno"},
                ]
            )
        )
        agent = self.construir_agente(llm)

        result = agent.responder("¿Cuál es el plazo?")

        self.assertEqual(
            result["respuesta"],
            "Tienes 30 días calendario para solicitar una devolución.",
        )

    def test_ejecuta_tool_y_devuelve_tool_message_al_modelo(self):
        validar, argumentos = herramienta("validar", {"ok": True, "codigo": "ELEGIBLE"})
        llm = modelo(
            AIMessage(
                content="",
                tool_calls=[{"name": "validar", "args": {"sku": "TEX-0031"}, "id": "call-1"}],
            ),
            AIMessage(content="La validación fue correcta."),
        )
        agent = self.construir_agente(llm, [validar])

        result = agent.responder("Valida el producto")

        self.assertEqual(argumentos, {"sku": "TEX-0031"})
        self.assertEqual(result["respuesta"], "La validación fue correcta.")
        self.assertEqual(result["eventos"][0]["herramienta"], "validar")
        self.assertEqual(result["eventos"][0]["status"], "ELEGIBLE")
        self.assertEqual(result["pasos"], 2)
        self.assertEqual(len(llm.llamadas), 2)
        respuesta_tool = [m for m in llm.llamadas[1] if isinstance(m, ToolMessage)]
        self.assertEqual(respuesta_tool[0].tool_call_id, "call-1")
        self.assertEqual(json.loads(respuesta_tool[0].content)["codigo"], "ELEGIBLE")
        self.registrar.assert_called_once()

    def test_tool_desconocida_se_reporta_al_modelo(self):
        llm = modelo(
            AIMessage(content="", tool_calls=[{"name": "no_existe", "args": {}, "id": "call-2"}]),
            AIMessage(content="No pude ejecutar esa acción."),
        )
        validar, _ = herramienta("validar")
        agent = self.construir_agente(llm, [validar])

        result = agent.responder("Ejecuta una herramienta inexistente")

        self.assertTrue(result["ok"])
        self.assertEqual(result["eventos"][0]["status"], "HERRAMIENTA_NO_PERMITIDA")
        self.assertFalse(result["eventos"][0]["resultado"]["ok"])

    def test_error_de_tool_se_convierte_en_resultado_controlado(self):
        consultar, _ = herramienta("consultar", error=RuntimeError("fallo controlado"))
        llm = modelo(
            AIMessage(content="", tool_calls=[{"name": "consultar", "args": {}, "id": "call-4"}]),
            AIMessage(content="No pude completar la consulta."),
        )
        agent = self.construir_agente(llm, [consultar])

        result = agent.responder("Consulta")

        self.assertTrue(result["ok"])
        self.assertEqual(result["eventos"][0]["status"], "ERROR_HERRAMIENTA")
        self.assertIn("fallo controlado", result["eventos"][0]["error"])
        self.assertIn("No respondas con información propia", result["eventos"][0]["resultado"]["siguiente_paso"])
        self.assertEqual(result["respuesta"], "No pude completar la consulta.")

    def test_limita_cantidad_de_llamadas_al_modelo(self):
        validar, _ = herramienta("validar")
        llm = ModeloFalso(
            messages=itertools.repeat(
                AIMessage(content="", tool_calls=[{"name": "validar", "args": {}, "id": "call-3"}])
            )
        )
        agent = self.construir_agente(llm, [validar], max_llamadas_modelo=2)

        result = agent.responder("Valida")

        self.assertFalse(result["ok"])
        self.assertIn("límite de acciones", result["respuesta"])
        self.assertEqual(len(llm.llamadas), 2)
        self.assertGreaterEqual(len(result["eventos"]), 1)

    def test_artifact_llega_al_panel_y_no_al_modelo(self):
        @tool("buscar", response_format="content_and_artifact")
        def buscar(consulta: str) -> tuple[str, dict]:
            """Herramienta de prueba con artifact."""
            return json.dumps({"ok": True, "respuesta": "breve"}), {
                "ok": True,
                "respuesta": "breve",
                "candidatos": [1, 2, 3],
            }

        llm = modelo(
            AIMessage(
                content="",
                tool_calls=[{"name": "buscar", "args": {"consulta": "plazo"}, "id": "call-5"}],
            ),
            AIMessage(content="Listo."),
        )
        agent = self.construir_agente(llm, [buscar])

        result = agent.responder("¿Plazo?")

        self.assertEqual(result["eventos"][0]["resultado"]["candidatos"], [1, 2, 3])
        enviado = [m for m in llm.llamadas[1] if isinstance(m, ToolMessage)][0]
        self.assertNotIn("candidatos", enviado.content)

    def test_conserva_llamadas_y_resultados_entre_turnos(self):
        validar, _ = herramienta("validar", {"ok": True, "codigo": "CONDICION_INSUFICIENTE"})
        llm = modelo(
            AIMessage(
                content="",
                tool_calls=[{"name": "validar", "args": {"sku": "TEX-0031"}, "id": "call-6"}],
            ),
            AIMessage(content="¿Tiene olores o manchas?"),
            AIMessage(content="Gracias."),
        )
        agent = self.construir_agente(llm, [validar])

        agent.responder("Quiero devolver la camiseta")
        segundo = agent.responder("No tiene olores ni manchas")

        contexto = llm.llamadas[2]
        humanos = [m.content for m in contexto if isinstance(m, HumanMessage)]
        self.assertEqual(humanos, ["Quiero devolver la camiseta", "No tiene olores ni manchas"])
        self.assertTrue(any(isinstance(m, ToolMessage) for m in contexto))
        self.assertEqual(segundo["respuesta"], "Gracias.")
        self.assertEqual(segundo["eventos"], [])

    def test_tras_el_limite_la_conversacion_continua_en_un_hilo_nuevo(self):
        validar, _ = herramienta("validar")
        llamada = AIMessage(content="", tool_calls=[{"name": "validar", "args": {}, "id": "call-7"}])
        llm = modelo(llamada, llamada, AIMessage(content="Hola de nuevo."))
        agent = self.construir_agente(llm, [validar], max_llamadas_modelo=2)

        cortado = agent.responder("Valida")
        siguiente = agent.responder("Hola")

        self.assertFalse(cortado["ok"])
        self.assertTrue(siguiente["ok"])
        self.assertEqual(siguiente["respuesta"], "Hola de nuevo.")

    def test_catalogo_de_casos_cubre_todos_los_escenarios(self):
        cases = json.loads((ROOT / "tests" / "casos_agente.json").read_text(encoding="utf-8"))
        self.assertEqual([case["id"] for case in cases], list("ABCDEFGHIJK"))


if __name__ == "__main__":
    unittest.main()
