"""One inventory and one active-document count for every part of the UI."""
import csv
import json
from pathlib import Path


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return {} if default is None else default


def load_inventory(root=Path('.')):
    root = Path(root)
    records = {}
    source = root / 'data/sources.csv'
    if source.exists():
        with source.open(encoding='utf-8-sig', newline='') as stream:
            records = {row['document_id']: row for row in csv.DictReader(stream)}
    records.update(read_json(root / 'data/dynamic/catalog.json'))
    records.update({key: row for key, row in read_json(root / 'data/uploads/catalog.json').items()
                    if row.get('upload_status') != 'duplicate'})
    manifest = read_json(root / 'data/manifests/index_manifest.json')
    active = set(manifest.get('source_document_ids', [])) if manifest.get('status') == 'ready' else set()
    for key in active - records.keys():
        records[key] = {'document_id': key, 'title': key}
    for key, row in records.items():
        row['_index_status'] = 'Đã lập chỉ mục' if key in active else 'Chưa có trong chỉ mục'
    counts = {'active': len(active), 'catalog': len(records), 'pending': len(records) - len(active),
              'chunks': manifest.get('total_chunks', 0) if active else 0}
    return list(records.values()), manifest, counts
