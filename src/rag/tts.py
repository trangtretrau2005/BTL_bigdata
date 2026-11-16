"""Vietnamese speech: local Piper, optional online neural voices and labeled fallbacks."""
from __future__ import annotations

import base64
import asyncio
from functools import lru_cache
from contextvars import ContextVar
from concurrent.futures import ThreadPoolExecutor
import logging
import re
import time
import io
import os
import wave
import json
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)
_speech_provider = ContextVar('speech_provider', default=None)
_neural_retry_at = 0.0
_provider_lock = Lock()
_piper_lock = Lock()

def last_speech_provider():
    return _speech_provider.get()

@lru_cache(maxsize=128)
def _google_phrase(text: str, lang: str) -> bytes:
    # One phrase per MP3: concatenating MP3 files gives incorrect duration and seeking.
    import requests
    response = requests.get('https://translate.google.com/translate_tts',
        params={'ie': 'UTF-8', 'tl': lang, 'client': 'tw-ob', 'q': text},
        headers={'User-Agent': 'Mozilla/5.0'}, timeout=(4, 8))
    response.raise_for_status()
    if 'audio' not in response.headers.get('Content-Type', '') or len(response.content) < 100:
        raise RuntimeError('Dịch vụ dự phòng không trả âm thanh')
    return response.content


def clean_text_for_speech(text: str) -> str:
    """Keep the answer itself; strip source labels and visual-only formatting."""
    if not text:
        return ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\[(?:S\d+|Trang\s*\d+(?:[–-]\d+)?)\]", "", text, flags=re.IGNORECASE)
    spoken_numbers = ('Thứ nhất', 'Thứ hai', 'Thứ ba', 'Thứ tư', 'Thứ năm', 'Thứ sáu', 'Thứ bảy', 'Thứ tám', 'Thứ chín', 'Thứ mười')
    text = re.sub(r'(?m)^\s*(10|[1-9])[.)]\s+', lambda m: spoken_numbers[int(m.group(1)) - 1] + ', ', text)
    text = re.sub(r"(?m)^\s*(?:[-•]|\d+[.)])\s+", "", text)
    ordinals = dict(zip('abcdefgh', ('Thứ nhất','Thứ hai','Thứ ba','Thứ tư','Thứ năm','Thứ sáu','Thứ bảy','Thứ tám')))
    text = re.sub(r'(?m)^\s*\(([a-h])\)\s*', lambda m: ordinals[m.group(1)] + ', ', text)
    text = re.sub(r"[*_#`>|]+", " ", text)
    replacements = {
        "QĐ-TTg": "Quyết định Thủ tướng Chính phủ",
        "NĐ-CP": "Nghị định Chính phủ",
        "QH15": "Quốc hội khóa mười lăm",
        "QH13": "Quốc hội khóa mười ba",
        "EU AI Act": "Đạo luật Trí tuệ nhân tạo của Liên minh châu Âu",
        "LLM": "mô hình ngôn ngữ lớn",
        "AI": "trí tuệ nhân tạo",
    }
    for short, spoken in replacements.items():
        text = re.sub(r"(?<!\w)" + re.escape(short) + r"(?!\w)", spoken, text)
    # Blank lines and list items become sentence pauses instead of rushed narration.
    lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if not line:
            continue
        if line[-1] not in ".!?;:":
            line += "."
        lines.append(line)
    text = " ".join(lines)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([,;:])\s*([,.;:])", r"\2", text)
    return re.sub(r"\s+", " ", text).strip()


def split_into_tts_chunks(text: str, max_len: int = 240) -> list[str]:
    """Subtitle phrases, split at punctuation without truncating the answer."""
    if max_len < 10:
        raise ValueError("max_len must be at least 10")
    clean = clean_text_for_speech(text)
    if not clean:
        return []
    pieces = re.split(r"(?<=[.!?;:])\s+", clean)
    chunks = []
    for piece in pieces:
        while len(piece) > max_len:
            end = piece.rfind(" ", 0, max_len + 1)
            if end < 1:
                end = max_len
            chunks.append(piece[:end].strip())
            piece = piece[end:].strip()
        if piece:
            chunks.append(piece)
    return chunks


@lru_cache(maxsize=32)
def _neural_audio(text: str, voice: str, rate: str) -> bytes:
    import edge_tts

    communicator = edge_tts.Communicate(
        text, voice, rate=rate, pitch="+0Hz", boundary="SentenceBoundary",
        connect_timeout=6, receive_timeout=12,
    )
    async def collect():
        parts = []
        async for chunk in communicator.stream():
            if chunk['type'] == 'audio':
                parts.append(chunk['data'])
        return b''.join(parts)
    async def bounded_collect():
        return await asyncio.wait_for(collect(), timeout=8)
    audio = asyncio.run(bounded_collect())
    if not audio:
        raise RuntimeError("Dịch vụ giọng nói không trả âm thanh")
    return audio


@lru_cache(maxsize=1)
def _piper_voice():
    model = Path(os.getenv('PIPER_VOICE_PATH', 'data/models/piper/vi_VN-vais1000-medium.onnx'))
    if not model.is_file():
        raise FileNotFoundError('Chưa tải model Piper: python -m scripts.setup_voice')
    import onnxruntime
    from piper import PiperVoice
    from piper.config import PiperConfig
    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    return PiperVoice(
        session=onnxruntime.InferenceSession(str(model), sess_options=options, providers=['CPUExecutionProvider']),
        config=PiperConfig.from_dict(json.loads(Path(str(model) + '.json').read_text(encoding='utf-8'))),
    )


