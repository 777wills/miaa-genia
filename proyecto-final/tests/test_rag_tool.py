import importlib
import json
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

module_names = ("tools", "rag")
previous_modules = {name: sys.modules.get(name) for name in module_names}

# Se sustituye rag para no cargar modelos ni el índice al importar las herramientas.
sys.modules["rag"] = ModuleType("rag")
sys.modules.pop("tools", None)

try:
    tools_module = importlib.import_module("tools")
    consultar_base_conocimiento = tools_module.consultar_base_conocimiento
finally:
    for name, previous in previous_modules.items():
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous


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

        with patch.object(tools_module, "_cadena_rag", return_value=cadena):
            mensaje = consultar_base_conocimiento.invoke(
                {
                    "name": "consultar_base_conocimiento",
                    "args": {"consulta": "plazo devolución"},
                    "id": "call-rag",
                    "type": "tool_call",
                }
            )

        contenido = json.loads(mensaje.content)
        self.assertTrue(contenido["ok"])
        self.assertEqual(contenido["respuesta"], "El plazo es de 30 días.")
        self.assertEqual(contenido["fragmentos"][0]["fuente"], "politica-devoluciones.md")
        self.assertNotIn("candidatos", contenido)

        artefacto = mensaje.artifact
        self.assertEqual(artefacto["metodo"], "chroma_bge_reranker")
        self.assertEqual(artefacto["candidatos"][0]["metadata"]["similitud"], 0.83)
        self.assertEqual(
            artefacto["fragmentos_finales"][0]["metadata"]["puntaje_reranker"], 0.91
        )

    def test_verificacion_expone_condiciones_booleanas_opcionales(self):
        esquema = tools_module.verificar_elegibilidad_devolucion.args
        self.assertEqual(
            set(esquema) - {"numero_pedido", "sku", "motivo"},
            {
                "sin_uso", "conserva_etiquetas", "sin_olores_ni_manchas", "conserva_empaque",
                "accesorios_completos", "conserva_cables_y_manual", "sin_marcas_escritura",
            },
        )
        self.assertIn("etiquetas", esquema["conserva_etiquetas"]["description"])


if __name__ == "__main__":
    unittest.main()