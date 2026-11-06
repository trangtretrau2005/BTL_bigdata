"""Deterministic, character-based overlapping chunks, with citations metadata."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path


def chunk_text(text: str, size: int = 1000, overlap: int = 150):
    if not 0 <= overlap < size:
        raise ValueError("Require 0 <= overlap < size")
    if not text.strip():
        return
    start, total = 0, len(text)
    while start < total:
        end = min(start + size, total)
        if end < total:
            # Prefer an end-of-sentence/paragraph boundary when close to end.
            tail_start = start + int(size * 0.65)
            if tail_start < end:
                candidates = [text.rfind(mark, tail_start, end) for mark in ("\n\n", ". ", ".\n", "; ")]
                boundary = max(candidates)
                if boundary > start + overlap:
                    end = boundary + (2 if text[boundary:boundary+2] in ("\n\n", ". ", "; ") else 1)
        yield start, end, text[start:end]
        if end >= total:
            break
        next_start = end - overlap
        if next_start <= start:
            next_start = end
        start = next_start


def chunk_document(doc: dict, size=1000, overlap=150):
    doc_id = doc["document_id"]
    for i, (start, end, text) in enumerate(chunk_text(doc["text"], size, overlap)):
        chunk_id = hashlib.sha256(f"{doc_id}|{start}|{end}|{text}".encode("utf-8")).hexdigest()
        yield {"chunk_id": chunk_id, "document_id": doc_id, "chunk_index": i,
               "char_start": start, "char_end": end, "text": text,
               **{k: doc.get(k) for k in ("source_document_id", "title", "source_url", "region",
                                               "published_date", "document_type", "source_path", "text_sha256")}}


def stable_chunk_id(document_id: str, version: str, chunk_index: int, text: str) -> str:
    """Tao ma dinh danh on dinh cho tung chunk.

    Dung de tai tao chunk ID khi rebuild index ma khong can re-download du lieu.
    Ket qua la deterministic: cung input luon cho cung output (TC02).
    """
    payload = f"{document_id}:{version}:{chunk_index}:{text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run(input_path: str, output_path: str, size=1000, overlap=150):
    # PyArrow reads Spark Parquet output, including partitioned datasets.
    import pyarrow.dataset as ds
    dataset = ds.dataset(input_path, format="parquet")
    out = Path(output_path)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "chunks.jsonl"
    doc_count = chunk_count = 0
    with target.open("w", encoding="utf-8") as file:
        for batch in dataset.to_batches(batch_size=64):
            for doc in batch.to_pylist():
                doc_count += 1
                for chunk in chunk_document(doc, size, overlap):
                    file.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                    chunk_count += 1
    if not chunk_count:
        raise ValueError("No chunks created")
    print(f"Chunking complete: {doc_count} documents / {chunk_count} chunks -> {target}")
    return chunk_count


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="data/processed")
    p.add_argument("--output", default="data/chunks")
    p.add_argument("--size", type=int, default=1000)
    p.add_argument("--overlap", type=int, default=150)
    a = p.parse_args()
    run(a.input, a.output, a.size, a.overlap)


if __name__ == "__main__":
    main()
