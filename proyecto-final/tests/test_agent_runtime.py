import importlib
import json
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class Message:
    def __init__(self, content="", tool_calls=None, tool_call_id=None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.tool_call_id = tool_call_id


class AIMessage(Message):
    pass


class HumanMessage(Message):
    pass


class SystemMessage(Message):
    pass


class ToolMessage(Message):
    pass


class FakeTool:
    def __init__(self, result=None, error=None):
        self.result = result or {"ok": True, "codigo": "OK"}
        self.error = error
        self.arguments = None

    def invoke(self, arguments):
        self.arguments = arguments
        if self.error:
            raise self.error
        return self.result


class FakeLLM:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return self.answers.pop(0)


def cargar_agente_aislado(tool_map):
    names = (
        "agent",
        "tools",
        "dotenv",
        "langchain_core",
        "langchain_core.messages",
        "langchain_google_genai",
    )
    previous = {name: sys.modules.get(name) for name in names}

    core = ModuleType("langchain_core")
    core.__path__ = []
    messages = ModuleType("langchain_core.messages")
    messages.AIMessage = AIMessage
    messages.HumanMessage = HumanMessage
    messages.SystemMessage = SystemMessage
    messages.ToolMessage = ToolMessage
    dotenv = ModuleType("dotenv")
    dotenv.load_dotenv = lambda *_args, **_kwargs: None
    google = ModuleType("langchain_google_genai")
    google.ChatGoogleGenerativeAI = object
    tools = ModuleType("tools")
    tools.TOOLS = []
    tools.TOOL_MAP = tool_map

    sys.modules.update(
        {
            "langchain_core": core,
            "langchain_core.messages": messages,
            "langchain_google_genai": google,
            "dotenv": dotenv,
            "tools": tools,
        }
    )
    sys.modules.pop("agent", None)
    try:
        module = importlib.import_module("agent")
    finally:
        for name, original in previous.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
    return module


class TestAgentRuntime(unittest.TestCase):
    def construir_agente(self, llm, tool_map=None, max_steps=4):
        module = cargar_agente_aislado(tool_map or {})
        agent = module.IrisAgent.__new__(module.IrisAgent)
        agent.llm = llm
        agent.session_id = "test-session"
        agent.max_steps = max_steps
        return module, agent

    def test_respuesta_directa_no_invoca_tools(self):
        llm = FakeLLM([AIMessage(content="¡Hola! Estoy bien, gracias.")])
        _module, agent = self.construir_agente(llm)

        result = agent.responder("Hola, ¿cómo estás?")

        self.assertTrue(result["ok"])
        self.assertEqual(result["eventos"], [])
        self.assertEqual(len(llm.calls), 1)

    def test_ejecuta_tool_y_devuelve_tool_message_al_modelo(self):
        tool = FakeTool({"ok": True, "codigo": "ELEGIBLE"})
        llm = FakeLLM(
            [
                AIMessage(
                    tool_calls=[
                        {"name": "validar", "args": {"sku": "TEX-0031"}, "id": "call-1"}
                    ]
                ),
                AIMessage(content="La validación fue correcta."),
            ]
        )
        module, agent = self.construir_agente(llm, {"validar": tool})

        with patch.object(module, "registrar_evento"):
            result = agent.responder("Valida el producto")

        self.assertEqual(tool.arguments, {"sku": "TEX-0031"})
        self.assertEqual(result["respuesta"], "La validación fue correcta.")
        self.assertEqual(result["eventos"][0]["status"], "ELEGIBLE")
        self.assertEqual(len(llm.calls), 2)
        self.assertTrue(any(isinstance(message, module.ToolMessage) for message in llm.calls[1]))

    def test_tool_desconocida_se_reporta_al_modelo(self):
        llm = FakeLLM(
            [
                AIMessage(tool_calls=[{"name": "no_existe", "args": {}, "id": "call-2"}]),
                AIMessage(content="No pude ejecutar esa acción."),
            ]
        )
        module, agent = self.construir_agente(llm)

        with patch.object(module, "registrar_evento"):
            result = agent.responder("Ejecuta una herramienta inexistente")

        self.assertEqual(result["eventos"][0]["status"], "HERRAMIENTA_NO_PERMITIDA")
        self.assertFalse(result["eventos"][0]["resultado"]["ok"])

    def test_error_de_tool_se_convierte_en_resultado_controlado(self):
        llm = FakeLLM(
            [
                AIMessage(
                    tool_calls=[{"name": "consultar", "args": {}, "id": "call-4"}]
                ),
                AIMessage(content="No pude completar la consulta."),
            ]
        )
        module, agent = self.construir_agente(
            llm,
            {"consultar": FakeTool(error=RuntimeError("fallo controlado"))},
        )

        with patch.object(module, "registrar_evento"):
            result = agent.responder("Consulta")

        self.assertEqual(result["eventos"][0]["status"], "ERROR_HERRAMIENTA")
        self.assertIn("fallo controlado", result["eventos"][0]["error"])

    def test_limita_cantidad_de_pasos(self):
        llm = FakeLLM(
            [AIMessage(tool_calls=[{"name": "validar", "args": {}, "id": "call-3"}])]
        )
        module, agent = self.construir_agente(
            llm,
            {"validar": FakeTool()},
            max_steps=1,
        )

        with patch.object(module, "registrar_evento"):
            result = agent.responder("Valida")

        self.assertFalse(result["ok"])
        self.assertEqual(result["pasos"], 1)

    def test_catalogo_de_casos_cubre_los_ocho_escenarios(self):
        cases = json.loads((ROOT / "tests" / "casos_agente.json").read_text(encoding="utf-8"))
        self.assertEqual([case["id"] for case in cases], list("ABCDEFGH"))


if __name__ == "__main__":
    unittest.main()