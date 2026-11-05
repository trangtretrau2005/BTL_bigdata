
import sys
from pathlib import Path
import argparse

# Thêm thư mục gốc dự án vào Python path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.parser import DocumentParser


def main():

    parser = argparse.ArgumentParser(
        description="Parse collected documents"
    )

    parser.add_argument(
        "--raw",
        required=True
    )

    parser.add_argument(
        "--output",
        required=True
    )

    args = parser.parse_args()

    document_parser = DocumentParser(
        raw_dir=args.raw,
        output_dir=args.output,
        manifest_path=(
            "data/manifests/ingestion_manifest.json"
        )
    )

    document_parser.parse_all()


if __name__ == "__main__":
    main()
