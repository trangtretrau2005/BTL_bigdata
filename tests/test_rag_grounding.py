"""Failure paths and grounding contracts, without running model services."""
import json
from types import SimpleNamespace

import pytest

from src.rag import answerer, retriever, tts


@pytest.fixture
def hits():
    return [
        {"chunk_id": f"chunk-{i}", "document_id": "doc-1", "title": "AI policy", "text": "AI cần giám sát con người.",
         "source_url": "https://example.org/policy", "score": 0.85, "retrieval_mode": "vector"}
        for i in (1, 2)
    ]


def test_generation_failure_is_visible_not_an_extractive_answer(monkeypatch, hits):
    def unavailable(*args):
        raise RuntimeError("Ollama offline")
    monkeypatch.setattr(answerer, "ollama_post", unavailable)
    result = answerer.answer("AI cần giám sát như thế nào?", retrieved_chunks=hits)
    assert result["status"] == "error"
    assert result["answer"] is None
    assert "Ollama offline" in result["error_message"]


def test_missing_citations_retries_and_rejects(monkeypatch, hits):
    calls = []
    def uncited(endpoint, payload):
        calls.append(payload)
        return {"response": "Hệ thống AI cần có sự giám sát của con người."}
    monkeypatch.setattr(answerer, "ollama_post", uncited)
    result = answerer.answer("AI cần giám sát như thế nào?", retrieved_chunks=hits)
    assert result["status"] == "error"
    assert len(calls) == 2
    assert all(p["think"] is False for p in calls)


def test_invalid_labels_never_removed_to_accept_claim(monkeypatch, hits):
    monkeypatch.setattr(answerer, "ollama_post", lambda *args: {"response": "AI bị phạt một tỷ đồng. [S99]"})
    result = answerer.answer("Chính sách AI quy định gì?", retrieved_chunks=hits)
    assert result["status"] == "error"
    assert result["citations"] == []


def test_only_used_sources_returned_and_thinking_hidden(monkeypatch, hits):
    monkeypatch.setattr(answerer, "ollama_post", lambda *args: {
        "response": "<think>Internal reasoning</think>AI cần có sự giám sát của con người. [S2]"
    })
    result = answerer.answer("AI cần giám sát như thế nào?", retrieved_chunks=hits)
    assert result["status"] == "answered"
    assert "Internal reasoning" not in result["answer"]
    assert [c["source_id"] for c in result["citations"]] == ["S2"]
    assert result["retrieval_mode"] == "vector"


def test_unrelated_question_refused_before_network(monkeypatch, hits):
    def unexpected(*args, **kwargs):
        pytest.fail("Out-of-scope questions must not call a model")
    monkeypatch.setattr(answerer, "ollama_post", unexpected)
    result = answerer.answer("Giá vàng hôm nay là bao nhiêu?", retrieved_chunks=hits)
    assert result["status"] == "insufficient_evidence"


def test_explicit_model_refusal_not_counted_as_answer(monkeypatch, hits):
    monkeypatch.setattr(answerer, "ollama_post", lambda *args: {"response": answerer.NO_EVIDENCE})
    assert answerer.answer("AI có nghĩa vụ gì?", retrieved_chunks=hits)["status"] == "insufficient_evidence"

def test_thinking_budget_exhaustion_does_not_retry_citation_generation(monkeypatch, hits):
    calls=[]
    def unfinished(*args):
        calls.append(1)
        return {'thinking':'unfinished reasoning', 'response':'', 'done_reason':'length'}
    monkeypatch.setattr(answerer,'ollama_post',unfinished)
    result=answerer.answer('AI có nghĩa vụ gì?',retrieved_chunks=hits)
    assert result['status']=='error'
    assert 'thinking' in result['error_message']
    assert len(calls)==1

