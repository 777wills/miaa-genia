"""Núcleo del sistema RAG de EcoMarket.

Reúne las piezas que comparten la indexación, el asistente y el experimento: carga y
segmentación de los documentos, modelo de embeddings, base vectorial, recuperación, reranking,
recuperación exacta de pedidos y la cadena LCEL que produce la respuesta.
"""

from __future__ import annotations

import csv
import json
import os
import re
import tomllib
import unicodedata
from functools import lru_cache
from operator import itemgetter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable, RunnableLambda, RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from sentence_transformers import CrossEncoder

BASE_DIR = Path(__file__).resolve().parent
DATOS_DIR = BASE_DIR / "datos"
INDICE_DIR = BASE_DIR / "indice"
ARCHIVO_ENTORNO = BASE_DIR.parent / ".env"

ARCHIVO_POLITICA = DATOS_DIR / "politica-devoluciones.md"
ARCHIVO_FAQ = DATOS_DIR / "faq.json"
ARCHIVO_CATALOGO = DATOS_DIR / "catalogo-productos.csv"
ARCHIVO_GUIA = DATOS_DIR / "guia-envios-y-pagos.pdf"
ARCHIVO_PEDIDOS = DATOS_DIR / "pedidos.json"

COLECCION = "ecomarket"
MODELO_EMBEDDINGS = "intfloat/multilingual-e5-base"
TAMANO_FRAGMENTO = 800
SOLAPE_FRAGMENTO = 120

PATRON_SEGUIMIENTO = re.compile(r"ECO-\d{4}-\d{4}", re.IGNORECASE)
PATRON_TITULO_GUIA = re.compile(r"^\d{1,2}\. [A-ZÁÉÍÓÚÑ][^\n]*$", re.MULTILINE)
PATRON_PIE_GUIA = re.compile(r"^EcoMarket · Guía de envíos y pagos · Página \d+\s*$", re.MULTILINE)

SIN_CONOCIMIENTO = (
    "No se recuperó ningún fragmento de la base de conocimiento con relevancia suficiente para "
    "esta consulta."
)


# ---------------------------------------------------------------------------------------------
# Carga y segmentación de documentos
# ---------------------------------------------------------------------------------------------


def slug(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    sin_numeral = re.sub(r"^\s*\d+\.\s*", "", sin_tildes.lower())
    return re.sub(r"[^a-z0-9]+", "-", sin_numeral).strip("-")


def divisor_recursivo() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=TAMANO_FRAGMENTO,
        chunk_overlap=SOLAPE_FRAGMENTO,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def compactar_tablas_markdown(texto: str) -> str:
    """Quita el relleno de espacios y las filas separadoras de las tablas Markdown."""
    lineas = []
    for linea in texto.splitlines():
        if re.fullmatch(r"\s*\|[\s|:-]+\|\s*", linea):
            continue
        if linea.lstrip().startswith("|"):
            linea = re.sub(r" {2,}", " ", linea)
        lineas.append(linea)
    return "\n".join(lineas)


def fragmentar_politica() -> list[Document]:
    texto = compactar_tablas_markdown(ARCHIVO_POLITICA.read_text(encoding="utf-8"))
    por_encabezado = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "titulo"), ("##", "seccion")], strip_headers=True
    )
    recursivo = divisor_recursivo()

    fragmentos: list[Document] = []
    for bloque in por_encabezado.split_text(texto):
        seccion = bloque.metadata.get("seccion", "Presentación")
        contenido = re.sub(r"[ \t]+\n", "\n", bloque.page_content)
        for numero, parte in enumerate(recursivo.split_text(contenido), start=1):
            fragmentos.append(
                Document(
                    page_content=f"Política de devoluciones > {seccion}\n\n{parte}",
                    metadata={
                        "id": f"politica-{slug(seccion)}-{numero}",
                        "fuente": ARCHIVO_POLITICA.name,
                        "tipo": "politica",
                        "seccion": seccion,
                    },
                )
            )
    return fragmentos


def fragmentar_faq() -> list[Document]:
    datos = json.loads(ARCHIVO_FAQ.read_text(encoding="utf-8"))
    return [
        Document(
            page_content=(
                f"Preguntas frecuentes > {item['categoria']}\n\n"
                f"Pregunta: {item['pregunta']}\nRespuesta: {item['respuesta']}"
            ),
            metadata={
                "id": f"faq-{item['id']}",
                "fuente": ARCHIVO_FAQ.name,
                "tipo": "faq",
                "seccion": item["categoria"],
            },
        )
        for item in datos["preguntas"]
    ]


