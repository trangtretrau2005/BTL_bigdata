# Thư viện Chính sách AI — Data Lake, RAG và LLM

Tra cứu văn bản pháp luật, chính sách và hướng dẫn quản trị AI bằng tiếng Việt. Câu trả lời dựa trên tài liệu đã thu thập, kèm dẫn chứng để đối chiếu.

## Khởi chạy

Cần Docker Desktop. Cấu hình máy demo: RTX 3050 6 GB, Python/Spark chạy trong Docker Linux.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_project.ps1
```

Script tạo `.env` từ `.env.example` nếu chưa có, build ứng dụng và tải BGE-M3, `qwen3:4b-instruct-2507-q4_K_M` cùng model giọng Việt Piper. Model Ollama được giữ trong Docker volumes; model giọng nói được giữ tại `data/models/piper` trong dự án.

- Ứng dụng: http://localhost:8501
- Qdrant: http://localhost:6333/dashboard
- HDFS: http://localhost:9870

Máy không có NVIDIA có thể chạy CPU, với tốc độ chậm hơn:

```powershell
docker compose -f compose.yaml -f compose.cpu.yaml up -d --build
```

## Cập nhật tự động qua API

Ở thanh bên, bấm **Cập nhật dữ liệu** để lấy văn bản AI mới từ API công khai Bộ Tư pháp. Hệ thống tự lấy toàn văn JSON/HTML, xử lý bằng Spark, tạo chỉ mục mới và đồng bộ HDFS; không cần tải từng PDF. Có tiến độ, chống trùng và báo lỗi theo nguồn. Mặc định kiểm tra 2 năm gần đây, tối đa 20 văn bản mới/cập nhật mỗi lượt; có thể cập nhật tiếp khi còn dữ liệu chờ.

```powershell
docker compose exec -T app python -m scripts.update_data --providers vbpl --max-documents 20
```

Xem [hợp đồng API, checkpoint và các lớp Data Lake](docs/DYNAMIC_API_UPDATE.md). Thay đổi giới hạn tại [cấu hình API](data/api_sources.json). Adapter Federal Register hiện tắt vì URL toàn văn trả trang chặn truy cập; các trang này không được dùng làm dữ liệu hỏi đáp.

## Tải tài liệu của bạn lên

1. Ở thanh bên, mở **Tải tài liệu lên** và chọn một hoặc nhiều tệp **PDF, DOCX, TXT, HTML, XML**.
2. Chọn khu vực/ngôn ngữ của tệp. Trong **Nguồn cập nhật tự động**, có thể bỏ chọn **Lấy thêm văn bản từ API** nếu chỉ muốn xử lý tệp của bạn.
3. Bấm **Cập nhật dữ liệu**. Worker tự lưu bản gốc, trích xuất nội dung, chạy Spark ETL → Parquet → chia đoạn → embedding → Qdrant → HDFS.
4. Khi hoàn tất, chọn tài liệu trong **Văn bản cụ thể** để hỏi đáp. Nguồn trả lời có nút **Tải tệp gốc**; tệp cũng có thể tải lại trong **Tải tài liệu lên → Tệp đã lưu**.

Giới hạn 10 tệp/lượt, 50 MB/tệp, tổng 100 MB. Word cần định dạng `.docx`. PDF scan ảnh cần OCR trước; tệp không đọc được hiển thị lỗi riêng và không được đưa vào tra cứu. Tải lại cùng tệp không tạo tài liệu trùng; nội dung trùng với một tài liệu có sẵn được ghi rõ **Nội dung đã có trong thư viện**.

Tệp mang provenance `user_upload`, giữ tên gốc, checksum và nhãn **Tệp do người dùng tải lên**. Không cần URL bên ngoài và không tự coi tệp là văn bản chính thức hay tự xác nhận hiệu lực. Dữ liệu lưu tại `data/uploads`, đồng bộ lên các vùng HDFS `raw/uploads` và `parsed/uploads`; Parquet/Chunks dùng cùng cơ chế snapshot phiên bản với nguồn API.

Nếu có tệp hợp lệ, lỗi kết nối API được ghi riêng để các tệp vẫn tiếp tục xử lý. Pipeline trước khi công bố bị lỗi thì chỉ mục đang dùng được giữ nguyên. Tệp hợp lệ đã lưu có thể được xử lý lại bằng nút cập nhật hoặc:

```powershell
docker compose exec -T app python -m scripts.update_data --uploads-only
```

Xem [bản cập nhật tải tệp và giọng đọc](docs/UPLOAD_AND_VOICE_UPDATE.md), gồm kết quả thử PDF thật và kiểm thử hồi quy.

## Thu thập và xử lý corpus khởi tạo

Danh mục `data/sources.csv` có nguồn Việt Nam, EU, NIST, OECD, UNESCO, ASEAN, Singapore, Anh, Úc và Canada. Không phải mọi nguồn trong danh mục đều tải hoặc trích xuất thành công.

```powershell
# Tải bản gốc và parse, tối đa 4 worker
docker compose exec -T app python -m scripts.fetch_ai_corpus

