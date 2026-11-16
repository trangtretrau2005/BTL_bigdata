> Phân tích trạng thái ban đầu. Xem [RUN_VERIFICATION.md](RUN_VERIFICATION.md) và README để biết bản đã sửa.

# Phân tích dự án và trạng thái khởi chạy

Ngày kiểm tra: 16/11/2026. Phạm vi: mã Python trong `app.py`, `src/`, `scripts/`, `tests/`, `evaluation/`; cấu hình, README, danh mục dữ liệu và tài liệu PRD. Chưa thay đổi logic nghiệp vụ hoặc dữ liệu gốc.

## 1. Kiến trúc thực tế

```text
data/sources.csv
  → DocumentCollector → data/raw + ingestion_manifest.json
  → DocumentParser → data/parsed/*.json
  → Spark ETL → data/processed/*.parquet
  → Chunker → data/chunks/chunks.jsonl + chunks.parquet
  → Ollama / BGE-M3 → Qdrant
  → Retriever → Ollama / Qwen3 → câu trả lời + citations
  → Streamlit + avatar Canvas + giọng nói
```

| Thành phần | Vai trò và hành vi hiện tại |
|---|---|
| `src/ingestion/collector.py` | Đọc CSV, tải PDF/HTML/TXT, kiểm tra một số trang chặn truy cập, tính SHA-256 và ghi manifest. Có nhánh API riêng cho Federal Register/EUR-Lex và dùng bản local khi tải lỗi. |
| `src/ingestion/parser.py` | Đọc PDF, HTML, DOCX, TXT; chuẩn hóa text và ghép metadata. Khi nhiều định dạng cùng ID, ưu tiên TXT trước HTML, DOCX và PDF. |
| `src/processing/spark_etl.py` | Spark chuẩn hóa khoảng trắng, khu vực, loại text ngắn, khử trùng theo hash nội dung và ghi Parquet/báo cáo. Có nhánh ghi bằng PyArrow khi Windows thiếu NativeIO. |
| `src/processing/chunker.py` | Chia theo ký tự với gối đầu; tìm điểm ngắt gần điều/mục/đoạn/câu; hash toàn đoạn để tạo ID ổn định. Mặc định 1.000 ký tự, gối đầu 150. |
| `src/rag/indexer.py` | Gọi Ollama embedding theo batch, kiểm tra số chiều và upsert vào Qdrant bằng UUID ổn định. Chạy lại cùng dữ liệu không thêm ID trùng; chưa dọn chunk cũ khi nguồn thay đổi. |
| `src/rag/retriever.py` | Truy xuất vector, lọc khu vực và tài liệu. Khi có exception, chuyển sang tìm kiếm local với mở rộng từ khóa Việt–Anh. Thuật toán local dùng điểm khớp từ có trọng số IDF, chưa phải BM25 chuẩn. |
| `src/rag/answerer.py` | Đặt ngưỡng điểm, tạo prompt có nhãn nguồn, gọi Qwen3, kiểm tra nhãn và thử lại khi nhãn sai. Khi gọi model lỗi, tự trả các trích đoạn thay thế. |
| `app.py` | Ba tab: hỏi đáp/avatar, tìm văn bản, danh mục. Có lọc khu vực; chưa có bộ chọn tài liệu dù backend hỗ trợ. |
| `src/rag/tts.py`, `avatar_component.py` | TTS qua Google Translate, STT qua Google Speech Recognition; avatar Canvas dùng Web Audio hoặc Web Speech API. Các tính năng giọng nói có phụ thuộc mạng/trình duyệt. |
| `scripts/`, `evaluation/`, `tests/` | CLI từng bước, điều phối ETL/chunk/index, sinh checksum và đánh giá. `run_pipeline --step all` hiện chỉ bao gồm ETL, chunk và index. |

## 2. Dữ liệu kiểm tra được

- Danh mục: 30 tài liệu, gồm 15 Việt Nam và 15 quốc tế.
- Parsed: 30 bản ghi; 28 lấy từ TXT, 2 lấy từ PDF.
- Processed: 30 tài liệu, 220.989 ký tự; không có bản bị loại/trùng ở lần ETL kiểm tra.
- Chunks: 302 ID khác nhau; tất cả có tên và URL nguồn. 146 đoạn thiếu `page_start`; HTML có thể không có số trang, còn đoạn tiếp nối PDF cần kiểm tra việc giữ vị trí.
- Bộ đánh giá thực tế có 40 câu: 30 có đáp án và 10 ngoài phạm vi; khác mô tả 30 câu trong README/PRD.
- `scripts/fetch_ai_corpus.py` chứa 28 nội dung tài liệu viết sẵn trong `AI_CORPUS_TEXTS`. 27 file TXT hiện có trùng hoàn toàn với các chuỗi này sau khi bỏ khoảng trắng đầu/cuối. File TXT về EO 14110 có thêm phần metadata. Không thể xem các chuỗi này là bản gốc đã xác minh chỉ vì có URL chính thức trong metadata.

## 3. Các điểm cần điều chỉnh sau khi thống nhất yêu cầu

