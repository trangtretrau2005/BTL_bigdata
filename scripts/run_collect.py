
import argparse

from src.ingestion.collector import DocumentCollector


def main():

    parser = argparse.ArgumentParser(
        description="Collect AI policy documents"
    )

    parser.add_argument(
        "--sources",
        required=True
    )

    parser.add_argument(
        "--output",
        required=True
    )

    args = parser.parse_args()

    collector = DocumentCollector(
        output_dir=args.output,
        manifest_path=(
            "data/manifests/ingestion_manifest.json"
        )
    )

    results = collector.collect_from_csv(
        args.sources
    )

    success = sum(
        result["status"] == "downloaded"
        for result in results
    )

    failed = len(results) - success

    print("\n========== COLLECT SUMMARY ==========")

    print("Total:", len(results))
    print("Success:", success)
    print("Failed:", failed)


if __name__ == "__main__":
    main()
