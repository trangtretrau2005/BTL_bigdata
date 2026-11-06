import pytest


def test_transform_spark():
    pyspark = pytest.importorskip("pyspark")
    from pyspark.sql import SparkSession
    from src.processing.spark_etl import transform
    try:
        spark = SparkSession.builder.master("local[1]").appName("etl-test").getOrCreate()
    except Exception as exc:
        pytest.skip(f"Spark/Java unavailable: {exc}")
    try:
        df = spark.createDataFrame([
            {"title": "A", "text": "This is a long enough document for the quality filter, with policy content.", "region": "viet nam"},
            {"title": "A", "text": "This is a long enough document for the quality filter, with policy content.", "region": "viet nam"},
            {"title": "B", "text": "tiny", "region": "EU"},
        ])
        rows = transform(df).collect()
        assert len(rows) == 1
        assert rows[0]["region"] == "VN"
        assert len(rows[0]["document_id"]) == 64
    finally:
        spark.stop()
