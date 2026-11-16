"""APIs/user uploads -> parsed JSON -> Spark/Parquet -> vector snapshot -> HDFS."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import re
from datetime import datetime, timezone
from src.catalog import read_json
from src.ingestion.dynamic_api import DynamicIngestor
from src.ingestion.uploads import parse_uploads, finalize_uploads
from src.rag.indexer import _save_json
from src.updates.service import ROOT, file_lock, get_update_status, save_status, start_update


def prepare_inputs(root, destination):
    """Dynamic whole-text snapshots replace the same canonical document, not its history."""
    chosen = {}
    for directory in ['data/verified_parsed', 'data/dynamic/parsed', 'data/uploads/parsed']:
        for path in sorted((root / directory).glob('*.json')):
            record = read_json(path)
            allowed = {'user_upload'} if directory == 'data/uploads/parsed' else {'official_download', 'official_api'}
            if record.get('parse_status') == 'success' and record.get('provenance') in allowed and record.get('document_id') and record.get('text'):
                chosen[record['document_id']] = (path, record)
    signature = hashlib.sha256(json.dumps(sorted([
        [key] + [record.get(field) for field in ('content_hash', 'title', 'source_url', 'legal_status', 'effective_date')]
        for key, (_, record) in chosen.items()]), ensure_ascii=False).encode()).hexdigest()
    destination.mkdir(parents=True, exist_ok=True)
    for key, (path, _) in chosen.items():
        shutil.copy2(path, destination / (key + '.json'))
    return signature, len(chosen)


def execute_pipeline(job_id, root, signature, inputs):
    from src.processing.spark_etl import run as etl
    from src.processing.chunker import run as chunk
    from src.rag.indexer import run as index
    from src.rag.common import collection_name, setting
    job = Path('data/updates') / job_id
    processed, chunks = job / 'processed', job / 'chunks'
    save_status(job_id, root, stage='etl', progress=30, message='Đang chuẩn hóa và khử trùng văn bản bằng Spark.')
    etl(str(inputs), str(processed), 'local[2]')
    save_status(job_id, root, stage='chunk', progress=45, message='Đang chia đoạn và gắn nguồn trích dẫn.')
    chunk(str(processed), str(chunks))
    save_status(job_id, root, stage='index', progress=55, message='Đang bổ sung vector và chuẩn bị chỉ mục mới.')
    index(str(chunks), batch_size=int(setting('EMBED_BATCH_SIZE', 8)), rebuild=True,
        snapshot_name=collection_name() + '__api_' + job_id, reuse_existing=True,
        processed_path=str(processed), corpus_signature=signature)
    return processed, chunks


def run_update(job_id, root=ROOT):
    root = Path(root).resolve()
    if not re.fullmatch(r'\d{8}_\d{6}_[0-9a-f]{8}', job_id):
        raise ValueError('Định danh lượt cập nhật không hợp lệ')
    state = read_json(root / 'data/manifests/update_status.json')
    if state.get('job_id') != job_id:
        raise RuntimeError('Lượt cập nhật không khớp')
    with file_lock(root / 'data/manifests/update_run.lock'):
        try:
            save_status(job_id, root, status='running', stage='parse', progress=3, message='Đang kiểm tra tài liệu tải lên.')
            def progress(**values):
                changes = {'message': values.get('message', 'Đang thu thập dữ liệu.')}
                if 'progress' in values:
                    changes['progress'] = int(values['progress'])
                save_status(job_id, root, **changes)
            uploads = parse_uploads(root, progress=progress)
            save_status(job_id, root, upload_report=uploads, stage='collect', progress=5,
                message='Đang kiểm tra nguồn API.' if state['providers'] else 'Đã đọc tệp; đang chuẩn bị dữ liệu xử lý.')
            report = {'providers': {}, 'errors': [], 'changed': 0, 'changed_document_ids': []}
            if state['providers']:
                try:
                    report = DynamicIngestor(root, progress=progress).run(state['providers'], state['max_documents'])
                except Exception as exc:
                    saved_uploads = any((root / 'data/uploads/parsed').glob('*.json'))
                    if not uploads['parsed'] and not state.get('upload_ids') and not saved_uploads:
                        raise
                    report['errors'].append({'provider': 'api', 'error': str(exc)[:600]})
            save_status(job_id, root, collection_report=report, progress=25)
            inputs = root / 'data/updates' / job_id / 'input'
            signature, count = prepare_inputs(root, inputs)
            active = read_json(root / 'data/manifests/index_manifest.json')
            errors = list(report['errors']) + uploads['errors']
            incomplete = any(s.get('status') != 'ok' for s in report['providers'].values()) or bool(uploads['failed'])
            if active.get('corpus_signature') == signature:
                finalize_uploads(root, active)
                save_status(job_id, root, status='partial' if incomplete or errors else 'no_changes',
                    stage='done', progress=100, message='Đã kiểm tra nguồn; chưa có thay đổi cần lập chỉ mục.',
                    added_documents=0, active_documents=len(active.get('source_document_ids', [])), collection_report=report, warnings=errors,
                    finished_at=datetime.now(timezone.utc).isoformat())
                return
            before = set(active.get('source_document_ids', []))
            processed, chunks = execute_pipeline(job_id, root, signature, inputs)
            active = read_json(root / 'data/manifests/index_manifest.json')
            warnings = errors
            finalize_uploads(root, active)
            save_status(job_id, root, stage='lake', progress=90, message='Đã công bố chỉ mục mới; đang đồng bộ Data Lake.')
            try:
                from scripts.sync_lake import sync_lake
                sync_lake(processed=str(processed), chunks=str(chunks), dataset_version=job_id)
            except Exception as exc:
                warnings.append({'provider': 'hdfs', 'error': str(exc)[:400]})
            backlog = sum(s.get('backlog', 0) for s in report['providers'].values())
            after = set(active.get('source_document_ids', []))
            updated = len(set(report.get('changed_document_ids', []) + uploads['changed_document_ids']) & before & after)
            save_status(job_id, root, status='partial' if warnings or incomplete else 'completed', stage='done', progress=100,
                message='Đã cập nhật dữ liệu vào tra cứu.' + (' Còn tài liệu chờ lượt tiếp theo.' if backlog else ''),
                added_documents=len(after - before), updated_documents=updated,
                active_documents=len(after), total_chunks=active.get('total_chunks', 0), warnings=warnings,
                finished_at=datetime.now(timezone.utc).isoformat())
        except Exception as exc:
            save_status(job_id, root, status='failed', stage='failed', message='Lượt cập nhật chưa hoàn tất. Bạn có thể thử lại.',
                error=str(exc)[:1000], finished_at=datetime.now(timezone.utc).isoformat())
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job-id', help='Internal worker identifier')
    parser.add_argument('--providers', nargs='+', choices=['vbpl', 'federal_register'])
    parser.add_argument('--uploads-only', action='store_true', help='Process queued uploads without fetching APIs')
    parser.add_argument('--max-documents', type=int, default=20)
    args = parser.parse_args()
    if args.job_id:
        run_update(args.job_id)
    else:
        print(json.dumps(start_update([] if args.uploads_only else args.providers, args.max_documents), ensure_ascii=False, indent=2))