# Xử lý bản tải đã kiểm tra và công bố snapshot mới
docker compose exec -T app python -m scripts.run_pipeline --step all --skip-collect --rebuild

# Chạy cả thu thập, parse, ETL, chunk, index và HDFS
docker compose exec -T app python -m scripts.run_pipeline --step all --rebuild
```

Dùng `scripts.fetch_ai_corpus --refresh` khi cần tải lại nguồn đã có. Có thể chạy riêng `--step collect`, `parse`, `etl`, `chunk`, `index`, `lake`.

Các lệnh trên tái tạo từ danh mục nguồn cố định. Luồng **Cập nhật dữ liệu** ghép các bản đã xác minh với toàn văn API và công bố phiên bản kết hợp.

```text
Nguồn chính thức → verified_raw → verified_parsed → Spark ETL → Parquet
                                                           → Chunks → BGE-M3 → Qdrant
Câu hỏi → vector tìm kiếm → đoạn/điều khoản liên quan → Qwen3 Instruct → trả lời và nguồn
Raw / Parsed / Processed / Chunks / Manifests → WebHDFS → /ai_docs
```

Spark chạy `local[2]` trong container. Pipeline xử lý staging local, sau đó lưu các lớp dữ liệu lên HDFS qua WebHDFS và đối chiếu kích thước từng tệp. Đây là demo Data Lake một máy, chưa phải benchmark Spark phân tán.

## Bản chạy hiện tại

- Corpus khởi tạo có 69 mục nguồn; số văn bản tra cứu tăng khi thu thập thêm qua API. Các vị trí trên giao diện cùng đếm `source_document_ids` trong [manifest đang hoạt động](data/manifests/index_manifest.json), không lấy tổng mục nguồn thay số văn bản đã lập chỉ mục.
- Các đoạn giữ URL nguồn, phiên bản và metadata; Qdrant công bố alias sau khi hoàn tất đủ vector. Xem số đoạn và đường dẫn Processed/Chunks của phiên bản hiện tại trong manifest.
- HDFS lưu Raw, Parsed, Parquet, Chunks và Manifests; dữ liệu xử lý qua API được lưu theo phiên bản. Xem kết quả đồng bộ trong `data/manifests/lake_manifest.json`.
- Giao diện Times New Roman, nền ngà, xanh đậm và vàng; thư viện dùng thẻ tài liệu, lọc trạng thái và phân trang.
- Một người thuyết trình nữ, chuyển động theo nhịp âm thanh, phụ đề theo đoạn, phát/tạm dừng/đọc lại và điều chỉnh tốc độ.
- Giao diện dùng một lựa chọn giọng nữ **Hoài My**; đã bỏ menu chọn giọng nam và Việt cục bộ. Nếu dịch vụ chưa sẵn sàng, bộ phát ghi rõ giọng dự phòng thực tế, không giả là âm thanh Hoài My.

### Nghe thử và đọc câu trả lời

1. Mở **Khám phá trợ lý giọng nói** → **Nghe thử giọng đọc** → **Phát**.
2. Sau khi hỏi đáp, nhấn **Tạo giọng đọc cho câu trả lời**, rồi **Phát** trong khung người thuyết trình.
3. Đổi tốc độ trong thanh bên thì tạo lại âm thanh. Khung mới không dùng nhầm bản âm thanh của tốc độ cũ.
4. Nếu cần tải model đọc dự phòng: `docker compose exec -T app python -m scripts.setup_voice`.

Âm thanh được phát từng đoạn, không nối các MP3 gây sai thời lượng. Chuyển động miệng là minh họa theo biên độ âm thanh, không phải video người thật hay đồng bộ khẩu hình theo từng âm vị.
Xem [bản cập nhật giọng nói và giao diện](docs/VOICE_UI_UPDATE.md) và [nguồn, giấy phép model](docs/VOICE_ATTRIBUTION.md).

Nguồn Công báo được tải qua API/CDN chính thức. Không dùng các đoạn pháp luật viết sẵn để thay tài liệu thật. Trang metadata, chữ ký số hoặc PDF scan không đọc được không được xem là toàn văn.

Ngữ cảnh lấy từ Qdrant; với câu hỏi khớp tiêu đề về phạm vi điều chỉnh hoặc hành vi bị cấm, hệ thống lấy toàn điều tương ứng từ bản Processed cùng phiên bản. Kết quả ghi `context_kind=article` và `anchor_chunk_id` để phân biệt điều khoản mở rộng với chunk vector ban đầu.

Khi Qdrant/Ollama lỗi, hệ thống báo lỗi thay vì âm thầm trả lời trích đoạn. Nhãn trích dẫn sai bị chặn, chỉ hiện nguồn được model sử dụng. Chạy lại chỉ mục cùng ID không tạo trùng; rebuild dùng snapshot và đổi alias sau khi kiểm tra đủ point.

Một số tên nhóm nhạy cảm được biên tập đối chiếu với nguồn trong `data/curated_summaries.json`, chỉ dùng khi checksum toàn điều khớp chính xác. UI ghi rõ bản tóm tắt biên tập, không giả là câu trả lời LLM vừa sinh. Việc này không thay thế tài liệu gốc trong corpus.

## Báo cáo Chương 2–3 và bộ hình

Đã có [mục lục đề xuất](docs/bao_cao/01_MUC_LUC_DE_XUAT.md), [bản nháp đầy đủ](docs/bao_cao/02_BAN_NHAP_CHUONG_2_3.md) và [bản HTML dễ đọc](docs/bao_cao/02_BAN_NHAP_CHUONG_2_3.html). Nội dung gồm thiết kế Data Lake/API/upload/Spark/RAG, người thuyết trình và thử nghiệm thật trên máy demo.

[Bộ 16 biểu đồ](docs/bao_cao/03_BIEU_DO_THONG_KE.md) có PNG/SVG; [40 hình minh chứng](docs/bao_cao/DANH_MUC_HINH.md) gồm sơ đồ và ảnh ứng dụng, HDFS, Qdrant, người nói. [Hướng dẫn báo cáo](docs/bao_cao/README.md) giải thích nguồn số liệu, cách tái tạo và giới hạn phép đo. Snapshot báo cáo có 63 tài liệu/3.285 đoạn; tránh trộn với số liệu của các bản chạy trước.

## Kiểm thử và đánh giá

```powershell
docker compose exec -T app python -m pytest tests -q -p no:cacheprovider
docker compose exec -T app python evaluation/service_smoke.py
# Đo truy xuất, không gọi model sinh:
docker compose exec -T app python evaluation/eval_runner.py --retrieval-only
```

Kiểm thử Python bao gồm tải tệp, provenance, PDF/DOCX/TXT, chống trùng, API tăng dần, thống kê số văn bản, worker nền, nút cập nhật, Spark, chỉ mục và RAG; kiểm thử JavaScript cho bộ phát chạy bằng `node tests/presenter_player.test.cjs`. Xem [cập nhật API](docs/DYNAMIC_API_UPDATE.md), [giọng nói](docs/VOICE_UI_UPDATE.md) và [báo cáo nền tảng trước đó](docs/RUN_VERIFICATION.md). Bộ đánh giá cũ còn có đáp án xây từ corpus trước đây; nhóm cần đối chiếu lại từng đáp án với bản gốc trước khi dùng làm benchmark. Chỉ số tìm đúng tài liệu và ID nguồn không tự chứng minh nội dung câu trả lời đúng.

## Lưu ý vận hành

- `.env` ưu tiên hơn `config.yaml`. Đổi model embedding hoặc chunking cần rebuild chỉ mục.
- Bản `qwen3:4b` hiện chỉ hỗ trợ thinking trên image được kiểm tra; ứng dụng dùng chính xác bản Instruct nêu trên để có câu trả lời hoàn chỉnh trong giới hạn token.
- Lượt nạp model đầu có thể mất vài phút. Model được giữ 10 phút trên GPU để giảm thời gian các câu sau.
- `legal_status=unknown` là chưa xác minh hiệu lực. Luôn đối chiếu đoạn nguồn khi sử dụng câu trả lời.
- Giọng Hoài My và nhận diện câu hỏi bằng giọng nói gửi nội dung tương ứng tới dịch vụ bên ngoài. Nếu bộ đọc dùng Piper dự phòng thì nội dung đọc được xử lý trên máy. Giao diện báo rõ nhà cung cấp thực tế. LLM và Qdrant chạy local.
- Dữ liệu cũ đã được giữ trong `data/backups`. Nguồn lỗi có trong `verified_collection_report.json`.
- Các cổng chỉ mở trên localhost. Dừng bằng `docker compose stop`; tránh `down -v` nếu muốn giữ model và dữ liệu.
