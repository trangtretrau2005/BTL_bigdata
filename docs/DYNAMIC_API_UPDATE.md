# Cập nhật văn bản AI qua API

## Số đếm trên giao diện

Trước đây, 47 là số văn bản đã lập chỉ mục; 69 là tổng mục trong danh mục thu thập, có cả nguồn lỗi, thiếu toàn văn hoặc trùng nội dung. Hai số có ý nghĩa khác nhau.

[Bộ thống kê chung](../src/catalog.py) lấy danh sách `source_document_ids` từ [manifest chỉ mục](../data/manifests/index_manifest.json). Thanh bên, phần giới thiệu và bộ lọc hỏi đáp đều dùng cùng tập này. Thư viện mặc định chỉ hiện văn bản tra cứu được. Tổng mục nguồn và phần chưa sẵn sàng nằm riêng trong **Tình trạng nguồn dữ liệu**.

## Thao tác cập nhật

Mở http://localhost:8501, bấm **Cập nhật dữ liệu** ở thanh bên. Ứng dụng tự thực hiện:

Có thể chọn tệp trong **Tải tài liệu lên** trước khi bấm nút này. Tệp được tự trích xuất và ghép vào cùng luồng ETL, chia đoạn, embedding, chỉ mục và HDFS. Bỏ chọn **Lấy thêm văn bản từ API** để chỉ xử lý tệp tải lên. Xem [hướng dẫn tải tài liệu](../README.md#tải-tài-liệu-của-bạn-lên).

1. Đọc danh mục API theo ngày ban hành mới nhất và lọc tài liệu về trí tuệ nhân tạo.
2. Lấy toàn văn HTML trong JSON; lưu bản phản hồi gốc, checksum và URL nguồn.
3. Chuẩn hóa, khử trùng bằng Spark và ghi Parquet.
4. Chia đoạn, giữ metadata nguồn, tái sử dụng vector không đổi và tạo vector cho đoạn mới.
5. Kiểm tra đủ point rồi chuyển alias Qdrant sang snapshot mới; làm mới thống kê giao diện.
6. Đồng bộ các lớp dữ liệu lên HDFS qua WebHDFS.

Không cần người dùng chọn hay tải từng PDF. Worker chạy nền, tiếp tục khi chuyển tab hoặc Streamlit chạy lại. Khóa tệp ngăn hai phiên trình duyệt khởi động hai lượt cập nhật đồng thời. Nếu dừng container thì worker dừng; lần sau giao diện cho phép chạy lại.

Mặc định kiểm tra 2 năm gần đây và nhận tối đa 20 văn bản mới/cập nhật mỗi nguồn trong một lượt. Có thể chọn 10 hoặc 50. Khi còn dữ liệu ngoài giới hạn, giao diện báo chưa hoàn tất và cho cập nhật tiếp. Đây là kiểm tra theo yêu cầu khi nhấn nút, chưa có lịch chạy định kỳ.

## API Bộ Tư pháp

[Cấu hình nguồn](../data/api_sources.json) và [mã thu thập](../src/ingestion/dynamic_api.py) sử dụng endpoint công khai của Bộ Tư pháp đã kiểm tra bằng request thật, không dùng API key trong luồng này.

Danh mục phân trang:

```http
POST https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/all
Content-Type: application/json

{
  "pageNumber": 1,
  "pageSize": 50,
  "keyword": "\"trí tuệ nhân tạo\"",
  "sortBy": "issueDate",
  "sortDirection": "DESC"
}
```

Response cần có `success=true` và `data.items`. Mỗi mục chứa `id`, `title`, `issueDate`, `agencyName`, `document_url` cùng metadata khác. Dùng cụm tìm kiếm có dấu ngoặc kép để hạn chế kết quả chỉ trùng từng từ.

Toàn văn:

```http
GET https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/{id}
```

Chỉ trích xuất `data.documentContent.content`. Các trường tóm tắt, phân tích AI hoặc metadata không được dùng thay toàn văn. Giữ nguyên trạng thái hiệu lực do nguồn cung cấp; không tự suy đoán một văn bản còn hiệu lực.

Đây là endpoint công khai được xác minh thực nghiệm, chưa có tài liệu hợp đồng API/SLA đi kèm dự án. Bộ thu thập kiểm tra cấu trúc phản hồi và báo lỗi nếu hợp đồng thay đổi. HTTP 200 không đủ để coi dữ liệu hợp lệ: trang chặn truy cập, chuyển hướng ngoài nguồn chính thức và nội dung quá ngắn đều bị loại.

## Đọc tăng dần và chống trùng

- Lưu định danh từ xa, hash metadata, hash toàn văn và thời điểm đã kiểm tra. Trong cùng ngày, metadata không đổi thì không tải lại toàn văn đã có.
- Sau khi quét hoàn tất, lưu checkpoint; lượt sau đọc từ checkpoint với khoảng chồng 7 ngày theo ngày ban hành. Cơ chế này ưu tiên văn bản mới, không phải giám sát mọi sửa đổi của tất cả văn bản cũ.
- Khi lỗi phân trang, giữ các kết quả hợp lệ đã lấy nhưng không nâng checkpoint. Lượt sau quét lại phần chưa hoàn tất.
- Số hiệu, cơ quan ban hành và năm giúp nhận diện văn bản đã có. Ví dụ quyết định `127/QĐ-TTg` cần ghép năm ban hành để không nhầm các quyết định khác năm. Toàn văn API mới thay phiên bản cùng định danh trong đầu vào xử lý; các phản hồi gốc vẫn được giữ.
- Dữ liệu giống hệt được Spark khử trùng theo checksum nội dung. Vì vậy số bản ghi API nhận được có thể lớn hơn số văn bản mới đưa vào tra cứu.

## Các lớp của Data Lake

| Lớp | Dữ liệu | Lưu trữ |
| --- | --- | --- |
| Bronze | JSON danh mục và phản hồi toàn văn bất biến theo SHA-256 | `data/dynamic/raw`, HDFS `/ai_docs/raw/api` |
| Parsed | Văn bản chuẩn hóa, định danh, metadata và provenance | `data/dynamic/parsed`, HDFS `/ai_docs/parsed/api` |
| Silver | Parquet đã làm sạch/khử trùng bằng Spark | `data/updates/{job}/processed`, HDFS `/ai_docs/processed/{job}` |
| Gold | Đoạn có nguồn và snapshot vector | `data/updates/{job}/chunks`, HDFS `/ai_docs/chunks/{job}`, Qdrant |
| Điều phối | Checkpoint, báo cáo lỗi, trạng thái worker, manifest phiên bản | `data/manifests` và bản đồng bộ HDFS |

[Luồng cập nhật](../scripts/update_data.py) dùng snapshot riêng cho từng lượt. RAG đọc đường dẫn Processed/Chunks từ manifest đang hoạt động để khớp đúng phiên bản chỉ mục. Lỗi trước khi công bố giữ chỉ mục cũ. Nếu HDFS lỗi sau khi đã công bố chỉ mục, giao diện báo cập nhật một phần; tra cứu mới vẫn dùng được. Spark chạy `local[2]`; đây là demo Data Lake trên một máy, chưa phải triển khai hay benchmark Spark phân tán.

## Nguồn Federal Register tùy chọn

Đã có adapter theo [API chính thức Federal Register](https://www.federalregister.gov/developers/documentation/api/v1). API danh mục/metadata truy cập được trong lần kiểm tra, nhưng URL toàn văn trả về trang **Request Access**, kể cả khi mã HTTP là 200. Adapter này hiện **tắt mặc định**; các trang đó không được đưa vào bộ tra cứu. Chỉ bật lại sau khi kiểm tra truy cập toàn văn thành công. Nút cập nhật hiện dùng nguồn Bộ Tư pháp.

## Chạy từ dòng lệnh

```powershell
# Xếp một lượt cập nhật nền, giống thao tác trên giao diện
docker compose exec -T app python -m scripts.update_data --providers vbpl --max-documents 20

# Kiểm thử toàn bộ
docker compose exec -T app python -m pytest -q -p no:cacheprovider
```

[Trạng thái lượt mới nhất](../data/manifests/update_status.json) có `job_id`, giai đoạn, số văn bản thay đổi, lỗi theo nguồn và kết quả công bố. Log worker nằm tại `data/updates/{job_id}/worker.log`. Thay đổi giới hạn trang, thời gian nhìn lại hoặc bật nguồn tại [cấu hình API](../data/api_sources.json).

Xem [kết quả nghiệm thu chạy API thật](API_RUN_VERIFICATION.md) và [bằng chứng kiểm tra dịch vụ](../evaluation/dynamic_api_live_check.json).
