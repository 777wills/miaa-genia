from __future__ import annotations

import json
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


@tool(response_format="content_and_artifact")
def consultar_base_conocimiento(consulta: str) -> tuple[str, dict]:
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

    finales = resumir(resultado["fragmentos"])
    # El modelo solo recibe la respuesta y los fragmentos finales; los candidatos van al panel.
    contenido = {
        "ok": True,
        "respuesta": resultado["respuesta"],
        "fragmentos": [
            {"fuente": f["metadata"].get("fuente"), "contenido": f["contenido"]} for f in finales
        ],
    }
    artefacto = {
        "ok": True,
        "respuesta": resultado["respuesta"],
        "candidatos": resumir(resultado["candidatos"]),
        "fragmentos_finales": finales,
        "metodo": "chroma_bge_reranker",
    }
    return json.dumps(contenido, ensure_ascii=False), artefacto

@tool
def consultar_pedido(numero_pedido: str) -> dict:
    """Consulta datos de un pedido por su número de seguimiento ECO-AAAA-NNNN. Úsala antes de afirmar estados o productos."""
    return devoluciones.consultar_pedido(numero_pedido)

@tool(parse_docstring=True)
def verificar_elegibilidad_devolucion(
    numero_pedido: str,
    sku: str,
    motivo: str,
    sin_uso: bool | None = None,
    conserva_etiquetas: bool | None = None,
    sin_olores_ni_manchas: bool | None = None,
    conserva_empaque: bool | None = None,
    accesorios_completos: bool | None = None,
    conserva_cables_y_manual: bool | None = None,
    sin_marcas_escritura: bool | None = None,
) -> dict:
    """Valida si un producto puede iniciar una devolución. Debe ejecutarse antes de generar una etiqueta.

    Revisa el mensaje completo del cliente: cada condición es true si el cliente la afirmó, false si
    dijo lo contrario y se omite solo si no la mencionó. La respuesta indica qué condiciones faltan.

    Args:
        numero_pedido: Número de seguimiento ECO-AAAA-NNNN.
        sku: SKU del producto que se quiere devolver.
        motivo: Motivo de la devolución con las palabras del cliente.
        sin_uso: El producto está sin uso ("sin uso", "sin usar", "nuevo").
        conserva_etiquetas: El producto conserva sus etiquetas ("conserva las etiquetas", "tiene las etiquetas adheridas").
        sin_olores_ni_manchas: No tiene olores ni manchas.
        conserva_empaque: Conserva el empaque original.
        accesorios_completos: Tiene los accesorios completos.
        conserva_cables_y_manual: Conserva los cables y el manual.
        sin_marcas_escritura: No tiene marcas de escritura.
    """
    return devoluciones.verificar_elegibilidad(
        numero_pedido=numero_pedido,
        sku=sku,
        motivo=motivo,
        condiciones={
            "sin_uso": sin_uso,
            "conserva_etiquetas": conserva_etiquetas,
            "sin_olores_ni_manchas": sin_olores_ni_manchas,
            "conserva_empaque": conserva_empaque,
            "accesorios_completos": accesorios_completos,
            "conserva_cables_y_manual": conserva_cables_y_manual,
            "sin_marcas_escritura": sin_marcas_escritura,
        },
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
