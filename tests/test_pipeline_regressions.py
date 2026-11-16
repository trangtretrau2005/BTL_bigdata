import csv
from pathlib import Path
from src.processing.chunker import chunk_document
from src.ingestion.parser import DocumentParser

def test_chunk_continuation_keeps_page_and_version():
    doc = {'document_id':'d', 'version_id':'v2', 'text':'[Trang 3]\nArticle 1\n' + 'Policy content. ' * 80,
           'language':'en', 'legal_status':'unknown', 'source_url':'https://www.nist.gov/example'}
    chunks = list(chunk_document(doc, size=180, overlap=30))
    assert len(chunks) > 3
    assert all(c['page_start'] == 3 and c['page_end'] == 3 for c in chunks)
    assert all(c['version_id'] == 'v2' and c['language'] == 'en' for c in chunks)

def test_signature_with_more_than_200_chars_is_not_legal_content():
    text = 'Cơ quan phát hành: VĂN PHÒNG CHÍNH PHỦ\nNgười ký: CỤC THÔNG TIN VÀ TRUYỀN THÔNG CHÍNH PHỦ\nEmail: thongtinchinhphu@chinhphu.vn\nCơ quan: VĂN PHÒNG CHÍNH PHỦ\nThời gian ký: 03.09.2026 12:07:13 +07:00'
    assert len(text) > 190
    assert DocumentParser.is_only_digital_signature(text)

def test_html_full_text_inside_aspnet_form_is_preserved(tmp_path):
    html=tmp_path/'original.html'
    html.write_text('<html><body><form><input value="search"><main>Article 1. AI policy text.</main></form></body></html>',encoding='utf-8')
    parser=DocumentParser(str(tmp_path),str(tmp_path/'parsed'),str(tmp_path/'manifest.json'),str(tmp_path/'sources.csv'))
    assert 'Article 1. AI policy text.' in parser.parse_html(html)

def test_evaluation_service_error_is_not_a_successful_refusal(tmp_path, monkeypatch):
    from evaluation.eval_runner import run_evaluation
    import src.rag.retriever as retriever
    def offline(*args, **kwargs):
        raise ConnectionError('service offline')
    monkeypatch.setattr(retriever, 'retrieve', offline)
    path = tmp_path/'eval.csv'
    with path.open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=['question_id','question','expected_document_id','has_answer'])
        writer.writeheader()
        writer.writerow({'question_id':'o1','question':'Unrelated question','expected_document_id':'','has_answer':'false'})
    result = run_evaluation(str(path), str(tmp_path/'result.json'))
    assert result['out_of_scope_refused'] == 0
    assert result['error_count'] == 1
    assert result['citation_validity_percent'] is None
