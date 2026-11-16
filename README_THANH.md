# Processing và RAG — trạng thái hiện tại

Tài liệu vận hành chính: [README.md](README.md). Kết quả kiểm tra: [docs/RUN_VERIFICATION.md](docs/RUN_VERIFICATION.md).

Bản cập nhật mới nhất: [API động và nút Cập nhật dữ liệu](docs/DYNAMIC_API_UPDATE.md); bản trước: [giọng đọc, người thuyết trình và nguồn bổ sung](docs/VOICE_UI_UPDATE.md).
Số văn bản/chunk hiện tại lấy từ [manifest chỉ mục](data/manifests/index_manifest.json). Thanh bên và phần giới thiệu dùng cùng số văn bản đã sẵn sàng hỏi đáp; tổng mục nguồn được thống kê riêng.
Giao diện dùng một lựa chọn giọng nữ Hoài My. Piper được giữ làm dự phòng khi dịch vụ trực tuyến chưa sẵn sàng; bộ phát ghi rõ nhà cung cấp thực tế.
Tải PDF/DOCX/TXT/HTML/XML trong **Tải tài liệu lên**, rồi bấm **Cập nhật dữ liệu** để tự trích xuất, ETL, chia đoạn, tạo vector và lưu HDFS. Xem [hướng dẫn tải tệp](README.md#tải-tài-liệu-của-bạn-lên).

Module đã nối corpus tải chính thức, Spark, Qdrant, Ollama và HDFS trong Docker. Nội dung pháp luật viết sẵn không còn được dùng trong luồng thu thập mặc định.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_project.ps1
docker compose exec -T app python -m scripts.fetch_ai_corpus
docker compose exec -T app python -m scripts.run_pipeline --step all --skip-collect --rebuild
# Cập nhật tăng dần, ghép corpus đã có với toàn văn lấy qua API
docker compose exec -T app python -m scripts.update_data --providers vbpl --max-documents 20
```

- Spark ETL giữ ngôn ngữ, phiên bản, hiệu lực, URL và nguồn gốc; làm sạch và khử trùng, ghi Parquet.
- Chunking theo ký tự: mặc định 2.200, overlap 240; giữ vị trí trang/điều.
- BGE-M3 tạo vector 1.024 chiều. Alias Qdrant là `ai_documents_verified_v2`, rebuild tạo snapshot riêng.
- Qwen3 4B Instruct sinh câu trả lời tiếng Việt có trích dẫn. Không dùng bản 4B chỉ hỗ trợ thinking để tránh hết giới hạn trước phần trả lời.
- Truy xuất có thể mở rộng anchor vector thành toàn điều khoản tương ứng với câu hỏi, có metadata phân biệt rõ.
- Lỗi dịch vụ được thông báo; không tự đóng vai LLM bằng câu trả lời trích đoạn.
- HDFS lưu Raw, Parsed, Processed, Chunks và Manifests qua WebHDFS. Spark hiện xử lý staging local, chưa benchmark cluster.

```powershell
docker compose exec -T app python -m pytest tests -q -p no:cacheprovider
```

Thông số `.env` ưu tiên hơn `config.yaml`. Khi đổi model embedding hoặc chunking phải tạo lại snapshot và đánh giá truy xuất. Các bài kiểm thử tự động không thay cho kiểm chứng nội dung pháp lý và hiệu lực văn bản.
