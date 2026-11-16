"""Download original official AI documents; no embedded or generated legal text.

Defaults to staging directories so a failed source cannot replace a working corpus.
Run: python -m scripts.fetch_ai_corpus
"""
from __future__ import annotations
import argparse
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.collector import DocumentCollector
from src.ingestion.parser import DocumentParser


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sources', default='data/sources.csv')
    p.add_argument('--raw', default='data/verified_raw')
    p.add_argument('--parsed', default='data/verified_parsed')
    p.add_argument('--manifest', default='data/manifests/verified_ingestion_manifest.json')
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--timeout', type=int, default=20)
    p.add_argument('--limit', type=int)
    p.add_argument('--refresh', action='store_true')
    args = p.parse_args()
    if not 1 <= args.workers <= 8:
        p.error('--workers must be between 1 and 8')
    with open(args.sources, encoding='utf-8-sig', newline='') as stream:
        documents = [dict(row) for row in csv.DictReader(stream) if row.get('document_id') and row.get('enabled', 'true').lower() != 'false']
    if args.limit:
        documents = documents[:args.limit]
    ids = [d['document_id'] for d in documents]
    if len(ids) != len(set(ids)):
        p.error('document_id must be unique')
    collector = DocumentCollector(args.raw, args.manifest, timeout=args.timeout)
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(collector.collect_one, document, refresh=args.refresh): document['document_id'] for document in documents}
        for task in as_completed(pending):
            result = task.result()
            results.append(result)
            print(f"{result['document_id']}: {result['status']}", flush=True)
    parser = DocumentParser(args.raw, args.parsed, args.manifest, args.sources)
    parsed = []
    # Parse exactly the validated files returned by this collection run, not stale siblings.
    for result in sorted(results, key=lambda r: r['document_id']):
        if result['status'] in {'downloaded', 'downloaded_cached'}:
            parsed.append(parser.parse_one(Path(result['file_path'])))
    summary = {'catalog_documents': len(documents), 'downloaded': sum(r['status'] in {'downloaded','downloaded_cached'} for r in results), 'parsed': sum(r['status'] == 'parsed' for r in parsed), 'download_failures': [r for r in results if r['status'] == 'download_failed'], 'parse_failures': [r for r in parsed if r['status'] != 'parsed'], 'raw_path': args.raw, 'parsed_path': args.parsed, 'manifest_path': args.manifest}
    report = Path(args.manifest).with_name('verified_collection_report.json')
    report.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if not k.endswith('failures')}, ensure_ascii=False, indent=2), flush=True)
    if not summary['parsed']:
        raise SystemExit('No official documents parsed; existing corpus was not replaced.')


if __name__ == '__main__':
    main()
