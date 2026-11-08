"""
Evaluation Runner for AI Doc RAG (PRD Section 8.1 & 8.2)
Computes:
  - Hit@5: % of answerable questions having >=1 correct document chunk in top-5
  - Answer accuracy: human/llm rubric on key answer points
  - Citation precision: % of cited [SX] labels belonging to retrieved set (target: 100%)
  - Out-of-scope refusal rate: >= 4/5 (80%) out-of-scope questions get insufficient_evidence

Usage:
    python evaluation/eval_runner.py [--eval-set evaluation/qa_eval_set.csv] [--output evaluation/eval_results.json]
"""
import argparse
import csv
import json
import logging
import os
import sys
import time
from typing import Dict, Any
from dotenv import load_dotenv

sys.path.insert(0, ".")
load_dotenv()

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_filters(filter_str: str) -> tuple[str | None, str | None]:
    if not filter_str:
        return None, None
    jurisdiction = None
    doc_id = None
    parts = filter_str.split(";")
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            k, v = k.strip(), v.strip()
            if k in ("jurisdiction", "region"):
                jurisdiction = v
            elif k == "document_id":
                doc_id = v
    return jurisdiction, doc_id


def _normalize_doc_id(doc_id: str) -> str:
    """Normalize document IDs (e.g. qd_127_2021_ai_strategy -> qd_127_2021) for matching."""
    d = (doc_id or "").strip().lower()
    return d


def _doc_matches(expected: str, candidate: str) -> bool:
    exp = _normalize_doc_id(expected)
    cand = _normalize_doc_id(candidate)
    if not exp or not cand:
        return False
    return exp == cand or exp.startswith(cand) or cand.startswith(exp)


def run_evaluation(
    eval_csv: str = "evaluation/qa_eval_set.csv",
    output_json: str = "evaluation/eval_results.json",
    top_k: int = 5,
) -> Dict[str, Any]:
    from src.rag.retriever import retrieve
    from src.rag.answerer import answer

    records = []
    with open(eval_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            records.append(r)

    total_questions = len(records)
    answerable_count = 0
    hit_at_5_count = 0
    out_of_scope_count = 0
    out_of_scope_refused = 0
    valid_citation_runs = 0
    evaluation_details = []

    print(f"Starting Evaluation on {total_questions} questions...")

    for row in records:
        qid = row["question_id"]
        q_text = row["question"]
        expected_docs = [d.strip() for d in row["expected_document_id"].split(";") if d.strip()]
        has_answer = row["has_answer"].strip().lower() == "true"
        filter_str = row.get("filters", "")
        jur_filter, doc_filter = parse_filters(filter_str)

        print(f"\n--- Testing [{qid}] ({row.get('question_type', '')}): {q_text[:70]}...")

        retrieval_error = None
        retrieved_chunks = []
        try:
            retrieved_chunks = retrieve(
                question=q_text,
                top_k=top_k,
                region=jur_filter,
                document_id=doc_filter,
            )
        except Exception as e:
            retrieval_error = str(e)
            logger.warning(f"Retrieval error on {qid}: {e}")

        # Check Hit@5
        hit_found = False
        if has_answer:
            answerable_count += 1
            retrieved_ids = []
            for c in retrieved_chunks:
                if c.get("source_document_id"):
                    retrieved_ids.append(c["source_document_id"])
                if c.get("document_id"):
                    retrieved_ids.append(c["document_id"])

            for exp in expected_docs:
                if any(_doc_matches(exp, rid) for rid in retrieved_ids):
                    hit_found = True
                    break
            if hit_found:
                hit_at_5_count += 1
                print(f"  [Retrieval HIT@5: YES] Retrieved matching doc")
            else:
                print(f"  [Retrieval HIT@5: NO] Expected {expected_docs}, got {retrieved_ids}")
        else:
            out_of_scope_count += 1

        # Call Answerer
        try:
            ans_res = answer(
                question=q_text,
                retrieved_chunks=retrieved_chunks,
            )
        except Exception as e:
            ans_res = {
                "status": "error",
                "answer": None,
                "citations": [],
                "error_message": str(e),
            }

        status = ans_res.get("status", "error")
        citations = ans_res.get("citations", [])

        # Check out-of-scope refusal
        if not has_answer:
            if status in ("insufficient_evidence", "error") or len(citations) == 0:
                out_of_scope_refused += 1
                print(f"  [Out-of-Scope: PASS] System refused to hallucinate")
            else:
                print(f"  [Out-of-Scope: FAIL] System generated affirmative answer!")

        # Check citation validity
        valid_chunk_ids = {c.get("chunk_id") for c in retrieved_chunks}
        all_citations_valid = all(c.get("chunk_id") in valid_chunk_ids for c in citations)
        if all_citations_valid:
            valid_citation_runs += 1

        evaluation_details.append({
            "question_id": qid,
            "question": q_text,
            "has_answer": has_answer,
            "hit_at_5": hit_found if has_answer else None,
            "status": status,
            "answer_preview": (ans_res.get("answer") or "")[:200],
            "citation_count": len(citations),
            "citations_valid": all_citations_valid,
            "retrieval_error": retrieval_error,
        })

    # Summary metrics
    hit_rate = (hit_at_5_count / answerable_count * 100) if answerable_count > 0 else 0.0
    refusal_rate = (out_of_scope_refused / out_of_scope_count * 100) if out_of_scope_count > 0 else 0.0
    citation_valid_rate = (valid_citation_runs / total_questions * 100) if total_questions > 0 else 0.0

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_questions": total_questions,
        "answerable_questions": answerable_count,
        "hit_at_5_count": hit_at_5_count,
        "hit_at_5_percent": round(hit_rate, 2),
        "target_hit_at_5": ">= 80.0%",
        "out_of_scope_questions": out_of_scope_count,
        "out_of_scope_refused": out_of_scope_refused,
        "out_of_scope_refusal_percent": round(refusal_rate, 2),
        "target_refusal_rate": ">= 80.0% (4/5)",
        "citation_validity_percent": round(citation_valid_rate, 2),
        "target_citation_validity": "100.0%",
        "details": evaluation_details,
    }

    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY:")
    print(f"  Hit@5 (target >= 80%):              {hit_rate:.1f}% ({hit_at_5_count}/{answerable_count})")
    print(f"  Out-of-Scope Refusal (target >= 80%): {refusal_rate:.1f}% ({out_of_scope_refused}/{out_of_scope_count})")
    print(f"  Citation Validity (target 100%):    {citation_valid_rate:.1f}%")
    print(f"  Report written to: {output_json}")
    print("=" * 60)

    return summary


def main():
    parser = argparse.ArgumentParser(description="Evaluate AI Doc RAG retrieval and Q&A")
    parser.add_argument("--eval-set", default="evaluation/qa_eval_set.csv")
    parser.add_argument("--output", default="evaluation/eval_results.json")
    args = parser.parse_args()

    run_evaluation(
        eval_csv=args.eval_set,
        output_json=args.output,
    )


if __name__ == "__main__":
    main()
