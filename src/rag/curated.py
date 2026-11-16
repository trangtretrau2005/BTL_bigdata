"""Reviewed topic labels are usable only with the exact official article text."""
import hashlib
import json
from pathlib import Path

def lookup_summary(hit, path='data/curated_summaries.json'):
    if hit.get('context_kind') != 'article':
        return None
    try:
        records=json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):
        return None
    digest=hashlib.sha256(hit['text'].encode('utf-8')).hexdigest()
    return next((r for r in records if r['source_document_id']==hit.get('source_document_id')
                 and r['article_text_sha256']==digest),None)
