#!/usr/bin/env bash
# Construye el índice si no existe, ejecuta las ocho consultas con las dos configuraciones de
# recuperación y corre el experimento de métricas.

set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-.venv/bin/python}"

if [[ ! -x "$PYTHON" ]]; then
  echo "No se encontró el intérprete $PYTHON. Crea el entorno virtual como indica el README." >&2
  exit 1
fi

if [[ ! -d src/indice ]]; then
  "$PYTHON" src/indexar.py --listar
fi

mkdir -p outputs/sin-reranking outputs/reranking

for consulta in src/datos/consultas/*.txt; do
  nombre="$(basename "$consulta" .txt)"

  "$PYTHON" src/app.py "$consulta" \
    --configuracion src/settings-sin-reranking.toml \
    --salida "outputs/sin-reranking/${nombre}.txt" > /dev/null

  "$PYTHON" src/app.py "$consulta" \
    --configuracion src/settings-reranking.toml \
    --salida "outputs/reranking/${nombre}.txt" > /dev/null

  echo "Procesado: ${nombre}"
done

"$PYTHON" src/experimento.py

echo "Listo. Respuestas y reporte del experimento disponibles en outputs/"
