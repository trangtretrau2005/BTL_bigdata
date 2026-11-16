# Kiểm tra bản chạy — 16/11/2026

Trạng thái sau đợt sửa, thay cho các nhận xét vận hành ban đầu trong PROJECT_ANALYSIS.md.

## Kết quả vận hành

- Docker Compose đang chạy ứng dụng Streamlit, Qdrant, Ollama và HDFS NameNode/DataNode. Các cổng 8501/6333/9870 chỉ mở tại localhost.
- GPU NVIDIA RTX 3050 6 GB được cấp cho Ollama. BGE-M3 và Qwen3 4B Instruct đều được xác nhận chạy 100% GPU.
- Danh mục có 50 nguồn; tải được 41 tài liệu gốc; 33 tài liệu khác nhau được đưa vào chỉ mục, gồm 7 văn bản Việt Nam. Tất cả 33 bản parse có provenance official_download, URL HTTPS và checksum khác nhau.
- Spark ETL đạt 33/33 bản ghi. Tạo 2.499 chunk; Qdrant kiểm tra đúng 2.499 point trước khi công bố alias ai_documents_verified_v2.
- HDFS lưu 94 tệp, 82.454.491 byte, gồm Raw, Parsed, Processed, Chunks và Manifests. Đồng bộ kiểm tra kích thước từng tệp.
- Dữ liệu cũ được giữ trong data/backups trước khi thay Processed/Chunks.

## Kiểm thử

- 51 kiểm thử đạt trong Docker Linux, gồm Spark, ingestion, metadata/trang, snapshot, lỗi dịch vụ, trích dẫn, đầu ra có cấu trúc và Streamlit AppTest.
- pip check không phát hiện xung đột dependency; git diff --check không có lỗi whitespace.
- Kiểm tra trực quan chưa hoàn tất vì người dùng dừng Computer Use bằng Escape. Giao diện đã được kiểm tra bằng AppTest: ba tab, nhập câu hỏi, bộ lọc và nguồn đối chiếu.
- TTS chính Edge neural hiện không trả âm thanh ổn định. Đã sửa lỗi chờ vô hạn và bổ sung giọng dự phòng có thông báo. Mẫu tạo được 46.080 byte MP3. Nhãn nguồn không được đọc lặp lại; danh sách được chuyển thành thứ nhất, thứ hai… và giữ dấu câu để ngắt nhịp.

## Đối chiếu chất lượng

Ba câu smoke kiểm tra phạm vi Luật AI Việt Nam, bốn chức năng NIST và các nhóm hành vi cấm của EU. Kết quả cùng timing được lưu tại evaluation/service_smoke_results_final.json. Mười câu ngoài phạm vi được kiểm tra riêng. Đây là kiểm tra vận hành trên mẫu, chưa phải benchmark độ chính xác pháp lý toàn corpus.

Lần thử model 1.7B từng đảo điều kiện loại trừ quốc phòng/an ninh. Bản 4B thông thường lại chỉ hỗ trợ thinking trên image Ollama hiện tại, hết token trước câu trả lời. Bản chạy cuối dùng chính xác qwen3:4b-instruct-2507-q4_K_M và image Ollama được pin digest.

Để tránh trộn các điều gần chủ đề, truy xuất vector được mở rộng sang đúng điều khoản từ bản Processed cùng document_id khi câu hỏi khớp tiêu đề. Kết quả ghi context_kind=article, anchor_chunk_id và vị trí ký tự. Câu phạm vi Việt Nam hiện giữ đúng nội dung: hoạt động AI chỉ phục vụ quốc phòng, an ninh, cơ yếu không thuộc phạm vi điều chỉnh.

Với danh sách các nhóm cấm, backend yêu cầu đầu ra có đủ các nhãn có trong điều khoản và chỉ tóm tắt chủ đề theo nhóm. Các ngoại lệ dài không được model tự diễn giải trong phần tên nhóm; người dùng được hướng dẫn đối chiếu toàn văn giữ nguyên trong nguồn. Điều này hạn chế lỗi đảo điều kiện nhưng không chứng minh mọi câu trả lời của hệ thống đều chính xác.

## Giới hạn còn phải theo dõi

- Một số nguồn chặn tải, đổi URL hoặc chỉ cung cấp scan. Chúng có log và chưa được coi là nội dung tìm kiếm; không thay bằng văn bản soạn sẵn.
- Chưa xác minh hiệu lực toàn bộ corpus; unknown được giữ nguyên. Bộ đáp án cũ cần nhóm rà lại theo tài liệu thật trước khi dùng chấm chất lượng.
- Nhãn trích dẫn hợp lệ không thay cho đối chiếu nội dung. LLM vẫn có thể diễn giải sai.
- Model tải lần đầu có thể mất vài phút; các câu sau nhanh hơn khi model đã sẵn sàng trên GPU. Hai model được giữ 10 phút.
- Spark xử lý staging local, HDFS lưu các lớp dữ liệu bằng WebHDFS; chưa có benchmark Spark cluster.
- Giọng nam/nữ neural phụ thuộc dịch vụ ngoài; bản chạy hiện có thể dùng giọng Việt dự phòng. TTS/STT gửi nội dung tới dịch vụ bên ngoài khi được bật.

## Bản tóm tắt theo điều khoản đã đối chiếu

Model vẫn có thể thu hẹp hoặc diễn giải sai ngoại lệ khi dịch tiếng Việt. Riêng tên tám nhóm tại Article 5 được lưu dưới dạng tóm tắt biên tập, gắn SHA-256 với nguyên văn điều khoản đã tải. Hệ thống chỉ dùng bản này khi source_document_id và hash khớp; nguồn đổi thì bản biên tập tự mất hiệu lực. UI ghi rõ answer_mode=curated_summary, model=null; các câu phạm vi và NIST vẫn do LLM sinh. Không tính bản biên tập là kết quả sinh của LLM.

Trong smoke cuối có hai câu do LLM sinh và một câu từ bản tóm tắt biên tập gắn nguồn. Mười câu ngoài phạm vi được từ chối trước inference. Đây là kiểm tra vận hành, không phải điểm độ chính xác chung.

Kết quả nghiệm thu cuối: mã thoát smoke = 0; 2 câu do LLM sinh và 1 bản biên tập gắn nguồn đều answered, 10/10 câu ngoài phạm vi bị từ chối. Thời gian mẫu tương ứng 5,94 giây; 33,06 giây; 0,88 giây, khi model đã sẵn sàng. Không dùng các số này làm cam kết tốc độ chung.
