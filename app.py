"""AI Policy Library: focused, source-grounded legal research."""
from __future__ import annotations
import hashlib
import json
import os
from html import escape
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from src.rag.answerer import answer
from src.rag.avatar_component import build_talking_avatar_html
from src.rag.retriever import retrieve
from src.rag.tts import clean_text_for_speech, synthesize_speech, split_into_tts_chunks, transcribe_vietnamese_audio
from src.catalog import load_inventory
from src.updates.service import start_update, get_update_status, ACTIVE, UpdateBusy
from src.ingestion.uploads import EXTENSIONS, upload_catalog, uploaded_file

load_dotenv()
TOP_K = int(os.getenv("TOP_K", "5"))
st.set_page_config(page_title="Thư viện Chính sách AI", page_icon="⚖", layout="wide")
st.markdown("""
<style>
:root { --ink:#172d3a; --muted:#66737b; --gold:#b48a47; --paper:#faf8f3; }
html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background:var(--paper); }
html, body, .stApp, input, textarea, button, select,
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"],
[data-baseweb="select"], [data-baseweb="tab"], [data-testid="stMetricValue"] {
  font-family:"Times New Roman",Times,serif !important;
}
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li { font-size:19px; line-height:1.7; color:var(--ink); }
[data-testid="stSidebar"] { background:#f0eee7; border-right:1px solid #deddd4; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { font-size:17px; }
.block-container { max-width:1280px; padding-top:2rem; padding-bottom:3rem; }
h1,h2,h3,h4 { color:var(--ink) !important; font-family:"Times New Roman",Times,serif !important; }
h2 { font-size:29px !important; font-weight:500 !important; letter-spacing:-.5px; }
h3 { font-size:23px !important; font-weight:500 !important; }
.brand { font-size:25px; color:var(--ink); line-height:1.2; margin-bottom:8px; }
.brand small { display:block; font-size:11px; letter-spacing:2.8px; margin-top:10px; color:#8d713e; }
.hero { display:flex; align-items:center; justify-content:space-between; gap:28px; padding:36px 42px; margin:0 0 24px;
  background:#173443; border-radius:7px; overflow:hidden; border:1px solid #254858; }
.hero-copy { max-width:670px; }
.eyebrow { font-size:12px; letter-spacing:3px; color:#d9bd89; text-transform:uppercase; margin-bottom:17px; }
.hero h1 { font-size:46px !important; font-weight:400 !important; color:#fffdf7 !important; line-height:1.13; margin:0 0 16px; letter-spacing:-1px; }
.hero p { color:#d4dfe2 !important; font-size:19px !important; line-height:1.6 !important; margin:0; max-width:560px; }
.hero-art { width:245px; min-width:190px; opacity:.95; }
.hero-foot { display:flex; gap:24px; margin-top:23px; color:#e1ccaa; font-size:13px; letter-spacing:.4px; }
.status-line { font-size:15px; color:#58666c; padding:2px 0; }
.status-dot { display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:8px; }
.section-kicker { color:#92733f; font-size:12px; text-transform:uppercase; letter-spacing:2px; margin:10px 0 8px; }
.empty-state { border:1px dashed #d6d3c8; background:#f5f3ec; padding:24px 28px; border-radius:5px; margin-top:20px; }
.empty-state strong { display:block; color:#243d49; font-size:22px; font-weight:400; margin-bottom:7px; }
.empty-state span { color:#6c777b; font-size:17px; line-height:1.7; }
[data-testid="stTextArea"] textarea, [data-testid="stTextInput"] input { background:#fffefb !important; color:#172d3a !important; font-size:19px !important; line-height:1.5; }
[data-testid="stTextArea"] > div, [data-testid="stTextInput"] > div { border-radius:5px !important; }
[data-testid="stButton"] button { border-radius:4px !important; font-size:17px !important; border-color:#d3d2c9; }
[data-testid="stButton"] button[kind="primary"] { background:#173443; border-color:#173443; color:white; }
[data-testid="stButton"] button[kind="primary"] p { color:white !important; }
[data-testid="stTabs"] [data-baseweb="tab-list"] { gap:30px; border-bottom:1px solid #deddd4; margin-bottom:23px; }
[data-testid="stTabs"] [data-baseweb="tab"] { padding:9px 0 13px; font-size:19px !important; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background:#b48a47; height:2px; }
[data-testid="stExpander"] { background:#fffefb; border-color:#e2dfd5; border-radius:5px; }
[data-testid="stCaptionContainer"] p { font-size:15px !important; color:#68777d !important; }
[data-testid="stMetricLabel"] p { font-size:14px !important; }
[data-testid="stMetricValue"] { font-size:29px !important; color:var(--ink); }
footer { visibility:hidden; }
@media(max-width:850px) { .hero { padding:26px 24px; } .hero h1 { font-size:34px !important; } .hero-art { display:none; } .hero-foot { flex-wrap:wrap; gap:10px 20px; } }
</style>
""", unsafe_allow_html=True)
st.markdown('<style>' + Path('src/rag/library.css').read_text(encoding='utf-8') + '</style>', unsafe_allow_html=True)


