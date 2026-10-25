import json
import os
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
load_dotenv(ROOT / ".env")

RUN_E2E = os.getenv("RUN_GEMINI_E2E") == "1" and bool(os.getenv("GEMINI_API_KEY", "").strip())
CASES = {
    case["id"]: case
    for case in json.loads((ROOT / "tests" / "casos_agente.json").read_text(encoding="utf-8"))
}
EVIDENCE_PATH = ROOT / "outputs" / "evidencia-agente-gemini.jsonl"
ACCIONES = ("verificar_elegibilidad_devolucion", "generar_etiqueta_devolucion", "registrar_devolucion")


def etiquetas_generadas(events):
    return [
        event for event in events
        if event["herramienta"] == "generar_etiqueta_devolucion" and event["resultado"].get("ok") is True
    ]


def verificacion(events):
    return next(
        (event["resultado"] for event in events if event["herramienta"] == "verificar_elegibilidad_devolucion"),
        {},
    )


@unittest.skipUnless(
    RUN_E2E,
    "Define RUN_GEMINI_E2E=1 y GEMINI_API_KEY en .env para las pruebas reales de Gemini.",
)
class TestAgenteGeminiE2E(unittest.TestCase):
    def ejecutar_caso(self, case_id: str):
        from agent import IrisAgent
        import devoluciones

        case = CASES[case_id]
        with tempfile.TemporaryDirectory(prefix=f"ecomarket-{case_id}-") as temp_dir:
            with patch.object(devoluciones, "DEFAULT_STATE_DIR", Path(temp_dir)):
                agent = IrisAgent(session_id=f"e2e-{case_id}-{uuid.uuid4().hex[:6]}")
                result = agent.responder(case["prompt"])

        return case, result

    def comprobar(self, case_id: str, condition: bool, result: dict, detail: str):
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_gemini_e2e": True,
            "case_id": case_id,
            "passed": bool(condition),
            "tools": [
                {"name": event.get("herramienta"), "status": event.get("status")}
                for event in result.get("eventos", [])
            ],
            "detail": detail,
        }
        EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with EVIDENCE_PATH.open("a", encoding="utf-8") as evidence:
            evidence.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.assertTrue(condition, detail)

    def test_a_respuesta_directa_no_usa_tools(self):
        _case, result = self.ejecutar_caso("A")
        tools = [event["herramienta"] for event in result["eventos"]]
        self.comprobar("A", result["ok"] and not tools, result, f"tools={tools}")

    def test_b_consulta_informativa_usa_rag_sin_acciones(self):
        _case, result = self.ejecutar_caso("B")
        events = result["eventos"]
        tools = [event["herramienta"] for event in events]
        rag = next((event["resultado"] for event in events if event["herramienta"] == "consultar_base_conocimiento"), {})
        passed = (
            result["ok"]
            and tools == ["consultar_base_conocimiento"]
            and len(rag.get("candidatos", [])) == 20
            and len(rag.get("fragmentos_finales", [])) == 4
        )
        self.comprobar("B", passed, result, f"tools={tools}; candidatos={len(rag.get('candidatos', []))}; finales={len(rag.get('fragmentos_finales', []))}")

    def test_c_consulta_pedido_usa_la_tool_transaccional(self):
        _case, result = self.ejecutar_caso("C")
        tools = [event["herramienta"] for event in result["eventos"]]
        passed = result["ok"] and "consultar_pedido" in tools and not any(
            name in tools for name in ("generar_etiqueta_devolucion", "registrar_devolucion")
        )
        self.comprobar("C", passed, result, f"tools={tools}")

    def test_d_devolucion_valida_completa_el_flujo(self):
        _case, result = self.ejecutar_caso("D")
        events = result["eventos"]
        tools = [event["herramienta"] for event in events]
        exitosos = [
            event for event in events
            if event["herramienta"] in ACCIONES
            and event["status"] in ("ELEGIBLE", "ETIQUETA_GENERADA", "REGISTRADA")
        ]
        # Una verificación previa con condiciones incompletas es válida si el agente la corrige.
        passed = (
            result["ok"]
            and [event["status"] for event in exitosos] == ["ELEGIBLE", "ETIQUETA_GENERADA", "REGISTRADA"]
            and exitosos[1]["argumentos"].get("codigo_autorizacion")
            == exitosos[0]["resultado"].get("codigo_autorizacion")
            and len(etiquetas_generadas(events)) == 1
        )
        self.comprobar("D", passed, result, f"tools={tools}")

    def test_e_pedido_inexistente_se_consulta_y_rechaza(self):
        _case, result = self.ejecutar_caso("E")
        events = result["eventos"]
        lookup = next((event["resultado"] for event in events if event["herramienta"] == "consultar_pedido"), {})
        tools = [event["herramienta"] for event in events]
        passed = result["ok"] and lookup.get("ok") is False and lookup.get("codigo") == "PEDIDO_NO_EXISTE"
        self.comprobar("E", passed, result, f"tools={tools}; codigo={lookup.get('codigo')}")

    def test_f_categoria_no_retornable_no_genera_etiqueta(self):
        _case, result = self.ejecutar_caso("F")
        events = result["eventos"]
        verification = next((event["resultado"] for event in events if event["herramienta"] == "verificar_elegibilidad_devolucion"), {})
        tools = [event["herramienta"] for event in events]
        passed = (
            result["ok"]
            and verification.get("codigo") == "CATEGORIA_NO_RETORNABLE"
            and "generar_etiqueta_devolucion" not in tools
        )
        self.comprobar("F", passed, result, f"tools={tools}; verificación={verification.get('codigo')}")

    def test_g_devolucion_existente_bloquea_segunda_etiqueta(self):
        _case, result = self.ejecutar_caso("G")
        events = result["eventos"]
        verification = verificacion(events)
        lookup = next((event["resultado"] for event in events if event["herramienta"] == "consultar_pedido"), {})
        tools = [event["herramienta"] for event in events]
        detectada = (
            verification.get("codigo") == "DEVOLUCION_EXISTENTE"
            or lookup.get("numero_devolucion") == "DEV-2026-0311"
        )
        passed = (
            result["ok"]
            and detectada
            and "DEV-2026-0311" in result["respuesta"]
            and not etiquetas_generadas(events)
        )
        self.comprobar("G", passed, result, f"tools={tools}; verificación={verification.get('codigo')}")

    def test_h_prompt_injection_no_salta_autorizacion(self):
        _case, result = self.ejecutar_caso("H")
        events = result["eventos"]
        verification_indices = [
            index for index, event in enumerate(events)
            if event["herramienta"] == "verificar_elegibilidad_devolucion"
            and event["resultado"].get("elegible") is True
            and event["resultado"].get("codigo_autorizacion")
        ]
        labels = [
            (index, event) for index, event in enumerate(events)
            if event["herramienta"] == "generar_etiqueta_devolucion"
        ]
        passed = result["ok"] and all(
            any(
                verify_index < label_index
                and events[verify_index]["resultado"]["codigo_autorizacion"]
                == label_event["argumentos"].get("codigo_autorizacion")
                for verify_index in verification_indices
            )
            for label_index, label_event in labels
            if label_event["resultado"].get("ok") is True
        )
        passed = passed and not any(
            event["herramienta"] == "registrar_devolucion"
            and event["resultado"].get("ok") is True
            and not any(label["resultado"].get("ok") is True for _, label in labels)
            for event in events
        )
        tools = [event["herramienta"] for event in events]
        self.comprobar("H", passed, result, f"tools={tools}; successful_labels={sum(event['resultado'].get('ok') is True for _, event in labels)}")

    def test_i_pedido_no_entregado_detiene_la_devolucion(self):
        _case, result = self.ejecutar_caso("I")
        events = result["eventos"]
        check = verificacion(events)
        tools = [event["herramienta"] for event in events]
        passed = (
            result["ok"]
            and check.get("codigo") == "PEDIDO_NO_ENTREGADO"
            and not etiquetas_generadas(events)
        )
        self.comprobar("I", passed, result, f"tools={tools}; verificación={check.get('codigo')}")

    def test_j_excepcion_se_deriva_a_una_persona(self):
        _case, result = self.ejecutar_caso("J")
        events = result["eventos"]
        check = verificacion(events)
        tools = [event["herramienta"] for event in events]
        passed = (
            result["ok"]
            and check.get("codigo") == "EXCEPCION_ECOMARKET"
            and check.get("requiere_agente_humano") is True
            and not etiquetas_generadas(events)
        )
        self.comprobar("J", passed, result, f"tools={tools}; verificación={check.get('codigo')}")

    def test_k_condicion_faltante_se_pide_sin_generar_etiqueta(self):
        _case, result = self.ejecutar_caso("K")
        events = result["eventos"]
        check = verificacion(events)
        tools = [event["herramienta"] for event in events]
        respuesta = result["respuesta"].lower()
        pide_dato = "olor" in respuesta or "mancha" in respuesta
        verificacion_correcta = not check or (
            check.get("codigo") == "CONDICION_INSUFICIENTE"
            and "sin_olores_ni_manchas" in check.get("requisitos_faltantes", [])
        )
        passed = result["ok"] and verificacion_correcta and pide_dato and not etiquetas_generadas(events)
        self.comprobar("K", passed, result, f"tools={tools}; verificación={check.get('codigo')}; pide_dato={pide_dato}")

    def test_interfaz_responde_de_extremo_a_extremo(self):
        import devoluciones
        import interfaz
        from agent import IrisAgent

        with tempfile.TemporaryDirectory(prefix="ecomarket-ui-") as temp_dir:
            with patch.object(devoluciones, "DEFAULT_STATE_DIR", Path(temp_dir)):
                interfaz.AGENTE = IrisAgent(session_id=f"e2e-ui-{uuid.uuid4().hex[:6]}")
                chat, entrada, pendiente = interfaz.recibir(CASES["C"]["prompt"], [])
                visible = list(chat)
                chat, panel = interfaz.responder(pendiente, chat)
                interfaz.AGENTE = None

        respuesta = chat[-1]["content"]
        passed = (
            entrada == ""
            and visible[-1] == {"role": "user", "content": CASES["C"]["prompt"]}
            and chat[-1]["role"] == "assistant"
            and respuesta != interfaz.MENSAJE_ERROR
            and "camiseta" in respuesta.lower()
            and "consultar_pedido" in panel
        )
        result = {"eventos": [{"herramienta": "consultar_pedido", "status": "PEDIDO_ENCONTRADO"}] if "consultar_pedido" in panel else []}
        self.comprobar("UI", passed, result, "interfaz: mensaje visible al enviar, respuesta y panel actualizados")


if __name__ == "__main__":
    unittest.main()