def formatear_pesos(valor: str) -> str:
    return f"${int(valor):,} COP".replace(",", ".")


def describir_producto(fila: dict[str, str]) -> str:
    if not fila["unidades_disponibles"]:
        disponibilidad = "Disponible bajo pedido"
    elif int(fila["unidades_disponibles"]) == 0:
        disponibilidad = "Agotado"
    else:
        disponibilidad = f"Disponible ({fila['unidades_disponibles']} unidades)"
    garantia = (
        f"{fila['garantia_meses']} meses"
        if int(fila["garantia_meses"]) > 0
        else "Garantía legal del Estatuto del Consumidor"
    )
    return (
        f"Catálogo de productos > {fila['categoria']}\n\n"
        f"Producto: {fila['nombre']} (SKU {fila['sku']})\n"
        f"Categoría: {fila['categoria']}\n"
        f"Descripción: {fila['descripcion']}\n"
        f"Precio: {formatear_pesos(fila['precio_cop'])}\n"
        f"Disponibilidad: {disponibilidad}\n"
        f"Material: {fila['material']}\n"
        f"Origen: {fila['origen']}\n"
        f"Certificación: {fila['certificacion']}\n"
        f"Admite devolución: {fila['admite_devolucion']}\n"
        f"Garantía: {garantia}"
    )


def fragmentar_catalogo() -> list[Document]:
    with ARCHIVO_CATALOGO.open(encoding="utf-8", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    return [
        Document(
            page_content=describir_producto(fila),
            metadata={
                "id": f"catalogo-{fila['sku'].lower()}",
                "fuente": ARCHIVO_CATALOGO.name,
                "tipo": "catalogo",
                "seccion": fila["categoria"],
                "sku": fila["sku"],
            },
        )
        for fila in filas
    ]


def limpiar_pagina_pdf(texto: str) -> str:
    sin_pie = PATRON_PIE_GUIA.sub("", texto)
    return re.sub(r"[ \t]{2,}", " ", sin_pie).strip()


def fragmentar_guia() -> list[Document]:
    # Se une el texto de todas las páginas para que ninguna sección quede partida por un salto de página.
    paginas = PyPDFLoader(str(ARCHIVO_GUIA)).load()
    texto = "\n".join(limpiar_pagina_pdf(pagina.page_content) for pagina in paginas)
    inicios = [0, *(titulo.start() for titulo in PATRON_TITULO_GUIA.finditer(texto))]
    bloques = [texto[inicio:fin].strip() for inicio, fin in zip(inicios, [*inicios[1:], len(texto)])]
    recursivo = divisor_recursivo()

    fragmentos: list[Document] = []
    for bloque in filter(None, bloques):
        titulo = PATRON_TITULO_GUIA.match(bloque)
        seccion = titulo.group(0) if titulo else "Presentación"
        for numero, parte in enumerate(recursivo.split_text(bloque), start=1):
            fragmentos.append(
                Document(
                    page_content=f"Guía de envíos y pagos > {seccion}\n\n{parte}",
                    metadata={
                        "id": f"guia-{slug(seccion)}-{numero}",
                        "fuente": ARCHIVO_GUIA.name,
                        "tipo": "guia",
                        "seccion": seccion,
                    },
                )
            )
    return fragmentos


def construir_base_conocimiento() -> list[Document]:
    fragmentos = [
        *fragmentar_politica(),
        *fragmentar_faq(),
        *fragmentar_catalogo(),
        *fragmentar_guia(),
    ]
    ids = [fragmento.metadata["id"] for fragmento in fragmentos]
    duplicados = {i for i in ids if ids.count(i) > 1}
    if duplicados:
        raise ValueError(f"Identificadores de fragmento duplicados: {sorted(duplicados)}")
    return fragmentos


# ---------------------------------------------------------------------------------------------
# Modelos y base vectorial
# ---------------------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def obtener_embeddings() -> HuggingFaceEmbeddings:
    # multilingual-e5 fue entrenado con prefijos distintos para pasajes y consultas.
    return HuggingFaceEmbeddings(
        model_name=MODELO_EMBEDDINGS,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True, "prompt": "passage: "},
        query_encode_kwargs={"normalize_embeddings": True, "prompt": "query: "},
    )


