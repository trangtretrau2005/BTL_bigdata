import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json
from src.rag.answerer import answer


def main():
    p = argparse.ArgumentParser(description="Ask the AI-law RAG system")
    p.add_argument("question")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--region", default=None)
    p.add_argument("--document-id", default=None)
    a = p.parse_args()
    print(json.dumps(answer(a.question, a.top_k, a.region, a.document_id), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
