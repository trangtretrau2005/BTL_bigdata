"""Build a verified vector index, publishing rebuilt snapshots through an atomic alias."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid
import time

from qdrant_client import models
from .common import collection_name, embeddings, qdrant_client, setting


def read_chunks(path: str):
    source = Path(path)
    if source.is_dir():
        source = source / "chunks.jsonl"
    with source.open(encoding="utf-8-sig") as file:
        for line_no, line in enumerate(file, 1):
            if line.strip():
                item = json.loads(line)
                if not item.get("chunk_id") or not item.get("text") or not item.get("source_url"):
                    raise ValueError(f"Chunk dòng {line_no} thiếu ID, nội dung hoặc URL nguồn")
                yield item


def ensure_collection(client, name: str, vector_size: int):
    if not client.collection_exists(name):
        client.create_collection(name, vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE))
    else:
        vectors = client.get_collection(name).config.params.vectors
        if getattr(vectors, "size", None) != vector_size:
            raise ValueError(f"Collection '{name}' có số chiều khác model; hãy tạo snapshot mới")


def upload_batch(client, name, batch, *, reuse_from=None):
    vectors = [None] * len(batch)
    if reuse_from:
        stored = client.retrieve(collection_name=reuse_from,
            ids=[str(uuid.uuid5(uuid.NAMESPACE_URL, row['chunk_id'])) for row in batch],
            with_vectors=True, with_payload=True)
        existing = {str(point.id): point for point in stored}
        for i, row in enumerate(batch):
            point = existing.get(str(uuid.uuid5(uuid.NAMESPACE_URL, row['chunk_id'])))
            if point and isinstance(point.vector, list) and point.vector and (point.payload or {}).get('text') == row['text'] and (point.payload or {}).get('embedding_model') == setting('EMBEDDING_MODEL', 'bge-m3'):
                vectors[i] = point.vector
    missing = [i for i, vector in enumerate(vectors) if vector is None]
    if missing:
        fresh = embeddings([batch[i]['text'] for i in missing])
        if len(fresh) != len(missing):
            raise ValueError('Embedding API trả sai số vector mới')
        for i, vector in zip(missing, fresh):
            vectors[i] = vector
    if len(vectors) != len(batch) or not vectors or not vectors[0]:
        raise ValueError("Embedding API trả sai số vector")
    ensure_collection(client, name, len(vectors[0]))
    if any(len(vector) != len(vectors[0]) for vector in vectors):
        raise ValueError("Embedding dimensions changed inside batch")
    indexed_at = datetime.now(timezone.utc).isoformat()
    points = [
        models.PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, row["chunk_id"])),
            vector=vector,
            payload={**row, "embedding_model": setting("EMBEDDING_MODEL", "bge-m3"), "indexed_at": indexed_at},
        )
        for row, vector in zip(batch, vectors)
    ]
    client.upsert(collection_name=name, points=points, wait=True)
    return len(points)


def _save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Docker bind mounts on Windows may briefly lock a file during replacement.
    # A unique staging file also prevents writers from sharing the same .tmp path.
    temporary = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    for attempt in range(7):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 6:
                raise
            time.sleep(min(.05 * 2 ** attempt, .8))


def run(
    chunks: str, batch_size: int = 8, *, rebuild: bool = False,
    snapshot_name: str | None = None, manifest_path: str = "data/manifests/index_manifest.json",
    reuse_existing: bool = False, processed_path: str = 'data/processed', corpus_signature: str | None = None,
):
    if batch_size < 1:
        raise ValueError("batch-size must be >=1")
    rows = list(read_chunks(chunks))
    if not rows:
        raise ValueError("No chunks to index")
    chunk_ids = {row["chunk_id"] for row in rows}
    if len(chunk_ids) != len(rows):
        raise ValueError("Chunk IDs trùng trong tập đầu vào")
    client, public_name = qdrant_client(), collection_name()
    alias_targets = {alias.alias_name: alias.collection_name for alias in client.get_aliases().aliases}
    if rebuild and client.collection_exists(public_name) and public_name not in alias_targets:
        raise ValueError(
            f"'{public_name}' là collection vật lý. Để rebuild an toàn, đặt QDRANT_COLLECTION "
            "thành một tên alias mới (ví dụ ai_documents_verified_v2), rồi chạy --rebuild."
        )
    if snapshot_name and (not rebuild or snapshot_name == public_name):
        raise ValueError("--snapshot-name chỉ dùng với --rebuild và phải khác tên alias")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    target = (snapshot_name or f"{public_name}__{stamp}_{uuid.uuid4().hex[:6]}") if rebuild else public_name
    manifest = Path(manifest_path)
    progress_path = manifest.with_name("index_progress.json")
    input_hash = hashlib.sha256("|".join(sorted(chunk_ids)).encode("utf-8")).hexdigest()
    if snapshot_name and snapshot_name in alias_targets.values():
        raise ValueError("Không tiếp tục ghi lên snapshot đang phục vụ người dùng; hãy tạo snapshot mới")
    if snapshot_name and client.collection_exists(snapshot_name):
        previous = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {}
        if previous.get("snapshot") != snapshot_name or previous.get("input_hash") != input_hash:
            raise ValueError("Snapshot tiếp tục không khớp tập chunk; hãy rebuild với snapshot mới")
    progress = {
        "status": "running", "collection": public_name, "snapshot": target, "rebuild": rebuild,
        "total_chunks": len(rows), "completed_chunks": 0, "embedding_model": setting("EMBEDDING_MODEL", "bge-m3"),
        "input_hash": input_hash,
    }
    try:
        _save_json(progress_path, progress)
        for offset in range(0, len(rows), batch_size):
            batch = rows[offset:offset + batch_size]
            reuse_from = public_name if reuse_existing and public_name in alias_targets else None
            upload_batch(client, target, batch, reuse_from=reuse_from)
            progress.update(completed_chunks=offset + len(batch), updated_at=datetime.now(timezone.utc).isoformat())
            _save_json(progress_path, progress)
            print(f"Indexed {offset + len(batch)}/{len(rows)} chunks -> {target}", flush=True)

        actual_count = client.count(collection_name=target, exact=True).count
        if rebuild and actual_count != len(rows):
            raise RuntimeError(f"Snapshot có {actual_count} point, cần {len(rows)}; alias cũ được giữ nguyên")
        if rebuild:
            operations = []
            if public_name in alias_targets:
                operations.append(models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name=public_name)))
            operations.append(models.CreateAliasOperation(create_alias=models.CreateAlias(
                collection_name=target, alias_name=public_name,
            )))
            client.update_collection_aliases(change_aliases_operations=operations)

        completed = {
            "status": "ready", "collection": public_name, "snapshot": target,
            "total_documents": len({row["document_id"] for row in rows}),
            "source_document_ids": sorted({row.get('source_document_id') or row['document_id'] for row in rows}),
            "total_chunks": actual_count, "input_chunks": len(rows),
            "embedding_model": setting("EMBEDDING_MODEL", "bge-m3"),
            "indexed_at": datetime.now(timezone.utc).isoformat(), "rebuild": rebuild,
            "processed_path": str(processed_path),
            "chunks_path": str(Path(chunks) / 'chunks.jsonl') if Path(chunks).is_dir() else str(chunks),
            "corpus_signature": corpus_signature,
        }
        _save_json(manifest, completed)
        _save_json(progress_path, {**progress, "status": "ready"})
        print(f"Index complete: {len(rows)} upserts, {actual_count} active points in '{public_name}'", flush=True)
        return len(rows)
    except Exception as exc:
        _save_json(progress_path, {**progress, "status": "failed", "error": str(exc)})
        raise RuntimeError(
            f"Index chưa hoàn tất ({progress['completed_chunks']}/{len(rows)} chunk): {exc}. "
            f"Snapshot đang xây: {target}. Với rebuild, alias trước đó được giữ nguyên nếu chưa chuyển. "
            "Có thể chạy lại --rebuild --snapshot-name <tên snapshot> để tiếp tục upsert."
        ) from exc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", default="data/chunks")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--rebuild", action="store_true", help="Build a new snapshot and atomically publish its alias")
    parser.add_argument("--snapshot-name", help="Reuse a staging snapshot after an interrupted rebuild")
    parser.add_argument("--manifest", default="data/manifests/index_manifest.json")
    args = parser.parse_args()
    run(args.chunks, args.batch_size, rebuild=args.rebuild, snapshot_name=args.snapshot_name, manifest_path=args.manifest)


if __name__ == "__main__":
    main()
