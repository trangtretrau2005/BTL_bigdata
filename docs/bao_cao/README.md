# Bộ báo cáo Chương 2–3 và hình minh chứng

## Mở tài liệu

1. [Mục lục đề xuất](01_MUC_LUC_DE_XUAT.md): cấu trúc chương và dung lượng gợi ý.
2. [Bản nháp đầy đủ Markdown](02_BAN_NHAP_CHUONG_2_3.md) hoặc [bản HTML dễ đọc](02_BAN_NHAP_CHUONG_2_3.html): Chương 2 thiết kế, Chương 3 thử nghiệm, tài liệu tham khảo và phụ lục.
3. [Bộ 16 biểu đồ](03_BIEU_DO_THONG_KE.md) hoặc [gallery HTML](03_BIEU_DO_THONG_KE.html).
4. [Danh mục 40 hình](DANH_MUC_HINH.md): 10 sơ đồ, 16 biểu đồ và 14 ảnh chụp thật, gồm người thuyết trình và HDFS ở mức tệp.
5. [Danh mục 63 tài liệu và 15 truy vấn](PHU_LUC_DANH_MUC_DU_LIEU.md); [CSV dữ liệu](evidence/dataset_catalog.csv).
6. Mẫu giọng nói: [đoạn 1](am_thanh/nguoi_thuyet_trinh_doan_01.wav), [đoạn 2](am_thanh/nguoi_thuyet_trinh_doan_02.wav).

Bản HTML dùng Times New Roman, bảng và hình có chú thích; bấm ảnh để mở lớn. Khi mở HTML cần giữ nguyên các thư mục đi kèm. Có thể in từ trình duyệt; sau khi ghép vào Word, dùng Heading/Captions của Word để tạo số trang và danh mục tự động theo mẫu trường. SVG phù hợp phóng to/in; PNG biểu đồ 300 dpi phù hợp chèn Word. Lưu đồ toàn hệ thống rất dài, nên đặt trang riêng và dùng các lưu đồ con khi thuyết minh.

## Phạm vi số liệu

Ngày đo 16/11/2026. Snapshot chính có **63 tài liệu, 3.285 đoạn**, catalog 85 mục; các biểu đồ sử dụng snapshot này. Phép thử upload dùng bộ tách biệt một tài liệu/30 đoạn. Spark chạy `local[2]`, HDFS một DataNode/replication 1; chưa phải benchmark cụm phân tán. Bộ truy xuất có 15 câu độc lập, lặp ba lượt để đo thời gian. Hit@5 là tìm đúng ID tài liệu, không phải tỷ lệ trả lời đúng pháp luật.

Người nói là nhân vật SVG nữ, phụ đề theo đoạn audio và miệng theo năng lượng tín hiệu. UI giữ một lựa chọn Hoài My, phiên đo thật dùng Piper dự phòng và ghi rõ provider. Mẫu WAV cùng checksum được lưu làm bằng chứng; chưa đo MOS hoặc lip-sync âm vị.

HDFS hiển thị Size/Replication/Block Size bằng 0 ở **dòng thư mục** là bình thường. Đã mở tệp Parquet thật, đọc lại checksum và kiểm tra fsck HEALTHY. Xem [bằng chứng HDFS](evidence/hdfs_file_verification.json), [log fsck](evidence/hdfs_fsck.log) và [ảnh mức tệp](hinh_anh/hinh_3_30_hdfs_tep_that.png).

## Bằng chứng và chỉnh sửa

Chỉnh nội dung ở [chuong_2.md](chuong_2.md), [chuong_3.md](chuong_3.md) và [TAI_LIEU_THAM_KHAO.md](TAI_LIEU_THAM_KHAO.md), sau đó chạy script build để cập nhật bản kết hợp/HTML. Không sửa số trong biểu đồ bằng tay; sửa cách thống kê hoặc lấy lại dữ liệu rồi xuất lại. Mỗi hình có checksum ở [report_asset_manifest.json](evidence/report_asset_manifest.json); nguồn biểu đồ ở [chart_manifest.json](evidence/chart_manifest.json); ảnh chụp có timestamp ở [screenshot_manifest.json](evidence/screenshot_manifest.json).

