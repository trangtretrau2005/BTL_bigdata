import csv
import json
from datetime import datetime, timezone
from pathlib import Path
import uuid
from types import SimpleNamespace
import pytest
from src.catalog import load_inventory
from src.ingestion.dynamic_api import DynamicIngestor, document_number
import requests
from src.rag import indexer
from src.updates import service
from scripts import update_data

TODAY = datetime.now(timezone.utc).date().isoformat()
TEXT = 'Điều 1. Quản trị trí tuệ nhân tạo. Hệ thống cần minh bạch và có giám sát của con người. ' * 5


def seed(root):
    (root / 'data/manifests').mkdir(parents=True)
    (root / 'data').mkdir(exist_ok=True)
    config = json.loads(Path('data/api_sources.json').read_text(encoding='utf-8'))
    (root / 'data/api_sources.json').write_text(json.dumps(config), encoding='utf-8')
    with (root / 'data/sources.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['document_id','title','source_org','source_url'])
        writer.writeheader()
        writer.writerow({'document_id':'existing_law','title':'Luật 134/2025/QH15 — Trí tuệ nhân tạo','source_org':'Quốc hội','source_url':'https://congbao.chinhphu.vn/example'})
    (root / 'data/manifests/index_manifest.json').write_text(json.dumps({'status':'ready','source_document_ids':['existing_law'],'total_chunks':5}),encoding='utf-8')


class FakeResponse:
    def __init__(self, payload=None, text=''):
        self.payload, self.text = payload, text
    def json(self): return self.payload
    def raise_for_status(self): pass


class FakeAPI:
    def __init__(self, empty=False): self.calls=[]; self.empty=empty
    def request(self, method, url, **kwargs):
        self.calls.append((method,url,kwargs))
        assert not url.endswith('.pdf')
        if url.endswith('/all'):
            assert method == 'POST'
            assert kwargs['json']['sortBy'] == 'issueDate' and kwargs['json']['sortDirection'] == 'DESC'
            return FakeResponse({'success':True,'data':{'total':1,'items':[{'id':'api-1','title':'Luật Trí tuệ nhân tạo 134/2025/QH15','issueDate':TODAY,'document_url':'https://vbpl.vn/van-ban/chi-tiet/api-1','agencyName':'Quốc hội'}]}})
        return FakeResponse({'success':True,'data':{'id':'api-1','title':'Luật Trí tuệ nhân tạo 134/2025/QH15','agencyName':'Quốc hội','issueDate':TODAY,'docType':{'name':'Luật'},'documentContent':{'content':'' if self.empty else '<body><p>'+TEXT+'</p></body>'}}})


def test_api_full_text_is_json_and_repeated_ingestion_is_idempotent(tmp_path):
    seed(tmp_path); api=FakeAPI()
    first=DynamicIngestor(tmp_path,api).run(['vbpl'],10)
    assert first['changed']==1
    record=json.loads((tmp_path/'data/dynamic/parsed/existing_law.json').read_text(encoding='utf-8'))
    assert record['provenance']=='official_api' and TEXT.strip() in record['text']
    assert record['raw_path'].endswith('.json') and Path(record['raw_path']).is_file()
    assert record['api_url'].startswith('https://vbpl-bientap-gateway.moj.gov.vn/')
    detail_calls=sum(not url.endswith('/all') for _,url,_ in api.calls)
    second=DynamicIngestor(tmp_path,api).run(['vbpl'],10)
    assert second['changed']==0 and second['providers']['vbpl']['unchanged']==1
    assert sum(not url.endswith('/all') for _,url,_ in api.calls)==detail_calls
    rows,manifest,counts=load_inventory(tmp_path)
    assert counts=={'active':1,'catalog':1,'pending':0,'chunks':5}
    assert rows[0]['source_url'].startswith('https://vbpl.vn/')


def test_empty_api_body_never_becomes_indexed_full_text(tmp_path):
    seed(tmp_path)
    report=DynamicIngestor(tmp_path,FakeAPI(empty=True)).run(['vbpl'],10)
    assert report['changed']==0 and report['providers']['vbpl']['failed']==1
    assert not list((tmp_path/'data/dynamic/parsed').glob('*.json'))
    state=json.loads((tmp_path/'data/manifests/dynamic_ingestion_manifest.json').read_text())
    assert 'vbpl' not in state['providers']
    assert load_inventory(tmp_path)[2]['active']==1


def test_http_200_request_access_page_is_not_legal_full_text(tmp_path):
    seed(tmp_path)
    class Blocked(FakeAPI):
        def request(self, method, url, **kwargs):
            response = super().request(method, url, **kwargs)
            if not url.endswith('/all'):
                response.payload['data']['documentContent']['content'] = (
                    '<html><title>Federal Register :: Request Access</title><body>'
                    + 'Programmatic access is limited. ' * 20 + '</body></html>')
            return response
    report = DynamicIngestor(tmp_path, Blocked()).run(['vbpl'], 10)
    assert report['changed'] == 0 and report['providers']['vbpl']['failed'] == 1
    assert not list((tmp_path/'data/dynamic/parsed').glob('*.json'))


def test_multiple_remote_ids_for_same_act_count_as_one_changed_document(tmp_path):
    seed(tmp_path)
    class Duplicate(FakeAPI):
        def request(self, method, url, **kwargs):
            response=super().request(method,url,**kwargs)
            if url.endswith('/all'):
                first=response.payload['data']['items'][0]
                response.payload['data'].update(total=2,items=[first, {**first,'id':'api-2',
                    'document_url':'https://vbpl.vn/van-ban/chi-tiet/api-2'}])
            elif url.endswith('/api-2'):
                response.payload['data']['id']='api-2'
                response.payload['data']['title']=response.payload['data']['title'].upper()
            return response
    report=DynamicIngestor(tmp_path,Duplicate()).run(['vbpl'],10)
    assert report['changed']==1 and report['providers']['vbpl']['changed']==1
    assert report['changed_document_ids']==['existing_law']
    assert len(list((tmp_path/'data/dynamic/parsed').glob('*.json')))==1


def test_later_catalog_page_failure_keeps_valid_earlier_candidates(tmp_path):
    seed(tmp_path)
    class Partial(FakeAPI):
        def request(self, method, url, **kwargs):
            if url.endswith('/all') and kwargs['json']['pageNumber'] == 2:
                raise requests.HTTPError('500 Server Error')
            response = super().request(method, url, **kwargs)
            if url.endswith('/all'):
                response.payload['data']['total'] = 100
            return response
    report = DynamicIngestor(tmp_path, Partial()).run(['vbpl'], 10)
    assert report['changed'] == 1
    assert report['providers']['vbpl']['status'] == 'partial'
    assert '500 Server Error' in report['errors'][0]['error']
    state = json.loads((tmp_path/'data/manifests/dynamic_ingestion_manifest.json').read_text())
    assert 'vbpl' not in state['providers']


def test_decision_number_uses_issuer_and_issue_year_to_reuse_canonical_id(tmp_path):
    seed(tmp_path)
    assert document_number('Quyết định số 127/QĐ-TTg', '2021-01-26') == '127/qd-ttg/2021'
    assert document_number('127/QĐ-TTg', '2026-01-26') != document_number('127/QĐ-TTg', '2021-01-26')
    assert document_number('Luật 134/2025/QH15', '2026-11-16') == '134/2025/qh15'
    with (tmp_path/'data/sources.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['document_id','title','source_org','published_date'])
        writer.writeheader()
        writer.writerow({'document_id':'strategy','title':'Chiến lược Trí tuệ nhân tạo 127/QĐ-TTg',
                         'source_org':'Thủ tướng Chính phủ','published_date':'2021-01-26'})
    ingestor = DynamicIngestor(tmp_path, FakeAPI())
    assert ingestor.canonical[('127/qd-ttg/2021','thu tuong chinh phu')] == 'strategy'
    assert ('127/qd-ttg/2026','thu tuong chinh phu') not in ingestor.canonical


def test_inventory_separates_pending_sources_and_active_documents(tmp_path):
    seed(tmp_path)
    (tmp_path/'data/dynamic').mkdir()
    (tmp_path/'data/dynamic/catalog.json').write_text(json.dumps({'pending':{'document_id':'pending','title':'New AI law'}}))
    _,_,counts=load_inventory(tmp_path)
    assert counts['active']==1 and counts['catalog']==2 and counts['pending']==1


def test_changed_metadata_reuses_vector_only_when_text_and_model_match(tmp_path,monkeypatch):
    class Client:
        points=[]
        def retrieve(self,**kwargs):
            return [SimpleNamespace(id=str(uuid.uuid5(uuid.NAMESPACE_URL,'a')),vector=[1.,0.],
                payload={'text':'Old text','embedding_model':indexer.setting('EMBEDDING_MODEL','bge-m3')})]
        def collection_exists(self,name):return False
        def create_collection(self,*args,**kwargs):pass
        def upsert(self,**kwargs):self.points=kwargs['points']
    embedded=[]
    def embed(texts): embedded.extend(texts); return [[0.,1.] for _ in texts]
    monkeypatch.setattr(indexer,'embeddings',embed)
    client=Client()
    indexer.upload_batch(client,'new',[{'chunk_id':'a','text':'Old text','source_url':'https://vbpl.vn/one'},
        {'chunk_id':'b','text':'New text','source_url':'https://vbpl.vn/two'}],reuse_from='old')
    assert embedded==['New text']
    assert client.points[0].vector==[1.,0.] and client.points[1].vector==[0.,1.]


def test_start_update_is_singleton_across_requests(tmp_path,monkeypatch):
    seed(tmp_path); launched=[]
    monkeypatch.setattr(service.subprocess,'Popen',lambda *args,**kwargs:launched.append((args,kwargs)))
    one=service.start_update(['vbpl'],10,root=tmp_path)
    two=service.start_update(['vbpl'],10,root=tmp_path)
    assert one['job_id']==two['job_id'] and len(launched)==1
    assert launched[0][1]['cwd']==tmp_path.resolve()


def test_dead_worker_is_reported_as_interrupted_without_killing_processes(tmp_path):
    seed(tmp_path)
    (tmp_path/'data/manifests/update_status.json').write_text(json.dumps({'status':'running','job_id':'old','started_at':TODAY+'T00:00:00+00:00'}))
    with service.file_lock(tmp_path/'data/manifests/update_run.lock'):
        assert service.get_update_status(tmp_path)['status']=='running'
    assert service.get_update_status(tmp_path)['status']=='interrupted'


def test_input_snapshot_prefers_api_version_and_ignores_retrieval_time(tmp_path):
    seed(tmp_path)
    for directory,text in [('verified_parsed','old'),('dynamic/parsed','new')]:
        folder=tmp_path/'data'/directory;folder.mkdir(parents=True)
        (folder/'existing_law.json').write_text(json.dumps({'document_id':'existing_law','text':text,
            'content_hash':text,'parse_status':'success','provenance':'official_api' if 'dynamic' in directory else 'official_download'}))
    sig,count=update_data.prepare_inputs(tmp_path,tmp_path/'one')
    assert count==1 and json.loads((tmp_path/'one/existing_law.json').read_text())['text']=='new'
    assert update_data.prepare_inputs(tmp_path,tmp_path/'two')[0]==sig


def test_failed_index_update_keeps_previous_manifest(tmp_path,monkeypatch):
    seed(tmp_path); job='20261116_090000_abcdef12'
    (tmp_path/'data/manifests/update_status.json').write_text(json.dumps({'job_id':job,'providers':['vbpl'],'max_documents':10,'status':'queued'}))
    before=(tmp_path/'data/manifests/index_manifest.json').read_bytes()
    monkeypatch.setattr(DynamicIngestor,'run',lambda *a,**k:{'providers':{},'changed':1,'errors':[]})
    def fail(*a):raise RuntimeError('Embedding service offline')
    monkeypatch.setattr(update_data,'execute_pipeline',fail)
    with pytest.raises(RuntimeError,match='offline'):update_data.run_update(job,tmp_path)
    assert (tmp_path/'data/manifests/index_manifest.json').read_bytes()==before
    assert service.get_update_status(tmp_path)['status']=='failed'
