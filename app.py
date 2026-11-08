"""
Streamlit UI - Tone Xanh Trắng, Chữ To, Tối Giản, Có Hình Người Nói & Voice 2 Chiều.
Chay: streamlit run app.py
"""
import base64
import csv
import hashlib
import json
import os
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from src.rag.answerer import answer
from src.rag.avatar_component import build_talking_avatar_html
from src.rag.retriever import retrieve
from src.rag.tts import (
    clean_text_for_speech,
    synthesize_speech_base64,
    transcribe_vietnamese_audio,
)

load_dotenv()

TOP_K = int(os.getenv("TOP_K", "4"))

st.set_page_config(
    page_title="Trợ lý Pháp luật AI",
    page_icon="👩‍⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- CSS: 1 TONE XANH - TRẮNG, CHỮ TO, BỚT RỐI ---
st.markdown(
    """
    <style>
    /* Nền trắng tinh, chữ xanh đậm rõ nét */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #ffffff !important;
        color: #0f172a !important;
    }
    [data-testid="stSidebar"] {
        background-color: #f0f7ff !important;
        border-right: 2px solid #dbeafe !important;
    }
    /* Chữ to toàn bộ giao diện */
    html, body, p, li, div, span, label {
        font-size: 18px !important;
        color: #0f172a;
    }
    h1 {
        font-size: 30px !important;
        color: #1d4ed8 !important;
        font-weight: 800 !important;
    }
    h2, h3 {
        font-size: 23px !important;
        color: #1e40af !important;
        font-weight: 700 !important;
    }
    /* Ô nhập câu hỏi chữ to, viền xanh */
    textarea, input[type="text"] {
        font-size: 19px !important;
        background-color: #ffffff !important;
        color: #0f172a !important;
        border: 2px solid #93c5fd !important;
        border-radius: 12px !important;
    }
    textarea:focus, input[type="text"]:focus {
        border-color: #1d4ed8 !important;
        box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.15) !important;
    }
    /* Nút bấm to, tone xanh trắng */
    .stButton > button {
        font-size: 18px !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        padding: 10px 18px !important;
        border: 2px solid #93c5fd !important;
        background-color: #f0f7ff !important;
        color: #1d4ed8 !important;
    }
    .stButton > button:hover {
        background-color: #dbeafe !important;
        border-color: #1d4ed8 !important;
    }
    .stButton > button[kind="primary"] {
        background-color: #1d4ed8 !important;
        color: #ffffff !important;
        border-color: #1d4ed8 !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #1e40af !important;
    }
    /* Hộp câu trả lời nền xanh nhạt, chữ to */
    .answer-card {
        background-color: #f0f7ff;
        border: 2px solid #93c5fd;
        border-left: 7px solid #1d4ed8;
        border-radius: 14px;
        padding: 18px 22px;
        margin-top: 12px;
        margin-bottom: 16px;
        font-size: 19px !important;
        line-height: 1.65;
    }
    /* Tabs chữ to */
    button[data-baseweb="tab"] p {
        font-size: 19px !important;
        font-weight: 700 !important;
        color: #1e40af !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _read_json(path_str: str) -> dict:
    p = Path(path_str)
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


if "avatar_spoken_text" not in st.session_state:
    st.session_state.avatar_spoken_text = (
        "Xin chào! Mời bạn bấm vào câu hỏi hoặc nói vào Micro để tôi giải đáp pháp luật A.I."
    )
if "avatar_audio_b64" not in st.session_state:
    st.session_state.avatar_audio_b64 = None
if "avatar_sentences" not in st.session_state:
    st.session_state.avatar_sentences = [st.session_state.avatar_spoken_text]
if "avatar_autoplay" not in st.session_state:
    st.session_state.avatar_autoplay = False
if "last_qa_result" not in st.session_state:
    st.session_state.last_qa_result = None
if "last_audio_hash" not in st.session_state:
    st.session_state.last_audio_hash = None
if "qa_input_text" not in st.session_state:
    st.session_state.qa_input_text = ""


# --- Sidebar tối giản ---
with st.sidebar:
    st.markdown("# 👩‍⚖️ Pháp luật AI")

    idx_manifest = _read_json("data/manifests/index_manifest.json")
    doc_total = idx_manifest.get("total_documents", 30)
    chunk_total = idx_manifest.get("total_chunks", 302)

    c1, c2 = st.columns(2)
    c1.metric("📄 Văn bản", doc_total)
    c2.metric("📦 Đoạn", chunk_total)

    st.divider()

    presenter_choice = st.radio(
        "🧑 Chọn Người nói:",
        ["👩‍⚖️ Nữ (Minh Anh)", "👨‍⚖️ Nam (Quốc Khánh)"],
        index=0,
    )
    presenter_gender = "female" if "Nữ" in presenter_choice else "male"
    enable_voice_tts = st.toggle("🔊 Tự động phát giọng nói", value=True)

    st.divider()

    jurisdiction = st.selectbox(
        "🌐 Khu vực:",
        ["Tat ca", "VN", "EU", "US", "INTERNATIONAL"],
        format_func=lambda x: {
            "Tat ca": "Tất cả khu vực",
            "VN": "🇻🇳 Việt Nam",
            "EU": "🇪🇺 Châu Âu (EU)",
            "US": "🇺🇸 Hoa Kỳ (US)",
            "INTERNATIONAL": "🌍 Quốc tế",
        }.get(x, x),
    )


def _run_qa_and_voice(question_text: str):
    jfilter = None if jurisdiction == "Tat ca" else jurisdiction
    retrieved = retrieve(
        question=question_text,
        top_k=TOP_K,
        region=jfilter,
    )
    result = answer(
        question=question_text,
        retrieved_chunks=retrieved,
    )
    st.session_state.last_qa_result = result

    raw_ans = result.get("answer") or "Không tìm thấy đủ căn cứ trong kho tài liệu."
    spoken = clean_text_for_speech(raw_ans)

    st.session_state.avatar_spoken_text = spoken
    if enable_voice_tts:
        audio_b64, sents = synthesize_speech_base64(spoken, lang="vi")
        st.session_state.avatar_audio_b64 = audio_b64
        st.session_state.avatar_sentences = sents if sents else [spoken]
        st.session_state.avatar_autoplay = True
    else:
        st.session_state.avatar_audio_b64 = None
        st.session_state.avatar_sentences = [spoken]
        st.session_state.avatar_autoplay = False


# --- Tabs gọn gàng ---
tab_qa, tab_search, tab_datalake = st.tabs([
    "🎙️ Hỏi Đáp & Người Nói",
    "🔍 Tìm Văn Bản",
    "📊 Danh Sách 30 Luật AI",
])

# ===================== TAB 1: HỎI ĐÁP & NGƯỜI NÓI =====================
with tab_qa:
    col_avatar, col_qa = st.columns([5, 7], gap="large")

    with col_qa:
        # 1. Nút chọn nhanh (1 chạm)
        q_cols = st.columns(3)
        sample_q1 = "Luật Trí tuệ nhân tạo 134/2025 quy định gì?"
        sample_q2 = "Chiến lược AI Việt Nam đến 2030 đặt mục tiêu gì?"
        sample_q3 = "EU AI Act cấm những hệ thống AI nào?"

        if q_cols[0].button("🇻🇳 Luật AI Việt Nam", use_container_width=True):
            st.session_state.qa_input_text = sample_q1
            with st.spinner("Đang trả lời..."):
                _run_qa_and_voice(sample_q1)
        if q_cols[1].button("🎯 Chiến lược AI 2030", use_container_width=True):
            st.session_state.qa_input_text = sample_q2
            with st.spinner("Đang trả lời..."):
                _run_qa_and_voice(sample_q2)
        if q_cols[2].button("🇪🇺 Luật AI Châu Âu", use_container_width=True):
            st.session_state.qa_input_text = sample_q3
            with st.spinner("Đang trả lời..."):
                _run_qa_and_voice(sample_q3)

        # 2. Micro nói trực tiếp
        audio_recorded = st.audio_input("🎙️ Bấm Micro để nói câu hỏi:")
        if audio_recorded is not None:
            raw_wav = audio_recorded.getvalue()
            wav_hash = hashlib.md5(raw_wav).hexdigest()
            if wav_hash != st.session_state.last_audio_hash:
                st.session_state.last_audio_hash = wav_hash
                with st.spinner("Đang nghe..."):
                    transcribed = transcribe_vietnamese_audio(raw_wav)
                if transcribed:
                    st.session_state.qa_input_text = transcribed
                    with st.spinner("Đang trả lời..."):
                        _run_qa_and_voice(transcribed)

        # 3. Ô nhập câu hỏi chữ to
        qa_query = st.text_area(
            "✍️ Hoặc nhập câu hỏi tại đây:",
            value=st.session_state.qa_input_text,
            height=85,
            placeholder="Nhập câu hỏi của bạn (Ví dụ: Luật Trí tuệ nhân tạo là gì?)...",
        )

        if st.button("🔊 HỎI & NGHE TRẢ LỜI", key="qa_btn", type="primary", use_container_width=True):
            if qa_query.strip():
                st.session_state.qa_input_text = qa_query.strip()
                with st.spinner("Đang trả lời..."):
                    _run_qa_and_voice(qa_query.strip())

        # 4. Kết quả ngắn gọn, chữ to
        result = st.session_state.last_qa_result
        if result:
            status = result.get("status")
            if status == "answered":
                st.markdown(
                    f'<div class="answer-card">{result["answer"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.warning(result.get("answer") or "Không đủ căn cứ từ tài liệu hiện có.")

            citations = result.get("citations", [])
            if citations:
                with st.expander(f"📚 Xem {len(citations)} nguồn trích dẫn pháp lý"):
                    for cit in citations:
                        loc = cit.get("location") or ""
                        st.markdown(f"**[{cit['source_id']}] {cit['title']}** ({loc})")
                        st.caption(cit.get("excerpt", "")[:260] + "...")
                        if cit.get("source_url"):
                            st.link_button("🔗 Mở văn bản gốc", cit["source_url"])

    with col_avatar:
        avatar_html = build_talking_avatar_html(
            spoken_text=st.session_state.avatar_spoken_text,
            audio_b64=st.session_state.avatar_audio_b64,
            sentences=st.session_state.avatar_sentences,
            presenter_gender=presenter_gender,
            auto_play=st.session_state.avatar_autoplay,
        )
        components.html(avatar_html, height=495, scrolling=False)

        if st.session_state.avatar_audio_b64:
            audio_bytes = base64.b64decode(st.session_state.avatar_audio_b64)
            st.audio(audio_bytes, format="audio/mp3")

# ===================== TAB 2: TÌM VĂN BẢN =====================
with tab_search:
    query = st.text_input(
        "🔍 Nhập từ khóa cần tìm:",
        placeholder="Ví dụ: dữ liệu cá nhân, rủi ro cao, đạo đức AI...",
    )
    if st.button("🔍 Tìm kiếm ngay", key="search_btn", type="primary"):
        if query.strip():
            jfilter = None if jurisdiction == "Tat ca" else jurisdiction
            results = retrieve(question=query, top_k=TOP_K, region=jfilter)
            for i, chunk in enumerate(results, 1):
                with st.expander(f"[{i}] {chunk.get('title', '')}", expanded=(i == 1)):
                    st.markdown(chunk["text"])
                    if chunk.get("source_url"):
                        st.link_button("🔗 Mở nguồn gốc", chunk["source_url"])

# ===================== TAB 3: DANH SÁCH 30 LUẬT AI =====================
with tab_datalake:
    sources_csv = Path("data/sources.csv")
    if sources_csv.exists():
        with open(sources_csv, "r", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        display_rows = [
            {
                "Mã": r.get("document_id"),
                "Tên văn bản AI": r.get("title"),
                "Khu vực": r.get("jurisdiction"),
                "Loại": r.get("doc_type"),
                "Năm": r.get("published_date"),
            }
            for r in rows
        ]
        st.dataframe(display_rows, use_container_width=True, hide_index=True)
