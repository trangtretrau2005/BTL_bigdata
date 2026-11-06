"""Semantic retrieval with optional region and document filters."""
from __future__ import annotations
from .common import collection_name, embeddings, qdrant_client


def retrieve(question: str, top_k: int = 5, region: str | None = None, document_id: str | None = None):
    if not question.strip():
        raise ValueError("Empty question")
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    from qdrant_client import models
    conditions = []
    if region and region.upper() != "ALL":
        conditions.append(models.FieldCondition(key="region", match=models.MatchValue(value=region.upper())))
    if document_id:
        conditions.append(models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id)))
    search_filter = models.Filter(must=conditions) if conditions else None
    client = qdrant_client()
    if not client.collection_exists(collection_name()):
        raise RuntimeError("Qdrant collection does not exist. Run the indexing step first.")
    query_vector = embeddings([question])[0]
    hits = client.query_points(collection_name=collection_name(), query=query_vector,
                               query_filter=search_filter, limit=top_k, with_payload=True).points
    return [{"score": float(hit.score), **(hit.payload or {})} for hit in hits]
