"""Semantic retrieval with optional region and document filters.

Supports Qdrant + Ollama embeddings as primary engine, with automatic fallback
to local BM25/bilingual lexical-semantic search over data/chunks/chunks.jsonl
when Qdrant or Ollama service is offline.
"""
from __future__ import annotations
import json
import math
import re
import unicodedata
from pathlib import Path
from .common import collection_name, embeddings, qdrant_client, setting

# Stopwords tiếng Việt & tiếng Anh phổ biến để tránh khớp nhiễu với câu hỏi ngoài phạm vi
_STOPWORDS = {
    "la", "gi", "cua", "va", "cac", "nhung", "trong", "theo", "cho", "ve", "co", "duoc",
    "nhu", "the", "nao", "ra", "sao", "tai", "tu", "den", "nam", "so", "khi", "ma", "thi",
    "bao", "nhieu", "ai", "o", "dau", "voi", "hay", "hoac", "mot", "nay", "do", "all",
    "the", "of", "and", "in", "to", "for", "on", "with", "is", "are", "what", "how", "by",
    "quy", "dinh", "van", "ban", "noi", "dung", "현", "hien", "nay", "nam", "ngay", "thang",
}

# Từ điển mở rộng truy vấn song ngữ Việt -> Anh cho kho văn bản AI quốc tế
_VI_TO_EN_EXPANSIONS = {
    "cam": ["prohibited", "article 5", "unacceptable", "ban", "social scoring"],
    "rui ro cao": ["high-risk", "high risk", "requirements", "obligations", "annex iii"],
    "nghia vu": ["obligations", "requirements", "providers", "compliance"],
    "muc phat": ["penalties", "35 000 000", "7 %", "article 99", "fines"],
    "phu luc iii": ["annex iii", "8 areas", "biometrics", "critical infrastructure"],
    "bon chuc nang": ["four core functions", "govern", "map", "measure", "manage"],
    "ai tao sinh": ["generative ai", "genai", "confabulation", "hallucination", "cbrn", "600-1"],
    "ao giac": ["hallucination", "confabulation"],
    "dao duc": ["ethics", "ethical", "values", "principles", "unesco", "australia", "asean"],
    "gia tri cot loi": ["core values", "values", "human rights", "inclusiveness", "peaceful"],
    "nguyen tac": ["principles", "inclusive growth", "transparency", "accountability", "fairness"],
    "con nguoi": ["human-in-the-loop", "human-over-the-loop", "human-out-of-the-loop", "human oversight", "human-centred"],
    "singapore": ["singapore", "imda", "pdpc", "human-in-the-loop", "human-over-the-loop"],
    "sac lenh": ["executive order", "14110", "dual-use foundation models", "red-teaming", "10^26"],
    "14110": ["14110", "executive order", "dual-use foundation models", "red-teaming", "10^26"],
    "hoa ky": ["united states", "executive order 14110", "federal register", "dual-use"],
    "cong uoc khung": ["framework convention", "council of europe", "cets no. 225", "human rights"],
    "hoi dong chau au": ["council of europe", "cets no. 225", "framework convention"],
    "asean": ["asean", "seven guiding principles", "7 guiding principles"],
    "uc": ["australia", "contestability", "8 ai ethics principles"],
    "australia": ["australia", "contestability", "8 ai ethics principles"],
    "42001": ["42001", "aims", "management system", "pdca", "impact assessment"],
    "he thong quan ly ai": ["aims", "42001", "management system", "pdca"],
    "uk": ["uk", "aisi", "safety institute", "frontier ai"],
}


def _strip_accents(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    norm = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in norm if unicodedata.category(ch) != "Mn")


def _tokenize(text: str) -> list[str]:
    clean = _strip_accents(text.lower())
    tokens = re.findall(r"[a-z0-9_]+", clean)
    return [t for t in tokens if len(t) > 1 and t not in _STOPWORDS]


