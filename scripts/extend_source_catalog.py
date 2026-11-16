"""Idempotently merge reviewed official source metadata, without inventing document text."""
import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlparse


def extend(catalog: Path, additions: Path) -> int:
    with catalog.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    known = {row['document_id'] for row in rows}
    specs = json.loads(additions.read_text(encoding='utf-8'))
    appended = []
    for spec in specs:
        if spec['document_id'] in known:
            continue
        if urlparse(spec['source_url']).scheme != 'https':
            raise ValueError('Official source URLs must use HTTPS')
        row = {key: '' for key in fields}
        row.update(language='en', doc_type='guideline', status='unknown', enabled='true',
            jurisdiction='International', file_format='html', license='See original publication',
            notes='Official source snapshot; legal status is not inferred. Full text must pass download and parsing checks.')
        row.update(spec)
        if set(row) - set(fields):
            raise ValueError('Unknown metadata fields')
        appended.append(row)
        known.add(spec['document_id'])
    temporary = catalog.with_suffix('.csv.tmp')
    with temporary.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows + appended)
    temporary.replace(catalog)
    return len(appended)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=Path('data/sources.csv'))
    parser.add_argument('--additions', type=Path, default=Path('data/additional_sources.json'))
    args = parser.parse_args()
    print(f'Added {extend(args.catalog, args.additions)} official source entries.')
