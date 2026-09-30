"""Interfaz de chat para probar el asistente de EcoMarket con o sin reranking.

Reutiliza la cadena LCEL de rag.py: la conversación de la izquierda muestra las respuestas de Iris
a medida que se generan y el panel de la derecha, los fragmentos y pedidos que recibió el modelo.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

import gradio as gr
from langchain_core.documents import Document

import rag

VARIANTES = {
    "Con reranking": rag.BASE_DIR / "settings-reranking.toml",
    "Sin reranking": rag.BASE_DIR / "settings-sin-reranking.toml",
}
VARIANTE_INICIAL = "Con reranking"
TURNOS_HISTORIAL = 3
LARGO_EXTRACTO = 300

CLASIFICACIONES = {
    "RESUELTO_POR_ASISTENTE": ("Resuelto por el asistente", "resuelto"),
    "REQUIERE_AGENTE_HUMANO": ("Requiere agente humano", "humano"),
    "SIN_INFORMACION_DISPONIBLE": ("Sin información disponible", "sin-informacion"),
}
PATRON_CLASIFICACION = re.compile(r"\n?[ \t*]*Clasificación:?[ \t*]*([A-Z_]+)[ \t*]*$")

TITULO = "# Iris · Asistente de atención al cliente de EcoMarket"
SUBTITULO = (
    "Responde con base en la política de devoluciones, las preguntas frecuentes, el catálogo de "
    "productos y la guía de envíos y pagos de EcoMarket. Es un prototipo académico con datos "
    "ficticios del caso de estudio y **no atiende pedidos reales**."
)

CSS = """
.panel-fragmentos h3 { margin: 0 0 0.75rem 0; }
.panel-fragmentos .estado { font-style: italic; color: var(--body-text-color-subdued); }
.panel-fragmentos .tarjeta { margin-bottom: 1rem; }
.panel-fragmentos .tarjeta p { margin: 0 0 0.4rem 0; }
.panel-fragmentos .meta { color: var(--body-text-color-subdued); font-size: 0.9em; }
.panel-fragmentos blockquote {
    margin: 0; padding: 0.25rem 0 0.25rem 0.75rem;
    border-left: 3px solid var(--border-color-primary);
    color: var(--body-text-color-subdued); font-size: 0.92em;
}
.panel-fragmentos .aviso {
    padding: 0.6rem 0.8rem; border-radius: 6px;
    border: 1px solid var(--border-color-primary); margin-bottom: 1rem;
}
.panel-fragmentos .etiqueta {
    display: inline-block; padding: 0.15rem 0.7rem; border-radius: 999px;
    font-size: 0.85em; font-weight: 600; margin-bottom: 1rem;
}
.panel-fragmentos .resuelto { background: rgba(34, 197, 94, 0.18); color: #22c55e; }
.panel-fragmentos .humano { background: rgba(245, 158, 11, 0.18); color: #f59e0b; }
.panel-fragmentos .sin-informacion { background: rgba(148, 163, 184, 0.2); color: #94a3b8; }
.panel-fragmentos .pie { color: var(--body-text-color-subdued); font-size: 0.85em; }
"""

CONFIGURACIONES: dict[str, dict[str, Any]] = {}
CADENAS: dict[str, Any] = {}


# ---------------------------------------------------------------------------------------------
# Preparación
# ---------------------------------------------------------------------------------------------


def precargar() -> None:
    """Construye las dos cadenas y carga los modelos para que el primer mensaje no pague la carga."""
    print("Cargando modelos y base vectorial…")
    for nombre, ruta in VARIANTES.items():
        CONFIGURACIONES[nombre] = rag.cargar_configuracion(ruta)
        CADENAS[nombre] = rag.construir_cadena(CONFIGURACIONES[nombre])
    rag.recuperar_candidatos("precarga", 1)
    for configuracion in CONFIGURACIONES.values():
        if configuracion["recuperacion"].get("reranking", False):
            rag.obtener_reranker(configuracion["recuperacion"]["modelo_reranker"])


# ---------------------------------------------------------------------------------------------
# Texto de la respuesta
# ---------------------------------------------------------------------------------------------


def texto_visible(texto: str) -> str:
    """Oculta la última línea mientras pueda ser la clasificación, para que no aparezca en el chat."""
    lineas = texto.rstrip().split("\n")
    ultima = lineas[-1].strip(" *\t")
    if ultima and ("Clasificación:".startswith(ultima) or ultima.startswith("Clasificación")):
        return "\n".join(lineas[:-1]).rstrip()
    return texto.rstrip()


def separar_clasificacion(texto: str) -> tuple[str, str | None]:
    coincidencia = PATRON_CLASIFICACION.search(texto.rstrip())
    if not coincidencia:
        return texto.strip(), None
    return texto[: coincidencia.start()].strip(), coincidencia.group(1)


# ---------------------------------------------------------------------------------------------
# Panel de fragmentos
# ---------------------------------------------------------------------------------------------


def numero(valor: float) -> str:
    return f"{valor:.4f}".replace(".", ",")


def extracto(contenido: str) -> str:
    encabezado, _, cuerpo = contenido.partition("\n\n")
    # En la guía, el cuerpo repite el título de la sección que ya muestra el encabezado.
    cuerpo = cuerpo.removeprefix(encabezado.split(" > ")[-1])
    plano = " ".join(cuerpo.replace("**", "").split())
    if len(plano) <= LARGO_EXTRACTO:
        return plano
    return plano[:LARGO_EXTRACTO].rsplit(" ", 1)[0] + "…"


def tarjeta_fragmento(posicion: int, fragmento: Document, reranking: bool) -> str:
    meta = fragmento.metadata
    encabezado = fragmento.page_content.split("\n", 1)[0]
    datos = f"similitud {numero(meta['similitud'])} · posición vectorial {meta['posicion_vectorial']}"
    if reranking:
        datos += f" · reranker {numero(meta['puntaje_reranker'])}"
    return (
        '<div class="tarjeta">'
        f"<p><b>{posicion}. {html.escape(encabezado)}</b> "
        f'<span class="meta">· {datos}</span></p>'
        f"<blockquote>{html.escape(extracto(fragmento.page_content))}</blockquote>"
        "</div>"
    )


def tarjeta_pedido(numero_pedido: str, pedido: dict[str, Any] | None) -> str:
    if pedido is None:
        return (
            '<div class="tarjeta">'
            f"<p><b>Pedido {html.escape(numero_pedido)}</b> "
            '<span class="meta">· búsqueda exacta en pedidos.json</span></p>'
            "<blockquote>El número no existe en los registros de EcoMarket.</blockquote>"
            "</div>"
        )
    productos = ", ".join(p["nombre"] for p in pedido["productos"])
    detalle = (
        f"Cliente: {pedido['cliente']} · Destino: {pedido['ciudad_destino']} · "
        f"Transportadora: {pedido['transportadora']} · Productos: {productos}"
    )
    return (
        '<div class="tarjeta">'
        f"<p><b>Pedido {html.escape(numero_pedido)} · {html.escape(pedido['estado'])}</b> "
        '<span class="meta">· búsqueda exacta en pedidos.json</span></p>'
        f"<blockquote>{html.escape(detalle)}</blockquote>"
        "</div>"
    )


def pedidos_citados(consulta: str) -> list[tuple[str, dict[str, Any] | None]]:
    indice = {pedido["numero_seguimiento"]: pedido for pedido in rag.cargar_pedidos()}
    return [(n, indice.get(n)) for n in rag.extraer_numeros_seguimiento(consulta)]


def renderizar_panel(
    variante: str,
    pedidos: list[tuple[str, dict[str, Any] | None]] | None = None,
    fragmentos: list[Document] | None = None,
    estado: str | None = None,
    clasificacion: str | None = None,
) -> str:
    recuperacion = CONFIGURACIONES[variante]["recuperacion"]
    reranking = recuperacion.get("reranking", False)
    partes = ['<div class="panel-fragmentos">', "<h3>Fragmentos consultados</h3>"]

    if estado:
        partes.append(f'<p class="estado">{html.escape(estado)}</p>')
    if clasificacion in CLASIFICACIONES:
        texto, clase = CLASIFICACIONES[clasificacion]
        partes.append(f'<span class="etiqueta {clase}">{texto}</span>')
    for numero_pedido, pedido in pedidos or []:
        partes.append(tarjeta_pedido(numero_pedido, pedido))

    if fragmentos is None and not estado:
        partes.append(
            '<p class="estado">Aquí aparecerán los fragmentos que recibe Iris en cada respuesta.</p>'
        )
    elif fragmentos == [] and reranking:
        umbral = str(recuperacion.get("umbral_relevancia", 0)).replace(".", ",")
        partes.append(
            '<div class="aviso">Ningún fragmento alcanzó el umbral de relevancia '
            f"({umbral}). Iris no recibió conocimiento de la base y debe indicar que no cuenta con "
            "esa información.</div>"
        )
    else:
        partes += [
            tarjeta_fragmento(posicion, fragmento, reranking)
            for posicion, fragmento in enumerate(fragmentos or [], start=1)
        ]

    detalle = f"{recuperacion['k_candidatos']} candidatos → {recuperacion['n_finales']} fragmentos"
    if reranking:
        detalle += f" · umbral {str(recuperacion['umbral_relevancia']).replace('.', ',')}"
    partes += [f'<p class="pie">Variante: {variante.lower()} · {detalle}</p>', "</div>"]
    return "".join(partes)


# ---------------------------------------------------------------------------------------------
# Conversación
# ---------------------------------------------------------------------------------------------


def responder(mensaje: str, chat: list[dict], historial: list, variante: str):
    mensaje = (mensaje or "").strip()
    if not mensaje:
        yield chat, "", gr.skip(), historial
        return

    reranking = CONFIGURACIONES[variante]["recuperacion"].get("reranking", False)
    pedidos = pedidos_citados(mensaje)
    chat = [*chat, {"role": "user", "content": mensaje}]
    yield chat, "", renderizar_panel(variante, pedidos, estado="Buscando fragmentos en la base de conocimiento…"), historial

    texto = ""
    fragmentos: list[Document] | None = None
    entrada = {"consulta": mensaje, "historial": [tuple(t) for t in historial[-TURNOS_HISTORIAL:]]}
    try:
        for trozo in CADENAS[variante].stream(entrada):
            if "candidatos" in trozo:
                estado = (
                    "Reordenando los candidatos con el reranker…"
                    if reranking
                    else "Iris está redactando la respuesta…"
                )
                yield chat, "", renderizar_panel(variante, pedidos, estado=estado), historial
            if "fragmentos" in trozo:
                fragmentos = trozo["fragmentos"]
                panel = renderizar_panel(
                    variante, pedidos, fragmentos, estado="Iris está redactando la respuesta…"
                )
                yield chat, "", panel, historial
            if "respuesta" in trozo:
                if not texto:
                    chat.append({"role": "assistant", "content": ""})
                texto += trozo["respuesta"]
                chat[-1]["content"] = texto_visible(texto)
                yield chat, "", gr.skip(), historial
    except Exception as error:
        if not texto:
            chat.append({"role": "assistant", "content": ""})
        chat[-1]["content"] = (
            f"*No fue posible generar la respuesta ({type(error).__name__}). "
            "Revisa la clave de Gemini y la cuota disponible.*"
        )
        yield chat, "", renderizar_panel(variante, pedidos, fragmentos), historial
        return

    cuerpo, clasificacion = separar_clasificacion(texto)
    if not texto:
        chat.append({"role": "assistant", "content": ""})
    chat[-1]["content"] = f"{cuerpo}\n\n<sub>Variante: {variante.lower()}</sub>"
    historial = [*historial, [mensaje, cuerpo]]
    yield chat, "", renderizar_panel(variante, pedidos, fragmentos, clasificacion=clasificacion), historial


def limpiar(variante: str):
    return [], "", renderizar_panel(variante), []


def construir_interfaz() -> gr.Blocks:
    with gr.Blocks(title="Iris · EcoMarket") as interfaz:
        gr.Markdown(TITULO)
        gr.Markdown(SUBTITULO)
        historial = gr.State([])
        with gr.Row():
            with gr.Column(scale=3):
                chat = gr.Chatbot(label="Conversación", height=520)
                entrada = gr.Textbox(
                    label="¿En qué te puede ayudar Iris?",
                    placeholder="Escribe tu pregunta aquí y presiona Enter.",
                )
                with gr.Row():
                    enviar = gr.Button("Enviar", variant="primary")
                    boton_limpiar = gr.Button("Limpiar")
            with gr.Column(scale=2):
                variante = gr.Radio(
                    list(VARIANTES), value=VARIANTE_INICIAL, label="Variante de recuperación"
                )
                panel = gr.HTML(renderizar_panel(VARIANTE_INICIAL))

        entradas = [entrada, chat, historial, variante]
        salidas = [chat, entrada, panel, historial]
        # El panel muestra la etapa en curso; el indicador genérico de Gradio lo taparía.
        entrada.submit(responder, entradas, salidas, show_progress="hidden")
        enviar.click(responder, entradas, salidas, show_progress="hidden")
        boton_limpiar.click(limpiar, [variante], salidas)
        chat.clear(limpiar, [variante], salidas)
    return interfaz


def main() -> None:
    precargar()
    construir_interfaz().queue().launch(server_name="127.0.0.1", css=CSS)


if __name__ == "__main__":
    main()
