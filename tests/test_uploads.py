import hashlib
import io
import json
from pathlib import Path
import pytest
from src.catalog import load_inventory, read_json
from src.ingestion.uploads import save_uploads, parse_uploads, uploaded_file, finalize_uploads
from src.rag.answerer import _citation, build_prompt
from src.updates import service
from scripts import update_data

TEXT = ('Quy tắc thử nghiệm quản trị trí tuệ nhân tạo. Dữ liệu và mô hình cần được kiểm tra, '
        'giám sát và ghi nhận nguồn thông tin. Đây là nội dung dùng trong kiểm thử phần mềm.\n') * 5


def item(content=None, name='Chính sách AI.txt'):
    return {'name': name, 'content': content if content is not None else TEXT.encode('utf-8'), 'region': 'VN', 'language': 'vi'}


def test_upload_txt_is_explicitly_user_supplied_and_idempotent(tmp_path):
    first=save_uploads([item()], tmp_path)
    assert save_uploads([item(name='renamed.txt')],tmp_path)==first
    path,metadata=uploaded_file(first[0],tmp_path)
    assert path.read_bytes()==TEXT.encode('utf-8') and metadata['original_filename']=='Chính sách AI.txt'
    report=parse_uploads(tmp_path)
    assert report['parsed']==1 and report['failed']==0
    record=read_json(tmp_path/'data/uploads/parsed'/f'{first[0]}.json')
    assert record['provenance']=='user_upload' and record['source_url']=='upload://'+first[0]
    assert record['original_filename']=='Chính sách AI.txt' and record['legal_status']=='unknown'
    assert parse_uploads(tmp_path)['parsed']==0
    signature,count=update_data.prepare_inputs(tmp_path,tmp_path/'input')
    assert count==1
    assert update_data.prepare_inputs(tmp_path,tmp_path/'again')[0]==signature


@pytest.mark.parametrize('name,content', [('fake.pdf',b'not a pdf'), ('a.exe',b'payload'), ('empty.txt',b'')])
def test_invalid_upload_batch_never_partially_saves_files(tmp_path,name,content):
    with pytest.raises(ValueError):save_uploads([item(),item(content,name)],tmp_path)
    assert not list((tmp_path/'data/uploads/raw').glob('*'))


def test_filename_cannot_escape_upload_storage(tmp_path):
    ids=save_uploads([item(name='../../outside.txt')],tmp_path)
    path,row=uploaded_file(ids[0],tmp_path)
    assert path.is_relative_to((tmp_path/'data/uploads/raw').resolve())
    assert row['original_filename']=='outside.txt'
    assert uploaded_file('../../outside',tmp_path) is None


def test_changed_or_unreadable_uploads_do_not_enter_processed_input(tmp_path):
    ids=save_uploads([item()],tmp_path)
    path,_=uploaded_file(ids[0],tmp_path);path.write_bytes(b'changed content '*30)
    report=parse_uploads(tmp_path)
    assert report['failed']==1 and report['parsed']==0
    assert 'thay đổi' in report['errors'][0]['error']
    assert not list((tmp_path/'data/uploads/parsed').glob('*.json'))
    assert save_uploads([item()],tmp_path)==ids
    assert parse_uploads(tmp_path)['parsed']==1


def test_pdf_and_docx_extract_original_text(tmp_path):
    import fitz
    import docx
    pdf=fitz.open();page=pdf.new_page();page.insert_textbox(fitz.Rect(40,40,550,800), 'AI governance requires transparent data and human oversight. '*12)
    pdf_bytes=pdf.tobytes();pdf.close()
    word=docx.Document();word.add_paragraph(TEXT);out=io.BytesIO();word.save(out)
    ids=save_uploads([item(pdf_bytes,'AI policy.pdf'),item(out.getvalue(),'Chính sách.docx')],tmp_path)
    report=parse_uploads(tmp_path)
    assert report['parsed']==2 and not report['errors']
    assert '[Trang 1]' in read_json(tmp_path/'data/uploads/parsed'/f'{ids[0]}.json')['text']
    assert 'giám sát' in read_json(tmp_path/'data/uploads/parsed'/f'{ids[1]}.json')['text']


def test_duplicate_text_maps_to_existing_document_instead_of_pending_count(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    doc_id=save_uploads([item()],tmp_path)[0];parse_uploads(tmp_path)
    record=read_json(tmp_path/'data/uploads/parsed'/f'{doc_id}.json')
    processed=tmp_path/'data/processed';processed.mkdir()
    pq.write_table(pa.Table.from_pylist([{'source_document_id':'existing',
        'text_sha256':hashlib.sha256(record['text'].encode()).hexdigest()}]),processed/'part.parquet')
    manifest={'status':'ready','processed_path':'data/processed','source_document_ids':['existing'],'total_chunks':2}
    finalize_uploads(tmp_path,manifest)
    assert read_json(tmp_path/'data/uploads/catalog.json')[doc_id]['duplicate_of']=='existing'
    (tmp_path/'data/manifests/index_manifest.json').write_text(json.dumps(manifest))
    assert load_inventory(tmp_path)[2]=={'active':1,'catalog':1,'pending':0,'chunks':2}


def test_upload_only_can_start_without_any_api_source(tmp_path,monkeypatch):
    launched=[]
    monkeypatch.setattr(service.subprocess,'Popen',lambda *a,**k:launched.append((a,k)))
    state=service.start_update(providers=[],uploads=[item()],root=tmp_path)
    assert state['providers']==[] and len(state['upload_ids'])==1 and len(launched)==1
    assert uploaded_file(state['upload_ids'][0],tmp_path)
    with pytest.raises(service.UpdateBusy):service.start_update(providers=[],uploads=[item()],root=tmp_path)


@pytest.mark.parametrize('already_parsed', [False, True])
def test_uploads_keep_working_if_api_is_unavailable(tmp_path,monkeypatch,already_parsed):
    monkeypatch.setattr(service.subprocess,'Popen',lambda *a,**k:None)
    (tmp_path/'data').mkdir()
    (tmp_path/'data/api_sources.json').write_text(json.dumps({'vbpl':{'enabled':True}}))
    state=service.start_update(uploads=[item()],root=tmp_path)
    if already_parsed:
        assert parse_uploads(tmp_path)['parsed']==1
        service.save_status(state['job_id'],tmp_path,upload_ids=[])
    def offline(*a,**k):raise RuntimeError('API offline')
    monkeypatch.setattr(update_data.DynamicIngestor,'run',offline)
    # Stop at the indexing boundary; uploads must already have been parsed/staged.
    def pipeline(job,root,signature,inputs):
        assert len(list(inputs.glob('*.json')))==1
        assert read_json(next(inputs.glob('*.json')))['provenance']=='user_upload'
        raise RuntimeError('Reached indexing')
    monkeypatch.setattr(update_data,'execute_pipeline',pipeline)
    with pytest.raises(RuntimeError,match='Reached indexing'):update_data.run_update(state['job_id'],tmp_path)
    assert read_json(tmp_path/'data/manifests/update_status.json')['upload_report']['parsed']==(0 if already_parsed else 1)


def test_upload_citation_and_prompt_preserve_provenance():
    hit={'title':'AI policy', 'text':TEXT, 'source_document_id':'upload_x',
         'original_filename':'AI policy.pdf', 'source_url':'upload://upload_x', 'provenance':'user_upload'}
    citation=_citation(hit,'S1')
    assert citation['original_filename']=='AI policy.pdf' and citation['provenance']=='user_upload'
    assert 'chưa xác minh nguồn chính thức' in build_prompt('Quy định AI?', [hit])
