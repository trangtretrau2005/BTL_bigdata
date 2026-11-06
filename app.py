"""
Streamlit application - FR06, FR07, FR08, FR09, FR10.
Owner: Trang (group lead)

Giao dien tra cuu va hoi dap van ban phap luat & chinh sach AI.
Chay: streamlit run app.py
"""
import streamlit as st
import os
from dotenv import load_dotenv
from src.rag.retriever import retrieve
from src.rag.answerer import answer

load_dotenv()

# Config from environment
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "ai_documents")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3")
CHAT_MODEL = os.getenv("CHAT_MODEL", "qwen3:4b")
TOP_K = int(os.getenv("TOP_K", "5"))

st.set_page_config(
    page_title="AI Doc RAG",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Sidebar ---
with st.sidebar:
    st.title("📚 AI Doc RAG")
    st.caption("Tra cuu van ban phap luat & chinh sach AI")

    # TODO: Trang them document count, chunk count, snapshot time tu manifest
    # Vi du:
    # from src.ingestion.manifest import read_manifest
    # manifest = read_manifest("data/manifests/collection_manifest.json")
    # st.metric("Tai lieu", manifest.get("success", "—"))

    st.divider()

    jurisdiction = st.selectbox(
        "🌐 Khu vuc",
        ["Tat ca", "VN", "EU", "International", "ASEAN"],
        help="Loc ket qua theo khu vuc dia ly",
    )
    doc_filter = st.text_input(
        "📄 Loc theo ten/ID van ban (tuy chon)",
        placeholder="e.g., eu_ai_act_2024_1689",
    )
    top_k = st.slider("So ket qua toi da", min_value=1, max_value=10, value=TOP_K)

    st.divider()
    st.caption(f"Model embed: `{EMBEDDING_MODEL}`")
    st.caption(f"Model chat: `{CHAT_MODEL}`")
    st.caption(f"Qdrant: `{QDRANT_URL}`")

# --- Main area ---
tab_search, tab_qa = st.tabs(["🔍 Tra cuu", "💬 Hoi dap"])

# ===================== TAB TRA CUU =====================
with tab_search:
    st.subheader("Tim kiem ngu nghia")
    st.caption("Nhap tu khoa hoac cau hoi de tim cac doan van ban lien quan nhat.")

    query = st.text_area(
        "Nhap cau hoi hoac tu khoa",
        max_chars=2000,
        height=100,
        placeholder="Vi du: EU AI Act phan loai he thong rui ro cao nhu the nao?",
    )

    if st.button("🔍 Tim kiem", key="search_btn", type="primary"):
        if not query.strip():
            st.warning("Vui long nhap cau hoi hoac tu khoa.")
        else:
            with st.spinner("Dang tim kiem..."):
                try:
                    # region=None nghia la khong loc; "Tat ca" => None
                    jfilter = None if jurisdiction == "Tat ca" else jurisdiction
                    results = retrieve(
                        question=query,
                        top_k=top_k,
                        region=jfilter,
                        document_id=doc_filter or None,
                    )
                    if not results:
                        st.info("Khong tim thay ket qua phu hop. Thu mo rong bo loc hoac doi tu khoa.")
                    else:
                        st.success(f"Tim thay {len(results)} ket qua")
                        for i, chunk in enumerate(results, 1):
                            score = chunk.get("score", 0)
                            location = chunk.get("article") or chunk.get("section") or ""
                            with st.expander(
                                f"[{i}] {chunk.get('title', 'Khong ro')} — Score: {score:.3f}",
                                expanded=(i == 1),
                            ):
                                cols = st.columns([3, 1])
                                with cols[0]:
                                    st.markdown(f"**📌 Vi tri:** {location or '—'}")
                                    st.markdown(
                                        f"**🌐 Khu vuc:** `{chunk.get('region', '—')}`"
                                    )
                                with cols[1]:
                                    if chunk.get("source_url"):
                                        st.link_button("🔗 Xem nguon", chunk["source_url"])
                                st.divider()
                                st.markdown(chunk["text"])
                except NotImplementedError:
                    st.error(
                        "⚠️ Chuc nang retrieve() chua duoc implement. "
                        "Thanh can hoan thien src/rag/retriever.py"
                    )
                except Exception as e:
                    st.error(f"Loi ket noi: {e}")
                    st.info("Kiem tra Qdrant va Ollama dang chay, sau do thu lai.")

# ===================== TAB HOI DAP =====================
with tab_qa:
    st.subheader("Hoi dap co trich dan")
    st.caption("Dat cau hoi — he thong se tim nguon phu hop va sinh cau tra loi.")

    qa_query = st.text_area(
        "Cau hoi",
        max_chars=2000,
        height=100,
        key="qa_input",
        placeholder="Vi du: Chien luoc AI quoc gia Viet Nam dat muc tieu gi den nam 2030?",
    )

    if st.button("💬 Hoi dap", key="qa_btn", type="primary"):
        if not qa_query.strip():
            st.warning("Vui long nhap cau hoi.")
        else:
            with st.spinner("Dang tim kiem nguon va sinh cau tra loi..."):
                try:
                    jfilter = None if jurisdiction == "Tat ca" else jurisdiction

                    # Buoc 1: Retrieve — lay cac chunk lien quan
                    retrieved = retrieve(
                        question=qa_query,
                        top_k=top_k,
                        region=jfilter,
                        document_id=doc_filter or None,
                    )

                    # Buoc 2: Generate answer — dung chunks da lay, khong goi retrieve lan 2
                    result = answer(
                        question=qa_query,
                        retrieved_chunks=retrieved,
                    )

                    # Render ket qua
                    status = result.get("status")
                    if status == "answered":
                        st.success("✅ Cau tra loi")
                        st.markdown(result["answer"])
                    elif status == "insufficient_evidence":
                        st.warning("⚠️ Khong du can cu tu tai lieu hien co.")
                        if result.get("answer"):
                            st.markdown(result["answer"])
                    elif status == "error":
                        st.error(f"❌ Loi sinh cau tra loi: {result.get('error_message')}")
                        st.info("Cac nguon tim duoc van hien thi ben duoi.")

                    # Render citations
                    citations = result.get("citations", [])
                    if citations:
                        st.divider()
                        st.subheader("📚 Nguon tham khao")
                        for cit in citations:
                            with st.expander(
                                f"[{cit['source_id']}] {cit['title']}",
                                expanded=False,
                            ):
                                if cit.get("location"):
                                    st.markdown(f"**📌 Vi tri:** {cit['location']}")
                                st.markdown(f"> {cit['excerpt']}...")
                                if cit.get("source_url"):
                                    st.link_button("🔗 Xem tai lieu goc", cit["source_url"])

                    # Timings
                    timings = result.get("timings", {})
                    if timings.get("generation_ms"):
                        st.caption(f"⏱ Sinh cau tra loi: {timings['generation_ms']}ms")
                    if timings.get("retrieval_ms"):
                        st.caption(f"⏱ Tim kiem: {timings['retrieval_ms']}ms")

                except NotImplementedError as e:
                    st.error(f"⚠️ Chuc nang chua implement: {e}")
                except Exception as e:
                    st.error(f"Loi: {e}")
                    st.info("Kiem tra Qdrant, Ollama dang chay va da co du lieu index.")
