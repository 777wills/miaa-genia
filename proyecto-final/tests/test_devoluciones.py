import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
            "sin uso, conserva las etiquetas adheridas, sin olores ni manchas",
            self.state,
        )
        self.assertTrue(r["elegible"])
        self.assertIn("codigo_autorizacion", r)

    def test_textil_sin_confirmar_olores_y_mancha_no_es_elegible(self):
        r = verificar_elegibilidad(
            "ECO-2026-1042",
            "TEX-0031",
            "cambio de talla",
            "sin uso y conserva las etiquetas",
            self.state,
        )
        self.assertFalse(r["elegible"])
        self.assertEqual(r["codigo"], "CONDICION_INSUFICIENTE")

    def test_garantia_legal_se_escala_a_persona(self):
        r = verificar_elegibilidad(
            "ECO-2026-1042",
            "TEX-0031",
            "solicito aplicar la garantía legal",
            "sin uso, conserva las etiquetas adheridas, sin olores ni manchas",
            self.state,
        )
        self.assertFalse(r["elegible"])
        self.assertTrue(r["requiere_agente_humano"])
        self.assertEqual(r["codigo"], "REVISION_HUMANA")

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

    def test_pedido_inexistente(self):
        r = verificar_elegibilidad(
            "ECO-2026-9999", "TEX-0031", "cambio de talla", "", self.state
        )
        self.assertFalse(r["elegible"])
        self.assertEqual(r["codigo"], "PEDIDO_NO_EXISTE")

    def test_sku_inexistente(self):
        r = verificar_elegibilidad(
            "ECO-2026-1042", "SKU-9999", "cambio de talla", "", self.state
        )
        self.assertFalse(r["elegible"])
        self.assertEqual(r["codigo"], "SKU_NO_PERTENECE_PEDIDO")

    def test_fuera_de_plazo_se_escala(self):
        with patch("devoluciones._dias_desde_entrega", return_value=31):
            r = verificar_elegibilidad(
                "ECO-2026-1042",
                "TEX-0031",
                "cambio de talla",
                "sin uso, conserva las etiquetas adheridas, sin olores ni manchas",
                self.state,
            )
        self.assertFalse(r["elegible"])
        self.assertTrue(r["requiere_agente_humano"])
        self.assertEqual(r["codigo"], "FUERA_DE_PLAZO")

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

    def test_autorizacion_no_se_reutiliza(self):
        validacion = verificar_elegibilidad(
            "ECO-2026-1042",
            "TEX-0031",
            "cambio de talla",
            "sin uso, conserva las etiquetas adheridas, sin olores ni manchas",
            self.state,
        )
        etiqueta = generar_etiqueta(validacion["codigo_autorizacion"], self.state)
        repetida = generar_etiqueta(validacion["codigo_autorizacion"], self.state)
        self.assertTrue(etiqueta["ok"])
        self.assertFalse(repetida["ok"])
        self.assertEqual(repetida["codigo"], "AUTORIZACION_CONSUMIDA")

    def test_no_crea_etiqueta_duplicada_para_el_mismo_producto(self):
        primera = verificar_elegibilidad(
            "ECO-2026-1042",
            "TEX-0031",
            "cambio de talla",
            "sin uso, conserva las etiquetas adheridas, sin olores ni manchas",
            self.state,
        )
        segunda = verificar_elegibilidad(
            "ECO-2026-1042",
            "TEX-0031",
            "cambio de color",
            "sin uso, conserva las etiquetas adheridas, sin olores ni manchas",
            self.state,
        )
        generar_etiqueta(primera["codigo_autorizacion"], self.state)
        repetida = generar_etiqueta(segunda["codigo_autorizacion"], self.state)
        self.assertFalse(repetida["ok"])
        self.assertEqual(repetida["codigo"], "ETIQUETA_EXISTENTE")

    def test_flujo_completo_y_sin_duplicado(self):
        v = verificar_elegibilidad(
            "ECO-2026-1042",
            "TEX-0031",
            "cambio de talla",
            "sin uso, conserva las etiquetas adheridas, sin olores ni manchas",
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
