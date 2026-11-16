import pytest
from src.rag import article_context

@pytest.fixture
def document(monkeypatch,tmp_path):
    path=tmp_path/'part.parquet';path.write_bytes(b'placeholder')
    monkeypatch.setattr(article_context.Path,'glob',lambda self,pattern:[path])
    text='Điều 1. Phạm vi điều chỉnh\nHoạt động AI tại Việt Nam. Quốc phòng không thuộc phạm vi.\nĐiều 2. Đối tượng áp dụng\nOther rules.'
    monkeypatch.setattr(article_context,'_documents',lambda signature:[{'document_id':'d','text':text}])
    return {'document_id':'d','chunk_id':'real-anchor','text':'Other retrieved text','score':.8}

def test_scope_is_exact_article_not_nearby_rules(document):
    result=article_context.focus_article('Phạm vi điều chỉnh của Luật AI là gì?',[document])
    assert len(result)==1 and result[0]['context_kind']=='article'
    assert 'không thuộc phạm vi' in result[0]['text']
    assert 'Other rules' not in result[0]['text']
    assert result[0]['anchor_chunk_id']=='real-anchor'

def test_other_questions_keep_vector_results(document):
    assert article_context.focus_article('AI quản trị rủi ro thế nào?',[document])==[document]


def test_article_expansion_follows_published_dataset_version(tmp_path, monkeypatch):
    import json
    import pyarrow as pa
    import pyarrow.parquet as pq
    monkeypatch.chdir(tmp_path)
    (tmp_path/'data/manifests').mkdir(parents=True)
    for version, text in [('old', 'Nội dung cũ.'), ('new', 'Nội dung API mới.')]:
        folder=tmp_path/'data/updates'/version/'processed';folder.mkdir(parents=True)
        pq.write_table(pa.Table.from_pylist([{'document_id':'d', 'text':
            'Điều 1. Phạm vi điều chỉnh\n'+text+'\nĐiều 2. Đối tượng áp dụng\nOther rules.'}]),folder/'part.parquet')
    manifest=tmp_path/'data/manifests/index_manifest.json'
    hit={'document_id':'d','chunk_id':'anchor','text':'vector anchor'}
    article_context._documents.cache_clear()
    try:
        for version, expected in [('new','Nội dung API mới.'), ('old','Nội dung cũ.')]:
            manifest.write_text(json.dumps({'processed_path':f'data/updates/{version}/processed'}))
            result=article_context.focus_article('Phạm vi điều chỉnh là gì?',[hit])
            assert expected in result[0]['text']
            assert result[0]['anchor_chunk_id']=='anchor' and 'Other rules' not in result[0]['text']
    finally:
        article_context._documents.cache_clear()
