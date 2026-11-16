# Mục lục đề xuất — Chương 2 và Chương 3

**Đề tài:** Xây dựng nền tảng Data Lake tích hợp RAG và LLM hỗ trợ tra cứu, hỏi đáp văn bản pháp luật, chính sách và quy định về trí tuệ nhân tạo.

Giữ nguyên Chương 1 đã viết về cơ sở lý thuyết. Chương 2 giải thích **nhóm đã thiết kế và hiện thực hệ thống như thế nào**; Chương 3 trình bày **đã chạy gì, đo bằng cách nào và kết quả thực tế ra sao**. Các số trang dưới đây là dung lượng biên tập gợi ý, chưa phải số trang sau dàn trang Word.

## Chương 2. Phân tích và thiết kế hệ thống

| Mục | Nội dung cần trình bày | Hình/bảng chính | Dung lượng gợi ý |
|---|---|---|---|
| 2.1 | Bài toán, người dùng, yêu cầu chức năng và yêu cầu dữ liệu | Bảng yêu cầu và tiêu chí nghiệm thu | 2 trang |
| 2.2 | Cơ sở lựa chọn kiến trúc và công nghệ; phân biệt triển khai thực tế với hướng mở rộng | Bảng quyết định thiết kế và tài liệu tham khảo | 2 trang |
| 2.3 | Kiến trúc tổng thể và flowchart toàn hệ thống, cả luồng nạp lẫn luồng tra cứu | Hình 2.1–2.2 | 2–3 trang |
| 2.4 | Thiết kế dữ liệu: phạm vi, nguồn, Bronze/Parsed/Silver/Gold, schema, metadata, định danh | Hình 2.9; bảng lớp dữ liệu và từ điển dữ liệu | 3 trang |
| 2.5 | Nguồn API động: hợp đồng danh mục/toàn văn, phân trang, cửa sổ thời gian, checkpoint, chống trùng | Hình 2.3; bảng tham số API | 2–3 trang |
| 2.6 | Luồng tải tệp lên và xử lý tự động; kiểm tra tệp, provenance, tải lại bản gốc | Hình 2.4; bảng quy tắc tiếp nhận | 2 trang |
| 2.7 | Spark ETL: làm sạch, chuẩn hóa, khử trùng, chất lượng dữ liệu, ghi Parquet | Hình 2.5; bảng quy tắc ETL | 2–3 trang |
| 2.8 | Chia đoạn, embedding, Qdrant và công bố snapshot | Hình 2.7; bảng tham số chỉ mục | 2 trang |
| 2.9 | Luồng hỏi đáp RAG: truy xuất, mở rộng điều khoản, sinh câu trả lời và kiểm tra trích dẫn | Hình 2.6; bảng trạng thái đầu ra | 2 trang |
| 2.10 | Thiết kế giao diện và trợ lý giọng nói: TTS, người thuyết trình nữ, phụ đề, hoạt ảnh, điều khiển phát | Hình 2.10; bảng thiết kế chức năng người nói | 2–3 trang |
| 2.11 | Triển khai Docker/HDFS, giám sát, lỗi và giới hạn hiện tại | Hình 2.8; bảng dịch vụ và xử lý lỗi | 2 trang |

## Chương 3. Triển khai, thử nghiệm và đánh giá

| Mục | Nội dung cần trình bày | Hình/bảng chính | Dung lượng gợi ý |
|---|---|---|---|
| 3.1 | Mục tiêu thực nghiệm và nguyên tắc lấy bằng chứng | Bảng nhóm thí nghiệm | 1 trang |
| 3.2 | Yêu cầu tài nguyên; cấu hình máy thực nghiệm, phần mềm và mô hình | Bảng phần cứng/phần mềm/tham số | 2 trang |
| 3.3 | Bộ dữ liệu, snapshot, thống kê khu vực/ngôn ngữ/loại/nguồn/năm | Hình 3.12–3.16 và 3.21 | 3 trang |
| 3.4 | Thống kê độ dài tài liệu, đoạn, chất lượng metadata và dung lượng Data Lake | Hình 3.17–3.20, 3.25 | 3 trang |
| 3.5 | Kiểm thử chức năng, API tăng dần, upload xuyên suốt pipeline và chống trùng | Bảng kiểm thử; Hình 3.6–3.8 | 2–3 trang |
| 3.6 | Thực nghiệm Spark ETL ở ba mức dữ liệu lặp | Bảng 9 lần chạy; Hình 3.22 | 2 trang |
| 3.7 | Đánh giá truy xuất trên 15 câu hỏi; Hit@k, MRR, độ trễ và trường hợp lỗi | Bảng từng câu; Hình 3.23 | 2–3 trang |
| 3.8 | Kiểm tra hỏi đáp đầu cuối và dẫn chứng | Hình 3.3–3.5, 3.24 | 2 trang |
| 3.9 | Minh chứng triển khai ứng dụng, HDFS, Qdrant; giải thích Size/Replication/Block Size ở thư mục và tệp | Hình 3.1–3.2, 3.9–3.11, 3.30 | 2 trang |
| 3.10 | Thử nghiệm người thuyết trình, audio, phụ đề, hoạt ảnh và điều khiển phát | Hình 3.27–3.29; bảng nghiệm thu và thông số WAV | 2–3 trang |
| 3.11 | Thảo luận, hạn chế, đối chiếu mục tiêu và hướng mở rộng | Bảng kỹ năng Data Engineering | 2 trang |

## Phụ lục nên kèm theo

1. Danh mục 63 tài liệu đang lập chỉ mục, URL và nguồn thu thập.
2. Bộ 15 truy vấn đánh giá và ID tài liệu kỳ vọng.
3. Nhật ký, JSON/CSV kết quả, báo cáo kiểm thử tự động.
4. Mã nguồn Graphviz và lệnh tái tạo sơ đồ, biểu đồ, ảnh chụp.
5. Tài liệu tham khảo công nghệ và nguồn dữ liệu chính thức.

## Cách chọn hình khi giới hạn số trang

Giữ Hình 2.1, 2.2 và các lưu đồ 2.3–2.7 trong nội dung chính vì thể hiện đầy đủ công việc Data Engineering. Lưu đồ tổng thể rất dài nên in trang riêng, ưu tiên SVG; các lưu đồ con giải thích chi tiết từng khối. Giữ biểu đồ 3.12, 3.15, 3.18, 3.22, 3.23 và một số ảnh giao diện trong nội dung chính; chuyển các hình thống kê còn lại sang phụ lục nếu cần rút gọn. Không thu nhỏ nhiều hình đến mức không đọc được.

Bản nháp hoàn chỉnh: [Chương 2–3](02_BAN_NHAP_CHUONG_2_3.md). Các biểu đồ có phiên bản PNG 300 dpi và SVG trong [thư mục hình ảnh](hinh_anh/).
