import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from devoluciones import generar_etiqueta, registrar_devolucion, verificar_elegibilidad

class TestDevoluciones(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_devolucion_textil_valida(self):
        r = verificar_elegibilidad(
            "ECO-2026-1042",
            "TEX-0031",
            "cambio de talla",
            "sin uso y con etiquetas",
            self.state,
        )
        self.assertTrue(r["elegible"])
        self.assertIn("codigo_autorizacion", r)

    def test_pedido_no_entregado(self):
        r = verificar_elegibilidad(
            "ECO-2026-1087",
            "HOG-0204",
            "cambié de opinión",
            "sin uso y con empaque",
            self.state,
        )
        self.assertFalse(r["elegible"])
        self.assertEqual(r["codigo"], "PEDIDO_NO_ENTREGADO")

    def test_perecedero_no_retornable(self):
        r = verificar_elegibilidad(
            "ECO-2026-1372",
            "ALI-0455",
            "ya no lo quiero",
            "sin abrir",
            self.state,
        )
        self.assertFalse(r["elegible"])
        self.assertEqual(r["codigo"], "CATEGORIA_NO_RETORNABLE")

    def test_excepcion_averia_requiere_persona(self):
        r = verificar_elegibilidad(
            "ECO-2026-1372",
            "ALI-0455",
            "llegó con el empaque roto",
            "sin abrir",
            self.state,
        )
        self.assertFalse(r["elegible"])
        self.assertTrue(r["requiere_agente_humano"])
        self.assertEqual(r["codigo"], "EXCEPCION_ECOMARKET")

    def test_devolucion_ya_existente(self):
        r = verificar_elegibilidad(
            "ECO-2026-1268",
            "TEX-0145",
            "cambio de talla",
            "sin uso y con etiquetas",
            self.state,
        )
        self.assertFalse(r["elegible"])
        self.assertEqual(r["codigo"], "DEVOLUCION_EXISTENTE")

    def test_no_genera_etiqueta_sin_autorizacion(self):
        r = generar_etiqueta("AUT-INVENTADA", self.state)
        self.assertFalse(r["ok"])
        self.assertEqual(r["codigo"], "AUTORIZACION_INVALIDA")

    def test_flujo_completo_y_sin_duplicado(self):
        v = verificar_elegibilidad(
            "ECO-2026-1042",
            "TEX-0031",
            "cambio de talla",
            "sin uso y con etiquetas",
            self.state,
        )
        e = generar_etiqueta(v["codigo_autorizacion"], self.state)
        self.assertTrue(e["ok"])

        reg1 = registrar_devolucion(e["numero_etiqueta"], self.state)
        self.assertTrue(reg1["ok"])
        self.assertEqual(reg1["codigo"], "REGISTRADA")

        reg2 = registrar_devolucion(e["numero_etiqueta"], self.state)
        self.assertTrue(reg2["ok"])
        self.assertEqual(reg2["codigo"], "YA_REGISTRADA")

if __name__ == "__main__":
    unittest.main()