def _read_json(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@st.cache_data(ttl=30, show_spinner=False)
def _inventory() -> tuple[list[dict], dict, dict]:
    return load_inventory()


@st.cache_data(ttl=20, show_spinner=False)
def _service_status() -> dict:
    result = {"qdrant": False, "ollama": False, "embedding": False, "chat": False}
    try:
        name = os.getenv("QDRANT_COLLECTION", "ai_documents")
        info = requests.get(os.getenv("QDRANT_URL", "http://localhost:6333").rstrip("/") + "/collections/" + name, timeout=1.5)
        info.raise_for_status()
        result["qdrant"] = (info.json().get("result", {}).get("points_count") or 0) > 0
    except (requests.RequestException, ValueError, TypeError):
        pass
    try:
        response = requests.get(os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/") + "/api/tags", timeout=1.5)
        response.raise_for_status()
        names = {m.get("name", "") for m in response.json().get("models", [])}
        result["ollama"] = True
        for key, env, default in (("embedding", "EMBEDDING_MODEL", "bge-m3"), ("chat", "CHAT_MODEL", "qwen3:4b")):
            model = os.getenv(env, default)
            result[key] = model in names or (":" not in model and model + ":latest" in names)
    except (requests.RequestException, ValueError, TypeError):
        pass
    return result


def _upload_download(source: dict, key: str):
    url = source.get('source_url') or ''
    if not url.startswith('upload://'):
        return
    stored = uploaded_file(url.removeprefix('upload://'))
    if stored:
        path, entry = stored
        st.caption('Tệp do người dùng tải lên · Chưa xác minh nguồn chính thức')
        st.download_button('Tải tệp gốc', data=path.read_bytes(), file_name=entry['original_filename'], key=key)


@st.fragment(run_every=3)
def _update_panel():
    state = get_update_status()
    busy = state.get('status') in ACTIVE
    with st.expander('Tải tài liệu lên'):
        generation = st.session_state.get('upload_widget_version', 0)
        files = st.file_uploader('Chọn tài liệu', type=sorted(ext[1:] for ext in EXTENSIONS),
            accept_multiple_files=True, key=f'upload_files_{generation}', disabled=busy)
        st.caption('Chọn tệp rồi nhấn Cập nhật dữ liệu. Tối đa 10 tệp, 50 MB/tệp, tổng 100 MB. PDF scan ảnh cần OCR trước.')
        region = st.selectbox('Khu vực của tệp', ['VN', 'EU', 'US', 'ASEAN', 'INTERNATIONAL', 'UNKNOWN'],
            format_func=lambda value: REGIONS.get(value, 'Chưa xác định'), key='upload_region', disabled=busy)
        language = st.selectbox('Ngôn ngữ của tệp', ['vi', 'en'], format_func=lambda value: 'Tiếng Việt' if value == 'vi' else 'Tiếng Anh',
            key='upload_language', disabled=busy)
        stored = upload_catalog()
        if stored:
            chosen = st.selectbox('Tệp đã lưu', list(stored), format_func=lambda value: stored[value]['original_filename'], key='stored_upload')
            row = stored[chosen]
            statuses = {'pending': 'Chờ xử lý', 'parsed': 'Đã đọc, chờ lập chỉ mục', 'indexed': 'Đã sẵn sàng tra cứu',
                'duplicate': 'Nội dung đã có trong thư viện', 'failed': 'Chưa đọc được tệp'}
            st.caption(statuses.get(row.get('upload_status'), 'Đã lưu tệp'))
            if row.get('error'):
                st.caption(row['error'])
            _upload_download(row, 'download_stored_upload')
    with st.expander('Nguồn cập nhật tự động'):
        fetch_api = st.checkbox('Lấy thêm văn bản từ API', value=True, key='fetch_api', disabled=busy)
        config = _read_json('data/api_sources.json')
        for source in config.values():
            if source.get('enabled'):
                st.caption(source['name'])
        st.caption('Lấy toàn văn qua API. Lần đầu kiểm tra văn bản ban hành trong 2 năm gần đây; các lượt sau đọc tăng dần và kiểm tra trùng.')
        limit = st.selectbox('Văn bản mới/cập nhật tối đa mỗi nguồn / lượt', [10, 20, 50], index=1, key='update_limit', disabled=busy or not fetch_api)
    if st.button('Cập nhật dữ liệu', key='update_data_btn', use_container_width=True, disabled=busy):
        try:
            options = {'max_documents': limit}
            if not fetch_api:
                options['providers'] = []
            if files:
                options['uploads'] = [{'name': file.name, 'content': file.getvalue(), 'region': region, 'language': language} for file in files]
            state = start_update(**options)
            if files:
                st.session_state.upload_widget_version = generation + 1
            busy = True
        except UpdateBusy:
            st.info('Đã có một lượt cập nhật đang chạy.')
        except ValueError as exc:
            st.error(str(exc))
        except Exception:
            st.error('Chưa khởi động được cập nhật. Bạn thử lại sau.')
    if busy:
        progress = state.get('progress', 0)
        if state.get('stage') == 'index':
            indexing = _read_json('data/manifests/index_progress.json')
            if state.get('job_id', '__none__') in indexing.get('snapshot', ''):
                progress = 55 + 30 * indexing.get('completed_chunks', 0) / max(1, indexing.get('total_chunks', 1))
        st.progress(min(100, int(progress)), text=state.get('message') or 'Đang cập nhật dữ liệu…')
        st.caption('Bạn vẫn có thể hỏi đáp. Lượt cập nhật tiếp tục khi bạn chuyển tab.')
    elif state:
        status = state.get('status')
        if status in {'completed', 'no_changes', 'partial'}:
            st.caption(state.get('message', 'Đã kiểm tra nguồn dữ liệu.'))
            st.caption(f"Thêm {state.get('added_documents', 0)} · Đang tra cứu {state.get('active_documents', 0)} văn bản")
        else:
            st.warning(state.get('message', 'Lượt cập nhật trước chưa hoàn tất.'))
        if state.get('finished_at'):
            checked = datetime.fromisoformat(state['finished_at']).astimezone(ZoneInfo('Asia/Ho_Chi_Minh'))
            st.caption('Kiểm tra gần nhất: ' + checked.strftime('%d/%m/%Y %H:%M'))
        with st.expander('Kết quả từng nguồn'):
            uploads = state.get('upload_report', {})
            if uploads:
                st.caption(f"Tệp tải lên: đọc được {uploads.get('parsed', 0)} tệp, {uploads.get('failed', 0)} tệp lỗi.")
            for source in state.get('collection_report', {}).get('providers', {}).values():
                label = 'chưa kết nối được' if source.get('status') == 'error' else ('chưa hoàn tất' if source.get('status') == 'partial' else 'đã kiểm tra')
                st.caption(f"{source['name']}: {label}; {source['scanned']} bản ghi, {source['changed']} thay đổi, {source['failed']} lỗi toàn văn.")
                if source.get('backlog') or source.get('scan_limited'):
                    st.caption('Còn dữ liệu ngoài giới hạn lượt này; có thể cập nhật tiếp.')
            for error in state.get('warnings', state.get('collection_report', {}).get('errors', [])):
                st.caption(str(error.get('provider', 'Nguồn')) + ': ' + str(error.get('error', ''))[:300])
            if state.get('error'):
                st.caption(state['error'])
        if status in {'completed', 'no_changes', 'partial'} and st.session_state.get('seen_update_job') != state.get('job_id'):
            st.session_state.seen_update_job = state['job_id']
            _inventory.clear()
            _service_status.clear()
            st.rerun()


rows, manifest, counts = _inventory()
services = _service_status()
for key, value in {"last_qa_result": None, "last_question": "", "qa_question": "", "last_audio_hash": None,
                   "avatar_spoken_text": "", "avatar_audio_b64": None, "avatar_sentences": []}.items():
    if key not in st.session_state:
        st.session_state[key] = value
REGIONS = {"ALL": "Tất cả khu vực", "VN": "Việt Nam", "EU": "Liên minh châu Âu", "US": "Hoa Kỳ", "ASEAN": "ASEAN", "INTERNATIONAL": "Quốc tế"}

with st.sidebar:
    st.markdown('<div class="brand">⚖ Thư viện Chính sách AI<small>AI POLICY LIBRARY</small></div>', unsafe_allow_html=True)
    st.caption("Tra cứu có căn cứ · Đối chiếu nguồn gốc")
    st.divider()
    st.markdown("### Phạm vi tra cứu")
    jurisdiction = st.selectbox("Khu vực", list(REGIONS), format_func=REGIONS.get, key="jurisdiction")
    filtered_catalog = [r for r in rows if jurisdiction == "ALL" or r.get("jurisdiction", "").upper() == jurisdiction]
    doc_options = {r["document_id"]: r.get("title") or r["document_id"] for r in filtered_catalog if r.get("document_id") and r.get('_index_status') == 'Đã lập chỉ mục'}
    document_id = st.selectbox("Văn bản cụ thể", [""] + list(doc_options), format_func=lambda x: doc_options.get(x, "Tất cả văn bản"), key="document_filter")
    with st.expander("Giọng đọc & hiển thị"):
        enable_voice = st.toggle("Hiện khung giọng đọc", value=True, key="enable_voice")
        speech_speed = st.select_slider("Tốc độ đọc", ["Chậm rãi", "Vừa phải", "Nhanh"], value="Vừa phải", key="speech_speed")
        show_avatar = st.toggle("Hiện người thuyết trình", value=True, key="show_avatar")
        st.caption("Một giọng nữ tiếng Việt. Khi dịch vụ Hoài My chưa sẵn sàng, khung đọc thông báo giọng dự phòng đang dùng.")
    voice = 'vi-VN-HoaiMyNeural'
    rate = {"Chậm rãi": "-12%", "Vừa phải": "-5%", "Nhanh": "+5%"}[speech_speed]
    st.divider()
    a, b = st.columns(2)
    a.metric("Đang tra cứu", counts['active'])
    b.metric("Đoạn có nguồn", counts['chunks'])
    with st.expander('Tình trạng nguồn dữ liệu'):
        st.caption(f"{counts['catalog']} mục nguồn đang theo dõi")
        st.caption(f"{counts['active']} văn bản đã sẵn sàng hỏi đáp")
        st.caption(f"{counts['pending']} mục chưa sẵn sàng: chưa tải, thiếu toàn văn, bị chặn hoặc chưa lập chỉ mục.")
    _update_panel()
    ready = services["qdrant"] and services["embedding"] and services["chat"]
    label, color = ("Sẵn sàng hỏi đáp", "#39816d") if ready else ("Dịch vụ chưa sẵn sàng", "#b48442")
    st.markdown(f'<div class="status-line"><span class="status-dot" style="background:{color}"></span>{label}</div>', unsafe_allow_html=True)
    with st.expander("Trạng thái hệ thống"):
        for name, ok in (("Chỉ mục Qdrant", services["qdrant"]), ("Mô hình embedding", services["embedding"]), ("Mô hình trả lời", services["chat"])):
            st.caption(("✓ " if ok else "○ ") + name)
        if st.button("Kiểm tra lại", use_container_width=True):
            _service_status.clear()
            _inventory.clear()
            st.rerun()

st.markdown("""
<section class="hero">
  <div class="hero-copy">
    <div class="eyebrow">Nghiên cứu · Chính sách · Trí tuệ nhân tạo</div>
    <h1>Hiểu chính sách AI.<br>Đi từ nguồn tin cậy.</h1>
    <p>Đặt câu hỏi, tìm điều khoản liên quan và đối chiếu từng nhận định với văn bản trong thư viện.</p>
    <div class="hero-foot"><span>01 &nbsp; Đặt câu hỏi</span><span>02 &nbsp; Đọc dẫn chứng</span><span>03 &nbsp; Mở nguồn gốc</span></div>
  </div>
  <svg class="hero-art" viewBox="0 0 260 240" xmlns="http://www.w3.org/2000/svg" aria-label="Minh họa hồ sơ chính sách và cán cân pháp luật" role="img">
    <defs><linearGradient id="paper" x2="1" y2="1"><stop stop-color="#faf5e9"/><stop offset="1" stop-color="#d9c5a2"/></linearGradient></defs>
    <circle cx="140" cy="116" r="102" fill="none" stroke="#52717b" stroke-width=".7"/>
    <circle cx="140" cy="116" r="82" fill="none" stroke="#52717b" stroke-width=".7" stroke-dasharray="2 8"/>
    <path d="M64 72h114v148H64z" fill="#0f2936" stroke="#66828a" transform="rotate(-12 121 146)"/>
    <path d="M86 40h89l26 27v137H86z" fill="url(#paper)"/>
    <path d="M175 40v28h26" fill="none" stroke="#a28a61"/>
    <path d="M105 157h76M105 170h64M105 183h47" stroke="#ae986f" stroke-width="2"/>
    <path d="M143 78v59m-22 4h44m-34-63h24m-42 18h60m-55 0-12 24h25zm50 0-12 24h25z" fill="none" stroke="#244452" stroke-width="2.7" stroke-linejoin="round"/>
    <circle cx="143" cy="91" r="4" fill="#b48a47"/>
    <circle cx="211" cy="164" r="22" fill="#244b59" stroke="#c9aa74"/>
    <path d="m202 164 6 6 12-13" fill="none" stroke="#e2c798" stroke-width="2"/>
    <path d="M34 184h23M45 173v23M218 45h16M226 37v16" stroke="#bca174" stroke-width="1"/>
  </svg>
</section>
""", unsafe_allow_html=True)
st.markdown(f'''<div class="overview">
<div><strong>{counts['active']}</strong><span>văn bản đang tra cứu</span></div>
<div><strong>{counts['chunks']:,}</strong><span>đoạn có dẫn nguồn</span></div>
<div><strong>Việt Nam & quốc tế</strong><span>Pháp luật · Quản trị · Đạo đức AI</span></div>
</div>''', unsafe_allow_html=True)


@st.cache_data(ttl=600, max_entries=12, show_spinner=False)
def _prepare_speech(spoken: str, selected_voice: str, selected_rate: str) -> dict:
    bundle = synthesize_speech(spoken, lang='vi', voice=selected_voice, rate=selected_rate)
    if not bundle.get('segments'):
        raise RuntimeError(bundle.get('error') or 'Chưa tạo được giọng đọc.')
    return bundle


def _speech_panel(spoken: str, prefix: str, *, preview: bool = False) -> None:
    request_key = hashlib.sha256(json.dumps([spoken, voice, rate], ensure_ascii=False).encode('utf-8')).hexdigest()
    saved = st.session_state.get(prefix + '_speech', {})
    current = saved.get('key') == request_key
    label = 'Nghe thử giọng đọc' if preview else ('Tạo lại âm thanh' if current else 'Tạo giọng đọc cho câu trả lời')
    if st.button(label, key=prefix + '_generate', use_container_width=False):
        with st.spinner('Đang chuẩn bị giọng đọc tiếng Việt…'):
            try:
                bundle = _prepare_speech(spoken, voice, rate)
            except Exception:
                bundle = {'segments': [], 'provider': None, 'playback_rate': 1 + float(rate.rstrip('%')) / 100}
                st.info('Dịch vụ âm thanh chưa sẵn sàng. Nút Phát sẽ thử giọng tiếng Việt có trên thiết bị.')
        saved = {'key': request_key, 'bundle': bundle}
        st.session_state[prefix + '_speech'] = saved
        current = True
    bundle = saved.get('bundle', {}) if current else {}
    if not current:
        st.caption('Nhấn Tạo giọng đọc để nghe. Khi đổi giọng hoặc tốc độ, hãy tạo lại âm thanh.')
    components.html(build_talking_avatar_html(
        spoken_text=spoken if current else '', segments=bundle.get('segments', []),
        sentences=split_into_tts_chunks(spoken, 170) if current else [],
        presenter_gender='female',
        provider=bundle.get('provider'), playback_rate=bundle.get('playback_rate', 1.0),
        show_avatar=show_avatar, auto_play=False,
        device_local_only=voice.startswith('local:'),
        status_label='Sẵn sàng' if current else 'Chưa tạo âm thanh',
    ), height=490 if show_avatar else 450, scrolling=False)


def _run_qa(question: str) -> None:
    st.session_state.last_question = question
    st.session_state.last_scope = REGIONS[jurisdiction] + (" · " + doc_options[document_id] if document_id in doc_options else "")
    st.session_state.avatar_audio_b64 = None
    try:
        result = answer(question=question, top_k=TOP_K, region=None if jurisdiction == "ALL" else jurisdiction, document_id=document_id or None)
    except Exception:
        result = {"status": "error", "answer": None, "citations": [], "error_message": "Chưa kết nối được dịch vụ tra cứu. Hãy kiểm tra trạng thái hệ thống và thử lại."}
    st.session_state.last_qa_result = result
    if result.get("status") == "answered":
        spoken = clean_text_for_speech(result.get("answer") or "")
        st.session_state.avatar_spoken_text = spoken
        st.session_state.avatar_sentences = [spoken]


def _choose_example(question: str) -> None:
    st.session_state.qa_question = question


def _sources(citations: list[dict]) -> None:
    st.markdown("### Nguồn đối chiếu")
    for citation in citations:
        with st.expander(f"[{citation.get('source_id', '?')}] {citation.get('title') or 'Văn bản nguồn'}"):
            st.caption(citation.get("location") or "Chưa xác định vị trí")
            st.write(citation.get("excerpt") or "Chưa có đoạn trích.")
            if (citation.get("source_url") or "").startswith(("https://", "http://")):
                st.link_button("Mở văn bản gốc ↗", citation["source_url"])
            _upload_download(citation, 'citation_download_' + str(citation.get('source_id')))


tab_qa, tab_search, tab_library = st.tabs(["Hỏi đáp có dẫn chứng", "Tìm văn bản", "Thư viện tài liệu"])
with tab_qa:
    st.markdown('<div class="section-kicker">Bắt đầu từ điều bạn cần biết</div>', unsafe_allow_html=True)
    st.markdown('### Bạn muốn tìm hiểu điều gì?')
    question = st.text_area("Câu hỏi của bạn", key="qa_question", height=118, placeholder="Ví dụ: EU AI Act quy định những hành vi AI nào bị cấm?", label_visibility="collapsed")
    submit_col, _ = st.columns([2, 3])
    if submit_col.button("Tra cứu & trả lời  →", type="primary", key="qa_btn", use_container_width=True):
        if question.strip():
            with st.spinner("Đang tìm dẫn chứng và xây dựng câu trả lời…"):
                _run_qa(question.strip())
        else:
            st.warning("Bạn hãy nhập câu hỏi cần tra cứu.")
    with st.expander("Gợi ý câu hỏi hoặc nhập bằng giọng nói"):
        examples = [("AI bị cấm tại EU", "EU AI Act cấm những hành vi trí tuệ nhân tạo nào?"), ("Quản trị rủi ro", "NIST AI RMF gồm những chức năng quản trị rủi ro cốt lõi nào?"), ("Đạo đức AI", "UNESCO đề xuất những nguyên tắc đạo đức nào cho trí tuệ nhân tạo?")]
        for col, (label, sample) in zip(st.columns(3), examples):
            col.button(label, on_click=_choose_example, args=(sample,), use_container_width=True)
        audio_input = st.audio_input("Nói câu hỏi bằng tiếng Việt")
        if audio_input is not None:
            audio_hash = hashlib.sha256(audio_input.getvalue()).hexdigest()
            if audio_hash != st.session_state.last_audio_hash:
                st.session_state.last_audio_hash = audio_hash
                with st.spinner("Đang nhận diện giọng nói…"):
                    transcribed = transcribe_vietnamese_audio(audio_input.getvalue())
                if transcribed:
                    with st.spinner("Đang tra cứu câu hỏi vừa nghe…"):
                        _run_qa(transcribed)
                else:
                    st.warning("Chưa nhận diện được âm thanh. Bạn thử nói lại hoặc nhập câu hỏi.")
    result = st.session_state.last_qa_result
    if result:
        st.divider()
        st.caption("CÂU HỎI ĐANG ĐỐI CHIẾU")
        st.markdown(f"### {st.session_state.last_question}")
        st.caption(st.session_state.get("last_scope", ""))
        if result.get("status") == "answered":
            with st.container(border=True):
                st.markdown(result.get("answer") or "")
            if result.get("retrieval_mode") == "local":
                st.info("Kết quả sử dụng tìm kiếm từ khóa trong dữ liệu local.")
            if result.get('answer_mode') == 'curated_summary':
                st.caption('Bản tóm tắt biên tập theo đúng phiên bản điều khoản nguồn; không phải nội dung LLM vừa sinh.')
            if enable_voice:
                _speech_panel(clean_text_for_speech(result.get('answer') or ''), 'answer')
        elif result.get("status") == "insufficient_evidence":
            st.info(result.get("answer") or "Chưa tìm thấy đủ căn cứ trong thư viện. Bạn thử nêu rõ tên văn bản hoặc điều khoản.")
        else:
            st.error("Chưa thể tạo câu trả lời. Kiểm tra các dịch vụ trong thanh bên rồi thử lại.")
        if result.get("citations"):
            _sources(result["citations"])
    else:
        st.markdown('<div class="empty-state"><strong>Mỗi câu trả lời bắt đầu từ một nguồn.</strong><span>Nêu rõ chủ đề, khu vực hoặc số hiệu văn bản. Các đoạn dẫn chứng sẽ xuất hiện cùng câu trả lời để bạn kiểm tra.</span></div>', unsafe_allow_html=True)
    if enable_voice:
        with st.expander('Khám phá trợ lý giọng nói', expanded=not bool(result)):
            st.caption('Nghe thử một đoạn ngắn. Sau khi có câu trả lời, bạn có thể nghe toàn bộ nội dung cùng người thuyết trình.')
            _speech_panel('Xin chào, tôi là trợ lý tra cứu chính sách trí tuệ nhân tạo. Hãy cùng tìm hiểu quy định, đọc dẫn chứng, và đối chiếu văn bản gốc.', 'preview', preview=True)
    st.caption("Câu trả lời dựa trên tập tài liệu đã thu thập. Hãy đối chiếu văn bản gốc và tình trạng hiệu lực trước khi sử dụng.")

with tab_search:
    st.markdown("### Tìm đoạn văn bản liên quan")
    query = st.text_input("Từ khóa hoặc nội dung cần tìm", placeholder="Quản trị AI, dữ liệu cá nhân, hệ thống rủi ro cao…")
    if st.button("Tìm trong thư viện", key="search_btn", type="primary"):
        if query.strip():
            try:
                with st.spinner("Đang tìm văn bản…"):
                    hits = retrieve(question=query.strip(), top_k=TOP_K, region=None if jurisdiction == "ALL" else jurisdiction, document_id=document_id or None)
                if not hits:
                    st.info("Không tìm thấy đoạn phù hợp với phạm vi đã chọn.")
                for i, hit in enumerate(hits, 1):
                    with st.expander(f"{i:02d} · {hit.get('title') or 'Văn bản nguồn'}", expanded=i == 1):
                        location = [str(hit[k]) for k in ("article", "section") if hit.get(k)]
                        st.caption(" · ".join(location) or "Đoạn trích từ tài liệu")
                        st.write(hit.get("text", ""))
                        if (hit.get("source_url") or "").startswith(("https://", "http://")):
                            st.link_button("Mở văn bản gốc ↗", hit["source_url"])
                        _upload_download(hit, f'search_download_{i}')
            except Exception:
                st.error("Chưa kết nối được dịch vụ tìm kiếm. Kiểm tra trạng thái hệ thống và thử lại.")
        else:
            st.info("Nhập từ khóa hoặc một câu mô tả nội dung cần tìm.")

with tab_library:
    st.markdown("### Danh mục tài liệu")
    st.caption("Gồm văn bản pháp luật, chính sách, khuyến nghị và khung quản trị. Danh mục không đồng nghĩa mọi văn bản còn hiệu lực hoặc đã được lập chỉ mục.")
    title_filter = st.text_input("Lọc theo tên hoặc số hiệu", placeholder="NIST, UNESCO, 2024/1689…")
    indexed_only = st.toggle('Chỉ hiện văn bản đang tra cứu được', value=True, key='indexed_only')
    visible = [r for r in filtered_catalog if not document_id or r.get("document_id") == document_id]
    if indexed_only:
        visible = [r for r in visible if r.get('_index_status') == 'Đã lập chỉ mục']
    if title_filter.strip():
        term = title_filter.casefold().strip()
        visible = [r for r in visible if term in (r.get("title", "") + " " + r.get("document_id", "")).casefold()]
    st.caption(f"{len(visible)} tài liệu phù hợp")
    if visible:
        pages = max(1, (len(visible) + 11) // 12)
        page = st.selectbox('Trang tài liệu', range(1, pages + 1), format_func=lambda number: f'Trang {number} / {pages}', key='library_page')
        cards = []
        for row in visible[(page - 1) * 12:page * 12]:
            active = row.get('_index_status') == 'Đã lập chỉ mục'
            region = REGIONS.get(row.get('jurisdiction', '').upper(), row.get('jurisdiction', ''))
            url = row.get('source_url') or ''
            link = f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">Đọc nguồn gốc ↗</a>' if url.startswith('https://') else ''
            cards.append(f'''<article class="document-card"><div class="document-meta"><span>{escape(region)}</span><span class="{'indexed' if active else 'pending'}">{'Có thể tra cứu' if active else 'Chưa lập chỉ mục'}</span></div>
            <h4>{escape(row.get('title') or row['document_id'])}</h4><p>{escape(row.get('source_org') or 'Cơ quan ban hành')}</p><div class="document-bottom"><span>{escape(row.get('published_date') or 'Chưa rõ ngày ban hành')}</span>{link}</div></article>''')
        st.markdown('<div class="document-grid">' + ''.join(cards) + '</div>', unsafe_allow_html=True)
    else:
        st.info("Không có tài liệu khớp bộ lọc hiện tại.")