1. **Truy nguyên dữ liệu:** parser ưu tiên TXT nên các nội dung viết sẵn có thể được chọn thay cho PDF/HTML gốc. Cần tách dữ liệu minh họa với dữ liệu trích xuất thực, đối chiếu điều khoản và vị trí với nguồn gốc. Nhánh Federal Register lấy metadata rồi ghép với text viết sẵn, không tải toàn văn thực trong hàm `try_fetch_federal_register_api`.
2. **Phần Data Lake:** `config.yaml` có HDFS nhưng mã chạy hiện tại dùng đường dẫn local. Chưa có Dockerfile/Compose hoặc luồng nối đầy đủ Raw → Processed → Chunks trên HDFS. Qdrant chỉ là chỉ mục vector; chưa thay thế yêu cầu lưu trữ Data Lake trong PRD.
3. **Lỗi dịch vụ bị che bởi chế độ dự phòng:** `retriever.py` và `answerer.py` bắt exception rồi trả kết quả local. Người dùng có thể nhận `status=answered` khi cả Qdrant và LLM đều không hoạt động. Hành vi này khác yêu cầu báo lỗi dịch vụ trong PRD.
4. **Từ chối ngoài phạm vi:** ở lần đo local, cả 10/10 câu ngoài phạm vi vẫn nhận `answered`. Ngưỡng điểm hiện tại chưa đủ để xác định có bằng chứng trả lời. Điểm vector và điểm từ khóa local cũng không cùng thang đo để mặc nhiên dùng chung một ngưỡng.
5. **Trích dẫn:** kiểm tra nhãn chưa bắt buộc câu trả lời phải có nhãn nào. Sau lần thử lại, code có thể xóa nhãn sai nhưng giữ nguyên nhận định chưa có nguồn. Danh sách citations chứa toàn bộ ứng viên, kể cả nguồn không được nhắc trong câu trả lời. Nhãn hợp lệ không chứng minh nhận định đúng với nguồn.
6. **Schema chưa được áp dụng xuyên suốt:** các dataclass trong `schemas.py` chưa được dùng để kiểm tra đầu ra pipeline. ETL/chunker dùng `region` và thiếu nhiều trường như `version_id`, `language`, `legal_status`, `parse_status`; `document_type=standard` trong dữ liệu chưa có trong enum. Thông tin hiệu lực và phiên bản có thể mất trước bước hỏi đáp.
7. **Cấu hình và CLI:** chưa thấy module đọc `config.yaml`; nhiều tham số trong `.env` không được dùng cho chunking/pipeline. README ghi token nhưng chunker thực tế đếm ký tự. README hướng dẫn `--step collect/parse`, trong khi CLI chỉ chấp nhận `etl/chunk/index/all`. Lệnh collector nên chạy dạng `python -m scripts.run_collect` để bảo đảm import từ thư mục gốc.
8. **Kiểm thử và đánh giá:** nhiều bài trong `test_integration.py` mới kiểm tra schema hoặc dữ liệu mô phỏng, chưa kiểm tra dịch vụ thật. `eval_runner.py` kiểm tra tài liệu có trong top 5 và ID chunk hợp lệ, chưa xác minh đúng đoạn chuẩn hoặc chấm nội dung câu trả lời. Kết quả citation validity 100% vì vậy chưa có nghĩa nội dung chính xác.

## 4. Kết quả chạy ngày 16/11/2026

- Đã tạo `.venv` và cài dependencies theo `requirements.txt`; `pip check` không báo xung đột.
- 20 kiểm thử schema/chunker/answerer/integration và 1 kiểm thử Spark đều đạt, tổng 21. Đây chưa phải xác nhận end-to-end với dịch vụ thật.
- Đã chạy lại Spark ETL bằng `local[2]` vào `.venv/logs/verified_processed`, báo cáo `.venv/logs/verified_etl_report.json`; đạt 30/30 tài liệu. Tạo lại chunk trong bộ nhớ cho 302 ID trùng tập ID hiện có. Dữ liệu pipeline gốc được giữ nguyên.
- Spark launcher trên Windows lỗi khi dùng đường dẫn dự án có ký tự tiếng Việt. Phiên kiểm tra dùng junction `C:\Users\Lenovo\AppData\Local\CodexRuntime\BTL_bigdata` trỏ về thư mục dự án, đặt `SPARK_HOME` qua đường dẫn này và `SPARK_LOCAL_IP=127.0.0.1`. Không đổi tên hoặc di chuyển dự án.
- Streamlit đã chạy tại `http://127.0.0.1:8501`; health trả HTTP 200. Streamlit AppTest kiểm tra tải ba tab và thao tác hỏi đáp dự phòng không gặp exception. Chưa kiểm tra mic, âm thanh hoặc hoạt ảnh trực tiếp trong trình duyệt.
- Đo riêng chế độ local, chủ động không gọi Qdrant/Ollama: Hit@5 theo tài liệu là 29/30 (96,67%); từ chối ngoài phạm vi 0/10 (0%). Đây không phải số đo chất lượng RAG/LLM. Chi tiết ở `.venv/logs/local_baseline.json`.
- Docker Engine chưa sẵn sàng. Lệnh liệt kê WSL bị treo; `wsl --shutdown` hết thời gian sau 20 giây. Phiên làm việc không có quyền khởi động lại `WslService`; người dùng báo thao tác Administrator cũng treo hoặc lỗi. Cần lưu công việc, khởi động lại Windows, mở Docker Desktop rồi kiểm tra lại. Chưa xác minh Qdrant, Ollama, model hoặc HDFS hoạt động.

Mở lại giao diện sau khi khởi động lại máy, chạy ở thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

Kiểm tra Docker sau khi mở Docker Desktop:

```powershell
docker version
docker ps -a
```

Chỉ khi lệnh `docker version` trả được phần Server mới tiếp tục xác nhận và khởi chạy các dịch vụ container.