@lru_cache(maxsize=64)
def _piper_audio(text: str, rate: str) -> bytes:
    from piper import SynthesisConfig
    speed = max(.75, min(1.3, 1 + float(rate.rstrip('%')) / 100))
    buffer = io.BytesIO()
    with _piper_lock:
        voice = _piper_voice()
        with wave.open(buffer, 'wb') as output:
            voice.synthesize_wav(text, output, syn_config=SynthesisConfig(length_scale=1 / speed))
    # A short real pause between playlist phrases, included in the WAV duration.
    with wave.open(io.BytesIO(buffer.getvalue()), 'rb') as source:
        params = source.getparams()
        frames = source.readframes(source.getnframes())
    output = io.BytesIO()
    with wave.open(output, 'wb') as target:
        target.setparams(params)
        target.writeframes(frames + bytes(round(params.framerate * .18) * params.nchannels * params.sampwidth))
    return output.getvalue()


def synthesize_speech(text: str, lang: str = 'vi', *, voice: str | None = None,
                      rate: str = '-5%') -> dict:
    """A playlist with one subtitle per real audio segment, never a concatenated MP3.

    The provider cooldown prevents every click from waiting for the same outage.
    The UI must label the effective provider instead of promising an unavailable voice.
    """
    global _neural_retry_at
    clean = clean_text_for_speech(text)
    selected = voice or ('vi-VN-HoaiMyNeural' if lang == 'vi' else 'en-US-JennyNeural')
    if not clean:
        return {'segments': [], 'provider': None, 'voice': None, 'playback_rate': 1.0}
    with _provider_lock:
        try_neural = not selected.startswith('local:') and time.monotonic() >= _neural_retry_at
    if try_neural:
        phrases = split_into_tts_chunks(clean, max_len=700)
        try:
            audio_parts = [_neural_audio(phrase, selected, rate) for phrase in phrases]
            _speech_provider.set('edge')
            return {'segments': [{'text': phrase, 'audio_b64': base64.b64encode(audio).decode('ascii')}
                                 for phrase, audio in zip(phrases, audio_parts)],
                    'provider': 'edge', 'voice': selected, 'playback_rate': 1.0}
        except Exception as exc:
            logger.warning('Neural voice unavailable; retry after cooldown: %s', exc)
            with _provider_lock:
                _neural_retry_at = time.monotonic() + 300
    if lang == 'vi':
        phrases = split_into_tts_chunks(clean, max_len=240)
        try:
            parts = [_piper_audio(phrase, rate) for phrase in phrases]
            _speech_provider.set('piper')
            return {'segments': [{'text': phrase, 'audio_b64': base64.b64encode(audio).decode('ascii'), 'mime': 'audio/wav'}
                                 for phrase, audio in zip(phrases, parts)],
                    'provider': 'piper', 'voice': 'vi_VN-vais1000-medium', 'playback_rate': 1.0}
        except Exception as exc:
            logger.warning('Local Vietnamese voice unavailable: %s', exc)
            if selected.startswith('local:'):
                _speech_provider.set(None)
                return {'segments': [], 'provider': None, 'voice': None, 'playback_rate': 1.0,
                        'error': 'Chưa sẵn sàng giọng Việt cục bộ. Hãy chạy python -m scripts.setup_voice trong container.'}
    phrases = split_into_tts_chunks(clean, max_len=170)
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            parts = list(pool.map(lambda phrase: _google_phrase(phrase, lang), phrases))
        speed = max(.75, min(1.3, 1 + float(rate.rstrip('%')) / 100))
        _speech_provider.set('google')
        return {'segments': [{'text': phrase, 'audio_b64': base64.b64encode(audio).decode('ascii')}
                             for phrase, audio in zip(phrases, parts)],
                'provider': 'google', 'voice': 'vi' if lang == 'vi' else lang, 'playback_rate': speed}
    except Exception as exc:
        logger.warning('Alternate speech service unavailable: %s', exc)
        _speech_provider.set(None)
        return {'segments': [], 'provider': None, 'voice': None, 'playback_rate': 1.0,
                'error': 'Chưa kết nối được dịch vụ đọc. Bạn có thể thử giọng Việt trên thiết bị.'}


def synthesize_speech_base64(
    text: str, lang: str = "vi", *, voice: str | None = None, rate: str = "-5%",
) -> tuple[str | None, list[str]]:
    """Legacy single-clip API; multi-clip callers should use synthesize_speech.

    Never concatenate MP3 files: the browser would report an incorrect duration.
    """
    result = synthesize_speech(text, lang, voice=voice, rate=rate)
    phrases = split_into_tts_chunks(text)
    parts = result['segments']
    return (parts[0]['audio_b64'] if len(parts) == 1 else None), phrases



def transcribe_vietnamese_audio(audio_bytes: bytes) -> str | None:
    """Transcribe user-recorded WAV with Google Speech Recognition."""
    if not audio_bytes:
        return None
    try:
        import io
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        recognizer.operation_timeout = 15
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio_data = recognizer.record(source)
        text = recognizer.recognize_google(audio_data, language="vi-VN")
        return text.strip() if text else None
    except Exception as exc:
        logger.warning("Vietnamese transcription unavailable: %s", exc)
        return None
