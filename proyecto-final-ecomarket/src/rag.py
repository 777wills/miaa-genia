from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = BASE_DIR / "datos" / "conocimiento"
INDEX_DIR = BASE_DIR / "indice"
MODEL_EMBEDDINGS = "intfloat/multilingual-e5-base"
COLLECTION = "ecomarket-final"

def _documentos_locales() -> list[dict[str, str]]:
    documentos: list[dict[str, str]] = []

    for archivo in sorted(KNOWLEDGE_DIR.glob("*.md")):
        texto = archivo.read_text(encoding="utf-8")
        bloques = [b.strip() for b in re.split(r"\n(?=## )", texto) if b.strip()]
        for i, bloque in enumerate(bloques, 1):
            documentos.append({
                "id": f"{archivo.stem}-{i}",
                "fuente": archivo.name,
                "contenido": bloque,
            })

    faq_path = KNOWLEDGE_DIR / "faq.json"
    if faq_path.exists():
        datos = json.loads(faq_path.read_text(encoding="utf-8"))
        for item in datos.get("preguntas", []):
            documentos.append({
                "id": item["id"],
                "fuente": "faq.json",
                "contenido": f"{item['categoria']}\nPregunta: {item['pregunta']}\nRespuesta: {item['respuesta']}",
            })
    return documentos

@lru_cache(maxsize=1)
def _embeddings():
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(
        model_name=MODEL_EMBEDDINGS,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True, "prompt": "passage: "},
        query_encode_kwargs={"normalize_embeddings": True, "prompt": "query: "},
    )

def construir_indice() -> dict[str, Any]:
    from langchain_chroma import Chroma
    from langchain_core.documents import Document

    docs = _documentos_locales()
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    vectores = Chroma(
        collection_name=COLLECTION,
        embedding_function=_embeddings(),
        persist_directory=str(INDEX_DIR),
        collection_metadata={"hnsw:space": "cosine"},
    )
    existing = vectores.get()["ids"]
    if existing:
        vectores.delete(ids=existing)

    vectores.add_documents(
        [
            Document(
                page_content=d["contenido"],
                metadata={"id": d["id"], "fuente": d["fuente"]},
            )
            for d in docs
        ],
        ids=[d["id"] for d in docs],
    )
    return {"documentos_indexados": len(docs), "indice": str(INDEX_DIR)}

@lru_cache(maxsize=1)
def _vectorstore():
    from langchain_chroma import Chroma
    store = Chroma(
        collection_name=COLLECTION,
        embedding_function=_embeddings(),
        persist_directory=str(INDEX_DIR),
        collection_metadata={"hnsw:space": "cosine"},
    )
    if not store.get(limit=1)["ids"]:
        construir_indice()
    return store

def _lexical(query: str, k: int = 4) -> list[dict[str, Any]]:
    palabras = set(re.findall(r"[a-záéíóúñ0-9]+", query.lower()))
    resultados = []
    for doc in _documentos_locales():
        contenido_palabras = set(re.findall(r"[a-záéíóúñ0-9]+", doc["contenido"].lower()))
        score = len(palabras & contenido_palabras)
        resultados.append({**doc, "score": score})
    resultados.sort(key=lambda x: x["score"], reverse=True)
    return [r for r in resultados[:k] if r["score"] > 0]

def consultar(consulta: str, k: int = 4) -> dict[str, Any]:
    try:
        resultados = _vectorstore().similarity_search_with_score(consulta, k=k)
        fragmentos = [
            {
                "fuente": doc.metadata.get("fuente"),
                "contenido": doc.page_content,
                "similitud": round(1 - float(distancia), 4),
            }
            for doc, distancia in resultados
        ]
        return {"ok": True, "metodo": "chroma+multilingual-e5-base", "fragmentos": fragmentos}
    except Exception as error:
        fragmentos = _lexical(consulta, k=k)
        return {
            "ok": True,
            "metodo": "fallback_lexico",
            "advertencia": f"El índice vectorial no estuvo disponible: {type(error).__name__}",
            "fragmentos": fragmentos,
        }
