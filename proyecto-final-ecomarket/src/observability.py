from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "outputs" / "agent-actions.jsonl"

def _sanitizar(value: Any):
    if isinstance(value, dict):
        bloqueadas = {"cliente", "direccion", "telefono", "correo", "email"}
        return {k: ("***" if k.lower() in bloqueadas else _sanitizar(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitizar(v) for v in value]
    return value

def registrar_evento(session_id: str, herramienta: str, argumentos: dict, resultado: dict):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    evento = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "herramienta": herramienta,
        "argumentos": _sanitizar(argumentos),
        "resultado": _sanitizar(resultado),
    }
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(evento, ensure_ascii=False) + "\n")
