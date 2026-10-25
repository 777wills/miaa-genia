import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from devoluciones import (
    consultar_pedido,
    generar_etiqueta,
    registrar_devolucion,
    verificar_elegibilidad,
)

TEXTIL_OK = {"sin_uso": True, "conserva_etiquetas": True, "sin_olores_ni_manchas": True}

class TestDevoluciones(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_devolucion_textil_valida(self):
        r = verificar_elegibilidad(
            "ECO-2026-1042", "TEX-0031", "cambio de talla", TEXTIL_OK, self.state
        )
        self.assertTrue(r["elegible"])
        self.assertEqual(r["codigo"], "ELEGIBLE")
        self.assertIn("codigo_autorizacion", r)

    def test_condicion_no_informada_se_pide_al_cliente(self):
        r = verificar_elegibilidad(
            "ECO-2026-1042",
            "TEX-0031",
            "cambio de talla",
            {"sin_uso": True, "conserva_etiquetas": True},
            self.state,
        )
        self.assertFalse(r["elegible"])
        self.assertEqual(r["codigo"], "CONDICION_INSUFICIENTE")
        self.assertEqual(r["requisitos_faltantes"], ["sin_olores_ni_manchas"])
        self.assertIn("olores ni manchas", r["mensaje"])

    def test_condicion_incumplida_rechaza_la_devolucion(self):
        r = verificar_elegibilidad(
            "ECO-2026-1042",
            "TEX-0031",
            "cambio de talla",
            {**TEXTIL_OK, "conserva_etiquetas": False},
            self.state,
        )
        self.assertFalse(r["elegible"])
        self.assertEqual(r["codigo"], "CONDICION_NO_CUMPLIDA")
        self.assertEqual(r["requisitos_incumplidos"], ["conserva_etiquetas"])

    def test_sin_condiciones_lista_todos_los_requisitos_de_la_categoria(self):
        r = verificar_elegibilidad(
            "ECO-2026-1042", "HOG-0118", "cambié de opinión", None, self.state
        )
        self.assertEqual(r["codigo"], "CONDICION_INSUFICIENTE")
        self.assertEqual(
            r["requisitos_faltantes"],
            ["sin_uso", "conserva_empaque", "accesorios_completos"],
        )

    def test_electronica_no_exige_serie_al_cliente_y_la_anuncia_en_la_etiqueta(self):
        v = verificar_elegibilidad(
            "ECO-2026-1235",
            "ELE-0009",
            "no cumplió mis expectativas",
            {"conserva_empaque": True, "conserva_cables_y_manual": True},
            self.state,
        )
        self.assertTrue(v["elegible"])
        e = generar_etiqueta(v["codigo_autorizacion"], self.state)
        self.assertIn("número de serie", e["instruccion"])

    def test_garantia_legal_se_escala_a_persona(self):
        r = verificar_elegibilidad(
            "ECO-2026-1042",
            "TEX-0031",
            "solicito aplicar la garantía legal",
            TEXTIL_OK,
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
            {"sin_uso": True, "conserva_empaque": True, "accesorios_completos": True},
            self.state,
        )
        self.assertFalse(r["elegible"])
        self.assertEqual(r["codigo"], "PEDIDO_NO_ENTREGADO")

    def test_pedido_inexistente(self):
        r = verificar_elegibilidad(
            "ECO-2026-9999", "TEX-0031", "cambio de talla", None, self.state
        )
        self.assertFalse(r["elegible"])
        self.assertEqual(r["codigo"], "PEDIDO_NO_EXISTE")

    def test_sku_inexistente(self):
        r = verificar_elegibilidad(
            "ECO-2026-1042", "SKU-9999", "cambio de talla", None, self.state
        )
        self.assertFalse(r["elegible"])
        self.assertEqual(r["codigo"], "SKU_NO_PERTENECE_PEDIDO")

    def test_fuera_de_plazo_se_escala(self):
        with patch("devoluciones._dias_desde_entrega", return_value=31):
            r = verificar_elegibilidad(
                "ECO-2026-1042",
                "TEX-0031",
                "cambio de talla",
                TEXTIL_OK,
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
            None,
            self.state,
        )
        self.assertFalse(r["elegible"])
        self.assertEqual(r["codigo"], "CATEGORIA_NO_RETORNABLE")

    def test_excepcion_averia_requiere_persona(self):
        r = verificar_elegibilidad(
            "ECO-2026-1372",
            "ALI-0455",
            "llegó con el empaque roto",
            None,
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
            TEXTIL_OK,
            self.state,
        )
        self.assertFalse(r["elegible"])
        self.assertEqual(r["codigo"], "DEVOLUCION_EXISTENTE")

    def test_consulta_de_pedido_advierte_devolucion_en_curso(self):
        r = consultar_pedido("ECO-2026-1268")
        self.assertEqual(r["numero_devolucion"], "DEV-2026-0311")
        self.assertIn("DEV-2026-0311", r["mensaje"])
        self.assertNotIn("mensaje", consultar_pedido("ECO-2026-1042"))

    def test_no_genera_etiqueta_sin_autorizacion(self):
        r = generar_etiqueta("AUT-INVENTADA", self.state)
        self.assertFalse(r["ok"])
        self.assertEqual(r["codigo"], "AUTORIZACION_INVALIDA")

    def test_autorizacion_no_se_reutiliza(self):
        validacion = verificar_elegibilidad(
            "ECO-2026-1042", "TEX-0031", "cambio de talla", TEXTIL_OK, self.state
        )
        etiqueta = generar_etiqueta(validacion["codigo_autorizacion"], self.state)
        repetida = generar_etiqueta(validacion["codigo_autorizacion"], self.state)
        self.assertTrue(etiqueta["ok"])
        self.assertFalse(repetida["ok"])
        self.assertEqual(repetida["codigo"], "AUTORIZACION_CONSUMIDA")

    def test_etiqueta_sin_registrar_se_reutiliza_en_vez_de_duplicarse(self):
        primera = verificar_elegibilidad(
            "ECO-2026-1042", "TEX-0031", "cambio de talla", TEXTIL_OK, self.state
        )
        segunda = verificar_elegibilidad(
            "ECO-2026-1042", "TEX-0031", "cambio de color", TEXTIL_OK, self.state
        )
        original = generar_etiqueta(primera["codigo_autorizacion"], self.state)
        repetida = generar_etiqueta(segunda["codigo_autorizacion"], self.state)
        self.assertTrue(repetida["ok"])
        self.assertEqual(repetida["codigo"], "ETIQUETA_PENDIENTE_REGISTRO")
        self.assertEqual(repetida["numero_etiqueta"], original["numero_etiqueta"])
        registro = registrar_devolucion(repetida["numero_etiqueta"], self.state)
        self.assertEqual(registro["codigo"], "REGISTRADA")

    def test_etiqueta_registrada_no_se_vuelve_a_emitir(self):
        primera = verificar_elegibilidad(
            "ECO-2026-1042", "TEX-0031", "cambio de talla", TEXTIL_OK, self.state
        )
        segunda = verificar_elegibilidad(
            "ECO-2026-1042", "TEX-0031", "cambio de color", TEXTIL_OK, self.state
        )
        etiqueta = generar_etiqueta(primera["codigo_autorizacion"], self.state)
        registrar_devolucion(etiqueta["numero_etiqueta"], self.state)
        repetida = generar_etiqueta(segunda["codigo_autorizacion"], self.state)
        self.assertFalse(repetida["ok"])
        self.assertEqual(repetida["codigo"], "ETIQUETA_EXISTENTE")

    def test_verificacion_posterior_al_registro_detecta_duplicado(self):
        v = verificar_elegibilidad(
            "ECO-2026-1042", "TEX-0031", "cambio de talla", TEXTIL_OK, self.state
        )
        e = generar_etiqueta(v["codigo_autorizacion"], self.state)
        registrar_devolucion(e["numero_etiqueta"], self.state)
        otra = verificar_elegibilidad(
            "ECO-2026-1042", "TEX-0031", "cambio de color", TEXTIL_OK, self.state
        )
        self.assertEqual(otra["codigo"], "DEVOLUCION_EXISTENTE")

    def test_registro_sin_etiqueta_valida_se_rechaza(self):
        r = registrar_devolucion("RET-INVENTADA", self.state)
        self.assertFalse(r["ok"])
        self.assertEqual(r["codigo"], "ETIQUETA_NO_EXISTE")

    def test_flujo_completo_y_sin_duplicado(self):
        v = verificar_elegibilidad(
            "ECO-2026-1042", "TEX-0031", "cambio de talla", TEXTIL_OK, self.state
        )
        e = generar_etiqueta(v["codigo_autorizacion"], self.state)
        self.assertTrue(e["ok"])
        self.assertEqual(e["codigo"], "ETIQUETA_GENERADA")

        reg1 = registrar_devolucion(e["numero_etiqueta"], self.state)
        self.assertTrue(reg1["ok"])
        self.assertEqual(reg1["codigo"], "REGISTRADA")

        reg2 = registrar_devolucion(e["numero_etiqueta"], self.state)
        self.assertTrue(reg2["ok"])
        self.assertEqual(reg2["codigo"], "YA_REGISTRADA")

if __name__ == "__main__":
    unittest.main()
