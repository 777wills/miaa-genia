from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any
import unicodedata

BASE_DIR = Path(__file__).resolve().parent
DATOS_DIR = BASE_DIR / "datos"
DEFAULT_STATE_DIR = BASE_DIR / "runtime"
PEDIDOS_PATH = DATOS_DIR / "pedidos.json"

CONDICIONES = {
    "sin_uso": "está sin uso",
    "conserva_etiquetas": "conserva las etiquetas adheridas",
    "sin_olores_ni_manchas": "no tiene olores ni manchas",
    "conserva_empaque": "conserva el empaque original",
    "accesorios_completos": "tiene los accesorios completos",
    "conserva_cables_y_manual": "conserva los cables y el manual",
    "sin_marcas_escritura": "no tiene marcas de escritura",
}
# El número de serie de Electrónica lo verifica EcoMarket al recibir el producto, no el cliente.
REQUISITOS_POR_CATEGORIA = {
    "Hogar": ("sin_uso", "conserva_empaque", "accesorios_completos"),
    "Textiles": ("sin_uso", "conserva_etiquetas", "sin_olores_ni_manchas"),
    "Electrónica": ("conserva_empaque", "conserva_cables_y_manual"),
    "Papelería y oficina": ("sin_uso", "sin_marcas_escritura"),
}
CATEGORIAS_RETORNABLES = set(REQUISITOS_POR_CATEGORIA)
CATEGORIAS_NO_RETORNABLES = {
    "Alimentos perecederos",
    "Higiene personal",
    "Cuidado corporal y cosmética",
    "Productos personalizados o grabados",
    "Tarjetas de regalo y bonos digitales",
}
PALABRAS_EXCEPCION = (
    "averiado", "averiada", "roto", "rota", "derramado", "derramada",
    "empaque violado", "vencido", "vencida", "referencia incorrecta",
    "referencia equivocada", "referencia distinta", "menos de 15 dias", "sku equivocado",
    "producto distinto", "incompleto", "incompleta", "defecto",
    "no funciona", "fallo", "falla",
)
MOTIVOS_HUMANOS = (
    "garantia legal", "garantia", "indemnizacion", "fraude", "cobro duplicado",
    "cobros duplicados", "disputa de pago", "pasarela de pago", "amenaza legal",
    "demanda", "problema de salud", "afecto mi salud", "me hizo dano", "intoxicacion",
    "eliminar mis datos",
    "eliminacion de datos", "datos personales", "inconformidad reiterada",
    "muy molesto", "caso ambiguo", "situacion ambigua", "no es claro",
)

def _leer_json(path: Path, default: Any):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def _escribir_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def cargar_base() -> dict[str, Any]:
    return _leer_json(PEDIDOS_PATH, {"fecha_corte": None, "pedidos": []})

def obtener_pedido(numero_pedido: str) -> dict[str, Any] | None:
    numero = numero_pedido.strip().upper()
    for pedido in cargar_base()["pedidos"]:
        if pedido["numero_seguimiento"].upper() == numero:
            return pedido
    return None

def obtener_producto(pedido: dict[str, Any], sku: str) -> dict[str, Any] | None:
    sku = sku.strip().upper()
    for producto in pedido.get("productos", []):
        if producto["sku"].upper() == sku:
            return producto
    return None

def _dias_desde_entrega(pedido: dict[str, Any]) -> int | None:
    fecha_entrega = pedido.get("fecha_entrega_real")
    fecha_corte = cargar_base().get("fecha_corte")
    if not fecha_entrega or not fecha_corte:
        return None
    return (date.fromisoformat(fecha_corte) - date.fromisoformat(fecha_entrega)).days

def _hay_excepcion(motivo: str) -> bool:
    texto = _normalizar(motivo)
    return any(palabra in texto for palabra in PALABRAS_EXCEPCION)