def _local_retrieve(
    question: str,
    top_k: int = 5,
    norm_reg: str | None = None,
    doc_id: str | None = None,
) -> list[dict]:
    """Truy xuất BM25 + mở rộng song ngữ trực tiếp trên data/chunks/chunks.jsonl khi Qdrant/Ollama tắt."""
    chunks_path = Path(setting("CHUNKS_PATH", "data/chunks/chunks.jsonl"))
    if not chunks_path.exists():
        return []

    chunks: list[dict] = []
    with open(chunks_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if norm_reg:
                row_reg = (row.get("region") or "").upper()
                if norm_reg == "ASEAN":
                    if row_reg != "ASEAN" and "asean" not in (row.get("source_document_id") or "").lower():
                        continue
                elif row_reg != norm_reg:
                    continue
            if doc_id:
                if doc_id not in (row.get("document_id"), row.get("source_document_id")):
                    continue
            chunks.append(row)

    if not chunks:
        return []

    q_norm = _strip_accents(question.lower())
    q_tokens = _tokenize(question)

    # Mở rộng từ khóa song ngữ Việt -> Anh
    expanded_tokens = list(q_tokens)
    for vi_phrase, en_terms in _VI_TO_EN_EXPANSIONS.items():
        if vi_phrase in q_norm:
            for term in en_terms:
                expanded_tokens.extend(_tokenize(term))

    if not expanded_tokens:
        return []

    # Tính IDF trên tập chunks
    N = len(chunks)
    doc_Tokens_list: list[set[str]] = []
    df_counts: dict[str, int] = {}
    for ch in chunks:
        combined = f"{ch.get('title', '')} {ch.get('source_document_id', '')} {ch.get('article', '')} {ch.get('text', '')}"
        tok_set = set(_tokenize(combined))
        doc_Tokens_list.append(tok_set)
        for t in tok_set:
            df_counts[t] = df_counts.get(t, 0) + 1

    unique_q = list(dict.fromkeys(expanded_tokens))
    max_possible = sum(math.log(1.0 + (N / max(1, df_counts.get(t, N)))) for t in unique_q) or 1.0

    scored: list[dict] = []
    for ch, doc_toks in zip(chunks, doc_Tokens_list):
        raw_score = 0.0
        matched_specific = 0
        title_norm = _strip_accents((ch.get("title") or "").lower())
        body_norm = _strip_accents((ch.get("text") or "").lower())
        sid_norm = (ch.get("source_document_id") or "").lower()

        for t in unique_q:
            if t in doc_toks:
                idf = math.log(1.0 + (N / max(1, df_counts.get(t, 1))))
                weight = 1.35 if t in title_norm or t in sid_norm else 1.0
                raw_score += idf * weight
                if df_counts.get(t, N) <= max(3, int(N * 0.35)):
                    matched_specific += 1

        # Thưởng điểm nếu khớp số hiệu văn bản (vd: 127, 1671, 134, 142, 91, 356, 60, 47, 749, 942, 411, 06, 71, 86, 116, 14110, 42001, 1689)
        doc_numbers = re.findall(r"\b\d{2,5}\b", q_norm)
        for num in doc_numbers:
            if num in sid_norm or num in title_norm:
                raw_score += 4.5
                matched_specific += 2
            elif num in body_norm:
                raw_score += 2.0
                matched_specific += 1

        # Nếu không khớp bất kỳ từ khóa đặc trưng nào (câu hỏi ngoài phạm vi như GDP, vàng, bóng đá, GPT-5...)
        if matched_specific == 0 and raw_score < 2.2:
            norm_score = 0.10
        else:
            norm_score = min(0.98, 0.36 + 0.62 * (raw_score / (max_possible * 0.65 + 2.0)))

        item = dict(ch)
        item["score"] = round(float(norm_score), 4)
        scored.append(item)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def retrieve(
    question: str = "",
    top_k: int = 5,
    region: str | None = None,
    document_id: str | None = None,
    *,
    query: str | None = None,
    jurisdiction_filter: str | None = None,
    document_id_filter: str | None = None,
    **kwargs,
):
    q = (question or query or "").strip()
    if not q:
        raise ValueError("Empty question")
    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    reg = region or jurisdiction_filter
    doc_id = document_id or document_id_filter

    norm_reg = None
    if reg and reg.upper() not in ("ALL", "TAT CA", "TẤT CẢ"):
        norm_reg = "INTERNATIONAL" if reg.upper() in ("INTERNATIONAL", "GLOBAL", "INT") else reg.upper()

    try:
        from qdrant_client import models
        conditions = []
        if norm_reg:
            conditions.append(models.FieldCondition(key="region", match=models.MatchValue(value=norm_reg)))
        if doc_id:
            conditions.append(
                models.Filter(
                    should=[
                        models.FieldCondition(key="document_id", match=models.MatchValue(value=doc_id)),
                        models.FieldCondition(key="source_document_id", match=models.MatchValue(value=doc_id)),
                    ]
                )
            )
        search_filter = models.Filter(must=conditions) if conditions else None
        client = qdrant_client()
        if not client.collection_exists(collection_name()):
            raise RuntimeError("Qdrant collection does not exist.")
        query_vector = embeddings([q])[0]
        hits = client.query_points(
            collection_name=collection_name(),
            query=query_vector,
            query_filter=search_filter,
            limit=top_k,
            with_payload=True,
        ).points
        return [{"score": float(hit.score), **(hit.payload or {})} for hit in hits]
    except Exception:
        # Fallback tự động sang tìm kiếm cục bộ trên data/chunks/chunks.jsonl khi Qdrant/Ollama chưa bật
        return _local_retrieve(q, top_k=top_k, norm_reg=norm_reg, doc_id=doc_id)
