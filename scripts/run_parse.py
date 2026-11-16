"""Parse original documents with provenance and explicit scan failures."""
import sys
from pathlib import Path
import argparse
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.ingestion.parser import DocumentParser


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', default='data/raw')
    parser.add_argument('--output', default='data/parsed')
    parser.add_argument('--sources', default='data/sources.csv')
    parser.add_argument('--manifest', default='data/manifests/ingestion_manifest.json')
    args = parser.parse_args()
    results = DocumentParser(args.raw, args.output, args.manifest, args.sources).parse_all()
    if results and not any(r['status']=='parsed' for r in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
