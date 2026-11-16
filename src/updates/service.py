"""Start one durable update worker across Streamlit reruns and browser sessions."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import os
import subprocess
import sys
import uuid
from src.catalog import read_json
from src.rag.indexer import _save_json

ROOT = Path(__file__).resolve().parents[2]
ACTIVE = {'queued', 'running'}


class UpdateBusy(RuntimeError):
    pass


@contextmanager
def file_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open('a+b')
    acquired = False
    try:
        if os.name == 'nt':
            import msvcrt
            stream.seek(0, 2)
            if stream.tell() == 0:
                stream.write(b'0'); stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise UpdateBusy('Đang có một lượt cập nhật dữ liệu.') from exc
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise UpdateBusy('Đang có một lượt cập nhật dữ liệu.') from exc
        acquired = True
        yield
    finally:
        if acquired:
            if os.name == 'nt':
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def get_update_status(root=None):
    root = Path(root or ROOT)
    state = read_json(root / 'data/manifests/update_status.json')
    if state.get('status') not in ACTIVE:
        return state
    if state.get('status') == 'queued':
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(state['started_at'])).total_seconds()
        if age < 30:
            return state
    try:
        with file_lock(root / 'data/manifests/update_run.lock'):
            return {**state, 'status': 'interrupted', 'message': 'Lượt trước đã dừng. Bạn có thể cập nhật lại; dữ liệu đã công bố vẫn được giữ.'}
    except UpdateBusy:
        return state


def save_status(job_id, root=None, **changes):
    root = Path(root or ROOT)
    path = root / 'data/manifests/update_status.json'
    state = read_json(path)
    if state.get('job_id') != job_id:
        raise RuntimeError('Lượt cập nhật không còn là lượt đang được theo dõi')
    state.update(changes, updated_at=datetime.now(timezone.utc).isoformat())
    _save_json(path, state)
    return state


def start_update(providers=None, max_documents=20, root=None, uploads=None):
    root = Path(root or ROOT).resolve()
    config = read_json(root / 'data/api_sources.json')
    providers = [key for key, value in config.items() if value.get('enabled')] if providers is None else providers
    if any(key not in config or not config[key].get('enabled') for key in providers):
        raise ValueError('Nguồn API không hợp lệ')
    if not providers and not uploads and not read_json(root / 'data/uploads/catalog.json'):
        raise ValueError('Hãy chọn tệp tải lên hoặc bật nguồn API.')
    if not 1 <= int(max_documents) <= 100:
        raise ValueError('Giới hạn cập nhật không hợp lệ')
    with file_lock(root / 'data/manifests/update_start.lock'):
        current = get_update_status(root)
        if current.get('status') in ACTIVE:
            if uploads:
                raise UpdateBusy('Đợi lượt đang chạy hoàn tất trước khi tải thêm tệp.')
            return current
        # Also protect against a CLI worker whose state file is unavailable.
        with file_lock(root / 'data/manifests/update_run.lock'):
            from src.ingestion.uploads import save_uploads
            upload_ids = save_uploads(uploads, root) if uploads else []
            job_id = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_') + uuid.uuid4().hex[:8]
            job_dir = root / 'data/updates' / job_id
            job_dir.mkdir(parents=True)
            state = {'job_id': job_id, 'status': 'queued', 'stage': 'queued', 'progress': 0,
                'message': 'Đã xếp lịch xử lý tệp và cập nhật dữ liệu.', 'providers': providers,
                'upload_ids': upload_ids,
                'max_documents': int(max_documents), 'started_at': datetime.now(timezone.utc).isoformat(),
                'log_path': str(job_dir / 'worker.log')}
            _save_json(root / 'data/manifests/update_status.json', state)
        try:
            with (job_dir / 'worker.log').open('ab') as log:
                subprocess.Popen([sys.executable, '-u', '-m', 'scripts.update_data', '--job-id', job_id],
                    cwd=root, stdout=log, stderr=subprocess.STDOUT, close_fds=True,
                    start_new_session=os.name != 'nt',
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        except Exception as exc:
            save_status(job_id, root, status='failed', stage='failed', message='Không khởi động được lượt cập nhật.', error=str(exc))
            raise
        return state