def test_prohibited_groups_are_complete_without_generated_exceptions(monkeypatch, hits):
    hits[0].update(context_kind='article',text='Article 5\n(a)\nManipulation\n(b)\nSocial scoring\n(c)\nBiometrics')
    monkeypatch.setattr(answerer,'ollama_post',lambda *args:{'response':json.dumps({'topics':{'a':'Thao túng hành vi','b':'Chấm điểm xã hội','c':'Nhận dạng sinh trắc học'}})})
    result=answerer.answer('AI cấm hành vi nào?',retrieved_chunks=hits[:1])
    assert result['status']=='answered'
    assert all(f'({label})' in result['answer'] for label in 'abc')
    assert 'ngoại lệ cần đối chiếu' in result['answer']
    assert len(result['citations'])==1

def test_generated_exception_in_topic_is_rejected(monkeypatch, hits):
    hits[0].update(context_kind='article',text='Article 5\n(a)\nRule\n(b)\nRule\n(c)\nRule')
    monkeypatch.setattr(answerer,'ollama_post',lambda *args:{'response':json.dumps({'topics':{label:'Được phép trừ khi có ngoại lệ' for label in 'abc'}})})
    assert answerer.answer('AI cấm hành vi nào?',retrieved_chunks=hits[:1])['status']=='error'


def test_retrieval_failure_never_silently_uses_local(monkeypatch):
    def offline():
        raise ConnectionError("Qdrant offline")
    monkeypatch.setattr(retriever, "qdrant_client", offline)
    with pytest.raises(retriever.RetrievalError, match="Qdrant offline"):
        retriever.retrieve("AI policy", mode="vector")

def test_transient_qdrant_timeout_retries_vector_query(monkeypatch):
    class Timeout408(Exception):
        status_code=408
    calls=[]
    def query(**kwargs):
        calls.append(1)
        if len(calls)==1: raise Timeout408('busy')
        return SimpleNamespace(points=[SimpleNamespace(score=.8,payload={'text':'AI policy','chunk_id':'c','source_url':'https://www.nist.gov/'})])
    monkeypatch.setattr(retriever,'qdrant_client',lambda:SimpleNamespace(collection_exists=lambda name:True,query_points=query))
    monkeypatch.setattr(retriever,'embeddings',lambda texts:[[1.,0.]])
    monkeypatch.setattr(retriever.time,'sleep',lambda delay:None)
    result=retriever.retrieve('AI policy',mode='vector')
    assert len(calls)==2 and result[0]['retrieval_mode']=='vector'


def test_explicit_local_mode_has_no_irrelevant_zero_match(tmp_path, monkeypatch):
    path = tmp_path / "chunks.jsonl"
    path.write_text(json.dumps({"chunk_id": "a", "text": "AI transparency", "title": "AI", "region": "EU"}), encoding="utf-8")
    monkeypatch.setenv("CHUNKS_PATH", str(path))
    assert retriever.retrieve("zzzznooverlap", mode="local") == []
    result = retriever.retrieve("transparency", mode="local")
    assert result[0]["retrieval_mode"] == "local"


def test_speech_cleaning_keeps_content_without_repeating_source_labels():
    text = "**Nghĩa vụ AI** [S1]\n- Bảo vệ dữ liệu. [S2]\n- Minh bạch. [S1]"
    spoken = tts.clean_text_for_speech(text)
    assert "[S" not in spoken
    assert "trí tuệ nhân tạo" in spoken
    assert "Bảo vệ dữ liệu." in spoken
    assert "Minh bạch." in spoken
    long_text = "Một câu đầy đủ. " * 40
    assert len(tts.split_into_tts_chunks(long_text)) > 14


def test_neural_voice_and_tempo_are_forwarded(monkeypatch):
    settings = []
    def speech(text, voice, rate):
        settings.append((voice, rate))
        return b"mp3-audio"
    monkeypatch.setattr(tts, "_neural_audio", speech)
    audio, phrases = tts.synthesize_speech_base64("AI cần minh bạch.", voice="vi-VN-NamMinhNeural", rate="-10%")
    assert audio and phrases
    assert settings == [("vi-VN-NamMinhNeural", "-10%")]
