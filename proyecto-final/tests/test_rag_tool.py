import sys
import unittest
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

if importlib.util.find_spec("langchain_core") is None:
    langchain_core = ModuleType("langchain_core")
    langchain_core.__path__ = []
    langchain_tools = ModuleType("langchain_core.tools")

    def tool(function):
        function.name = function.__name__
        function.invoke = lambda arguments: function(**arguments)
        return function

    langchain_tools.tool = tool
    sys.modules["langchain_core"] = langchain_core
    sys.modules["langchain_core.tools"] = langchain_tools

rag_stub = ModuleType("rag")
sys.modules["rag"] = rag_stub

from tools import consultar_base_conocimiento


class TestHerramientaRag(unittest.TestCase):
    def test_conecta_cadena_y_devuelve_evidencia_de_recuperacion(self):
        candidato = SimpleNamespace(
            metadata={"fuente": "faq.json", "similitud": 0.83},
            page_content="El plazo es de 30 días.",
        )
        final = SimpleNamespace(
            metadata={"fuente": "politica-devoluciones.md", "puntaje_reranker": 0.91},
            page_content="La devolución se solicita dentro de 30 días.",
        )
        cadena = SimpleNamespace(
            invoke=lambda entrada: {
                "respuesta": "El plazo es de 30 días.",
                "candidatos": [candidato],
                "fragmentos": [final],
            }
        )

        with patch("tools._cadena_rag", return_value=cadena):
            resultado = consultar_base_conocimiento.invoke({"consulta": "plazo devolución"})

        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["metodo"], "chroma_bge_reranker")
        self.assertEqual(resultado["candidatos"][0]["metadata"]["similitud"], 0.83)
        self.assertEqual(
            resultado["fragmentos_finales"][0]["metadata"]["puntaje_reranker"], 0.91
        )


if __name__ == "__main__":
    unittest.main()