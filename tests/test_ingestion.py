import csv
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest
from src.ingestion.collector import DocumentCollector
from src.ingestion.manifest import ManifestManager
from src.ingestion.parser import DocumentParser


def catalog(tmp_path, document_id='doc'):
    path=tmp_path/'sources.csv'
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['document_id','title','source_url','jurisdiction','doc_type','language']);w.writeheader();w.writerow({'document_id':document_id,'title':'Official source','source_url':'https://www.nist.gov/test','jurisdiction':'US','doc_type':'guideline','language':'en'})
    return path


def test_reject_legacy_handwritten_txt(tmp_path):
    raw=tmp_path/'raw';raw.mkdir();(raw/'doc.txt').write_text('A fictional legal rule. '*30,encoding='utf-8')
    parser=DocumentParser(str(raw),str(tmp_path/'parsed'),str(tmp_path/'manifest.json'),str(catalog(tmp_path)))
    result=parser.parse_one(raw/'doc.txt')
    assert result['status']=='parse_failed'
    assert not (tmp_path/'parsed/doc.json').exists()


def test_official_download_provenance_and_parser_contract(tmp_path,monkeypatch):
    collector=DocumentCollector(str(tmp_path/'raw'),str(tmp_path/'manifest.json'))
    text=('Official public AI policy original content. '*30).encode()
    monkeypatch.setattr(collector,'download_content',lambda url:(text,'text/plain',url))
    source={'document_id':'doc','title':'Official source','source_url':'https://www.nist.gov/test','jurisdiction':'US','doc_type':'guideline','language':'en'}
    result=collector.collect_one(source)
    assert result['status']=='downloaded'
    parser=DocumentParser(str(tmp_path/'raw'),str(tmp_path/'parsed'),str(tmp_path/'manifest.json'),str(catalog(tmp_path)))
    assert parser.parse_one(Path(result['file_path']))['status']=='parsed'
    record=json.loads((tmp_path/'parsed/doc.json').read_text(encoding='utf-8'))
    assert record['parse_status']=='success'
    assert record['provenance']=='official_download'
    assert len(record['content_hash'])==64
    assert record['version_id']==record['content_hash'][:16]
    assert record['legal_status']=='unknown'


def test_pdf_source_cannot_accept_html_landing_page(tmp_path,monkeypatch):
    collector=DocumentCollector(str(tmp_path/'raw'),str(tmp_path/'manifest.json'))
    monkeypatch.setattr(collector,'download_content',lambda url:(b'<html><title>Official portal</title><main>'+b'Only metadata '*100+b'</main></html>','text/html',url))
    result=collector.collect_one({'document_id':'doc','source_url':'https://www.nist.gov/test','file_format':'pdf'})
    assert result['status']=='download_failed'
    assert not list((tmp_path/'raw').glob('*.html'))


def test_download_error_never_uses_arbitrary_legacy_txt(tmp_path,monkeypatch):
    raw=tmp_path/'raw';raw.mkdir();(raw/'doc.txt').write_text('Pretend law '*50)
    collector=DocumentCollector(str(raw),str(tmp_path/'manifest.json'))
    def fail(url): raise ConnectionError('offline')
    monkeypatch.setattr(collector,'download_content',fail)
    assert collector.collect_one({'document_id':'doc','source_url':'https://www.nist.gov/test'})['status']=='download_failed'


def test_parallel_manifest_updates_are_atomic(tmp_path):
    path=tmp_path/'manifest.json';manifest=ManifestManager(str(path))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda i:manifest.update(str(i),status='downloaded'),range(30)))
    assert len(json.loads(path.read_text(encoding='utf-8')))==30


def test_nfc_unicode_normalization():
    assert DocumentParser.normalize_text('pha\u0301p lua\u0323\u0302t')=='pháp luật'