def _normalizar(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()

def _requiere_humano(motivo: str) -> bool:
    texto = _normalizar(motivo)
    return any(palabra in texto for palabra in MOTIVOS_HUMANOS)

def _evaluar_condiciones(
    categoria: str, condiciones: dict[str, bool | None]
) -> tuple[list[str], list[str]]:
    """Devuelve (faltantes, incumplidos): None significa no informado; False, no cumple."""
    faltantes, incumplidos = [], []
    for requisito in REQUISITOS_POR_CATEGORIA[categoria]:
        valor = condiciones.get(requisito)
        if valor is None:
            faltantes.append(requisito)
        elif valor is False:
            incumplidos.append(requisito)
    return faltantes, incumplidos

def _describir(requisitos: list[str]) -> str:
    return "; ".join(CONDICIONES[requisito] for requisito in requisitos)

def _runtime(state_dir: Path | None) -> Path:
    return state_dir or DEFAULT_STATE_DIR

def _path(state_dir: Path | None, name: str) -> Path:
    return _runtime(state_dir) / name

def consultar_pedido(numero_pedido: str) -> dict[str, Any]:
    pedido = obtener_pedido(numero_pedido)
    if not pedido:
        return {"ok": False, "codigo": "PEDIDO_NO_EXISTE", "mensaje": "No existe ese número de seguimiento."}
    resultado = {
        "ok": True,
        "codigo": "PEDIDO_ENCONTRADO",
        "numero_pedido": pedido["numero_seguimiento"],
        "estado": pedido["estado"],
        "fecha_entrega_real": pedido.get("fecha_entrega_real"),
        "transportadora": pedido.get("transportadora"),
        "productos": [
            {"sku": p["sku"], "nombre": p["nombre"], "categoria": p["categoria"]}
            for p in pedido.get("productos", [])
        ],
        "numero_devolucion": pedido.get("numero_devolucion"),
    }
    if pedido.get("numero_devolucion"):
        resultado["mensaje"] = (
            f"El pedido ya tiene la devolución {pedido['numero_devolucion']} en curso. "
            "No se puede iniciar otra devolución para este pedido."
        )
    return resultado

def verificar_elegibilidad(
    numero_pedido: str,
    sku: str,
    motivo: str,
    condiciones: dict[str, bool | None] | None = None,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    pedido = obtener_pedido(numero_pedido)
    if not pedido:
        return {
            "ok": False, "elegible": False, "requiere_agente_humano": False,
            "codigo": "PEDIDO_NO_EXISTE",
            "mensaje": "El número de pedido no existe en los registros de EcoMarket.",
        }

    producto = obtener_producto(pedido, sku)
    if not producto:
        return {
            "ok": False, "elegible": False, "requiere_agente_humano": False,
            "codigo": "SKU_NO_PERTENECE_PEDIDO",
            "mensaje": "El SKU indicado no pertenece al pedido.",
        }

    if _requiere_humano(motivo):
        return {
            "ok": True, "elegible": False, "requiere_agente_humano": True,
            "codigo": "REVISION_HUMANA",
            "mensaje": "El motivo requiere atención de una persona. No se generará una etiqueta automática.",
        }

    if pedido.get("numero_devolucion") or pedido.get("estado") == "Devolución en curso":
        return {
            "ok": True, "elegible": False, "requiere_agente_humano": False,
            "codigo": "DEVOLUCION_EXISTENTE",
            "mensaje": f"El pedido ya tiene una devolución registrada: {pedido.get('numero_devolucion', 'en curso')}.",
        }

    registros = _leer_json(_path(state_dir, "devoluciones.json"), [])
    for registro in registros:
        if registro["numero_pedido"] == pedido["numero_seguimiento"] and registro["sku"] == producto["sku"]:
            return {
                "ok": True, "elegible": False, "requiere_agente_humano": False,
                "codigo": "DEVOLUCION_EXISTENTE",
                "mensaje": f"Ya existe el caso {registro['numero_caso']} para ese producto.",
            }

    if pedido.get("estado") != "Entregado":
        return {
            "ok": True, "elegible": False, "requiere_agente_humano": False,
            "codigo": "PEDIDO_NO_ENTREGADO",
            "mensaje": f"El pedido está en estado '{pedido.get('estado')}'. La devolución ordinaria se inicia después de la entrega.",
        }

    dias = _dias_desde_entrega(pedido)
    if dias is None:
        return {
            "ok": True, "elegible": False, "requiere_agente_humano": True,
            "codigo": "FECHA_NO_DISPONIBLE",
            "mensaje": "No fue posible validar la fecha de entrega. El caso debe revisarlo una persona.",
        }
    if dias > 30:
        return {
            "ok": True, "elegible": False, "requiere_agente_humano": True,
            "codigo": "FUERA_DE_PLAZO",
            "mensaje": f"Han pasado {dias} días desde la entrega. Los casos por fuera de 30 días requieren revisión humana.",
        }

    categoria = producto.get("categoria", "")
    if _hay_excepcion(motivo):
        return {
            "ok": True, "elegible": False, "requiere_agente_humano": True,
            "codigo": "EXCEPCION_ECOMARKET",
            "mensaje": (
                "El motivo puede corresponder a una excepción atribuible a EcoMarket. "
                "Debe solicitarse evidencia y revisar reposición o reembolso; no se genera una devolución física automática."
            ),
            "producto": producto["nombre"],
            "categoria": categoria,
        }

    if categoria in CATEGORIAS_NO_RETORNABLES:
        return {
            "ok": True, "elegible": False, "requiere_agente_humano": False,
            "codigo": "CATEGORIA_NO_RETORNABLE",
            "mensaje": f"La categoría '{categoria}' no admite devolución ordinaria según la política.",
            "producto": producto["nombre"],
            "categoria": categoria,
        }

    if categoria not in CATEGORIAS_RETORNABLES:
        return {
            "ok": True, "elegible": False, "requiere_agente_humano": True,
            "codigo": "CATEGORIA_SIN_REGLA",
            "mensaje": "La categoría no tiene una regla automática definida y debe revisarse manualmente.",
        }

    faltantes, incumplidos = _evaluar_condiciones(categoria, condiciones or {})
    if incumplidos:
        return {
            "ok": True, "elegible": False, "requiere_agente_humano": False,
            "codigo": "CONDICION_NO_CUMPLIDA",
            "mensaje": (
                f"Para la categoría '{categoria}' el producto debe cumplir: {_describir(incumplidos)}. "
                "Sin esa condición no procede la devolución ordinaria."
            ),
            "requisitos_incumplidos": incumplidos,
        }
    if faltantes:
        return {
            "ok": True, "elegible": False, "requiere_agente_humano": False,
            "codigo": "CONDICION_INSUFICIENTE",
            "mensaje": f"Falta confirmar que el producto {_describir(faltantes)}.",
            "siguiente_paso": (
                "Si el cliente ya lo dijo en la conversación, vuelve a verificar con esa condición en true; "
                "si no, pregúntale solo por ella."
            ),
            "requisitos_faltantes": faltantes,
        }

    base_token = f"{pedido['numero_seguimiento']}|{producto['sku']}|{motivo}|{cargar_base().get('fecha_corte')}"
    autorizacion = "AUT-" + hashlib.sha256(base_token.encode()).hexdigest()[:12].upper()
    autorizaciones = _leer_json(_path(state_dir, "autorizaciones.json"), {})
    autorizaciones[autorizacion] = {
        "numero_pedido": pedido["numero_seguimiento"],
        "sku": producto["sku"],
        "producto": producto["nombre"],
        "categoria": categoria,
        "motivo": motivo,
        "consumida": False,
    }
    _escribir_json(_path(state_dir, "autorizaciones.json"), autorizaciones)

    return {
        "ok": True,
        "elegible": True,
        "requiere_agente_humano": False,
        "codigo": "ELEGIBLE",
        "mensaje": "La devolución ordinaria cumple las reglas automáticas.",
        "codigo_autorizacion": autorizacion,
        "numero_pedido": pedido["numero_seguimiento"],
        "sku": producto["sku"],
        "producto": producto["nombre"],
        "dias_desde_entrega": dias,
    }

def generar_etiqueta(codigo_autorizacion: str, state_dir: Path | None = None) -> dict[str, Any]:
    autorizaciones = _leer_json(_path(state_dir, "autorizaciones.json"), {})
    autorizacion = autorizaciones.get(codigo_autorizacion)
    if not autorizacion:
        return {"ok": False, "codigo": "AUTORIZACION_INVALIDA", "mensaje": "No existe una autorización válida para generar la etiqueta."}
    if autorizacion.get("consumida"):
        return {"ok": False, "codigo": "AUTORIZACION_CONSUMIDA", "mensaje": "La autorización ya fue utilizada."}

    etiquetas = _leer_json(_path(state_dir, "etiquetas.json"), {})
    digest = hashlib.sha256(codigo_autorizacion.encode()).hexdigest().upper()
    numero_caso = f"DEV-2026-{int(digest[:6], 16) % 10000:04d}"
    numero_etiqueta = f"RET-{digest[6:16]}"

    for etiqueta in etiquetas.values():
        if etiqueta["numero_pedido"] == autorizacion["numero_pedido"] and etiqueta["sku"] == autorizacion["sku"]:
            if etiqueta["estado"] == "Generada":
                autorizacion["consumida"] = True
                _escribir_json(_path(state_dir, "autorizaciones.json"), autorizaciones)
                return {
                    "ok": True, "codigo": "ETIQUETA_PENDIENTE_REGISTRO",
                    "mensaje": "Ya existía una etiqueta para este producto; falta registrarla.",
                    **_datos_etiqueta(etiqueta),
                }
            return {
                "ok": False, "codigo": "ETIQUETA_EXISTENTE",
                "mensaje": f"Ya existe una etiqueta registrada para el caso {etiqueta['numero_caso']}.",
            }

    instruccion = "Empaca el producto y entrégalo en un punto autorizado dentro de los próximos 8 días calendario."
    if autorizacion.get("categoria") == "Electrónica":
        instruccion += " EcoMarket verificará el número de serie al recibir el producto."
    etiquetas[numero_etiqueta] = {
        "numero_caso": numero_caso,
        "numero_etiqueta": numero_etiqueta,
        "numero_pedido": autorizacion["numero_pedido"],
        "sku": autorizacion["sku"],
        "producto": autorizacion["producto"],
        "transportadora": "EnvíaVerde",
        "instruccion": instruccion,
        "estado": "Generada",
    }
    autorizacion["consumida"] = True
    _escribir_json(_path(state_dir, "etiquetas.json"), etiquetas)
    _escribir_json(_path(state_dir, "autorizaciones.json"), autorizaciones)

    return {
        "ok": True,
        "codigo": "ETIQUETA_GENERADA",
        "mensaje": f"Etiqueta {numero_etiqueta} generada para el caso {numero_caso}.",
        **_datos_etiqueta(etiquetas[numero_etiqueta]),
    }

def _datos_etiqueta(etiqueta: dict[str, Any]) -> dict[str, Any]:
    return {
        campo: etiqueta[campo]
        for campo in (
            "numero_caso", "numero_etiqueta", "numero_pedido", "sku", "transportadora", "instruccion",
        )
        if campo in etiqueta
    }

def registrar_devolucion(numero_etiqueta: str, state_dir: Path | None = None) -> dict[str, Any]:
    etiquetas = _leer_json(_path(state_dir, "etiquetas.json"), {})
    etiqueta = etiquetas.get(numero_etiqueta)
    if not etiqueta:
        return {"ok": False, "codigo": "ETIQUETA_NO_EXISTE", "mensaje": "No existe una etiqueta válida con ese número."}

    registros = _leer_json(_path(state_dir, "devoluciones.json"), [])
    for registro in registros:
        if registro["numero_etiqueta"] == numero_etiqueta:
            return {
                "ok": True, "codigo": "YA_REGISTRADA",
                "mensaje": "La devolución ya estaba registrada.",
                **registro,
            }

    registro = {
        "numero_caso": etiqueta["numero_caso"],
        "numero_etiqueta": numero_etiqueta,
        "numero_pedido": etiqueta["numero_pedido"],
        "sku": etiqueta["sku"],
        "estado": "Esperando entrega a transportadora",
    }
    registros.append(registro)
    _escribir_json(_path(state_dir, "devoluciones.json"), registros)
    etiqueta["estado"] = "Registrada"
    _escribir_json(_path(state_dir, "etiquetas.json"), etiquetas)

    return {"ok": True, "codigo": "REGISTRADA", "mensaje": "La devolución quedó registrada.", **registro}

def reset_runtime(state_dir: Path | None = None) -> None:
    directorio = _runtime(state_dir)
    directorio.mkdir(parents=True, exist_ok=True)
    for nombre in ("autorizaciones.json", "etiquetas.json", "devoluciones.json"):
        ruta = directorio / nombre
        if ruta.exists():
            ruta.unlink()
