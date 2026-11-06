import json
import os
import sys
import tempfile
from pathlib import Path
import pytest

system32_paths = [r"C:\Windows\System32", r"C:\Windows", r"C:\Windows\System32\Wbem"]
os.environ["PATH"] = ";".join(system32_paths) + ";" + os.environ.get("PATH", "")
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable


def test_transform_spark():
    pyspark = pytest.importorskip("pyspark")
    from pyspark.sql import SparkSession
    from src.processing.spark_etl import transform

    try:
        spark = (
            SparkSession.builder.master("local[1]")
            .appName("etl-test")
            .config("spark.pyspark.python", sys.executable)
            .config("spark.pyspark.driver.python", sys.executable)
            .getOrCreate()
        )
    except Exception as exc:
        pytest.skip(f"Spark/Java unavailable: {exc}")

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            data = [
                {"title": "A", "text": "This is a long enough document for the quality filter, with policy content.", "region": "viet nam"},
                {"title": "A", "text": "This is a long enough document for the quality filter, with policy content.", "region": "viet nam"},
                {"title": "B", "text": "tiny", "region": "EU"},
            ]
            json.dump(data, f)
            temp_path = f.name

        df = spark.read.option("multiLine", "true").json(temp_path)
        rows = transform(df).collect()
        assert len(rows) == 1
        assert rows[0]["region"] == "VN"
        assert len(rows[0]["document_id"]) == 64
    finally:
        spark.stop()
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
