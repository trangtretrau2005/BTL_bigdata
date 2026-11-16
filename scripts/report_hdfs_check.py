"""Read-only check of directory metadata, real files and HDFS copy content."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import requests
from src.settings import setting


def main():
    root=Path(__file__).resolve().parents[1]
    out=root/'docs/bao_cao/evidence';out.mkdir(parents=True,exist_ok=True)
    base=str(setting('HDFS_WEB_URL')).rstrip('/')+'/webhdfs/v1'
    def get(path,op):
        r=requests.get(base+path,params={'op':op,'user.name':'root'},timeout=30)
        r.raise_for_status();return r
    manifest=json.loads((root/'data/manifests/lake_manifest.json').read_text(encoding='utf-8'))
    parquet=next(f for f in manifest['files'] if '/processed/' in f['path'] and f['path'].endswith('.parquet'))
    pdf=next(f for f in manifest['files'] if f['path']=='/ai_docs/raw/luat_134_2025.pdf')
    samples=[]
    for f in [parquet,pdf]:
        status=get(f['path'],'GETFILESTATUS').json()['FileStatus']
        content=get(f['path'],'OPEN').content
        sha=hashlib.sha256(content).hexdigest()
        assert len(content)==f['bytes']==status['length'] and sha==f['sha256']
        samples.append({'path':f['path'],**{k:status[k] for k in ['type','length','replication','blockSize']},
                        'downloaded_bytes':len(content),'sha256_matches_source':True})
    report={'captured_at':datetime.now(timezone.utc).isoformat(),
        'directory':get('/ai_docs','GETFILESTATUS').json()['FileStatus'],
        'content_summary':get('/ai_docs','GETCONTENTSUMMARY').json()['ContentSummary'],
        'sample_files':samples}
    (out/'hdfs_file_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
