"""Read-only inventory and live-service evidence for chapters 2 and 3."""
from __future__ import annotations
import json
import csv
import platform
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.catalog import load_inventory, read_json
from src.rag.common import collection_name, qdrant_client, setting

OUT = ROOT / 'docs/bao_cao/evidence'


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def main():
    import pyarrow.dataset as ds
    import pyarrow.parquet as pq
    import requests
    rows, manifest, counts = load_inventory(ROOT)
    documents = ds.dataset(str(ROOT/manifest['processed_path']), format='parquet').to_table().to_pylist()
    chunks = [json.loads(line) for line in (ROOT/manifest['chunks_path']).read_text(encoding='utf-8').splitlines() if line.strip()]
    client = qdrant_client()
    info = client.get_collection(collection_name())
    actual = client.count(collection_name=collection_name(), exact=True).count
    assert actual == len(chunks) == counts['chunks']
    assert {d['source_document_id'] for d in documents} == set(manifest['source_document_ids'])
    active = [r for r in rows if r['document_id'] in manifest['source_document_ids']]
    lengths = sorted(len(c['text']) for c in chunks)
    quality = {
        'documents': len(documents), 'chunks': len(chunks),
        'unique_document_text_hashes': len({d['text_sha256'] for d in documents}),
        'missing_document_source': sum(not d.get('source_url') for d in documents),
        'missing_chunk_source': sum(not c.get('source_url') for c in chunks),
        'missing_chunk_version': sum(not c.get('version_id') for c in chunks),
        'duplicate_chunk_ids': len(chunks)-len({c['chunk_id'] for c in chunks}),
        'chunk_characters_min': min(lengths), 'chunk_characters_median': statistics.median(lengths),
        'chunk_characters_p95': lengths[int(.95*(len(lengths)-1))], 'chunk_characters_max': max(lengths),
        'document_characters': sum(len(d['text']) for d in documents),
        'regions': dict(Counter(d['region'] for d in documents)),
        'languages': dict(Counter(d.get('language') or 'unknown' for d in documents)),
        'types': dict(Counter(d.get('document_type') or 'unknown' for d in documents)),
        'provenance_documents': dict(Counter(d.get('provenance') for d in documents)),
        'provenance_chunks': dict(Counter(c.get('provenance') for c in chunks)),
    }
    packages = {name: version(name) for name in ['pyspark','pyarrow','streamlit','qdrant-client','requests','pytest','pymupdf','python-docx','edge-tts']}
    config = {name: setting(name, fallback) for name, fallback in [
        ('CHAT_MODEL',''),('EMBEDDING_MODEL',''),('CHUNK_SIZE',2200),('CHUNK_OVERLAP',240),
        ('TOP_K',5),('MIN_SCORE',.42),('EMBED_BATCH_SIZE',8),('REQUEST_TIMEOUT',300)]}
    model_base = str(setting('OLLAMA_BASE_URL')).rstrip('/')
    models = requests.get(model_base+'/api/tags', timeout=10).json()
    model_runtime = requests.get(model_base+'/api/ps', timeout=10).json()
    hdfs = str(setting('HDFS_WEB_URL')).rstrip('/')
    hdfs_root = str(setting('HDFS_BASE_PATH'))
    content = requests.get(hdfs+'/webhdfs/v1'+hdfs_root, params={'op':'GETCONTENTSUMMARY','user.name':'root'}, timeout=15)
    content.raise_for_status()
    parquet_files = []
    for p in sorted((ROOT/manifest['processed_path']).glob('*.parquet')):
        meta = pq.ParquetFile(p).metadata
        parquet_files.append({'file':p.name, 'bytes':p.stat().st_size, 'rows':meta.num_rows,
            'row_groups':meta.num_row_groups,'compression':meta.row_group(0).column(0).compression if meta.num_rows else None})
    facts = {'captured_at':datetime.now(timezone.utc).isoformat(), 'python':platform.python_version(),
        'os_container':platform.platform(),'packages':packages,'parameters':config,'counts':counts,
        'index':manifest,'qdrant':{'point_count':actual,'status':str(info.status),'vector_size':info.config.params.vectors.size,
            'distance':str(info.config.params.vectors.distance),'aliases':[a.model_dump() for a in client.get_aliases().aliases]},
        'quality':quality,'parquet':parquet_files,'parquet_schema':str(ds.dataset(str(ROOT/manifest['processed_path']),format='parquet').schema),
        'ollama_models':models,'ollama_runtime':model_runtime,'hdfs_entire_namespace':content.json(),
        'latest_sync':read_json(ROOT/'data/manifests/lake_manifest.json'),
        'api_config':read_json(ROOT/'data/api_sources.json'),
        'api_checkpoint':read_json(ROOT/'data/manifests/dynamic_ingestion_manifest.json').get('providers'),
        'latest_update':read_json(ROOT/'data/manifests/update_status.json')}
    save('system_facts.json',facts)
    chunk_counts=Counter(c.get('source_document_id') for c in chunks)
    doc_stats=[{k:d.get(k) for k in ['source_document_id','title','region','language','document_type','provenance','published_date','legal_status']} |
        {'characters':len(d['text']),'chunks':chunk_counts[d['source_document_id']]} for d in documents]
    with (OUT/'document_statistics.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(doc_stats[0]));w.writeheader();w.writerows(doc_stats)
    chunk_stats=[{'chunk_id':c['chunk_id'],'source_document_id':c.get('source_document_id'),'characters':len(c['text']),
                  'has_page':c.get('page_start') is not None,'has_article':bool(c.get('article'))} for c in chunks]
    with (OUT/'chunk_statistics.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(chunk_stats[0]));w.writeheader();w.writerows(chunk_stats)
    save('active_documents.json',active)
    save('previous_api_verification.json',read_json(ROOT/'evaluation/dynamic_api_live_check.json'))
    save('upload_verification.json',read_json(ROOT/'evaluation/upload_live_check.json'))
    for name in ['index_manifest.json','etl_report.json','chunk_manifest.json']:
        save(name,read_json(ROOT/'data/manifests'/name))
    print(json.dumps({'counts':counts,'quality':quality,'packages':packages}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
