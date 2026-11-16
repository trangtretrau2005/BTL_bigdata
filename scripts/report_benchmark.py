"""Small, reproducible retrieval/ETL experiments; never publishes an index."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.catalog import read_json
from src.rag.common import collection_name
from scripts.report_collect import OUT, save

CASES = [
 ('R01','Luật Trí tuệ nhân tạo 134/2025/QH15 quy định phạm vi điều chỉnh như thế nào?','luat_134_2025','VN'),
 ('R02','Quyết định 127/QĐ-TTg về chiến lược nghiên cứu phát triển và ứng dụng trí tuệ nhân tạo đến năm 2030.','qd_127_2021','VN'),
 ('R03','Chiến lược quốc gia trí tuệ nhân tạo trong Quyết định 1671/QĐ-TTg năm 2026.','qd_1671_2026','VN'),
 ('R04','Nghị định 142/2026/NĐ-CP quy định chi tiết thi hành Luật Trí tuệ nhân tạo.','nd_142_2026','VN'),
 ('R05','Quyết định 102/2026/QĐ-UBND Hà Nội quy định bảo đảm an toàn và quản lý rủi ro ứng dụng AI.','vbpl_cb2746e0-c933-11f1-93f8-53a9005d11e5','VN'),
 ('R06','Thông tư 53/2026/TT-NHNN quy định an toàn và quản lý rủi ro trí tuệ nhân tạo trong ngân hàng.','vbpl_99fa0140-c2ba-11f1-b8ec-99379998c900','VN'),
 ('R07','EU AI Act quy định nghĩa vụ cho hệ thống trí tuệ nhân tạo rủi ro cao như thế nào?','eu_ai_act_2024_1689','EU'),
 ('R08','Nghĩa vụ AI literacy của tổ chức theo hướng dẫn của Ủy ban châu Âu.','eu_ai_literacy','EU'),
 ('R09','NIST AI RMF 1.0 gồm bốn chức năng quản trị rủi ro cốt lõi nào?','nist_ai_rmf_1_0',''),
 ('R10','NIST Generative AI Profile AI 600-1 hướng dẫn rủi ro AI tạo sinh.','nist_gen_ai_profile',''),
 ('R11','NIST SP 800-218A hướng dẫn phát triển phần mềm an toàn cho AI.','nist_sp800_218a',''),
 ('R12','Khuyến nghị UNESCO về đạo đức trí tuệ nhân tạo có những nguyên tắc nào?','unesco_ai_ethics_guidance',''),
 ('R13','OECD AI Principles về minh bạch và trách nhiệm giải trình của hệ thống AI.','oecd_ai_principles',''),
 ('R14','ASEAN Guide on AI Governance and Ethics hướng dẫn quản trị AI.','asean_ai_ethics','ASEAN'),
 ('R15','Singapore Model AI Governance Framework hướng dẫn doanh nghiệp quản trị AI.','singapore_model_ai_gov',''),
]


def retrieval():
    from src.rag.retriever import retrieve
    from src.rag.answerer import answer
    manifest=read_json(ROOT/'data/manifests/index_manifest.json')
    expected={c[2] for c in CASES}
    assert expected <= set(manifest['source_document_ids']),expected-set(manifest['source_document_ids'])
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'retrieval_cases.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['case_id','question','expected_document_id','region_filter']);w.writerows(CASES)
    # Warm the embedding model once; this call is not included in latency statistics.
    warm_start=time.perf_counter();retrieve('Quản trị rủi ro trí tuệ nhân tạo',top_k=5)
    warmup=time.perf_counter()-warm_start
    runs=[]
    for repeat in range(1,4):
        for qid,question,doc,region in CASES:
            start=time.perf_counter()
            hits=retrieve(question,top_k=5,region=region or None)
            elapsed=time.perf_counter()-start
            ids=[h.get('source_document_id') or h['document_id'] for h in hits]
            rank=next((i for i,value in enumerate(ids,1) if value==doc),None)
            runs.append({'repeat':repeat,'case_id':qid,'question':question,'expected':doc,'region':region,
                'rank':rank,'hit_at_1':rank==1,'hit_at_5':rank is not None,'reciprocal_rank':1/rank if rank else 0,
                'elapsed_seconds':elapsed,'returned_source_ids':ids,'scores':[h['score'] for h in hits],
                'context_kinds':[h.get('context_kind','chunk') for h in hits]})
    negative=[]
    with (ROOT/'evaluation/qa_eval_set.csv').open(encoding='utf-8-sig') as f:
        questions=[r['question'] for r in csv.DictReader(f) if r['has_answer'].lower()=='false']
    for q in questions:
        start=time.perf_counter();r=answer(q)
        negative.append({'question':q,'status':r['status'],'elapsed_seconds':time.perf_counter()-start})
    times=sorted(r['elapsed_seconds'] for r in runs)
    summary={'kind':'15 manually selected document-identity queries, regional filters allowed, NO document_id filter',
        'captured_at':datetime.now(timezone.utc).isoformat(),'snapshot':manifest['snapshot'],
        'queries':len(CASES),'repeats':3,'runs':len(runs),'warmup_seconds_excluded':warmup,
        'hit_at_1':statistics.mean(r['hit_at_1'] for r in runs),'hit_at_5':statistics.mean(r['hit_at_5'] for r in runs),
        'mrr_at_5':statistics.mean(r['reciprocal_rank'] for r in runs),'latency_mean':statistics.mean(times),
        'latency_median':statistics.median(times),'latency_p95':times[int(.95*(len(times)-1))],
        'negative_count':len(negative),'negative_refused':sum(r['status']=='insufficient_evidence' for r in negative),
        'not_measured':['factual/legal answer accuracy','large-scale ANN recall','concurrent users','cold-start latency'],
        'details':runs,'negative_cases':negative}
    save('retrieval_results.json',summary)
    with (OUT/'retrieval_timings.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['repeat','case_id','rank','hit_at_1','hit_at_5','elapsed_seconds'])
        w.writeheader();w.writerows({k:r[k] for k in w.fieldnames} for r in runs)
    print(json.dumps({k:v for k,v in summary.items() if k not in {'details','negative_cases'}},ensure_ascii=False),flush=True)


def etl_benchmark():
    import pyarrow.dataset as ds
    from src.processing.spark_etl import run
    active=read_json(ROOT/'data/manifests/index_manifest.json')
    active_bytes=(ROOT/'data/manifests/index_manifest.json').read_bytes()
    documents=ds.dataset(str(ROOT/active['processed_path']),format='parquet').to_table().to_pylist()
    records=[{**d,'document_id':d['source_document_id']} for d in documents]
    work=ROOT/'.venv/report_benchmark';work.mkdir(parents=True,exist_ok=True)
    inputs={}
    for multiplier in [1,5,10]:
        path=work/f'input_{multiplier}x.jsonl'
        with path.open('w',encoding='utf-8') as f:
            for _ in range(multiplier):
                for row in records:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        inputs[multiplier]=path
    runs=[]
    # Separate warmup; JVM/OS caches are not reset between the measured jobs.
    run(str(inputs[1]),str(work/'warmup'),'local[2]',str(OUT/'etl_warmup.json'))
    expected=sorted((d['source_document_id'],d['text_sha256']) for d in documents)
    for repeat in range(1,4):
        for multiplier,path in inputs.items():
            target=work/f'processed_{multiplier}x_{repeat}'
            start=time.perf_counter()
            valid=run(str(path),str(target),'local[2]',str(OUT/f'etl_{multiplier}x_{repeat}.json'))
            elapsed=time.perf_counter()-start
            output=ds.dataset(str(target),format='parquet').to_table(columns=['source_document_id','text_sha256']).to_pylist()
            assert sorted((d['source_document_id'],d['text_sha256']) for d in output)==expected
            runs.append({'repeat':repeat,'multiplier':multiplier,'input_rows':len(records)*multiplier,
                'input_bytes':path.stat().st_size,'valid_rows':valid,'duplicates_removed':len(records)*multiplier-valid,
                'elapsed_seconds':elapsed,'output_parquet_bytes':sum(p.stat().st_size for p in target.glob('*.parquet')),
                'same_unique_content':True})
            save('etl_scaling_results.json',{'kind':'bounded duplicate-replay ETL experiment, NOT distributed throughput benchmark',
                'spark_master':'local[2]','base_documents':len(records),'repeats':3,'runs':runs})
    assert (ROOT/'data/manifests/index_manifest.json').read_bytes()==active_bytes
    with (OUT/'etl_scaling.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(runs[0]));w.writeheader();w.writerows(runs)
    print('ETL experiment passed; active index manifest unchanged.',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--part',choices=['retrieval','etl'],required=True);args=p.parse_args()
    retrieval() if args.part=='retrieval' else etl_benchmark()
