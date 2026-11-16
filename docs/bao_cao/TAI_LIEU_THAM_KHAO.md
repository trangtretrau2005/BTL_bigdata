# TÀI LIỆU THAM KHẢO

Các tài liệu công nghệ dưới đây là công bố nghiên cứu, tài liệu của dự án hoặc tài liệu từ cơ quan/nhà phát triển. Ngày truy cập/đối chiếu: **16/11/2026**. Số trong ngoặc vuông được dùng thống nhất trong hai chương. Nội dung thiết kế và số đo riêng của nhóm lấy từ mã nguồn và thư mục [evidence](evidence/), không gán cho các tài liệu bên ngoài.

[1] Apache Software Foundation, *HDFS Architecture*, Apache Hadoop 3.4.1, 2024. [Tài liệu chính thức](https://hadoop.apache.org/docs/r3.4.1/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html). Dùng cho vai trò NameNode/DataNode, block và replication.

[2] Apache Software Foundation, *WebHDFS REST API*, Apache Hadoop 3.4.1, 2024. [Tài liệu chính thức](https://hadoop.apache.org/docs/r3.4.1/hadoop-project-dist/hadoop-hdfs/WebHDFS.html). Dùng cho CREATE/redirect, GETFILESTATUS, LISTSTATUS, OPEN và GETCONTENTSUMMARY; phân biệt metadata thư mục và tệp.

[3] M. Zaharia và cộng sự, “Resilient Distributed Datasets: A Fault-Tolerant Abstraction for In-Memory Cluster Computing,” *USENIX NSDI*, 2012. [Bài nghiên cứu và thông tin hội nghị](https://www.usenix.org/conference/nsdi12/technical-sessions/presentation/zaharia). Cơ sở công nghệ Spark; không dùng bài này để khẳng định demo đã chạy trên nhiều máy.

[4] Apache Software Foundation, *Parquet Files — Spark SQL, DataFrames and Datasets Guide*, Apache Spark 3.5.3. [Bản tài liệu theo phiên bản](https://dist.apache.org/repos/dist/release/spark/docs/3.5.3/sql-data-sources-parquet.html). Cơ sở đọc/ghi Parquet và tùy chọn liên quan.

[5] Databricks, *What is the medallion lakehouse architecture?* [Tài liệu kiến trúc](https://docs.databricks.com/aws/en/lakehouse/medallion). Tham khảo mẫu phân lớp Bronze/Silver/Gold; hệ thống hiện tại không sử dụng Databricks hoặc Delta Lake.

[6] Apache Parquet, *Overview*. [Tài liệu định dạng](https://parquet.apache.org/docs/overview/). Cơ sở lựa chọn định dạng cột cho lớp Processed.

[7] P. Lewis và cộng sự, “Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks,” 2020, arXiv:2005.11401. [Bài nghiên cứu](https://arxiv.org/abs/2005.11401). Cơ sở kết hợp nguồn truy xuất với mô hình sinh.

[8] J. Chen và cộng sự, “BGE M3-Embedding: Multi-Lingual, Multi-Functionality, Multi-Granularity Text Embeddings Through Self-Knowledge Distillation,” 2024, arXiv:2402.03216. [Bài nghiên cứu](https://arxiv.org/abs/2402.03216). Dự án hiện chỉ khai thác dense embedding.

[9] Qdrant, *Collections*, mục collection aliases. [Tài liệu chính thức](https://qdrant.tech/documentation/manage-data/collections/). Cơ sở dùng alias và thay đổi alias nguyên tử trong Qdrant; không suy rộng thành giao dịch chung với HDFS/tệp manifest.

[10] A. Yang và cộng sự, “Qwen3 Technical Report,” 2025, arXiv:2505.09388. [Báo cáo kỹ thuật](https://arxiv.org/abs/2505.09388). Cơ sở lựa chọn họ mô hình Qwen3; tag triển khai cụ thể đối chiếu thêm ở [11].

[11] Ollama, *qwen3:4b-instruct-2507-q4_K_M*. [Model card của đúng tag](https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M). Dùng nhận diện bản Instruct, quy mô và lượng tử hóa; context ứng dụng do nhóm cấu hình là 6.144 token.

[12] P. Groth và L. Moreau (biên tập), *PROV-Overview: An Overview of the PROV Family of Documents*, W3C Working Group Note, 30/04/2013. [Tài liệu W3C](https://www.w3.org/TR/prov-overview/). Tham khảo ý tưởng truy nguyên entity/activity; không tuyên bố schema của dự án tuân thủ đầy đủ PROV-O.

[13] Docker, *How Compose works*. [Tài liệu chính thức](https://docs.docker.com/compose/intro/compose-application-model/). Cơ sở mô hình services, networks, volumes trong triển khai nhiều container.

[14] Streamlit, *st.file_uploader*, tài liệu phiên bản 1.41.0. [API reference](https://docs.streamlit.io/1.41.0/develop/api-reference/widgets/st.file_uploader). Tham khảo chức năng nhận nhiều tệp; giới hạn 10 tệp/50 MiB/100 MiB là quy tắc của dự án, không phải mặc định của Streamlit.

[15] Microsoft/Playwright, *Screenshots — Python*. [Tài liệu chính thức](https://playwright.dev/python/docs/screenshots). Dùng cho phương pháp lấy ảnh bằng chứng trong báo cáo, không phải thành phần runtime của pipeline RAG.

[16] MDN Web Docs, *AnalyserNode — Web Audio API*. [Tài liệu API](https://developer.mozilla.org/en-US/docs/Web/API/AnalyserNode). Cơ sở lấy mẫu âm thanh miền thời gian cho hoạt ảnh người nói; không phải tài liệu chứng minh lip-sync âm vị.

[17] rany2 và cộng tác viên, *edge-tts*. [Kho mã nguồn và hướng dẫn của tác giả](https://github.com/rany2/edge-tts). Thư viện truy cập dịch vụ đọc trực tuyến của Microsoft Edge; cần phân biệt với Azure Speech API có tài khoản thương mại.

[18] OHF-Voice, *Piper: fast and local neural text-to-speech engine*. [Kho mã nguồn](https://github.com/OHF-Voice/piper1-gpl). Backend TTS dự phòng; thông tin giấy phép và attribution của bản cài xem thêm [VOICE_ATTRIBUTION.md](../VOICE_ATTRIBUTION.md).

[19] rhasspy/piper-voices, *vi_VN-vais1000-medium — MODEL_CARD*, revision `3d796cc2f2c884b3517c527507e084f7bb245aea`. [Model card cố định phiên bản](https://huggingface.co/rhasspy/piper-voices/blob/3d796cc2f2c884b3517c527507e084f7bb245aea/vi/vi_VN/vais1000/medium/MODEL_CARD). Dùng cho nhận diện giọng tiếng Việt dự phòng; mẫu WAV trong báo cáo được đo lại từ playlist thực tế.

[20] Bộ Tư pháp, *Cơ sở dữ liệu quốc gia về pháp luật — nguồn công khai*. [Cổng dữ liệu](https://vbpl.vn/), endpoint danh mục `https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/all` và endpoint toàn văn `/api/qtdc/public/doc/{id}`. Hợp đồng payload/response trong báo cáo được xác minh bằng ứng dụng gọi HTTP thật, không phải trích một đặc tả API có cam kết ổn định. Xem [cấu hình nguồn](../../data/api_sources.json), [bằng chứng API](evidence/previous_api_verification.json) và [lượt giao diện](evidence/capture_update_status.json).

## Nguồn dữ liệu cụ thể của corpus

Để tránh nhập nhằng tài liệu công nghệ với văn bản đem đi tra cứu, danh mục dữ liệu được tách thành [PHU_LUC_DANH_MUC_DU_LIEU.md](PHU_LUC_DANH_MUC_DU_LIEU.md) và [CSV danh mục](evidence/dataset_catalog.csv). Phụ lục liệt kê toàn bộ 63 tài liệu đang hoạt động với URL, loại, ngôn ngữ, khu vực và provenance, đối chiếu theo snapshot của báo cáo. Đây là danh mục nguồn của bản dữ liệu đã thu thập, không khẳng định tất cả URL hiện còn truy cập được hoặc mọi văn bản còn hiệu lực.
