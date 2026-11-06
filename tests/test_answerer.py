from src.rag.answerer import build_prompt, answer, NO_EVIDENCE


def test_prompt_citations():
    prompt = build_prompt("Câu hỏi?", [{"title": "A", "text": "Nội dung", "region": "VN"}])
    assert "[S1]" in prompt and "Nội dung" in prompt


def test_no_hits_refuses(monkeypatch):
    monkeypatch.setattr("src.rag.answerer.retrieve", lambda *args, **kwargs: [])
    result = answer("Nội dung gì?")
    assert result["answer"] == NO_EVIDENCE
    assert result["insufficient_evidence"] is True
