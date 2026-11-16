"""Collect original public documents from the source catalog."""
import argparse
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.ingestion.collector import DocumentCollector


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', default='data/sources.csv')
    parser.add_argument('--output', default='data/raw')
    parser.add_argument('--manifest', default='data/manifests/ingestion_manifest.json')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    results = DocumentCollector(args.output, args.manifest).collect_from_csv(args.sources, refresh=args.refresh, limit=args.limit)
    if results and not any(r['status'] in {'downloaded','downloaded_cached'} for r in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
