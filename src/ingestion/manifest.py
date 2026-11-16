"""Atomic thread-safe ingestion manifest."""
import hashlib
import json
import threading
from pathlib import Path
from datetime import datetime, timezone


def calculate_checksum(file_path: str) -> str:
    digest = hashlib.sha256()
    with open(file_path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


class ManifestManager:
    def __init__(self, manifest_path: str):
        self.manifest_path = Path(manifest_path)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.records = json.loads(self.manifest_path.read_text(encoding='utf-8-sig')) if self.manifest_path.exists() else {}

    def update(self, document_id: str, **fields):
        with self._lock:
            record = dict(self.records.get(document_id, {}))
            record.update(fields)
            record['updated_at'] = datetime.now(timezone.utc).isoformat()
            self.records[document_id] = record
            self.save()

    def get(self, document_id: str):
        with self._lock:
            return dict(self.records.get(document_id, {})) or None

    def save(self):
        with self._lock:
            temporary = self.manifest_path.with_suffix(self.manifest_path.suffix + '.tmp')
            temporary.write_text(json.dumps(self.records, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(self.manifest_path)
