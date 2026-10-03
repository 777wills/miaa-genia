from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from langchain_core.tools import tool

import devoluciones
import rag


@lru_cache(maxsize=1)
def _cadena_rag():
    configuracion = rag.cargar_configuracion(
        Path(__file__).resolve().parent / "settings-reranking.toml"
    )
    return rag.construir_cadena(configuracion)


@tool
def consultar_base_conocimiento(consulta: str) -> dict:
    """Busca información oficial de EcoMarket en la base RAG. Úsala para políticas, devoluciones, envíos, pagos y preguntas informativas."""
    resultado = _cadena_rag().invoke({"consulta": consulta, "historial": []})

    def resumir(fragmentos):
        return [
            {
                "metadata": fragmento.metadata,
                "contenido": fragmento.page_content,
            }
            for fragmento in fragmentos
        ]

    return {
        "ok": True,
        "respuesta": resultado["respuesta"],
        "candidatos": resumir(resultado["candidatos"]),
        "fragmentos_finales": resumir(resultado["fragmentos"]),
        "metodo": "chroma_bge_reranker",
    }

@tool
def consultar_pedido(numero_pedido: str) -> dict:
    """Consulta datos de un pedido por su número de seguimiento ECO-AAAA-NNNN. Úsala antes de afirmar estados o productos."""
    return devoluciones.consultar_pedido(numero_pedido)

@tool
def verificar_elegibilidad_devolucion(
    numero_pedido: str,
    sku: str,
    motivo: str,
    condicion_producto: str = "",
) -> dict:
    """Valida si un producto puede iniciar devolución. Debe ejecutarse antes de generar una etiqueta."""
    return devoluciones.verificar_elegibilidad(
        numero_pedido=numero_pedido,
        sku=sku,
        motivo=motivo,
        condicion_producto=condicion_producto,
    )

@tool
def generar_etiqueta_devolucion(codigo_autorizacion: str) -> dict:
    """Genera una etiqueta de retorno únicamente con un código de autorización válido producido por verificar_elegibilidad_devolucion."""
    return devoluciones.generar_etiqueta(codigo_autorizacion)

@tool
def registrar_devolucion(numero_etiqueta: str) -> dict:
    """Registra la devolución a partir de una etiqueta válida ya generada."""
    return devoluciones.registrar_devolucion(numero_etiqueta)

TOOLS = [
    consultar_base_conocimiento,
    consultar_pedido,
    verificar_elegibilidad_devolucion,
    generar_etiqueta_devolucion,
    registrar_devolucion,
]
TOOL_MAP = {tool.name: tool for tool in TOOLS}
