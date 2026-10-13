from __future__ import annotations

import html
import json
import re
from typing import Any

import gradio as gr

from agent import IrisAgent
from devoluciones import reset_runtime

TITULO = "# Iris · Agente de devoluciones de EcoMarket"
SUBTITULO = (
    "Prototipo académico con datos ficticios. Iris conserva el RAG del Taller 2 y puede ejecutar "
    "herramientas para verificar y registrar devoluciones."
)

AGENTE: IrisAgent | None = None

def obtener_agente() -> IrisAgent:
    global AGENTE
    if AGENTE is None:
        AGENTE = IrisAgent()
    return AGENTE

def render_eventos(eventos: list[dict[str, Any]], session_id: str = "") -> str:
    if not eventos:
        return (
            "<div><h3>Actividad del agente</h3>"
            "<p>Aquí aparecerán las herramientas realmente ejecutadas.</p></div>"
        )

    bloques = ["<div><h3>Actividad del agente</h3>"]
    for i, evento in enumerate(eventos, 1):
        resultado = evento.get("resultado", {})
        codigo = evento.get("status", resultado.get("codigo", "OK"))
        mensaje = evento.get("error") or resultado.get("mensaje", "")
        duracion = evento.get("duracion_ms")
        detalles_rag = ""
        if evento.get("herramienta") == "consultar_base_conocimiento":
            candidatos = resultado.get("candidatos", [])
            finales = resultado.get("fragmentos_finales", [])
            metodo = resultado.get("metodo", "recuperación vectorial")
            mensaje = f"{len(candidatos)} candidatos; {len(finales)} fragmentos finales; {metodo}."
            clasificacion = re.search(
                r"Clasificación:\s*(RESUELTO_POR_ASISTENTE|REQUIERE_AGENTE_HUMANO|SIN_INFORMACION_DISPONIBLE)",
                resultado.get("respuesta", ""),
            )
            if clasificacion:
                mensaje += f" Clasificación: {clasificacion.group(1)}."

            def render_fragmentos(fragmentos: list[dict[str, Any]], incluir_contenido: bool) -> str:
                filas = []
                for fragmento in fragmentos:
                    metadata = fragmento.get("metadata", {})
                    etiqueta = " · ".join(
                        str(metadata[campo])
                        for campo in ("fuente", "seccion")
                        if metadata.get(campo)
                    )
                    puntajes = []
                    if "similitud" in metadata:
                        puntajes.append(f"similitud {metadata['similitud']}")
                    if "puntaje_reranker" in metadata:
                        puntajes.append(f"reranker {metadata['puntaje_reranker']}")
                    texto = fragmento.get("contenido", "")
                    if not incluir_contenido:
                        texto = texto[:240] + ("…" if len(texto) > 240 else "")
                    filas.append(
                        "<li><b>"
                        + html.escape(etiqueta or "Fragmento")
                        + "</b> <small>"
                        + html.escape(" · ".join(puntajes))
                        + "</small>"
                        + (f"<p>{html.escape(texto)}</p>" if texto else "")
                        + "</li>"
                    )
                return "<ol>" + "".join(filas) + "</ol>" if filas else "<p>Sin fragmentos.</p>"

            detalles_rag = (
                "<details><summary>Ver candidatos recuperados</summary>"
                + render_fragmentos(candidatos, False)
                + "</details><details><summary>Ver fragmentos enviados al modelo</summary>"
                + render_fragmentos(finales, True)
                + "</details>"
            )
        bloques.append(
            "<div style='margin-bottom:12px;padding:10px;border:1px solid #ddd;border-radius:8px'>"
            f"<b>{i}. {html.escape(str(evento.get('herramienta')))}</b><br>"
            f"<small>{html.escape(str(codigo))}</small><br>"
            f"{html.escape(str(mensaje))}<br>"
            f"<small>{html.escape(str(duracion)) + ' ms' if duracion is not None else ''}</small>"
            f"{detalles_rag}"
            "</div>"
        )
    bloques.append(f"<small>Sesión: {html.escape(session_id)}</small></div>")
    return "".join(bloques)

def responder(mensaje: str, chat: list[dict], historial: list):
    mensaje = (mensaje or "").strip()
    if not mensaje:
        return chat, "", render_eventos([]), historial

    chat = [*chat, {"role": "user", "content": mensaje}]
    try:
        resultado = obtener_agente().responder(
            mensaje,
            [tuple(x) for x in historial[-4:]],
        )
        respuesta = resultado["respuesta"]
        panel = render_eventos(resultado["eventos"], resultado["session_id"])
    except Exception as error:
        respuesta = (
            "No fue posible ejecutar el agente. "
            f"Revisa la configuración de Gemini. Detalle: {type(error).__name__}: {error}"
        )
        panel = render_eventos([])

    chat.append({"role": "assistant", "content": respuesta})
    historial = [*historial, [mensaje, respuesta]]
    return chat, "", panel, historial

def limpiar():
    global AGENTE
    AGENTE = None
    return [], "", render_eventos([]), []

def reiniciar_demo():
    reset_runtime()
    return "Estado local de la demostración reiniciado."

def construir_interfaz():
    with gr.Blocks(title="Iris · EcoMarket") as demo:
        gr.Markdown(TITULO)
        gr.Markdown(SUBTITULO)
        historial = gr.State([])

        with gr.Row():
            with gr.Column(scale=3):
                chat = gr.Chatbot(label="Conversación", height=520)
                entrada = gr.Textbox(
                    label="Mensaje",
                    placeholder="Ej.: Quiero devolver TEX-0031 del pedido ECO-2026-1042...",
                )
                with gr.Row():
                    enviar = gr.Button("Enviar", variant="primary")
                    borrar = gr.Button("Limpiar conversación")
            with gr.Column(scale=2):
                panel = gr.HTML(render_eventos([]))
                reset = gr.Button("Reiniciar estado de la demo")
                estado_reset = gr.Markdown("")

        gr.Examples(
            examples=[
                ["¿Cuánto tiempo tengo para solicitar una devolución?"],
                ["¿Qué productos tiene el pedido ECO-2026-1042?"],
                ["Quiero devolver la camiseta de algodón orgánico del pedido ECO-2026-1042. El SKU es TEX-0031, está sin uso, conserva las etiquetas y fue un cambio de talla."],
                ["Quiero devolver HOG-0204 del pedido ECO-2026-1087 porque cambié de opinión."],
                ["El café ALI-0455 del pedido ECO-2026-1372 llegó con el empaque roto."],
                ["Genera otra devolución para TEX-0145 del pedido ECO-2026-1268."],
            ],
            inputs=entrada,
        )

        inputs = [entrada, chat, historial]
        outputs = [chat, entrada, panel, historial]
        entrada.submit(responder, inputs, outputs)
        enviar.click(responder, inputs, outputs)
        borrar.click(limpiar, outputs=outputs)
        reset.click(reiniciar_demo, outputs=estado_reset)

    return demo

if __name__ == "__main__":
    construir_interfaz().queue().launch(server_name="127.0.0.1")
