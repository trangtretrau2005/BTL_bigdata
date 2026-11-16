# Giọng đọc cục bộ

Piper TTS 1.8.0: https://github.com/OHF-Voice/piper1-gpl — GPL-3.0.

Model `vi_VN-vais1000-medium`, một người nói, 22.050 Hz, được công bố bởi dự án
rhasspy/piper-voices. Bản model được cố định tại revision
`3d796cc2f2c884b3517c527507e084f7bb245aea`.

Model card: https://huggingface.co/rhasspy/piper-voices/blob/3d796cc2f2c884b3517c527507e084f7bb245aea/vi/vi_VN/vais1000/medium/MODEL_CARD

Dữ liệu huấn luyện: VAIS-1000 Vietnamese Speech Synthesis Corpus,
https://ieee-dataport.org/documents/vais-1000-vietnamese-speech-synthesis-corpus.
Model card nêu giấy phép dữ liệu CC BY 4.0:
https://creativecommons.org/licenses/by/4.0/.
Model được fine-tune từ giọng lessac (medium). Không dùng để mạo danh một cá nhân.

`scripts/setup_voice.py` lưu model card nguyên bản và checksum của từng file
trong `data/models/piper/`. Những file lớn được tải lại khi thiết lập, không đưa vào Git.
Lần tạo tiếng nói bằng lựa chọn cục bộ diễn ra trong máy/container; không gửi nội dung
câu trả lời ra dịch vụ TTS bên ngoài. Lựa chọn giọng cục bộ có một giọng;
Hoài My/Nam Minh là các lựa chọn dịch vụ trực tuyến riêng.
