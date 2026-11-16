# Tải tệp và một lựa chọn giọng đọc — 16/11/2026

## Cách sử dụng

1. Mở **Tải tài liệu lên** trong thanh bên, chọn PDF/DOCX/TXT/HTML/XML.
2. Chọn khu vực và ngôn ngữ. Nếu chỉ xử lý tệp, bỏ chọn **Lấy thêm văn bản từ API**.
3. Bấm **Cập nhật dữ liệu**. Tệp được lưu nguyên bản rồi tự trích xuất nội dung, xử lý Spark ETL, ghi Parquet, chia đoạn, tạo embedding, công bố snapshot Qdrant và đồng bộ HDFS.
4. Sau khi hoàn tất, chọn tên tài liệu trong **Văn bản cụ thể** để hỏi đáp. Có thể tải lại bản gốc trong nguồn trả lời, kết quả tìm kiếm hoặc danh sách **Tệp đã lưu**.

Giới hạn 10 tệp/lượt, 50 MB/tệp và 100 MB tổng. PDF scan ảnh cần OCR trước; Word cần `.docx`. Tệp không đọc được có lỗi riêng. Tệp hợp lệ vẫn xử lý được nếu API tạm không kết nối được. Có thể chạy lại các tệp đã lưu sau khi lỗi lập chỉ mục.

## Nguồn gốc và chống trùng

- [Bộ tiếp nhận tệp](../src/ingestion/uploads.py) dùng SHA-256 làm định danh lưu trữ; tên tệp gốc chỉ là metadata, không dùng làm đường dẫn tùy ý.
- Gắn provenance `user_upload`, trạng thái hiệu lực `unknown` và URI nội bộ `upload://...`. Không tự gắn nhãn nguồn chính thức hay yêu cầu người dùng phải có URL bên ngoài.
- Giữ tên gốc xuyên suốt parser → Parquet → chunk → vector → citation. Nguồn trả lời có nút tải đúng tệp đó.
- Cùng một tệp tải lại không tạo bản mới. Nội dung trùng được Spark khử trùng; giao diện báo **Nội dung đã có trong thư viện**, không đưa bản trùng vào số mục chờ lập chỉ mục.
- Bản gốc/parsed lưu tại `data/uploads`; HDFS có `raw/uploads` và `parsed/uploads`. Chỉ mục dùng cùng cơ chế snapshot với API; không công bố chỉ mục đang xây dở.

## Giọng đọc

Đã bỏ hai lựa chọn **Nam · Nam Minh** và **Việt · Cục bộ** khỏi giao diện. Còn một cấu hình giọng nữ Hoài My và một người thuyết trình nữ; vẫn điều chỉnh được tốc độ, tạm dừng và đọc lại. Đổi tốc độ sẽ yêu cầu tạo lại âm thanh để không phát bản cũ.

Piper/Google được giữ làm dự phòng khi dịch vụ trực tuyến chưa sẵn sàng. Bộ phát ghi rõ nhà cung cấp thực tế; không gắn tên Hoài My cho âm thanh dự phòng. Đây là một lựa chọn giọng trên giao diện, không phải cam kết dịch vụ Hoài My luôn kết nối được.

## Xác minh

- **86 kiểm thử Python đạt**, gồm nhập tệp, kiểm tra định dạng, không vượt thư mục lưu trữ, phát hiện checksum thay đổi, PDF/DOCX/TXT, chống trùng, nguồn trích dẫn, API lỗi, tiếp tục xử lý tệp đã parse, nút cập nhật, giọng đọc và các hồi quy RAG trước đó.
- Bộ kiểm thử JavaScript cho trình phát đạt.
- Chạy một PDF thật của Luật Trí tuệ nhân tạo qua đầy đủ pipeline trong bộ dữ liệu kiểm tra riêng: 1 tài liệu → 30 đoạn → Qdrant → HDFS; tìm kiếm trả đúng provenance/tên tệp và tải lại được đúng byte bản gốc.
- Lượt lặp lại trả `no_changes`; corpus chính và alias đang phục vụ được đối chiếu giữ nguyên. Bộ kiểm tra lưu riêng để tránh thêm dữ liệu thử vào thư viện chính.
- AppTest với tệp đã lưu xác nhận có file uploader, lịch sử tệp và nút **Tải tệp gốc**; không còn menu chọn giọng. Kiểm tra giao diện bằng AppTest, chưa nghiệm thu thao tác tải xuống bằng trình duyệt thật trong vòng này.

Xem [bằng chứng chạy thật](../evaluation/upload_live_check.json) và [hướng dẫn vận hành](../README.md#tải-tài-liệu-của-bạn-lên).
