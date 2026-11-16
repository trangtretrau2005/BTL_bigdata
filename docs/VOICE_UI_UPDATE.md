# Giọng nói, giao diện và nguồn — cập nhật 16/11/2026

## Kết quả

- 69 mục nguồn, 68 bật thu thập, 55 tải thành công, 47 văn bản đọc được và lập chỉ mục. Thêm 19 mục và 14 văn bản sử dụng được so với bản trước.
- 10 văn bản Việt Nam; 2.990 chunk trong Qdrant. Snapshot `ai_documents_verified_v2__20261116_080939_96fe70` đã công bố qua alias.
- HDFS đồng bộ 122 tệp, khoảng 100 MB. Số byte chính xác nằm trong `data/manifests/lake_manifest.json`.

## Giọng đọc và người thuyết trình

Sửa lỗi đổi giọng/tốc độ vẫn dùng âm thanh cũ bằng khóa theo nội dung, voice và rate.
Thay hai bộ phát độc lập bằng một khung người thuyết trình. Có nghe thử không cần chạy LLM.
Âm thanh tạo khi người dùng yêu cầu, không làm chậm bước nhận câu trả lời văn bản.

Giọng mặc định `Việt · Cục bộ` dùng Piper 1.8.0, model `vi_VN-vais1000-medium`, CPU hai luồng.
Model cố định revision, đối chiếu kích thước và SHA-256 từ kho chính thức. Xem
[attribution](VOICE_ATTRIBUTION.md). Đây là một giọng tiếng Việt, không giả là Hoài My/Nam Minh.
Mẫu chạy thật đã sinh WAV mono 22.050 Hz; kết quả lưu tại `evaluation/speech_live_check.json`.

Giữ Hoài My/Nam Minh khi Edge đáp ứng. Phiên thử trực tuyến hiện trả `NoAudioReceived`;
giao diện báo rõ giọng cục bộ/dự phòng thực tế. Có khoảng chờ trước khi thử lại dịch vụ lỗi.
Chế độ cục bộ không tự gửi nội dung sang Google nếu chưa tải được model.

Playlist dùng từng WAV/MP3 độc lập với phụ đề riêng. Không ghép MP3 nối đuôi và không ước lượng
phụ đề bằng số ký tự. Tốc độ không bị áp dụng hai lần; WAV có khoảng nghỉ ngắn giữa các câu.
Có phát/tạm dừng/đọc lại, tua trong đoạn hiện tại và điều chỉnh tốc độ. Browser fallback chỉ chọn
giọng tiếng Việt; nếu thiếu thì báo rõ, không đọc bằng giọng tiếng Anh. Khi yêu cầu cục bộ, chỉ chọn giọng thiết bị local.

Nhân vật nam/nữ là SVG minh họa trong trang phục công sở. Có chớp mắt, nhịp thở, miệng
và sóng âm theo biên độ Web Audio; không phải video người thật hoặc lip-sync từng âm vị.
Không tải ảnh cá nhân hoặc tài nguyên avatar từ dịch vụ ngoài.

## Giao diện

Giữ Times New Roman với xanh trầm, ngà và vàng dịu. Thêm số liệu thật, tab rõ ràng, thẻ tài liệu
và phân trang 12 mục/trang. Mặc định thư viện chỉ hiện văn bản đã lập chỉ mục, có công tắc xem toàn bộ danh mục.
Thay bảng dữ liệu giúp tránh nạp PyArrow nặng ngay khi mở phần hỏi đáp.
Metadata nguồn được escape khi tạo HTML; nội dung LLM vẫn dùng Markdown an toàn.

## Nguồn mới dùng được

- Việt Nam: Nghị định 165/2025/NĐ-CP, Luật Giao dịch điện tử 20/2023/QH15, bản chụp lịch sử Nghị định 13/2023/NĐ-CP.
- Singapore: hướng dẫn PDPC về dữ liệu cá nhân trong hệ thống AI khuyến nghị/ra quyết định.
- Anh: ATRS, mua sắm AI, đạo đức quyết định tự động, hướng dẫn phát triển AI an toàn của NCSC và đối tác.
- Hoa Kỳ: OMB M-25-21/M-25-22, NIST SP 800-218A.
- Quốc tế: Governing AI for Humanity của Liên Hợp Quốc.
- EU: FAQ nghĩa vụ GPAI và tổng quan hướng dẫn cho nhà cung cấp GPAI của Ủy ban châu Âu; tên tài liệu ghi đúng loại trang.

Ba văn bản EU và hai PDF Australia trong danh mục bổ sung chưa tải được; không tính chúng
là văn bản đang tìm kiếm được. Các nguồn bị chặn/scan được ghi trong báo cáo thu thập.
Không suy ra tình trạng hiệu lực pháp luật từ việc tải thành công.

Nhập thêm danh mục an toàn, không tạo trùng ID:

```powershell
python -m scripts.extend_source_catalog
docker compose exec -T app python -m scripts.fetch_ai_corpus
docker compose exec -T app python -m scripts.run_pipeline --step all --skip-collect --rebuild
```

## Kiểm tra

- 59 kiểm thử Python đạt trong Docker; 5 cảnh báo deprecation của PyMuPDF.
- JavaScript: phát WAV, tạm dừng/tiếp tục, tốc độ, phụ đề, kết thúc, đọc lại, kiểm tra giọng Việt và giọng thiết bị local.
- Âm thanh thật được kiểm tra bằng Piper và đọc thông số WAV; không dùng mock thay cho kiểm tra dịch vụ.
- Khóa tạm manifest trên bind mount Windows: dùng file tạm riêng, retry có giới hạn, giữ bản cũ trước khi replace thành công.
- Bộ duyệt an toàn tự động chặn thao tác chuyển tab Chrome vì cửa sổ đang ở ứng dụng tài khoản khác. Đã dừng điều khiển cửa sổ đó; chưa nghiệm thu trực quan toàn trang trong trình duyệt. Minh họa người thuyết trình được render và kiểm tra riêng.

Đây là kiểm tra chức năng, không phải chứng nhận độ chính xác pháp lý toàn corpus.
