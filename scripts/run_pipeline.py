import sys
from pathlib import Path
import argparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.processing.spark_etl import run as etl
from src.processing.chunker import run as chunk
from src.rag.indexer import run as index


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--step", choices=["etl", "chunk", "index", "all"], default="all")
    a = p.parse_args()
    if a.step in ("etl", "all"):
        etl("data/parsed", "data/processed")
    if a.step in ("chunk", "all"):
        chunk("data/processed", "data/chunks")
    if a.step in ("index", "all"):
        index("data/chunks")


if __name__ == "__main__":
    main()
