"""Asistente de atención al cliente de EcoMarket con recuperación aumentada (RAG).

Recibe el mensaje de un cliente, ejecuta la cadena LCEL definida en rag.py con la configuración
elegida (con o sin reranking) y guarda la respuesta junto con los fragmentos que la sustentan.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from rag import BASE_DIR, cargar_configuracion, construir_cadena


def describir_fragmentos(fragmentos: list[Document], reranking: bool) -> str:
    if not fragmentos:
        return "Fragmentos entregados al modelo: ninguno superó el umbral de relevancia.\n"
    filas = ["Fragmentos entregados al modelo:"]
    for posicion, fragmento in enumerate(fragmentos, start=1):
        meta = fragmento.metadata
        puntaje = f" · reranker {meta['puntaje_reranker']:.4f}" if reranking else ""
        filas.append(
            f"  {posicion}. {meta['id']} ({meta['fuente']}) · posición vectorial "
            f"{meta['posicion_vectorial']} · similitud {meta['similitud']:.4f}{puntaje}"
        )
    return "\n".join(filas) + "\n"


def construir_encabezado(
    consulta: Path, ruta_configuracion: Path, configuracion: dict[str, Any], resultado: dict
) -> str:
    general = configuracion["general"]
    recuperacion = configuracion["recuperacion"]
    reranking = recuperacion.get("reranking", False)
    detalle = (
        f"reranking con {recuperacion['modelo_reranker']} · umbral "
        f"{recuperacion.get('umbral_relevancia', 0)}"
        if reranking
        else "sin reranking"
    )
    return (
        f"Consulta: {consulta.name}\n"
        f"Configuración: {ruta_configuracion.name}\n"
        f"Modelo: {general['modelo']} · temperatura: {general.get('temperatura', 0)}\n"
        f"Recuperación: k={recuperacion['k_candidatos']} → n={recuperacion['n_finales']} · "
        f"{detalle}\n"
        f"{describir_fragmentos(resultado['fragmentos'], reranking)}"
        f"{'-' * 80}\n"
    )


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Genera la respuesta del asistente de EcoMarket para una consulta de cliente."
    )
    parser.add_argument("consulta", type=Path, help="Archivo de texto con el mensaje del cliente.")
    parser.add_argument(
        "--configuracion",
        type=Path,
        default=BASE_DIR / "settings-reranking.toml",
        help="Archivo TOML con los parámetros de recuperación, del modelo y los prompts.",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=None,
        help="Archivo donde se guarda la respuesta además de imprimirla.",
    )
    return parser


def main() -> None:
    argumentos = construir_parser().parse_args()

    if not argumentos.consulta.is_file():
        raise SystemExit(f"No se encontró el archivo de consulta: {argumentos.consulta}")
    if not argumentos.configuracion.is_file():
        raise SystemExit(f"No se encontró el archivo de configuración: {argumentos.configuracion}")

    configuracion = cargar_configuracion(argumentos.configuracion)
    consulta = argumentos.consulta.read_text(encoding="utf-8").strip()

    resultado = construir_cadena(configuracion).invoke({"consulta": consulta})
    respuesta = resultado["respuesta"].strip()
    encabezado = construir_encabezado(
        argumentos.consulta, argumentos.configuracion, configuracion, resultado
    )

    print(encabezado + respuesta)

    if argumentos.salida:
        argumentos.salida.parent.mkdir(parents=True, exist_ok=True)
        argumentos.salida.write_text(encabezado + respuesta + "\n", encoding="utf-8")
        print(f"\n[Respuesta guardada en {argumentos.salida}]", file=sys.stderr)


if __name__ == "__main__":
    main()
