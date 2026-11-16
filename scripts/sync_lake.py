"""Mirror pipeline artifacts into HDFS through WebHDFS; fail on transfer errors."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import requests
from src.settings import setting

def sync_lake(raw='data/verified_raw', parsed='data/verified_parsed', processed='data/processed', chunks='data/chunks', dataset_version=None):
    base = str(setting('HDFS_WEB_URL', 'http://localhost:9870')).rstrip('/')
    root = str(setting('HDFS_BASE_PATH', '/ai_docs')).rstrip('/')
    session = requests.Session()
    files = []
    zones = [('raw', raw), ('parsed', parsed),
             ('processed/' + dataset_version if dataset_version else 'processed', processed),
             ('chunks/' + dataset_version if dataset_version else 'chunks', chunks), ('manifests','data/manifests')]
    zones += [(zone, directory) for zone, directory in [('raw/api', 'data/dynamic/raw'), ('parsed/api', 'data/dynamic/parsed')] if Path(directory).exists()]
    zones += [(zone, directory) for zone, directory in [('raw/uploads', 'data/uploads/raw'), ('parsed/uploads', 'data/uploads/parsed')] if Path(directory).exists()]
    if Path('data/uploads/catalog.json').exists():
        # The upload catalog is copied with the manifests, not mixed with legal text.
        Path('data/manifests/upload_catalog.json').write_bytes(Path('data/uploads/catalog.json').read_bytes())
    for zone, directory in zones:
        source = Path(directory)
        if not source.exists():
            raise FileNotFoundError(source)
        response = session.put(f'{base}/webhdfs/v1{root}/{zone}', params={'op':'MKDIRS','user.name':'root'}, timeout=30)
        response.raise_for_status()
        for path in sorted(source.rglob('*')):
            if not path.is_file() or path.name.startswith('.') or path.name.endswith(('.crc','.tmp','.lock')) or path.name in {'lake_manifest.json', 'update_status.json'}:
                continue
            target = f'{root}/{zone}/{path.relative_to(source).as_posix()}'
            parent = target.rsplit('/', 1)[0]
            session.put(f'{base}/webhdfs/v1{quote(parent)}', params={'op':'MKDIRS','user.name':'root'},timeout=30).raise_for_status()
            response = session.put(f'{base}/webhdfs/v1{quote(target)}', params={'op':'CREATE','overwrite':'true','user.name':'root'}, allow_redirects=False,timeout=30)
            response.raise_for_status()
            if response.status_code != 307:
                raise RuntimeError(f'Expected WebHDFS redirect, received {response.status_code}')
            content = path.read_bytes()
            upload = session.put(response.headers['Location'], data=content, headers={'Content-Type':'application/octet-stream'},timeout=120)
            upload.raise_for_status()
            check=session.get(f'{base}/webhdfs/v1{quote(target)}',params={'op':'GETFILESTATUS','user.name':'root'},timeout=30)
            check.raise_for_status()
            if check.json()['FileStatus']['length'] != len(content):
                raise RuntimeError(f'HDFS length mismatch: {target}')
            files.append({'path':target,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
    report={'updated_at':datetime.now(timezone.utc).isoformat(),'file_count':len(files),'total_bytes':sum(f['bytes'] for f in files),'files':files,'status':'synced'}
    output=Path('data/manifests/lake_manifest.json'); output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'HDFS sync verified: {len(files)} files, {report["total_bytes"]} bytes')
    return report

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--raw',default='data/verified_raw'); p.add_argument('--parsed',default='data/verified_parsed')
    p.add_argument('--processed',default='data/processed'); p.add_argument('--chunks',default='data/chunks')
    args=p.parse_args(); sync_lake(**vars(args))
