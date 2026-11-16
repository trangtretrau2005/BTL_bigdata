"""Run the verified corpus pipeline, including ingestion and HDFS."""
import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--step', choices=['collect','parse','etl','chunk','index','lake','all'], default='all')
    p.add_argument('--sources', default='data/sources.csv')
    p.add_argument('--raw', default='data/verified_raw')
    p.add_argument('--parsed', default='data/verified_parsed')
    p.add_argument('--processed', default='data/processed')
    p.add_argument('--chunks', default='data/chunks')
    p.add_argument('--master', default='local[2]')
    p.add_argument('--skip-collect', action='store_true')
    p.add_argument('--skip-lake', action='store_true')
    p.add_argument('--rebuild', action='store_true')
    a = p.parse_args()
    steps = ['collect','parse','etl','chunk','index','lake'] if a.step == 'all' else [a.step]
    report = {'started_at': time.time(), 'steps': {}}
    manifest = 'data/manifests/verified_ingestion_manifest.json'
    for step in steps:
        if (step == 'collect' and a.skip_collect) or (step == 'lake' and a.skip_lake):
            continue
        start = time.monotonic()
        print(f'\n=== {step.upper()} ===', flush=True)
        if step == 'collect':
            from src.ingestion.collector import DocumentCollector
            result = DocumentCollector(a.raw, manifest_path=manifest).collect_from_csv(a.sources)
        elif step == 'parse':
            from src.ingestion.parser import DocumentParser
            result = DocumentParser(a.raw, a.parsed, manifest_path=manifest, sources_csv=a.sources).parse_all()
        elif step == 'etl':
            from src.processing.spark_etl import run
            result = run(a.parsed, a.processed, a.master)
        elif step == 'chunk':
            from src.processing.chunker import run
            result = run(a.processed, a.chunks)
        elif step == 'index':
            from src.rag.indexer import run
            from src.settings import setting
            result = run(a.chunks, batch_size=int(setting('EMBED_BATCH_SIZE', 8)), rebuild=a.rebuild)
        else:
            from scripts.sync_lake import sync_lake
            result = sync_lake(a.raw, a.parsed, a.processed, a.chunks)
        report['steps'][step] = {'elapsed_seconds': round(time.monotonic()-start,2), 'result': result}
        target = Path('data/manifests/pipeline_run.json')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print('Pipeline completed.', flush=True)


if __name__ == "__main__":
    main()
