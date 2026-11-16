"""Regressions for unavailable voices, segmented audio and changing voice settings."""
import base64
import json
import re

from src.rag import tts
from src.rag.avatar_component import build_talking_avatar_html


def test_fallback_playlist_preserves_text_order_speed_and_cooldown(monkeypatch):
    attempted = []
    def unavailable(*args):
        attempted.append(args)
        raise TimeoutError('neural service offline')
    monkeypatch.setattr(tts, '_neural_retry_at', 0)
    monkeypatch.setattr(tts, '_neural_audio', unavailable)
    monkeypatch.setattr(tts, '_piper_audio', unavailable)
    monkeypatch.setattr(tts, '_google_phrase', lambda phrase, lang: phrase.encode('utf-8'))
    text = 'AI cần minh bạch. Giám sát của con người rất cần thiết. ' * 8
    first = tts.synthesize_speech(text, voice='vi-VN-NamMinhNeural', rate='-12%')
    second = tts.synthesize_speech(text, voice='vi-VN-HoaiMyNeural')
    assert sum(len(args) == 3 for args in attempted) == 1  # Neural outage cooldown.
    assert first['provider'] == second['provider'] == 'google'
    assert first['voice'] == 'vi' and first['playback_rate'] == .88
    segments = first['segments']
    assert len(segments) > 1
    assert ' '.join(part['text'] for part in segments) == tts.clean_text_for_speech(text)
    for part in segments:
        assert base64.b64decode(part['audio_b64']).decode('utf-8') == part['text']
        assert len(part['text']) <= 170


def test_both_services_offline_never_fabricates_audio(monkeypatch):
    monkeypatch.setattr(tts, '_neural_retry_at', float('inf'))
    def unavailable(*args):
        raise ConnectionError('offline')
    monkeypatch.setattr(tts, '_google_phrase', unavailable)
    monkeypatch.setattr(tts, '_piper_audio', unavailable)
    result = tts.synthesize_speech('Trí tuệ nhân tạo cần minh bạch.')
    assert result['segments'] == [] and result['provider'] is None
    assert result['error']


def test_neural_playlist_keeps_requested_voice_without_double_speed(monkeypatch):
    monkeypatch.setattr(tts, '_neural_retry_at', 0)
    calls = []
    def neural(text, voice, rate):
        calls.append((text, voice, rate))
        return b'neural-mp3'
    monkeypatch.setattr(tts, '_neural_audio', neural)
    result = tts.synthesize_speech('AI cần minh bạch.', voice='vi-VN-NamMinhNeural', rate='+5%')
    assert result['provider'] == 'edge' and result['playback_rate'] == 1
    assert calls[0][1:] == ('vi-VN-NamMinhNeural', '+5%')


def test_model_text_cannot_escape_presenter_script():
    malicious = '</script><img src=x onerror=alert(1)>'
    html = build_talking_avatar_html(malicious, sentences=[malicious])
    assert malicious not in html
    assert html.count('</script>') == 1
    payload = re.search(r'const CONFIG=(.*);', html).group(1)
    assert json.loads(payload)['spokenText'] == malicious
    assert json.loads(payload)['autoPlay'] is False


def test_single_female_voice_changes_speed_without_stale_audio(monkeypatch):
    from streamlit.testing.v1 import AppTest
    calls = []
    def synthesize(text, **kwargs):
        calls.append((kwargs['voice'], kwargs['rate']))
        return {'segments': [{'text': text, 'audio_b64': base64.b64encode(str(kwargs).encode()).decode()}],
                'provider': 'edge', 'playback_rate': 1}
    monkeypatch.setattr('src.rag.tts.synthesize_speech', synthesize)
    app = AppTest.from_file('app.py', default_timeout=30).run()
    assert not any(box.key=='speech_voice' for box in app.selectbox)
    app.button(key='preview_generate').click().run()
    assert not app.exception
    assert calls == [('vi-VN-HoaiMyNeural','-5%')]
    previous_audio = json.loads(re.search(r'const CONFIG=(.*);',app.get('iframe')[-1].proto.srcdoc).group(1))['segments'][0]['audio_b64']
    app.select_slider(key='speech_speed').set_value('Nhanh').run()
    assert not app.exception
    # No new service call or use of the old female audio after changing the setting.
    assert calls == [('vi-VN-HoaiMyNeural','-5%')]
    for player in app.get('iframe'):
        assert previous_audio not in player.proto.srcdoc
    app.button(key='preview_generate').click().run()
    assert not app.exception
    assert calls == [('vi-VN-HoaiMyNeural','-5%'), ('vi-VN-HoaiMyNeural','+5%')]


def test_local_voice_never_sends_text_to_external_tts(monkeypatch):
    def network_unexpected(*args):
        raise AssertionError('Local mode must not call an online provider')
    monkeypatch.setattr(tts, '_neural_audio', network_unexpected)
    monkeypatch.setattr(tts, '_google_phrase', network_unexpected)
    monkeypatch.setattr(tts, '_piper_audio', lambda text, rate: b'RIFF-test-WAVE')
    result = tts.synthesize_speech('AI cần minh bạch.', voice='local:vi_VN-vais1000-medium')
    assert result['provider'] == 'piper'
    assert result['segments'][0]['mime'] == 'audio/wav'
    assert result['playback_rate'] == 1.0


def test_missing_local_model_does_not_send_text_to_online_fallback(monkeypatch):
    sent = []
    def missing(*args):
        raise FileNotFoundError('not installed')
    monkeypatch.setattr(tts, '_piper_audio', missing)
    monkeypatch.setattr(tts, '_google_phrase', lambda *args: sent.append(args))
    result = tts.synthesize_speech('AI cần minh bạch.', voice='local:vi_VN-vais1000-medium')
    assert not result['segments'] and not sent and result['error']
