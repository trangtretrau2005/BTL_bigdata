from src.processing.chunker import chunk_text, chunk_document


def test_long_text_coverage():
    text = "abcdef" * 400
    parts = list(chunk_text(text, size=200, overlap=30))
    assert parts[0][0] == 0
    assert parts[-1][1] == len(text)
    assert all(text[s:e] == chunk for s, e, chunk in parts)
    assert all(parts[i+1][0] <= parts[i][1] for i in range(len(parts)-1))
    assert len(parts) > 1


def test_chunk_ids_deterministic():
    doc = {"document_id": "d-1", "text": "hello world " * 100, "title": "Test", "region": "VN"}
    a = list(chunk_document(doc, size=100, overlap=20))
    b = list(chunk_document(doc, size=100, overlap=20))
    assert a == b
    assert all(x["document_id"] == "d-1" for x in a)


def test_reject_bad_overlap():
    try:
        list(chunk_text("abc", 10, 10))
        raise AssertionError("Expected ValueError")
    except ValueError:
        pass
