"""Live services check, separate from a quality benchmark."""
import argparse
import csv
import json
import time
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import requests
from src.rag.common import collection_name,qdrant_client,setting
from src.rag.answerer import answer

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='evaluation/service_smoke_results.json')
    args=parser.parse_args()
    report={'kind':'live smoke test; not a factual accuracy benchmark','checks':{},'answers':[]}
    client=qdrant_client()
    count=client.count(collection_name=collection_name(),exact=True).count
    report['checks']['qdrant_points']=count
    assert count>0
    r=requests.get(str(setting('OLLAMA_BASE_URL','http://localhost:11434')).rstrip('/')+'/api/tags',timeout=10)
    r.raise_for_status();report['checks']['models']=[m['name'] for m in r.json()['models']]
    cases=[('Luật Trí tuệ nhân tạo quy định phạm vi điều chỉnh như thế nào?','VN','luat_134_2025'),
           ('NIST AI RMF có bốn chức năng cốt lõi nào?',None,'nist_ai_rmf_1_0'),
           ('EU AI Act cấm những hành vi AI nào?','EU','eu_ai_act_2024_1689')]
    for question,region,doc in cases:
        print('Testing:',question,flush=True)
        start=time.monotonic();result=answer(question,region=region,document_id=doc)
        report['answers'].append({'question':question,'elapsed_seconds':round(time.monotonic()-start,2),'result':result})
        Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(question,result['status'],result.get('error_message'),flush=True)
    outside=[r['question'] for r in csv.DictReader(open('evaluation/qa_eval_set.csv',encoding='utf-8-sig')) if r['has_answer'].lower()=='false']
    report['checks']['outside_scope_refused']=sum(answer(q)['status']=='insufficient_evidence' for q in outside)
    report['checks']['outside_scope_questions']=len(outside)
    report['checks']['answered_smoke_cases']=sum(a['result']['status']=='answered' for a in report['answers'])
    report['checks']['llm_answered_cases']=sum(a['result']['status']=='answered' and a['result'].get('model') is not None for a in report['answers'])
    report['checks']['curated_summary_cases']=sum(a['result'].get('answer_mode')=='curated_summary' for a in report['answers'])
    Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report['checks'],ensure_ascii=False),flush=True)
    if report['checks']['answered_smoke_cases'] != len(cases) or report['checks']['outside_scope_refused'] != len(outside):
        raise SystemExit('Live smoke failed; inspect the JSON report.')

if __name__=='__main__':main()
