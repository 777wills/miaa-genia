#!/usr/bin/env bash
# Ejecuta las cinco consultas de prueba con las dos configuraciones de prompts
# y guarda las respuestas en outputs/basico y outputs/mejorado.

set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-.venv/bin/python}"

if [[ ! -x "$PYTHON" ]]; then
  echo "No se encontró el intérprete $PYTHON. Crea el entorno virtual como indica el README." >&2
  exit 1
fi

mkdir -p outputs/basico outputs/mejorado

for consulta in src/datos/consultas/*.txt; do
  nombre="$(basename "$consulta" .txt)"

  "$PYTHON" src/app.py "$consulta" \
    --configuracion src/settings.toml \
    --salida "outputs/basico/${nombre}.txt" > /dev/null

  "$PYTHON" src/app.py "$consulta" \
    --configuracion src/settings-final.toml \
    --salida "outputs/mejorado/${nombre}.txt" > /dev/null

  echo "Procesado: ${nombre}"
done

echo "Listo. Respuestas disponibles en outputs/"
