import hashlib,json
from src.rag.curated import lookup_summary

def test_curated_labels_require_exact_article_version(tmp_path):
    text='Article 5 official source text'
    file=tmp_path/'summaries.json'
    file.write_text(json.dumps([{'source_document_id':'eu','article_text_sha256':hashlib.sha256(text.encode()).hexdigest(),'topics':{'a':'Topic'}}]),encoding='utf-8')
    hit={'text':text,'source_document_id':'eu','context_kind':'article'}
    assert lookup_summary(hit,file)['topics']=={'a':'Topic'}
    assert lookup_summary({**hit,'text':text+' updated'},file) is None
    assert lookup_summary({**hit,'context_kind':'chunk'},file) is None
