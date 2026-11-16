"""A failed rebuild must not publish partial search data."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.rag import indexer


def test_manifest_replacement_retries_transient_windows_lock(tmp_path, monkeypatch):
    path = tmp_path / 'progress.json'
    path.write_text('{"status":"old"}', encoding='utf-8')
    original = Path.replace
    attempts = []
    def locked_twice(source, target):
        attempts.append(source.name)
        if len(attempts) < 3:
            assert json.loads(path.read_text())['status'] == 'old'
            raise PermissionError('Windows bind mount is briefly busy')
        return original(source, target)
    monkeypatch.setattr(Path, 'replace', locked_twice)
    monkeypatch.setattr(indexer.time, 'sleep', lambda seconds: None)
    indexer._save_json(path, {'status': 'ready'})
    assert len(attempts) == 3
    assert json.loads(path.read_text())['status'] == 'ready'


class FakeClient:
    def __init__(self):
        self.points = {}
        self.operations = []

    def get_aliases(self):
        return SimpleNamespace(aliases=[])

    def collection_exists(self, name):
        return name in self.points

    def create_collection(self, name, vectors_config):
        self.points[name] = []

    def get_collection(self, name):
        return SimpleNamespace(config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=2))))

    def upsert(self, collection_name, points, wait):
        self.points[collection_name].extend(points)

    def count(self, collection_name, exact):
        return SimpleNamespace(count=len(self.points[collection_name]))

    def update_collection_aliases(self, change_aliases_operations):
        self.operations.extend(change_aliases_operations)


def write_input(path):
    rows = [
        {"chunk_id": str(i), "document_id": "doc", "text": "AI policy", "source_url": "https://example.org"}
        for i in (1, 2)
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def test_completed_snapshot_is_published_and_metadata_saved(tmp_path, monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(indexer, "qdrant_client", lambda: client)
    monkeypatch.setattr(indexer, "collection_name", lambda: "verified")
    monkeypatch.setattr(indexer, "embeddings", lambda texts: [[0.1, 0.9] for text in texts])
    chunks, manifest = tmp_path / "chunks.jsonl", tmp_path / "index_manifest.json"
    write_input(chunks)
    assert indexer.run(str(chunks), 1, rebuild=True, manifest_path=str(manifest)) == 2
    assert len(client.operations) == 1
    info = json.loads(manifest.read_text(encoding="utf-8"))
    assert info["status"] == "ready" and info["total_chunks"] == 2
    first = client.points[info["snapshot"]][0]
    assert first.payload["embedding_model"] and first.payload["indexed_at"]


def test_failure_preserves_previous_manifest_and_does_not_publish(tmp_path, monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(indexer, "qdrant_client", lambda: client)
    monkeypatch.setattr(indexer, "collection_name", lambda: "verified")
    calls = []
    def embed(texts):
        calls.append(texts)
        if len(calls) == 2:
            raise RuntimeError("model timeout")
        return [[0.1, 0.9]]
    monkeypatch.setattr(indexer, "embeddings", embed)
    chunks, manifest = tmp_path / "chunks.jsonl", tmp_path / "index_manifest.json"
    write_input(chunks)
    manifest.write_text('{"status":"ready","snapshot":"old"}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="model timeout"):
        indexer.run(str(chunks), 1, rebuild=True, manifest_path=str(manifest))
    assert client.operations == []
    assert json.loads(manifest.read_text(encoding="utf-8"))["snapshot"] == "old"
    progress = json.loads((tmp_path / "index_progress.json").read_text(encoding="utf-8"))
    assert progress["status"] == "failed" and progress["completed_chunks"] == 1
