import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


class TestArtefactosRubrica(unittest.TestCase):
    def test_estan_las_cuatro_fases_y_material_de_entrega(self):
        required = [
            "README.md",
            "GUIA_VIDEO.md",
            "PROMPTS_DEMO.md",
            "VALIDACION_RUBRICA.md",
            "fase-1-arquitectura.md",
            "fase-2-implementacion.md",
            "fase-3-analisis-critico.md",
            "fase-4-despliegue.md",
            ".env.example",
        ]
        self.assertTrue(all((ROOT / name).is_file() for name in required))

    def test_conserva_parametros_del_rag_del_taller_dos(self):
        with (SRC / "settings-reranking.toml").open("rb") as file:
            settings = tomllib.load(file)
        retrieval = settings["recuperacion"]
        self.assertEqual(retrieval["k_candidatos"], 20)
        self.assertEqual(retrieval["n_finales"], 4)
        self.assertTrue(retrieval["reranking"])
        self.assertEqual(retrieval["modelo_reranker"], "BAAI/bge-reranker-v2-m3")
        self.assertEqual(retrieval["umbral_relevancia"], 0.005)
        self.assertTrue((SRC / "experimento.py").is_file())

    def test_agente_langchain_y_cinco_tools_estan_registrados(self):
        agent_source = (SRC / "agent.py").read_text(encoding="utf-8")
        tools_source = (SRC / "tools.py").read_text(encoding="utf-8")
        self.assertIn(".bind_tools(TOOLS)", agent_source)
        self.assertIn("tool_calls", agent_source)
        for name in (
            "consultar_base_conocimiento",
            "consultar_pedido",
            "verificar_elegibilidad_devolucion",
            "generar_etiqueta_devolucion",
            "registrar_devolucion",
        ):
            self.assertIn(name, tools_source)

    def test_gradio_muestra_recuperacion_y_actividad(self):
        interface_source = (SRC / "interfaz.py").read_text(encoding="utf-8")
        self.assertIn("gr.Blocks", interface_source)
        self.assertIn("gr.Chatbot", interface_source)
        self.assertIn("Ver candidatos recuperados", interface_source)
        self.assertIn("Ver fragmentos enviados al modelo", interface_source)
        self.assertIn("Actividad del agente", interface_source)

    def test_casos_de_agente_definen_a_h(self):
        import json

        cases = json.loads((ROOT / "tests" / "casos_agente.json").read_text(encoding="utf-8"))
        self.assertEqual([case["id"] for case in cases], list("ABCDEFGH"))


if __name__ == "__main__":
    unittest.main()