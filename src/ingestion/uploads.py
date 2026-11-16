"""Persist user files and parse them with explicit, non-official provenance."""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from src.catalog import read_json
from src.ingestion.parser import DocumentParser
from src.rag.indexer import _save_json

EXTENSIONS = {'.pdf', '.docx', '.txt', '.html', '.htm', '.xml'}
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_BATCH_BYTES = 100 * 1024 * 1024


def upload_catalog(root=Path('.')):
    return read_json(Path(root) / 'data/uploads/catalog.json')


def save_uploads(files, root=Path('.')):
    """Validate the complete batch before saving; names never become storage paths."""
    root = Path(root)
    if len(files) > 10:
        raise ValueError('Mỗi lượt chọn tối đa 10 tệp.')
    checked = []
    total = 0
    for item in files:
        name = str(item['name']).replace('\\', '/').rsplit('/', 1)[-1]
        suffix = Path(name).suffix.lower()
        content = item['content']
        if suffix not in EXTENSIONS or not name or '\x00' in name:
            raise ValueError('Chỉ nhận PDF, DOCX, TXT, HTML hoặc XML.')
        if not isinstance(content, bytes) or not 0 < len(content) <= MAX_FILE_BYTES:
            raise ValueError(f'{name}: tệp phải có nội dung và không vượt quá 50 MB.')
        total += len(content)
        if total > MAX_BATCH_BYTES:
            raise ValueError('Tổng các tệp trong một lượt không vượt quá 100 MB.')
        if suffix == '.pdf' and not content.startswith(b'%PDF-'):
            raise ValueError(f'{name}: nội dung không phải PDF hợp lệ.')
        if suffix == '.docx':
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                    if 'word/document.xml' not in archive.namelist():
                        raise ValueError('Thiếu nội dung Word.')
                    if sum(part.file_size for part in archive.infolist()) > MAX_BATCH_BYTES:
                        raise ValueError('DOCX giải nén vượt giới hạn 100 MB.')
            except (zipfile.BadZipFile, ValueError) as exc:
                raise ValueError(f'{name}: DOCX không hợp lệ hoặc quá lớn.') from exc
        checksum = hashlib.sha256(content).hexdigest()
        checked.append((item, name, suffix, content, checksum))

    catalog = upload_catalog(root)
    ids = []
    for item, name, suffix, content, checksum in checked:
        doc_id = 'upload_' + checksum
        ids.append(doc_id)
        if doc_id in catalog:
            row = catalog[doc_id]
            path = (root / row['raw_relative_path']).resolve()
            if not path.is_relative_to((root / 'data/uploads/raw').resolve()):
                raise ValueError('Đường dẫn lưu tệp không hợp lệ.')
            needs_repair = not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != checksum
            if needs_repair:
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix(path.suffix + '.tmp')
                temporary.write_bytes(content)
                temporary.replace(path)
            if row.get('upload_status') == 'failed' or needs_repair:
                row.update(upload_status='pending', error=None)
            continue
        relative = Path('data/uploads/raw') / (doc_id + suffix)
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_bytes(content)
        temporary.replace(path)
        catalog[doc_id] = {
            'document_id': doc_id, 'title': Path(name).stem, 'original_filename': name,
            'source_url': 'upload://' + doc_id, 'source_org': 'Người dùng tải lên',
            'jurisdiction': item.get('region') or 'VN', 'language': item.get('language') or 'vi',
            'doc_type': 'user_document', 'published_date': '', 'status': 'unknown',
            'provenance': 'user_upload', 'checksum': checksum, 'raw_relative_path': relative.as_posix(),
            'file_size': len(content), 'upload_status': 'pending',
            'uploaded_at': datetime.now(timezone.utc).isoformat(),
        }
    _save_json(root / 'data/uploads/catalog.json', catalog)
    return list(dict.fromkeys(ids))


def uploaded_file(document_id, root=Path('.')):
    if not re.fullmatch(r'upload_[0-9a-f]{64}', str(document_id or '')):
        return None
    root = Path(root).resolve()
    entry = upload_catalog(root).get(document_id)
    if not entry:
        return None
    path = (root / entry['raw_relative_path']).resolve()
    if not path.is_relative_to(root / 'data/uploads/raw') or not path.is_file():
        return None
    return path, entry


def parse_uploads(root=Path('.'), progress=None):
    root = Path(root)
    catalog = upload_catalog(root)
    report = {'parsed': 0, 'failed': 0, 'errors': [], 'changed_document_ids': []}
    pending = [row for row in catalog.values() if row.get('upload_status') == 'pending']
    if not pending:
        return report
    parser = DocumentParser(str(root / 'data/uploads/raw'), str(root / 'data/uploads/parsed'),
        str(root / 'data/manifests/upload_ingestion_manifest.json'), str(root / 'data/uploads/sources.csv'))
    for row in pending:
        doc_id = row['document_id']
        if progress:
            progress(message='Đang đọc tệp: ' + row['original_filename'])
        try:
            stored = uploaded_file(doc_id, root)
            if not stored:
                raise ValueError('Không tìm thấy tệp đã tải lên.')
            path, _ = stored
            parser.manifest.update(doc_id, **{k: row[k] for k in
                ('title', 'source_url', 'source_org', 'language', 'checksum', 'original_filename')},
                region=row['jurisdiction'], document_type='user_document', provenance='user_upload',
                collected_at=row['uploaded_at'])
            result = parser.parse_one(path)
            if result['status'] != 'parsed':
                raise ValueError(result['error'])
            row.update(upload_status='parsed', error=None)
            report['parsed'] += 1
            report['changed_document_ids'].append(doc_id)
        except Exception as exc:
            row.update(upload_status='failed', error=str(exc)[:600])
            report['failed'] += 1
            report['errors'].append({'provider': 'upload', 'document': doc_id,
                'filename': row['original_filename'], 'error': str(exc)[:600]})
        _save_json(root / 'data/uploads/catalog.json', catalog)
    return report


def finalize_uploads(root, manifest):
    """Identify uploaded text deduplicated into an existing indexed document."""
    root = Path(root)
    catalog = upload_catalog(root)
    if not catalog:
        return
    import pyarrow.dataset as ds
    processed = root / manifest.get('processed_path', 'data/processed')
    if not processed.exists():
        return
    active = set(manifest.get('source_document_ids', []))
    records = ds.dataset(processed, format='parquet').to_table(columns=['source_document_id', 'text_sha256']).to_pylist()
    by_hash = {r['text_sha256']: r['source_document_id'] for r in records}
    for key, row in catalog.items():
        if row.get('upload_status') == 'failed':
            continue
        if key in active:
            row.update(upload_status='indexed', duplicate_of=None)
        else:
            parsed = read_json(root / 'data/uploads/parsed' / (key + '.json'))
            text = parsed.get('text', '')
            if text:
                text = re.sub(r' *\n *', '\n', re.sub(r'[\u00a0\t\r]+', ' ', text)).strip()
                text = re.sub(r'\n{3,}', '\n\n', text)
                existing = by_hash.get(hashlib.sha256(text.encode()).hexdigest())
                if existing:
                    row.update(upload_status='duplicate', duplicate_of=existing)
    _save_json(root / 'data/uploads/catalog.json', catalog)
