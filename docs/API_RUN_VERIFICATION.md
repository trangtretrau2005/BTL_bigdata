# Nghiệm thu cập nhật API — 16/11/2026

## Dữ liệu và số đếm

| Chỉ số | Trước cập nhật API | Sau cập nhật API |
| --- | ---: | ---: |
| Văn bản đang tra cứu | 47 | 63 |
| Mục nguồn trong danh mục | 69 | 85 |
| Mục chưa có trong chỉ mục | 22 | 22 |
| Đoạn có nguồn | 2.990 | 3.285 |
| Văn bản Việt Nam trong chỉ mục | 10 | 26 |

Đã thêm 16 văn bản mới. Có 17 văn bản chuẩn hóa lấy qua API Bộ Tư pháp, gồm một văn bản đã có được cập nhật toàn văn. Qdrant có 325 đoạn mang provenance `official_api`. Các định danh nguồn thực tế trong toàn bộ 3.285 point khớp chính xác manifest.

Hai vị trí thống kê giao diện cùng báo 63 văn bản. Tổng 85 mục nguồn được trình bày riêng; 22 mục còn lại không được đưa vào bộ lọc hỏi đáp. Thư viện mặc định hiện đúng 63 tài liệu tra cứu được.

## Lượt chạy thật

- Lượt `20261116_092331_fd7870e9`: quét 7 trang/337 bản ghi nguồn, thêm 15 văn bản vào tra cứu. Một toàn văn phản hồi chậm nên kết quả báo cập nhật một phần.
- Lượt `20261116_093406_aaf12a03`: lấy thành công văn bản còn lại, không có lỗi toàn văn. Spark xử lý 63/63 bản ghi; tạo 3.285 đoạn và công bố snapshot mới. Đồng bộ kiểm tra kích thước 178 tệp/106.031.673 byte trong lượt cuối lên HDFS. Đây là thống kê tệp được đồng bộ trong lượt, không phải tổng dung lượng mọi phiên bản lịch sử trên HDFS.
- Lượt `20261116_093656_1034a1be`: dùng checkpoint, đọc 2 trang/100 bản ghi danh mục, kết quả `no_changes`. Manifest, số văn bản và snapshot đang dùng giữ nguyên; không tạo chỉ mục mới.

Snapshot đang hoạt động: `ai_documents_verified_v2__api_20261116_093406_aaf12a03`, qua alias `ai_documents_verified_v2`.

## Kiểm tra chức năng

- **73 kiểm thử Python đạt** trong Docker Linux; 5 cảnh báo deprecation từ PyMuPDF, không có lỗi kiểm thử.
- Kiểm tra API có toàn văn, idempotence, nhiều ID nguồn cùng một văn bản, chống nhập trang Request Access dù HTTP 200, lỗi phân trang, khóa worker, nút cập nhật và giữ manifest cũ khi pipeline lỗi.
- AppTest xác nhận số đếm thanh bên/phần giới thiệu khớp, thư viện có 63 tài liệu, bộ lọc có 63 văn bản cùng lựa chọn tất cả và nút cập nhật hoạt động.
- Truy xuất vector tìm được toàn văn mới của Thông tư 53/2026/TT-NHNN từ API, kèm đúng `source_document_id`, `api_provider` và URL gốc. Tìm kiếm từ khóa cũng đọc được dữ liệu của phiên bản mới.
- Mở rộng Điều 1 của Luật Trí tuệ nhân tạo đọc đúng bộ Processed đang được công bố qua manifest.
- HTTP health của ứng dụng trả thành công sau khi khởi chạy image mới; 5 dịch vụ Compose đang chạy.
- [Bằng chứng chạy dịch vụ](../evaluation/dynamic_api_live_check.json) lưu số đếm, snapshot, nguồn tìm được, kết quả idempotence và đồng bộ HDFS.

Kiểm tra giao diện dùng AppTest; vòng này chưa có nghiệm thu trực quan bằng trình duyệt. Kiểm tra văn bản mới tập trung vào truy xuất và đối chiếu nguồn, không phải benchmark độ chính xác chung của câu trả lời LLM.

## Nguồn bị loại

Federal Register truy cập được API metadata nhưng toàn văn chuyển tới trang Request Access. Trong lượt thử ban đầu, 5 trang này đã được cách ly, snapshot thử bị ngừng sử dụng và bản dữ liệu đã xác minh được khôi phục trước khi công bố các lượt Bộ Tư pháp. Các tệp xử lý thử tương ứng trên HDFS nằm trong khu quarantine. Bản ghi nguồn thô được giữ để đối chiếu.

Đã bổ sung kiểm tra trang chặn và kiểm tra URL sau chuyển hướng; adapter Federal Register tắt mặc định. Toàn bộ point trong snapshot hiện tại đã được kiểm tra và không chứa tài liệu từ adapter này.

Phạm vi cập nhật đang bật là API Bộ Tư pháp theo từ khóa trí tuệ nhân tạo, lần đầu 2 năm gần đây rồi dùng checkpoint. Không tuyên bố bao phủ mọi văn bản AI trên thế giới hay tự xác nhận hiệu lực pháp lý. Xem [thiết kế API và vận hành](DYNAMIC_API_UPDATE.md).
