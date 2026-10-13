import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from interfaz import render_eventos


class TestPanelActividad(unittest.TestCase):
    def test_muestra_puntajes_fragmentos_y_escapa_contenido_rag(self):
        panel = render_eventos(
            [
                {
                    "herramienta": "consultar_base_conocimiento",
                    "status": "OK",
                    "duracion_ms": 12.5,
                    "resultado": {
                        "ok": True,
                        "metodo": "chroma_bge_reranker",
                        "respuesta": "Respuesta breve.\nClasificación: RESUELTO_POR_ASISTENTE",
                        "candidatos": [
                            {
                                "metadata": {
                                    "fuente": "politica.md",
                                    "seccion": "Plazos",
                                    "similitud": 0.83,
                                },
                                "contenido": "Texto <script>alert(1)</script>",
                            }
                        ],
                        "fragmentos_finales": [
                            {
                                "metadata": {
                                    "fuente": "politica.md",
                                    "puntaje_reranker": 0.97,
                                },
                                "contenido": "El plazo es de 30 días.",
                            }
                        ],
                    },
                }
            ],
            "session-1",
        )

        self.assertIn("1 candidatos; 1 fragmentos finales", panel)
        self.assertIn("similitud 0.83", panel)
        self.assertIn("reranker 0.97", panel)
        self.assertIn("El plazo es de 30 días.", panel)
        self.assertIn("Clasificación: RESUELTO_POR_ASISTENTE", panel)
        self.assertNotIn("<script>", panel)
        self.assertIn("&lt;script&gt;", panel)


if __name__ == "__main__":
    unittest.main()