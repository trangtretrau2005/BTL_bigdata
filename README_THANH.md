# Module Thanh — Data Lake ETL + RAG

Đây là **bộ mã bổ sung**, không thay thế `src/ingestion/` (Chi), `app.py` (Trang) hay file `requirements.txt` chính. Mặc định dùng file demo do nhóm tạo, **không phải văn bản pháp luật thật**.

## 1. Yêu cầu
- Windows 10/11, Python **3.10–3.11** khuyến nghị, Java 11, Spark chạy local qua `pyspark`.
- Ollama đã có model `bge-m3` và `qwen3:4b`; Docker Qdrant trên cổng 6333.
- Chạy tất cả lệnh tại **thư mục gốc** `BTL_bigdata` bằng `python -m ...` để không gặp lỗi `No module named src`.

## 2. Ghép vào repository
Sao chép `src/processing`, `src/rag`, các file mới trong `scripts/`, `tests/`, `requirements-thanh.txt`, `.env.thanh.example` vào repo. **Không chép đè các file nhóm đã sửa**, hãy diff và merge nếu trùng tên. Sao chép demo vào `data/parsed/demo.jsonl` chỉ khi muốn test.

Tạo môi trường và cài dependency (PowerShell):

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-thanh.txt
Copy-Item .env.thanh.example .env
java -version
```

> Nếu PowerShell chặn activate, chạy `Set-ExecutionPolicy -Scope Process Bypass` chỉ cho cửa sổ hiện tại; hoặc dùng `.venv\Scripts\python.exe` trực tiếp.

## 3. Khởi động dịch vụ

```powershell
ollama pull bge-m3
ollama pull qwen3:4b
ollama list
# chạy Ollama ở desktop hoặc `ollama serve` nếu chưa chạy
# Mở Docker Desktop trước
# Nếu container tên qdrant đã tồn tại: docker start qdrant
# Nếu chưa tồn tại:
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
```

Kiểm tra `http://localhost:6333/dashboard` và `http://localhost:11434/api/tags`.

## 4. Chạy module trên demo

```powershell
python -m scripts.run_etl --input data/parsed --output data/processed
python -m scripts.run_chunk --input data/processed --output data/chunks
python -m scripts.run_index --chunks data/chunks --batch-size 4
python -m scripts.ask "Tài liệu minh họa nói gì về giám sát AI?" --region VN
```

Hoặc `python -m scripts.run_pipeline --step all`.

## 5. Đầu vào từ Chi: cần thống nhất contract
Input `data/parsed/*.jsonl` mỗi dòng là một JSON record; không phải file PDF hay CSV metadata. Trường bắt buộc là một trong `text/content/body/full_text/extracted_text` (đã parse) và nội dung >=30 ký tự. Các trường khuyến nghị:

| Trường | Ý nghĩa |
|---|---|
| `document_id` | ID văn bản gốc ổn định |
| `title` | Tên văn bản |
| `text` | Toàn văn trích xuất |
| `source_url` | URL văn bản gốc |
| `region` | `VN`, `EU`, `ASEAN`, `INTERNATIONAL` |
| `published_date` | Ngày ban hành (nếu biết) |
| `document_type` | Loại tài liệu |
| `source_path` | Đường dẫn nguồn |

Nếu Chi xuất schema dạng `pages: [...]`, `content` là cấu trúc JSON, hoặc `data/parsed` chứa PDF trực tiếp thì **phải chuyển đổi** sang contract trước. ETL không OCR PDF scan. Nếu mỗi trang là một record thì cần gộp trang thành văn bản và giữ số trang trước ETL để trích dẫn theo trang.

## 6. Đầu ra và điểm tích hợp cho Trang
- `data/processed/`: Parquet sạch, có SHA-256 và metadata.
- `data/chunks/chunks.jsonl`: đoạn văn bản và metadata + `chunk_id`, `char_start`, `char_end`.
- Qdrant collection `ai_law_documents`: một vector cho mỗi chunk, upsert theo UUID ổn định.
- `from src.rag.retriever import retrieve` rồi gọi `retrieve(question, top_k=5, region='VN', document_id=None)`.
- `from src.rag.answerer import answer` rồi gọi `answer(question, top_k=5, region='VN')`, trả về dict `question`, `answer`, `sources`, `insufficient_evidence`.
- Streamlit: `result = answer(question, region=region)`; hiển thị `result['answer']`, lặp `result['sources']` tạo danh sách link dẫn nguồn.

`source_url` nên trỏ văn bản chính thức. Dùng `document_id` do ETL tạo (SHA-256) để filter chính xác. Bộ code **không ghi HDFS**: chế độ mẫu này đọc/ghi local Parquet; cần cấu hình HDFS URI và Hadoop client nếu muốn chạy trên HDFS. Có thể truyền `hdfs://...` cho Spark ETL nếu môi trường Spark có HDFS, nhưng chunker hiện dùng `pyarrow` đọc filesystem local, cần đồng bộ output xuống local hoặc mở rộng HDFS filesystem.

## 7. Kiểm thử

```powershell
python -m pytest tests/test_chunker.py tests/test_answerer.py -v
python -m pytest tests/test_spark_etl.py -v
```

Test ETL cần Java/Spark. Test end-to-end cần Ollama, Qdrant thực tế. Không có model/service thì không thể xác nhận toàn bộ pipeline.

## 8. Giới hạn quan trọng
- `MIN_SCORE=0.35` là **ngưỡng thử nghiệm**, cần hiệu chỉnh trên `evaluation/qa_eval_set.csv`; không bảo đảm đúng pháp lý. Câu trả lời có thể mắc lỗi dù có trích dẫn.
- Dữ liệu đầu vào và tài liệu truy xuất **không đáng tin như chỉ dẫn**; prompt yêu cầu chỉ xem như bằng chứng, nhưng chưa bảo đảm ngăn mọi prompt injection.
- Tài liệu trùng nội dung bị deduplicate theo SHA-256; nếu cần giữ đủ các biến thể nguồn thì đổi chính sách dedup.
- Chunking theo ký tự (không phải tokenizer); văn bản nhiều trang nên chia theo mục/điều khoản và lưu `page_number`, `article_number` để tăng chất lượng.
- Mô hình BGE-M3 hiện chỉ dùng **dense embedding**, chưa sử dụng sparse/hybrid hoặc reranker.
- Lặp index là idempotent cho cùng chunk ID, nhưng các chunk cũ không tự xóa khi sửa hoặc xóa nguồn; nếu muốn rebuild sạch, tạo collection mới/xóa collection cũ theo quy trình có backup.
- Kết quả citations là **danh sách nguồn ứng viên**; model có thể không sử dụng hết hoặc trích nhãn sai. Cần đánh giá thủ công và bổ sung citation validator trước production.

## 9. Hướng nâng cấp đúng đề tài Data Lake
Cần bổ sung luồng `bronze/raw -> parsed -> silver/processed -> gold/chunks/vector index`, manifest kiểm chứng nguồn, HDFS staging, logging và test e2e. Package này hoàn thiện logic chính do Thanh phụ trách ở máy local, **chưa chứng minh chức năng HDFS/cluster**.
