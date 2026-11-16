"""Expand vector anchors to an exact article for explicit legal-heading questions."""
from functools import lru_cache
from pathlib import Path
import re
import unicodedata
from src.processing.chunker import SECTION_RE
from src.catalog import read_json

def folded(text):
    text = text.lower().replace('đ','d')
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD',text) if not unicodedata.combining(c)).split())

HEADERS = re.compile(r'(?mi)^[ \t]*((?:Article|Điều)\s+\d+[A-Za-z0-9.]*)(?:[ \t]*\n|[ \t]+)')

@lru_cache(maxsize=1)
def _documents(signature):
    import pyarrow.dataset as ds
    return ds.dataset(signature[0],format='parquet').to_table().to_pylist()

def focus_article(question, hits):
    query = folded(question)
    if 'pham vi dieu chinh' in query:
        headings = ('pham vi dieu chinh',)
    elif re.search(r'(?<!\w)cam(?!\w)',query) or 'prohibited' in query:
        headings = ('prohibited artificial intelligence practices','prohibited ai practices','hanh vi bi nghiem cam','cac hanh vi bi cam')
    else:
        return hits
    processed = read_json('data/manifests/index_manifest.json').get('processed_path', 'data/processed')
    files = list(Path(processed).glob('*.parquet'))
    if not files:
        return hits
    documents = _documents((processed, tuple((p.name,p.stat().st_mtime_ns) for p in sorted(files))))
    for hit in hits:
        document = next((d for d in documents if d.get('document_id') == hit.get('document_id')),None)
        if not document:
            continue
        text = document['text']
        sections = list(HEADERS.finditer(text))
        for index, match in enumerate(sections):
            end = sections[index+1].start() if index+1 < len(sections) else len(text)
            if not any(h in folded(text[match.end():min(match.end()+180,end)]) for h in headings):
                continue
            article = text[match.start():end].strip()
            if len(article) > 24000:
                continue
            pages = [(m.start(),int(m.group(1))) for m in re.finditer(r'\[Trang\s+(\d+)\]',text)]
            first = next((number for pos,number in reversed(pages) if pos <= match.start()),None)
            last = next((number for pos,number in reversed(pages) if pos < end),first)
            section = next((m.group(1).strip() for m in reversed(list(SECTION_RE.finditer(text))) if m.start() <= match.start()),None)
            return [{**hit, 'text':article, 'article':match.group(1), 'page_start':first,'page_end':last,
                     'section':section,
                     'context_kind':'article', 'retrieval_mode':'vector+article',
                     'anchor_chunk_id':hit['chunk_id'], 'context_char_start':match.start(), 'context_char_end':end}]
    return hits
