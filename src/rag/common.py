"""Shared settings and Ollama client; no LangChain dependency."""
from __future__ import annotations
import os
import requests
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # install requirements-thanh.txt before running services


def setting(name, default):
    return os.getenv(name, default)


def ollama_post(endpoint: str, payload: dict) -> dict:
    base = setting("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    timeout = int(setting("REQUEST_TIMEOUT", "180"))
    try:
        resp = requests.post(f"{base}{endpoint}", json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"Ollama {endpoint} failed at {base}: {exc}") from exc


def embeddings(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = setting("EMBEDDING_MODEL", "bge-m3")
    result = ollama_post("/api/embed", {"model": model, "input": texts, "truncate": False})
    vectors = result.get("embeddings")
    if not isinstance(vectors, list) or len(vectors) != len(texts) or not all(isinstance(v, list) and v for v in vectors):
        raise RuntimeError(f"Invalid Ollama embeddings response for model {model}")
    return vectors


def qdrant_client():
    from qdrant_client import QdrantClient
    return QdrantClient(url=setting("QDRANT_URL", "http://localhost:6333"), timeout=30)


def collection_name():
    return setting("QDRANT_COLLECTION", "ai_law_documents")
