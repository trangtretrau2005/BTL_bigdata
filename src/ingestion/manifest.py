
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone


def calculate_checksum(file_path: str) -> str:
    """Tính SHA-256 của file theo từng khối dữ liệu."""
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


class ManifestManager:
    def __init__(self, manifest_path: str):
        self.manifest_path = Path(manifest_path)
        self.manifest_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.records = {}

        if self.manifest_path.exists():
            with open(
                self.manifest_path,
                "r",
                encoding="utf-8"
            ) as file:
                self.records = json.load(file)

    def update(self, document_id: str, **fields):
        """Cập nhật trạng thái và metadata tài liệu."""

        record = self.records.get(document_id, {})

        record.update(fields)

        record["updated_at"] = datetime.now(
            timezone.utc
        ).isoformat()

        self.records[document_id] = record

        self.save()

    def get(self, document_id: str):
        return self.records.get(document_id)

    def save(self):
        with open(
            self.manifest_path,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                self.records,
                file,
                ensure_ascii=False,
                indent=2
            )
