"""Construye la base de conocimiento vectorial de EcoMarket.

Carga los cuatro documentos, los segmenta según su estructura, calcula los embeddings con
multilingual-e5-base y los guarda en una colección persistente de ChromaDB.
"""

from __future__ import annotations

import argparse
import time
from collections import Counter
from pathlib import Path

from rag import INDICE_DIR, MODELO_EMBEDDINGS, abrir_almacen, construir_base_conocimiento

ARCHIVO_LISTADO = Path(__file__).resolve().parent.parent / "outputs" / "indice" / "fragmentos.md"


def escribir_listado(fragmentos: list, destino: Path) -> None:
    lineas = [
        "# Fragmentos de la base de conocimiento",
        "",
        f"Total: {len(fragmentos)} fragmentos · modelo de embeddings: `{MODELO_EMBEDDINGS}`",
        "",
        "| ID | Tipo | Sección | Caracteres |",
        "| --- | --- | --- | --- |",
    ]
    lineas += [
        f"| `{f.metadata['id']}` | {f.metadata['tipo']} | {f.metadata['seccion']} | "
        f"{len(f.page_content)} |"
        for f in fragmentos
    ]
    lineas.append("")
    for fragmento in fragmentos:
        lineas += [f"## `{fragmento.metadata['id']}`", "", "```text", fragmento.page_content, "```", ""]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(lineas), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexa los documentos de EcoMarket en ChromaDB.")
    parser.add_argument(
        "--listar",
        action="store_true",
        help=f"Además de indexar, vuelca todos los fragmentos en {ARCHIVO_LISTADO.name}.",
    )
    argumentos = parser.parse_args()

    fragmentos = construir_base_conocimiento()
    conteo = Counter(f.metadata["tipo"] for f in fragmentos)
    print(f"Fragmentos generados: {len(fragmentos)} → {dict(conteo)}")

    inicio = time.perf_counter()
    almacen = abrir_almacen()
    almacen.delete_collection()
    almacen = abrir_almacen()
    almacen.add_documents(fragmentos, ids=[f.metadata["id"] for f in fragmentos])
    duracion = time.perf_counter() - inicio
    print(f"Índice guardado en {INDICE_DIR} en {duracion:.1f} s")

    if argumentos.listar:
        escribir_listado(fragmentos, ARCHIVO_LISTADO)
        print(f"Listado de fragmentos en {ARCHIVO_LISTADO}")


if __name__ == "__main__":
    main()
