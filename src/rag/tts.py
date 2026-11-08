"""Vietnamese & English Text-to-Speech (TTS) audio generator for the Talking AI Legal Avatar.

Generates MP3 audio (base64 encoded) in parallel across sentence chunks so the
HTML5 Talking Human Presenter can play real Vietnamese speech and synchronize
its mouth/jaw/viseme movements via Web Audio API AnalyserNode.
"""
from __future__ import annotations
import base64
from concurrent.futures import ThreadPoolExecutor
import re
import urllib.parse
import requests


def clean_text_for_speech(text: str) -> str:
    """Làm sạch văn bản Markdown và ký hiệu kỹ thuật để giọng đọc tự nhiên như phát thanh viên."""
    if not text:
        return ""
    s = text
    # Bỏ dấu trang [Trang X]
    s = re.sub(r"\[Trang\s*\d+\]", " ", s)
    # Đổi nhãn trích dẫn [S1] thành cụm từ đọc tự nhiên
    s = re.sub(r"\[S(\d+)\]", r", theo nguồn số \1,", s)
    # Bỏ ký tự markdown **, *, #, >, `, - ở đầu dòng
    s = re.sub(r"[*_#`>]+", " ", s)
    s = re.sub(r"(?m)^\s*[-•]\s*", "", s)
    # Đổi các từ viết tắt pháp lý phổ biến sang cách đọc rõ ràng
    s = re.sub(r"\bQĐ-TTg\b", "Quyết định Thủ tướng Chính phủ", s)
    s = re.sub(r"\bNĐ-CP\b", "Nghị định Chính phủ", s)
    s = re.sub(r"\bQH15\b", "Quốc hội khóa 15", s)
    s = re.sub(r"\bQH13\b", "Quốc hội khóa 13", s)
    # Gom khoảng trắng thừa
    s = re.sub(r"\s+", " ", s).strip()
    return s


def split_into_tts_chunks(text: str, max_len: int = 175) -> list[str]:
    """Tách văn bản thành các câu/cụm ngắn <= max_len ký tự để синтез giọng nói nhanh và không bị ngắt từ."""
    clean = clean_text_for_speech(text)
    if not clean:
        return []

    sentences = re.split(r"(?<=[.!?;\n])\s+", clean)
    chunks: list[str] = []
    current = ""

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        if len(sent) <= max_len:
            if len(current) + len(sent) + 1 <= max_len:
                current = f"{current} {sent}".strip()
            else:
                if current:
                    chunks.append(current)
                current = sent
        else:
            # Nếu câu quá dài, tách tiếp theo dấu phẩy hoặc khoảng trắng
            subparts = re.split(r"(?<=[,:])\s+", sent)
            for sub in subparts:
                sub = sub.strip()
                if not sub:
                    continue
                if len(current) + len(sub) + 1 <= max_len:
                    current = f"{current} {sub}".strip()
                else:
                    if current:
                        chunks.append(current)
                    if len(sub) <= max_len:
                        current = sub
                    else:
                        words = sub.split()
                        temp = ""
                        for w in words:
                            if len(temp) + len(w) + 1 <= max_len:
                                temp = f"{temp} {w}".strip()
                            else:
                                if temp:
                                    chunks.append(temp)
                                temp = w
                        current = temp

    if current:
        chunks.append(current)
    return chunks[:14]  # Giới hạn tối đa ~14 câu cho một lần thuyết trình mượt mà


def _fetch_single_mp3(chunk: str, lang: str = "vi") -> bytes:
    q = urllib.parse.quote(chunk)
    url = f"https://translate.google.com/translate_tts?ie=UTF-8&tl={lang}&client=tw-ob&q={q}"
    resp = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        timeout=8,
    )
    resp.raise_for_status()
    return resp.content


def synthesize_speech_base64(text: str, lang: str = "vi") -> tuple[str | None, list[str]]:
    """Sinh file âm thanh MP3 (trả về chuỗi base64 và danh sách các câu phụ đề).

    Nếu mạng hoặc dịch vụ TTS bị gián đoạn, trả về (None, sentences) để trình duyệt
    tự động chuyển sang Web Speech API.
    """
    sentences = split_into_tts_chunks(text, max_len=175)
    if not sentences:
        return None, []

    try:
        with ThreadPoolExecutor(max_workers=min(6, len(sentences))) as pool:
            futures = [pool.submit(_fetch_single_mp3, sent, lang) for sent in sentences]
            mp3_parts = [f.result(timeout=10) for f in futures]
        combined = b"".join(mp3_parts)
        if not combined:
            return None, sentences
        b64 = base64.b64encode(combined).decode("ascii")
        return b64, sentences
    except Exception:
        return None, sentences


def transcribe_vietnamese_audio(audio_bytes: bytes) -> str | None:
    """Nhận diện giọng nói tiếng Việt (Speech-to-Text) từ dữ liệu WAV của st.audio_input."""
    if not audio_bytes:
        return None
    try:
        import io
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio_data = recognizer.record(source)
        text = recognizer.recognize_google(audio_data, language="vi-VN")
        return text.strip() if text else None
    except Exception:
        return None
