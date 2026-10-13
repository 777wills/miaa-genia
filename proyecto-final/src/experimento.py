"""Experimento: recuperación sin reranking frente a recuperación con reranking.

Para cada consulta etiquetada se obtienen una sola vez los k candidatos del bi-encoder. La
variante A entrega los n primeros tal como los ordena la similitud de coseno; la variante B los
reordena con el cross-encoder y entrega sus n primeros. Ambas variantes ven exactamente los
mismos candidatos, de modo que cualquier diferencia se debe solo al reordenamiento.

No llama al modelo generativo: todas las métricas se calculan sobre la recuperación.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from rag import (
    BASE_DIR,
    DATOS_DIR,
    MODELO_EMBEDDINGS,
    cargar_configuracion,
    puntuar_con_reranker,
    recuperar_candidatos,
)

ARCHIVO_EVALUACION = DATOS_DIR / "evaluacion" / "consultas-evaluacion.json"
DIRECTORIO_SALIDA = BASE_DIR.parent / "outputs" / "experimento"
VARIANTES = {"A": "Sin reranking", "B": "Con reranking", "C": "Con reranking y umbral"}


# ---------------------------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------------------------


def grados(ids: list[str], relevantes: dict[str, int]) -> list[int]:
    return [relevantes.get(i, 0) for i in ids]


def dcg(valores: list[int]) -> float:
    return sum((2**g - 1) / math.log2(posicion + 1) for posicion, g in enumerate(valores, 1))


def calcular_metricas(ids: list[str], relevantes: dict[str, int], n: int) -> dict[str, float]:
    top = grados(ids[:n], relevantes)
    ideal = sorted(relevantes.values(), reverse=True)[:n]
    primer = next((p for p, g in enumerate(top, 1) if g > 0), None)
    return {
        "hit": 1.0 if primer else 0.0,
        "mrr": 1 / primer if primer else 0.0,
        "ndcg": dcg(top) / dcg(ideal) if ideal else 0.0,
        "precision": sum(1 for g in top if g > 0) / n,
        "recall": sum(1 for g in top if g > 0) / len(relevantes),
        "posicion_primer_relevante": primer or 0,
    }


def posicion_en(ids: list[str], objetivo: str) -> int:
    return ids.index(objetivo) + 1 if objetivo in ids else 0


# ---------------------------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------------------------


def evaluar(configuracion: dict[str, Any]) -> list[dict[str, Any]]:
    recuperacion = configuracion["recuperacion"]
    k, n = recuperacion["k_candidatos"], recuperacion["n_finales"]
    modelo_reranker = recuperacion["modelo_reranker"]
    umbral = recuperacion["umbral_relevancia"]
    consultas = json.loads(ARCHIVO_EVALUACION.read_text(encoding="utf-8"))["consultas"]

    # Precalentamiento para que la carga de los modelos no contamine la medición de latencia.
    puntuar_con_reranker("prueba", recuperar_candidatos("prueba", 2), modelo_reranker)

    resultados = []
    for item in consultas:
        inicio = time.perf_counter()
        candidatos: list[Document] = recuperar_candidatos(item["consulta"], k)
        latencia_vectorial = time.perf_counter() - inicio

        inicio = time.perf_counter()
        reordenados = puntuar_con_reranker(item["consulta"], candidatos, modelo_reranker)
        latencia_reranker = time.perf_counter() - inicio

        ids_a = [d.metadata["id"] for d in candidatos]
        ids_b = [d.metadata["id"] for d in reordenados]
        # Igual que seleccionar_fragmentos(): si el mejor no alcanza el umbral, no se entrega nada.
        ids_c = ids_b if reordenados[0].metadata["puntaje_reranker"] >= umbral else []
        relevantes = item["relevantes"]

        registro: dict[str, Any] = {
            **item,
            "ids_candidatos": ids_a,
            "ids_a": ids_a[:n],
            "ids_b": ids_b[:n],
            "ids_c": ids_c[:n],
            "puntajes_b": [d.metadata["puntaje_reranker"] for d in reordenados[:n]],
            "similitud_top1": candidatos[0].metadata["similitud"],
            "reranker_top1": reordenados[0].metadata["puntaje_reranker"],
            "latencia_vectorial": latencia_vectorial,
            "latencia_reranker": latencia_reranker,
        }
        if relevantes:
            registro["A"] = calcular_metricas(ids_a, relevantes, n)
            registro["B"] = calcular_metricas(ids_b, relevantes, n)
            registro["C"] = calcular_metricas(ids_c, relevantes, n)
            registro["recall_k"] = sum(1 for i in relevantes if i in ids_a) / len(relevantes)
            mejor = max(relevantes, key=relevantes.get)
            registro["mejor_id"] = mejor
            registro["mejor_pos_vectorial"] = posicion_en(ids_a, mejor)
            registro["mejor_pos_reranker"] = posicion_en(ids_b, mejor)
        resultados.append(registro)
        print(f"{item['id']}: listo")
    return resultados


# ---------------------------------------------------------------------------------------------
# Reporte
# ---------------------------------------------------------------------------------------------


def promedio(registros: list[dict], variante: str, metrica: str) -> float:
    return statistics.mean(r[variante][metrica] for r in registros)


def formato_posicion(posicion: int) -> str:
    return str(posicion) if posicion else "fuera"


def tabla(encabezados: list[str], filas: list[list[Any]]) -> list[str]:
    lineas = ["| " + " | ".join(encabezados) + " |", "| " + " | ".join("---" for _ in encabezados) + " |"]
    lineas += ["| " + " | ".join(str(c) for c in fila) + " |" for fila in filas]
    return lineas + [""]


def analizar_umbral(resultados: list[dict], umbral: float) -> dict[str, Any]:
    dentro = [r for r in resultados if r["relevantes"]]
    fuera = [r for r in resultados if not r["relevantes"]]
    minimo_dentro = min(r["reranker_top1"] for r in dentro)
    maximo_fuera = max(r["reranker_top1"] for r in fuera)
    return {
        "dentro": dentro,
        "fuera": fuera,
        "minimo_dentro": minimo_dentro,
        "maximo_fuera": maximo_fuera,
        "separable": maximo_fuera < minimo_dentro,
        "sim_minimo_dentro": min(r["similitud_top1"] for r in dentro),
        "sim_maximo_fuera": max(r["similitud_top1"] for r in fuera),
        "abstenciones_correctas": sum(1 for r in fuera if r["reranker_top1"] < umbral),
        "abstenciones_falsas": [r["id"] for r in dentro if r["reranker_top1"] < umbral],
    }


def fragmentos_perdidos_por_umbral(dentro: list[dict], umbral: float, n: int) -> tuple[int, int]:
    """Compara cuántos relevantes del top-n se perderían con umbral por consulta y por fragmento."""
    por_consulta = por_fragmento = 0
    for r in dentro:
        for posicion, identificador in enumerate(r["ids_b"][:n]):
            if identificador not in r["relevantes"]:
                continue
            if r["reranker_top1"] < umbral:
                por_consulta += 1
            if r["puntajes_b"][posicion] < umbral:
                por_fragmento += 1
    return por_consulta, por_fragmento


def escribir_reporte(resultados: list[dict], configuracion: dict[str, Any], destino: Path) -> None:
    recuperacion = configuracion["recuperacion"]
    k, n, umbral = (
        recuperacion["k_candidatos"],
        recuperacion["n_finales"],
        recuperacion["umbral_relevancia"],
    )
    dentro = [r for r in resultados if r["relevantes"]]
    metricas = [
        ("hit", f"Hit@{n}"),
        ("mrr", f"MRR@{n}"),
        ("ndcg", f"nDCG@{n}"),
        ("precision", f"Precision@{n}"),
        ("recall", f"Recall@{n}"),
    ]

    lineas = [
        "# Experimento: recuperación sin reranking frente a recuperación con reranking",
        "",
        f"- Consultas etiquetadas: {len(resultados)} ({len(dentro)} con respuesta en la base, "
        f"{len(resultados) - len(dentro)} fuera de alcance)",
        f"- Etapa 1 (ambas variantes): `{MODELO_EMBEDDINGS}` + ChromaDB, k = {k} candidatos",
        f"- Variante A: los {n} primeros candidatos según la similitud de coseno",
        f"- Variante B: los {n} primeros tras reordenar con `{recuperacion['modelo_reranker']}`",
        f"- Variante C: la variante B con el umbral de relevancia ({umbral}) aplicado al mejor "
        "candidato, tal como opera `settings-reranking.toml`: si no lo alcanza, no se entrega "
        "ningún fragmento",
        f"- Techo de la etapa 1: Recall@{k} = "
        f"{statistics.mean(r['recall_k'] for r in dentro):.3f} (proporción de fragmentos "
        f"relevantes que llegan a los {k} candidatos)",
        "",
        "## 1. Métricas agregadas",
        "",
    ]
    filas = []
    for clave, nombre in metricas:
        a, b, c = (promedio(dentro, v, clave) for v in VARIANTES)
        filas.append([nombre, f"{a:.3f}", f"{b:.3f}", f"{b - a:+.3f}", f"{c:.3f}", f"{c - a:+.3f}"])
    lineas += tabla(
        ["Métrica", VARIANTES["A"], VARIANTES["B"], "B − A", VARIANTES["C"], "C − A"], filas
    )
    lineas += [
        "Las secciones 2 a 4 comparan A y B para aislar el efecto del reordenamiento; el efecto "
        "del umbral se analiza en la sección 5.",
        "",
    ]

    lineas += ["## 2. Métricas por tipo de consulta", ""]
    filas = []
    for tipo in dict.fromkeys(r["tipo"] for r in dentro):
        grupo = [r for r in dentro if r["tipo"] == tipo]
        filas.append(
            [
                tipo,
                len(grupo),
                f"{promedio(grupo, 'A', 'mrr'):.3f}",
                f"{promedio(grupo, 'B', 'mrr'):.3f}",
                f"{promedio(grupo, 'A', 'ndcg'):.3f}",
                f"{promedio(grupo, 'B', 'ndcg'):.3f}",
            ]
        )
    lineas += tabla(
        ["Tipo", "Consultas", f"MRR@{n} A", f"MRR@{n} B", f"nDCG@{n} A", f"nDCG@{n} B"], filas
    )

    lineas += [
        "## 3. Detalle por consulta",
        "",
        "La columna «Posición del fragmento principal» indica dónde queda el fragmento de "
        f"relevancia 2 entre los {k} candidatos: primero según el bi-encoder y luego tras el "
        "reranking.",
        "",
    ]
    filas = []
    for r in dentro:
        delta = r["B"]["ndcg"] - r["A"]["ndcg"]
        filas.append(
            [
                r["id"],
                r["tipo"],
                r["consulta"],
                f"`{r['mejor_id']}`",
                f"{formato_posicion(r['mejor_pos_vectorial'])} → "
                f"{formato_posicion(r['mejor_pos_reranker'])}",
                f"{r['A']['ndcg']:.3f}",
                f"{r['B']['ndcg']:.3f}",
                f"{delta:+.3f}",
            ]
        )
    lineas += tabla(
        [
            "ID",
            "Tipo",
            "Consulta",
            "Fragmento principal",
            "Posición del fragmento principal",
            f"nDCG@{n} A",
            f"nDCG@{n} B",
            "Δ",
        ],
        filas,
    )

    mejoras = [r for r in dentro if r["B"]["ndcg"] > r["A"]["ndcg"] + 1e-9]
    empeoras = [r for r in dentro if r["B"]["ndcg"] < r["A"]["ndcg"] - 1e-9]
    lineas += [
        "## 4. Balance de cambios",
        "",
        f"- Consultas en las que el reranking mejora nDCG@{n}: {len(mejoras)} "
        f"({', '.join(r['id'] for r in mejoras) or 'ninguna'})",
        f"- Consultas en las que el reranking empeora nDCG@{n}: {len(empeoras)} "
        f"({', '.join(r['id'] for r in empeoras) or 'ninguna'})",
        f"- Consultas sin cambio: {len(dentro) - len(mejoras) - len(empeoras)}",
        "",
    ]
    for r in empeoras:
        lineas += [
            f"**{r['id']}** · «{r['consulta']}»",
            "",
            f"- Top-{n} sin reranking: {', '.join(f'`{i}`' for i in r['ids_a'])}",
            f"- Top-{n} con reranking: {', '.join(f'`{i}`' for i in r['ids_b'])}",
            "",
        ]

    analisis = analizar_umbral(resultados, umbral)
    perdidos_consulta, perdidos_fragmento = fragmentos_perdidos_por_umbral(dentro, umbral, n)
    siguiente_dentro = min(
        (r["reranker_top1"] for r in dentro if r["reranker_top1"] > analisis["maximo_fuera"]),
        default=1.0,
    )
    lineas += [
        "## 5. Umbral de relevancia y consultas fuera de alcance",
        "",
        "Puntaje del mejor candidato de cada consulta según cada modelo. Un buen separador asigna "
        "puntajes altos a las consultas con respuesta y bajos a las que no la tienen.",
        "",
    ]
    filas = [
        [
            r["id"],
            "fuera de alcance" if not r["relevantes"] else "con respuesta",
            f"{r['similitud_top1']:.4f}",
            f"{r['reranker_top1']:.4f}",
            "abstiene" if r["reranker_top1"] < umbral else "responde",
        ]
        for r in sorted(resultados, key=lambda r: r["reranker_top1"])
    ]
    lineas += tabla(
        ["ID", "Grupo", "Similitud coseno top-1", "Puntaje reranker top-1", f"Con umbral {umbral}"],
        filas,
    )
    lineas += [
        f"- Similitud de coseno: mínimo con respuesta = {analisis['sim_minimo_dentro']:.4f}, "
        f"máximo fuera de alcance = {analisis['sim_maximo_fuera']:.4f} → "
        f"{'separables' if analisis['sim_maximo_fuera'] < analisis['sim_minimo_dentro'] else 'se solapan'}",
        f"- Puntaje del reranker: mínimo con respuesta = {analisis['minimo_dentro']:.4f}, "
        f"máximo fuera de alcance = {analisis['maximo_fuera']:.4f} → "
        f"{'separables' if analisis['separable'] else 'se solapan'}",
        f"- Umbral configurado: {umbral}. Se aplica al puntaje del mejor candidato: si no lo "
        "alcanza, el modelo no recibe fragmentos y debe abstenerse",
        f"- Umbrales que separan todas las consultas fuera de alcance de la mayoría con respuesta: "
        f"entre {analisis['maximo_fuera']:.4f} y {siguiente_dentro:.4f}",
        f"- Abstenciones correctas: {analisis['abstenciones_correctas']} de "
        f"{len(analisis['fuera'])} consultas fuera de alcance (la variante A no tiene mecanismo de "
        "abstención y siempre entrega fragmentos)",
        f"- Abstenciones indebidas: {len(analisis['abstenciones_falsas'])} "
        f"({', '.join(analisis['abstenciones_falsas']) or 'ninguna'})",
        f"- Fragmentos relevantes del top-{n} que se pierden por el umbral: {perdidos_consulta} "
        f"aplicándolo al mejor candidato, frente a {perdidos_fragmento} si se aplicara a cada "
        "fragmento por separado",
        "",
        "Efecto de distintos umbrales sobre este conjunto:",
        "",
    ]
    filas = []
    for candidato in (0.001, 0.005, 0.01, 0.05, 0.1):
        efecto = analizar_umbral(resultados, candidato)
        filas.append(
            [
                candidato,
                f"{efecto['abstenciones_correctas']} de {len(efecto['fuera'])}",
                f"{len(efecto['abstenciones_falsas'])} "
                f"({', '.join(efecto['abstenciones_falsas']) or 'ninguna'})",
            ]
        )
    lineas += tabla(["Umbral", "Abstenciones correctas", "Abstenciones indebidas"], filas)

    latencia_a = statistics.mean(r["latencia_vectorial"] for r in resultados)
    latencia_b = statistics.mean(r["latencia_reranker"] for r in resultados)
    lineas += [
        "## 6. Costo en latencia (CPU)",
        "",
        *tabla(
            ["Etapa", "Media por consulta"],
            [
                ["Búsqueda vectorial (k candidatos)", f"{latencia_a * 1000:.0f} ms"],
                [f"Reranking de {k} candidatos", f"{latencia_b * 1000:.0f} ms"],
            ],
        ),
    ]

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(lineas), encoding="utf-8")


def escribir_csv(resultados: list[dict], destino: Path) -> None:
    campos = [
        "consulta_id", "tipo", "variante", "hit", "mrr", "ndcg", "precision", "recall",
        "posicion_primer_relevante", "similitud_top1", "reranker_top1", "top_n",
    ]
    with destino.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=campos)
        escritor.writeheader()
        for r in resultados:
            for variante in VARIANTES:
                metricas = r.get(variante, {})
                escritor.writerow(
                    {
                        "consulta_id": r["id"],
                        "tipo": r["tipo"],
                        "variante": variante,
                        **{c: round(metricas[c], 4) for c in ("hit", "mrr", "ndcg", "precision", "recall") if c in metricas},
                        "posicion_primer_relevante": metricas.get("posicion_primer_relevante", ""),
                        "similitud_top1": r["similitud_top1"],
                        "reranker_top1": r["reranker_top1"],
                        "top_n": " ".join(r[f"ids_{variante.lower()}"]),
                    }
                )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compara la recuperación sin y con reranking.")
    parser.add_argument(
        "--configuracion",
        type=Path,
        default=BASE_DIR / "settings-reranking.toml",
        help="TOML del que se toman k, n, el modelo de reranking y el umbral.",
    )
    argumentos = parser.parse_args()
    configuracion = cargar_configuracion(argumentos.configuracion)

    resultados = evaluar(configuracion)
    escribir_reporte(resultados, configuracion, DIRECTORIO_SALIDA / "reporte.md")
    escribir_csv(resultados, DIRECTORIO_SALIDA / "metricas.csv")
    print(f"Reporte en {DIRECTORIO_SALIDA / 'reporte.md'}")


if __name__ == "__main__":
    main()
