"""Asistente de atención al cliente de EcoMarket.

Ensambla una cadena de prompts a partir de un archivo de configuración, recupera el contexto
operativo de EcoMarket (pedidos y política de devoluciones) y consulta al modelo generativo.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

BASE_DIR = Path(__file__).resolve().parent
DATOS_DIR = BASE_DIR / "datos"
ARCHIVO_PEDIDOS = DATOS_DIR / "pedidos.json"
ARCHIVO_POLITICA = DATOS_DIR / "politica-devoluciones.md"
ARCHIVO_ENTORNO = BASE_DIR.parent / ".env"

PATRON_SEGUIMIENTO = re.compile(r"ECO-\d{4}-\d{4}", re.IGNORECASE)


def cargar_configuracion(ruta: Path) -> dict[str, Any]:
    with ruta.open("rb") as archivo:
        return tomllib.load(archivo)


def cargar_pedidos() -> list[dict[str, Any]]:
    with ARCHIVO_PEDIDOS.open(encoding="utf-8") as archivo:
        return json.load(archivo)["pedidos"]


def cargar_politica() -> str:
    return ARCHIVO_POLITICA.read_text(encoding="utf-8")


def extraer_numeros_seguimiento(consulta: str) -> list[str]:
    encontrados = [coincidencia.upper() for coincidencia in PATRON_SEGUIMIENTO.findall(consulta)]
    return list(dict.fromkeys(encontrados))


def recuperar_pedidos(consulta: str, pedidos: list[dict[str, Any]]) -> str:
    """Devuelve solo los pedidos citados en la consulta, marcando los que no existen."""
    numeros = extraer_numeros_seguimiento(consulta)
    if not numeros:
        return "No se identificó ningún número de seguimiento en la consulta del cliente."

    indice = {pedido["numero_seguimiento"]: pedido for pedido in pedidos}
    bloques: list[str] = []
    for numero in numeros:
        pedido = indice.get(numero)
        if pedido is None:
            bloques.append(
                f"El número de seguimiento {numero} NO EXISTE en los registros de EcoMarket."
            )
        else:
            bloques.append(json.dumps(pedido, ensure_ascii=False, indent=2))
    return "\n\n".join(bloques)


def construir_contexto(
    consulta: str,
    pedidos: list[dict[str, Any]],
    politica: str,
    recuperacion: str,
    incluir_politica: bool,
) -> str:
    if recuperacion == "selectiva":
        bloque_pedidos = recuperar_pedidos(consulta, pedidos)
    else:
        bloque_pedidos = json.dumps(pedidos, ensure_ascii=False, indent=2)

    secciones = [
        ">>>>> INICIO PEDIDOS",
        bloque_pedidos,
        "<<<<< FIN PEDIDOS",
    ]
    if incluir_politica:
        secciones += [
            "",
            ">>>>> INICIO POLITICA_DEVOLUCIONES",
            politica.strip(),
            "<<<<< FIN POLITICA_DEVOLUCIONES",
        ]
    return "\n".join(secciones)


def ensamblar_mensajes(
    contexto: str, consulta: str, prompts: dict[str, Any]
) -> list[types.Content]:
    """Encadena ejemplos etiquetados, contexto recuperado, consulta e instrucción final."""
    mensajes: list[types.Content] = []

    for ejemplo in prompts.get("ejemplos", []):
        mensajes.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=ejemplo["consulta"].strip())],
            )
        )
        mensajes.append(
            types.Content(
                role="model",
                parts=[types.Part.from_text(text=ejemplo["respuesta"].strip())],
            )
        )

    mensajes.append(
        types.Content(role="user", parts=[types.Part.from_text(text=contexto)])
    )
    mensajes.append(
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text=f">>>>> INICIO CONSULTA\n{consulta.strip()}\n<<<<< FIN CONSULTA"
                )
            ],
        )
    )
    mensajes.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompts["instruction_prompt"].strip())],
        )
    )
    return mensajes


def generar_respuesta(mensajes: list[types.Content], general: dict[str, Any], rol: str) -> str:
    load_dotenv(ARCHIVO_ENTORNO)
    clave = os.getenv("GEMINI_API_KEY")
    if not clave:
        raise SystemExit(
            "Falta la variable GEMINI_API_KEY. Copia .env.example a .env y escribe allí tu clave."
        )

    cliente = genai.Client(api_key=clave)
    configuracion = types.GenerateContentConfig(
        temperature=general.get("temperatura", 0),
        system_instruction=rol.strip() or None,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    respuesta = cliente.models.generate_content(
        model=general["modelo"],
        contents=mensajes,
        config=configuracion,
    )
    return (respuesta.text or "").strip()


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Genera la respuesta del asistente de EcoMarket para una consulta de cliente."
    )
    parser.add_argument("consulta", type=Path, help="Archivo de texto con el mensaje del cliente.")
    parser.add_argument(
        "--configuracion",
        type=Path,
        default=BASE_DIR / "settings.toml",
        help="Archivo TOML con los prompts y los parámetros del modelo.",
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
    general = configuracion["general"]
    prompts = configuracion["prompts"]

    consulta = argumentos.consulta.read_text(encoding="utf-8")
    contexto = construir_contexto(
        consulta=consulta,
        pedidos=cargar_pedidos(),
        politica=cargar_politica(),
        recuperacion=general.get("recuperacion", "selectiva"),
        incluir_politica=general.get("incluir_politica", True),
    )

    mensajes = ensamblar_mensajes(contexto, consulta, prompts)
    respuesta = generar_respuesta(mensajes, general, prompts.get("role_prompt", ""))

    print(respuesta)

    if argumentos.salida:
        argumentos.salida.parent.mkdir(parents=True, exist_ok=True)
        encabezado = (
            f"Consulta: {argumentos.consulta.name}\n"
            f"Configuración: {argumentos.configuracion.name}\n"
            f"Modelo: {general['modelo']} · temperatura: {general.get('temperatura', 0)}\n"
            f"{'-' * 80}\n"
        )
        argumentos.salida.write_text(encabezado + respuesta + "\n", encoding="utf-8")
        print(f"\n[Respuesta guardada en {argumentos.salida}]", file=sys.stderr)


if __name__ == "__main__":
    main()
