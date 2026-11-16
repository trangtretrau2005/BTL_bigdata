"""Self-contained speech player and illustrated human presenter."""
from __future__ import annotations
import json
from pathlib import Path


def build_talking_avatar_html(spoken_text: str, audio_b64: str | None = None,
    sentences: list[str] | None = None, presenter_gender: str = 'female',
    auto_play: bool = False, status_label: str = 'Sẵn sàng', *,
    segments: list[dict] | None = None, provider: str | None = None,
    playback_rate: float = 1.0, show_avatar: bool = True,
    device_local_only: bool = False) -> str:
    if segments is None:
        segments = [{'text': spoken_text, 'audio_b64': audio_b64}] if audio_b64 else []
    payload = {'spokenText': spoken_text or '', 'segments': segments,
        'sentences': sentences or ([spoken_text] if spoken_text else []),
        'gender': 'male' if presenter_gender == 'male' else 'female',
        'autoPlay': bool(auto_play), 'provider': provider,
        'rate': max(.65, min(1.5, float(playback_rate))),
        'showAvatar': bool(show_avatar), 'statusLabel': status_label,
        'deviceLocalOnly': bool(device_local_only)}
    # Model text is data only; it cannot close the script element.
    encoded = json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    encoded = encoded.replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    return Path(__file__).with_name('presenter.html').read_text(encoding='utf-8').replace('__PRESENTER_CONFIG__', encoded)
