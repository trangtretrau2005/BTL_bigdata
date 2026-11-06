"""Embed JSONL chunks through Ollama and upsert stable IDs into Qdrant."""
from __future__ import annotations
import argparse
import json
import uuid
from pathlib import Path
from qdrant_client import models
from .common import collection_name, embeddings, qdrant_client


def read_chunks(path: str):
    source = Path(path)
    if source.is_dir():
        source = source / "chunks.jsonl"
    with source.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if line.strip():
                item = json.loads(line)
                if not item.get("chunk_id") or not item.get("text"):
                    raise ValueError(f"Invalid chunk at line {line_no}")
                yield item


def ensure_collection(client, name: str, vector_size: int):
    if not client.collection_exists(name):
        client.create_collection(name, vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE))
    else:
        info = client.get_collection(name)
        vectors = info.config.params.vectors
        current_size = getattr(vectors, "size", None)
        if current_size != vector_size:
            raise ValueError(f"Collection '{name}' has dimension {current_size}, model returns {vector_size}; use a new collection")


def upload_batch(client, name, batch):
    vectors = embeddings([row["text"] for row in batch])
    ensure_collection(client, name, len(vectors[0]))
    if any(len(v) != len(vectors[0]) for v in vectors):
        raise ValueError("Embedding dimensions changed inside batch")
    points = []
    for row, vector in zip(batch, vectors):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, row["chunk_id"]))
        points.append(models.PointStruct(id=point_id, vector=vector, payload=row))
    client.upsert(collection_name=name, points=points, wait=True)
    return len(points)


def run(chunks: str, batch_size: int = 8):
    if batch_size < 1:
        raise ValueError("batch-size must be >=1")
    client, name = qdrant_client(), collection_name()
    total, batch = 0, []
    for row in read_chunks(chunks):
        batch.append(row)
        if len(batch) >= batch_size:
            total += upload_batch(client, name, batch)
            print(f"Indexed {total} chunks")
            batch = []
    if batch:
        total += upload_batch(client, name, batch)
    if not total:
        raise ValueError("No chunks to index")
    print(f"Index complete: {total} upserts into Qdrant collection '{name}'")
    return total


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--chunks", default="data/chunks")
    p.add_argument("--batch-size", type=int, default=8)
    a = p.parse_args()
    run(a.chunks, a.batch_size)


if __name__ == "__main__":
    main()