Các tài liệu cũ trong thư mục docs có thể mô tả snapshot trước 47 tài liệu/2.990 đoạn; không dùng lẫn với snapshot 63/3.285 trong báo cáo này. Các JSON/CSV trong bộ báo cáo là bằng chứng của phiên đo cụ thể.

## Tái tạo hình và số liệu

Chạy tại thư mục gốc của dự án khi Docker đã hoạt động. Chỉ chạy lại benchmark khi cần một phiên đo mới, vì kết quả và tài nguyên máy có thể thay đổi. Các script benchmark ghi vào staging riêng và không xây lại chỉ mục sản xuất.

```powershell
# Đọc lại thống kê từ snapshot đang hoạt động
docker compose exec -T app python -m scripts.report_collect

# Kiểm thử và đo: tạo bằng chứng mới
docker compose exec -T app python -m pytest tests -q -p no:cacheprovider --junitxml=docs/bao_cao/evidence/python_tests.xml
docker compose exec -T app python -m scripts.report_benchmark --part retrieval
docker compose exec -T app python -m scripts.report_benchmark --part etl
node tests/presenter_player.test.cjs
docker compose exec -T app python -m scripts.report_hdfs_check
docker compose exec -T namenode hdfs fsck /ai_docs

# Xuất sơ đồ (cần Graphviz và fonts-liberation trong container)
docker compose exec -T app python -m scripts.report_figures

# Công cụ báo cáo trên Windows dùng môi trường riêng .venv/report_tools
.venv/Scripts/python.exe scripts/report_capture.py
.venv/Scripts/python.exe scripts/report_capture.py --content-only
.venv/Scripts/python.exe scripts/report_capture.py --voice-only
.venv/Scripts/python.exe scripts/report_capture.py --infrastructure-only
.venv/Scripts/python.exe scripts/report_charts.py
.venv/Scripts/python.exe scripts/report_build.py
.venv/Scripts/python.exe scripts/report_preview.py
```

`report_capture.py` mở Chrome nền với profile mới, chỉ truy cập localhost. Chế độ đầy đủ bấm cập nhật API thật nhưng không gửi PDF đã chọn; ảnh chọn tệp và bằng chứng backend upload được tách rõ. Script kiểm tra giọng có phát audio thật. Các thư viện báo cáo chỉ cần trên máy tạo báo cáo; không thêm vào requirements runtime của ứng dụng.

Thiết lập công cụ báo cáo nếu tái tạo trên môi trường mới:

```powershell
.venv/Scripts/python.exe -m pip install --target .venv/report_tools matplotlib==3.11.2 Markdown==3.11.3 playwright==1.65.2
docker compose exec -u root -T app bash -lc "apt-get update && apt-get install -y graphviz fonts-liberation"
```

Máy tạo ảnh hiện dùng Chrome tại đường dẫn được khai báo trong [report_capture.py](../../scripts/report_capture.py). Nếu máy khác dùng vị trí Chrome khác, điều chỉnh đường dẫn đó. Gói Graphviz được cài vào container đang chạy; khi recreate container cần cài lại hoặc bổ sung vào image cho môi trường dựng báo cáo riêng.

Nếu corpus thay đổi, cập nhật lại phần mô tả, bảng và tổng số trong hai chương trước khi build. Script biểu đồ hiện chặn khi tổng khác 63/3.285 để tránh sinh ảnh mới nhưng giữ phần văn bản cũ. Các nguồn dữ liệu đầy đủ nằm trong phụ lục; thông tin nhóm/lớp và mẫu dàn trang cần nhóm điền khi hoàn thiện bản nộp.
