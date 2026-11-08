"""Deterministic, article-aware overlapping chunks, with citations metadata."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ARTICLE_RE = re.compile(
    r"(?:^|\n)\s*((?:Điều|ĐIỀU|Article|ARTICLE|Section|SECTION)\s+\d+[A-Za-z0-9\.]*)",
    re.MULTILINE,
)
SECTION_RE = re.compile(
    r"(?:^|\n)\s*((?:Chương|CHƯƠNG|Chapter|CHAPTER|Mục|MỤC|Part|PART)\s+[IVXLCDM0-9]+)",
    re.MULTILINE,
)
PAGE_RE = re.compile(r"\[Trang\s+(\d+)\]", re.IGNORECASE)


def extract_location_meta(text: str) -> dict:
    """Trích xuất Điều (article), Chương/Mục (section) và Trang (page_start) từ đoạn văn bản."""
    art_match = ARTICLE_RE.search(text)
    sec_match = SECTION_RE.search(text)
    pages = [int(m) for m in PAGE_RE.findall(text)]

    return {
        "article": art_match.group(1).strip() if art_match else None,
        "section": sec_match.group(1).strip() if sec_match else None,
        "page_start": min(pages) if pages else None,
        "page_end": max(pages) if pages else None,
    }


def chunk_text(text: str, size: int = 1000, overlap: int = 150):
    if not 0 <= overlap < size:
        raise ValueError("Require 0 <= overlap < size")
    if not text.strip():
        return
    start, total = 0, len(text)
    while start < total:
        end = min(start + size, total)
        if end < total:
            # Ưu tiên ngắt tại ranh giới Điều / Khoản / Đoạn văn / Câu
            tail_start = start + int(size * 0.60)
            if tail_start < end:
                article_breaks = [
                    text.rfind(mark, tail_start, end)
                    for mark in ("\nĐiều ", "\nArticle ", "\nMục ", "\nChương ", "\nSection ")
                ]
                best_art = max(article_breaks)
                if best_art > start + overlap:
                    end = best_art + 1
                else:
                    candidates = [
                        text.rfind(mark, tail_start, end)
                        for mark in ("\n\n", ". ", ".\n", ";\n", "; ")
                    ]
                    boundary = max(candidates)
                    if boundary > start + overlap:
                        end = boundary + (2 if text[boundary:boundary + 2] in ("\n\n", ". ", "; ") else 1)
        yield start, end, text[start:end]
        if end >= total:
            break
        next_start = end - overlap
        if next_start <= start:
            next_start = end
        start = next_start


def chunk_document(doc: dict, size=1000, overlap=150):
    doc_id = doc["document_id"]
    last_article = None
    last_section = None
    for i, (start, end, text) in enumerate(chunk_text(doc["text"], size, overlap)):
        chunk_id = hashlib.sha256(f"{doc_id}|{start}|{end}|{text}".encode("utf-8")).hexdigest()
        loc = extract_location_meta(text)
        if loc["article"]:
            last_article = loc["article"]
        if loc["section"]:
            last_section = loc["section"]

        yield {
            "chunk_id": chunk_id,
            "document_id": doc_id,
            "chunk_index": i,
            "char_start": start,
            "char_end": end,
            "text": text,
            "article": loc["article"] or last_article,
            "section": loc["section"] or last_section,
            "page_start": loc["page_start"],
            "page_end": loc["page_end"],
            **{
                k: doc.get(k)
                for k in (
                    "source_document_id",
                    "title",
                    "source_url",
                    "region",
                    "published_date",
                    "document_type",
                    "source_path",
                    "text_sha256",
                )
            },
        }


def stable_chunk_id(document_id: str, version: str, chunk_index: int, text: str) -> str:
    """Tạo mã định danh ổn định cho từng chunk (TC02)."""
    payload = f"{document_id}:{version}:{chunk_index}:{text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run(input_path: str, output_path: str, size=1000, overlap=150):
    import pyarrow as pa
    import pyarrow.dataset as ds
    import pyarrow.parquet as pq

    dataset = ds.dataset(input_path, format="parquet")
    out = Path(output_path)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "chunks.jsonl"
    parquet_target = out / "chunks.parquet"

    doc_count = chunk_count = 0
    all_chunks = []
    with target.open("w", encoding="utf-8") as file:
        for batch in dataset.to_batches(batch_size=64):
            for doc in batch.to_pylist():
                doc_count += 1
                for chunk in chunk_document(doc, size, overlap):
                    file.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                    all_chunks.append(chunk)
                    chunk_count += 1
    if not chunk_count:
        raise ValueError("No chunks created")

    # Lưu đồng thời định dạng Parquet theo yêu cầu PRD (FR05)
    table = pa.Table.from_pylist(all_chunks)
    pq.write_table(table, parquet_target)

    # Ghi manifest chỉ mục để hiển thị thống kê trên Streamlit (FR10)
    manifest_dir = Path("data/manifests")
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_data = {
        "total_documents": doc_count,
        "total_chunks": chunk_count,
        "chunk_size": size,
        "chunk_overlap": overlap,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(manifest_dir / "index_manifest.json", "w", encoding="utf-8") as mf:
        json.dump(manifest_data, mf, ensure_ascii=False, indent=2)

    print(f"Chunking complete: {doc_count} documents / {chunk_count} chunks -> {target} & {parquet_target}")
    return chunk_count


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="data/processed")
    p.add_argument("--output", default="data/chunks")
    p.add_argument("--size", type=int, default=1000)
    p.add_argument("--overlap", type=int, default=150)
    a = p.parse_args()
    run(a.input, a.output, a.size, a.overlap)


if __name__ == "__main__":
    main()