def abrir_almacen() -> Chroma:
    return Chroma(
        collection_name=COLECCION,
        embedding_function=obtener_embeddings(),
        persist_directory=str(INDICE_DIR),
        collection_metadata={"hnsw:space": "cosine"},
    )


@lru_cache(maxsize=1)
def obtener_almacen() -> Chroma:
    almacen = abrir_almacen()
    if not almacen.get(limit=1)["ids"]:
        raise SystemExit("El índice vectorial está vacío. Ejecuta primero: python src/indexar.py")
    return almacen


@lru_cache(maxsize=2)
def obtener_reranker(nombre_modelo: str) -> CrossEncoder:
    return CrossEncoder(nombre_modelo, device="cpu", max_length=512)


# ---------------------------------------------------------------------------------------------
# Recuperación en dos etapas
# ---------------------------------------------------------------------------------------------


def recuperar_candidatos(consulta: str, k: int) -> list[Document]:
    """Etapa 1: búsqueda por similitud de coseno con el bi-encoder."""
    resultados = obtener_almacen().similarity_search_with_score(consulta, k=k)
    candidatos = []
    for posicion, (documento, distancia) in enumerate(resultados, start=1):
        metadata = {
            **documento.metadata,
            "posicion_vectorial": posicion,
            "similitud": round(1 - distancia, 4),
        }
        candidatos.append(Document(page_content=documento.page_content, metadata=metadata))
    return candidatos


def puntuar_con_reranker(
    consulta: str, candidatos: list[Document], nombre_modelo: str
) -> list[Document]:
    """Etapa 2: el cross-encoder lee cada par (consulta, fragmento) y lo puntúa de 0 a 1."""
    if not candidatos:
        return []
    pares = [(consulta, candidato.page_content) for candidato in candidatos]
    puntajes = obtener_reranker(nombre_modelo).predict(pares)
    puntuados = [
        Document(
            page_content=candidato.page_content,
            metadata={**candidato.metadata, "puntaje_reranker": round(float(puntaje), 4)},
        )
        for candidato, puntaje in zip(candidatos, puntajes)
    ]
    return sorted(puntuados, key=lambda d: d.metadata["puntaje_reranker"], reverse=True)


def seleccionar_fragmentos(
    consulta: str, candidatos: list[Document], recuperacion: dict[str, Any]
) -> list[Document]:
    n = recuperacion["n_finales"]
    if not recuperacion.get("reranking", False):
        return candidatos[:n]

    reordenados = puntuar_con_reranker(consulta, candidatos, recuperacion["modelo_reranker"])
    # El umbral se aplica al mejor candidato: filtrar cada fragmento descarta relevantes de puntaje bajo.
    umbral = recuperacion.get("umbral_relevancia", 0.0)
    if not reordenados or reordenados[0].metadata["puntaje_reranker"] < umbral:
        return []
    return reordenados[:n]


def formatear_conocimiento(fragmentos: list[Document]) -> str:
    if not fragmentos:
        return SIN_CONOCIMIENTO
    return "\n\n".join(
        f"[Fragmento {i}]\n{fragmento.page_content}" for i, fragmento in enumerate(fragmentos, 1)
    )


# ---------------------------------------------------------------------------------------------
# Recuperación exacta de pedidos (datos transaccionales, fuera del índice vectorial)
# ---------------------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def cargar_pedidos() -> tuple[dict[str, Any], ...]:
    with ARCHIVO_PEDIDOS.open(encoding="utf-8") as archivo:
        return tuple(json.load(archivo)["pedidos"])


def extraer_numeros_seguimiento(consulta: str) -> list[str]:
    encontrados = [coincidencia.upper() for coincidencia in PATRON_SEGUIMIENTO.findall(consulta)]
    return list(dict.fromkeys(encontrados))


def recuperar_pedidos(consulta: str) -> str:
    """Devuelve solo los pedidos citados en la consulta, marcando los que no existen."""
    numeros = extraer_numeros_seguimiento(consulta)
    if not numeros:
        return "No se identificó ningún número de seguimiento en la consulta del cliente."

    indice = {pedido["numero_seguimiento"]: pedido for pedido in cargar_pedidos()}
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


