import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import observability


class TestObservability(unittest.TestCase):
    def test_registra_estado_error_duracion_y_enmascara_texto_libre(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "actions.jsonl"
            with patch.object(observability, "LOG_PATH", log_path):
                observability.registrar_evento(
                    "session-1",
                    "verificar_elegibilidad_devolucion",
                    {"numero_pedido": "ECO-2026-1042", "motivo": "dato privado"},
                    {"ok": False, "mensaje": "Requiere revisión"},
                    "REVISION_HUMANA",
                    "Requiere revisión",
                    3.25,
                )

            event = json.loads(log_path.read_text(encoding="utf-8"))

        self.assertEqual(event["tool"], "verificar_elegibilidad_devolucion")
        self.assertTrue(event["timestamp"])
        self.assertEqual(event["session_id"], "session-1")
        self.assertEqual(event["status"], "REVISION_HUMANA")
        self.assertEqual(event["error"], "Requiere revisión")
        self.assertEqual(event["duracion_ms"], 3.25)
        self.assertEqual(event["argumentos"]["numero_pedido"], "***")
        self.assertEqual(event["argumentos"]["motivo"], "***")


if __name__ == "__main__":
    unittest.main()