# ---------------------------------------------------------------------------------------------
# Prompt, modelo generativo y cadena LCEL
# ---------------------------------------------------------------------------------------------

PLANTILLA_CONTEXTO = """>>>>> INICIO PEDIDOS
{pedidos}
<<<<< FIN PEDIDOS

>>>>> INICIO CONOCIMIENTO
{conocimiento}
<<<<< FIN CONOCIMIENTO"""

PLANTILLA_CONSULTA = """>>>>> INICIO CONSULTA
{consulta}
<<<<< FIN CONSULTA"""

PLANTILLA_HISTORIAL = """>>>>> INICIO HISTORIAL
{turnos}
<<<<< FIN HISTORIAL"""


def cargar_configuracion(ruta: Path) -> dict[str, Any]:
    with ruta.open("rb") as archivo:
        return tomllib.load(archivo)


def construir_prompt(prompts: dict[str, Any]) -> ChatPromptTemplate:
    # Los textos fijos van como mensajes ya construidos para que sus llaves no se interpreten.
    mensajes: list[Any] = [SystemMessage(content=prompts["role_prompt"].strip())]
    for ejemplo in prompts.get("ejemplos", []):
        mensajes.append(HumanMessage(content=ejemplo["consulta"].strip()))
        mensajes.append(AIMessage(content=ejemplo["respuesta"].strip()))
    mensajes += [
        MessagesPlaceholder("historial", optional=True),
        ("human", PLANTILLA_CONTEXTO),
        ("human", PLANTILLA_CONSULTA),
        HumanMessage(content=prompts["instruction_prompt"].strip()),
    ]
    return ChatPromptTemplate.from_messages(mensajes)


def formatear_historial(
    historial: list[tuple[str, str]], prompts: dict[str, Any]
) -> list[HumanMessage]:
    """Convierte los turnos previos (consulta, respuesta) en el bloque HISTORIAL y su instrucción."""
    if not historial:
        return []
    turnos = "\n\n".join(
        f"Cliente: {consulta.strip()}\nIris: {respuesta.strip()}" for consulta, respuesta in historial
    )
    return [
        HumanMessage(content=PLANTILLA_HISTORIAL.format(turnos=turnos)),
        HumanMessage(content=prompts["historial_prompt"].strip()),
    ]


def construir_llm(general: dict[str, Any]) -> ChatGoogleGenerativeAI:
    load_dotenv(ARCHIVO_ENTORNO)
    clave = os.getenv("GEMINI_API_KEY")
    if not clave:
        raise SystemExit(
            "Falta la variable GEMINI_API_KEY. Copia .env.example a .env y escribe allí tu clave."
        )
    return ChatGoogleGenerativeAI(
        model=general["modelo"],
        temperature=general.get("temperatura", 0),
        google_api_key=clave,
    )


def construir_cadena(configuracion: dict[str, Any]) -> Runnable:
    """Arma la cadena completa: recuperar → (rerankear) → formatear → prompt → LLM → texto.

    Recibe {"consulta": str} y, opcionalmente, "historial" con los turnos previos como pares
    (consulta, respuesta). Devuelve el mismo diccionario enriquecido con los candidatos, los
    fragmentos entregados al modelo y la respuesta.
    """
    recuperacion = configuracion["recuperacion"]
    prompts = configuracion["prompts"]

    recuperar = RunnableLambda(
        lambda entrada: recuperar_candidatos(entrada["consulta"], recuperacion["k_candidatos"])
    )
    seleccionar = RunnableLambda(
        lambda entrada: seleccionar_fragmentos(
            entrada["consulta"], entrada["candidatos"], recuperacion
        )
    )
    generar = (
        {
            "consulta": itemgetter("consulta"),
            "pedidos": RunnableLambda(lambda entrada: recuperar_pedidos(entrada["consulta"])),
            "conocimiento": RunnableLambda(
                lambda entrada: formatear_conocimiento(entrada["fragmentos"])
            ),
            "historial": RunnableLambda(
                lambda entrada: formatear_historial(entrada.get("historial", []), prompts)
            ),
        }
        | construir_prompt(prompts)
        | construir_llm(configuracion["general"])
        | StrOutputParser()
    )

    return (
        RunnablePassthrough.assign(candidatos=recuperar)
        | RunnablePassthrough.assign(fragmentos=seleccionar)
        | RunnablePassthrough.assign(respuesta=generar)
    )
