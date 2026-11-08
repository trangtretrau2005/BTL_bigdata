"""Clean White-Blue Talking Human Presenter with Real-Time 60FPS Lip Sync."""
from __future__ import annotations
import json


def build_talking_avatar_html(
    spoken_text: str,
    audio_b64: str | None,
    sentences: list[str],
    presenter_gender: str = "female",
    auto_play: bool = True,
    status_label: str = "SẴN SÀNG",
) -> str:
    payload = {
        "spokenText": spoken_text or "",
        "audioB64": audio_b64 or "",
        "sentences": sentences or ([spoken_text] if spoken_text else []),
        "gender": presenter_gender,
        "autoPlay": bool(auto_play),
    }
    payload_json = json.dumps(payload, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8" />
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, sans-serif; }}
  body {{ background: transparent; color: #0f172a; overflow: hidden; }}
  .studio-shell {{
    background: #ffffff;
    border: 2px solid #bfdbfe;
    border-radius: 18px;
    overflow: hidden;
    box-shadow: 0 8px 24px rgba(29, 78, 216, 0.08);
  }}
  .studio-topbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    background: #eff6ff;
    border-bottom: 1px solid #dbeafe;
  }}
  .live-badge {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 5px 12px;
    border-radius: 999px;
    font-weight: 700;
    font-size: 14px;
    background: #dbeafe;
    color: #1d4ed8;
  }}
  .live-dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #2563eb;
    animation: pulse 1.2s infinite;
  }}
  @keyframes pulse {{
    0%, 100% {{ transform: scale(1); opacity: 1; }}
    50% {{ transform: scale(1.35); opacity: 0.45; }}
  }}
  .stage-wrap {{
    position: relative;
    width: 100%;
    height: 380px;
    background: linear-gradient(180deg, #f0f9ff 0%, #e0f2fe 65%, #ffffff 100%);
  }}
  canvas#avatarCanvas {{
    width: 100%;
    height: 100%;
    display: block;
  }}
  .lower-third {{
    position: absolute;
    left: 14px;
    right: 14px;
    bottom: 12px;
    background: rgba(255, 255, 255, 0.96);
    border: 1.5px solid #93c5fd;
    border-left: 6px solid #1d4ed8;
    border-radius: 12px;
    padding: 10px 14px;
    box-shadow: 0 6px 16px rgba(30, 64, 175, 0.10);
  }}
  .subtitle-box {{
    font-size: 17px;
    line-height: 1.45;
    color: #0f172a;
    min-height: 46px;
    max-height: 68px;
    overflow-y: auto;
    font-weight: 600;
  }}
  .controls-bar {{
    display: flex;
    gap: 8px;
    align-items: center;
    justify-content: space-between;
    padding: 12px 14px;
    background: #f8fafc;
    border-top: 1px solid #e2e8f0;
  }}
  .btn-group {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
  }}
  button.ctrl-btn, label.ctrl-btn {{
    background: #ffffff;
    color: #1e40af;
    border: 1.5px solid #93c5fd;
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 15px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.15s ease;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }}
  button.ctrl-btn:hover, label.ctrl-btn:hover {{
    background: #eff6ff;
    border-color: #2563eb;
  }}
  button.ctrl-btn.primary {{
    background: #1d4ed8;
    border-color: #1d4ed8;
    color: #ffffff;
  }}
  button.ctrl-btn.primary:hover {{
    background: #1e40af;
  }}
  select.ctrl-select {{
    background: #ffffff;
    color: #1e3a8a;
    border: 1.5px solid #93c5fd;
    border-radius: 10px;
    padding: 7px 10px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
  }}
  input#photoUpload {{ display: none; }}
</style>
</head>
<body>
<div class="studio-shell">
  <div class="studio-topbar">
    <div class="live-badge">
      <span class="live-dot"></span>
      <span id="stateBadge">TRỢ LÝ AI</span>
    </div>
    <div id="anchorNameLabel" style="color:#1e40af; font-size:15px; font-weight:700;">
      👩‍⚖️ Luật sư AI Minh Anh
    </div>
  </div>

  <div class="stage-wrap">
    <canvas id="avatarCanvas" width="680" height="400"></canvas>

    <div class="lower-third">
      <div class="subtitle-box" id="subtitleText">
        Xin chào! Hãy đặt câu hỏi để tôi đọc câu trả lời trực tiếp cho bạn.
      </div>
    </div>
  </div>

  <div class="controls-bar">
    <div class="btn-group">
      <button class="ctrl-btn primary" onclick="startSpeaking()">▶️ Đọc</button>
      <button class="ctrl-btn" onclick="stopSpeaking()">⏹️ Dừng</button>
      <button class="ctrl-btn" onclick="switchCharacter()">🔄 Đổi Nữ/Nam</button>
      <label class="ctrl-btn" for="photoUpload">📸 Ảnh thật</label>
      <input type="file" id="photoUpload" accept="image/*" onchange="handlePhotoUpload(event)" />
    </div>
    <select class="ctrl-select" onchange="changeSpeed(this.value)">
      <option value="1.0">1.0x</option>
      <option value="1.15" selected>1.15x</option>
      <option value="1.3">1.3x</option>
    </select>
  </div>
</div>

<script>
const CONFIG = {payload_json};

const canvas = document.getElementById('avatarCanvas');
const ctx = canvas.getContext('2d');
const subtitleEl = document.getElementById('subtitleText');
const stateBadgeEl = document.getElementById('stateBadge');
const anchorNameEl = document.getElementById('anchorNameLabel');

let characterGender = CONFIG.gender || 'female';
let isSpeaking = false;
let playbackSpeed = 1.15;

let mouthOpen = 0.0;
let mouthWide = 0.5;
let voiceEnergy = 0.0;
let spectrumBins = new Array(16).fill(3);

let blinkTimer = 0;
let isBlinking = false;
let headTilt = 0;
let headNod = 0;
let breathPhase = 0;

let audioCtx = null;
let audioEl = null;
let analyser = null;
let freqData = null;
let subInterval = null;
let customPhoto = null;

function updateAnchorLabel() {{
  if (customPhoto) {{
    anchorNameEl.textContent = "🧑 MC Ảnh Thật";
  }} else if (characterGender === 'female') {{
    anchorNameEl.textContent = "👩‍⚖️ Luật sư AI Minh Anh";
  }} else {{
    anchorNameEl.textContent = "👨‍⚖️ Cố vấn AI Quốc Khánh";
  }}
}}
updateAnchorLabel();

if (CONFIG.spokenText) {{
  subtitleEl.textContent = CONFIG.sentences && CONFIG.sentences.length > 0
    ? CONFIG.sentences[0]
    : CONFIG.spokenText;
}}

function switchCharacter() {{
  customPhoto = null;
  characterGender = (characterGender === 'female') ? 'male' : 'female';
  updateAnchorLabel();
}}

function handlePhotoUpload(ev) {{
  const file = ev.target.files && ev.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(e) {{
    const img = new Image();
    img.onload = function() {{
      customPhoto = img;
      updateAnchorLabel();
    }};
    img.src = e.target.result;
  }};
  reader.readAsDataURL(file);
}}

function changeSpeed(val) {{
  playbackSpeed = parseFloat(val) || 1.0;
  if (audioEl) audioEl.playbackRate = playbackSpeed;
}}

function stopSpeaking() {{
  isSpeaking = false;
  mouthOpen = 0;
  voiceEnergy = 0;
  if (audioEl) {{
    audioEl.pause();
    audioEl.currentTime = 0;
  }}
  if ('speechSynthesis' in window) window.speechSynthesis.cancel();
  if (subInterval) {{
    clearInterval(subInterval);
    subInterval = null;
  }}
  stateBadgeEl.textContent = "SẴN SÀNG";
}}

function startSubtitleSync(durationSec) {{
  if (subInterval) clearInterval(subInterval);
  const sents = CONFIG.sentences || [];
  if (!sents.length) return;
  const totalChars = sents.reduce((acc, s) => acc + s.length, 0) || 1;
  let elapsed = 0;
  const stepMs = 150;
  subtitleEl.textContent = sents[0];

  subInterval = setInterval(() => {{
    if (!isSpeaking) {{
      clearInterval(subInterval);
      return;
    }}
    elapsed += (stepMs / 1000) * playbackSpeed;
    const progress = Math.min(0.99, elapsed / Math.max(1, durationSec));
    let charTarget = progress * totalChars;
    let accum = 0;
    for (let i = 0; i < sents.length; i++) {{
      accum += sents[i].length;
      if (charTarget <= accum) {{
        subtitleEl.textContent = sents[i];
        break;
      }}
    }}
  }}, stepMs);
}}

function startSpeaking() {{
  stopSpeaking();
  if (!CONFIG.spokenText) return;

  if (CONFIG.audioB64) {{
    try {{
      if (!audioCtx) {{
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        audioCtx = new AudioContextClass();
      }}
      if (audioCtx.state === 'suspended') audioCtx.resume();
      audioEl = new Audio("data:audio/mp3;base64," + CONFIG.audioB64);
      audioEl.playbackRate = playbackSpeed;

      const source = audioCtx.createMediaElementSource(audioEl);
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.65;
      source.connect(analyser);
      analyser.connect(audioCtx.destination);
      freqData = new Uint8Array(analyser.frequencyBinCount);

      audioEl.onloadedmetadata = () => startSubtitleSync(audioEl.duration || 16);
      audioEl.onplay = () => {{
        isSpeaking = true;
        stateBadgeEl.textContent = "🔊 ĐANG NÓI";
      }};
      audioEl.onended = () => {{
        stopSpeaking();
        stateBadgeEl.textContent = "✅ ĐÃ XONG";
      }};
      audioEl.onerror = () => speakWithBrowserTTS();
      audioEl.play().catch(() => speakWithBrowserTTS());
      return;
    }} catch (err) {{
      speakWithBrowserTTS();
      return;
    }}
  }}
  speakWithBrowserTTS();
}}

function speakWithBrowserTTS() {{
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(CONFIG.spokenText);
  utter.lang = 'vi-VN';
  utter.rate = playbackSpeed;
  utter.pitch = characterGender === 'female' ? 1.08 : 0.88;

  const voices = window.speechSynthesis.getVoices();
  const viVoice = voices.find(v => v.lang.toLowerCase().includes('vi'));
  if (viVoice) utter.voice = viVoice;

  utter.onstart = () => {{
    isSpeaking = true;
    stateBadgeEl.textContent = "🔊 ĐANG NÓI";
    startSubtitleSync(Math.max(4, CONFIG.spokenText.length / 14));
  }};
  utter.onboundary = () => {{
    mouthOpen = 0.55 + Math.random() * 0.4;
    mouthWide = 0.35 + Math.random() * 0.55;
  }};
  utter.onend = () => {{
    stopSpeaking();
    stateBadgeEl.textContent = "✅ ĐÃ XONG";
  }};
  window.speechSynthesis.speak(utter);
}}

function updateAudioVisemes(t) {{
  if (isSpeaking && analyser && freqData) {{
    analyser.getByteFrequencyData(freqData);
    let lowSum = 0;
    for (let i = 2; i <= 10; i++) lowSum += freqData[i];
    const lowAvg = lowSum / 9;

    let midSum = 0;
    for (let i = 11; i <= 28; i++) midSum += freqData[i];
    const midAvg = midSum / 18;

    let highSum = 0;
    for (let i = 29; i <= 50; i++) highSum += freqData[i];
    const highAvg = highSum / 22;

    const targetOpen = Math.min(1.0, Math.max(0.0, (lowAvg * 0.65 + midAvg * 0.35 - 18) / 115));
    const targetWide = Math.min(1.0, Math.max(0.25, 0.35 + (midAvg + highAvg * 0.6) / (lowAvg + 60) * 0.45));

    mouthOpen = mouthOpen * 0.55 + targetOpen * 0.45;
    mouthWide = mouthWide * 0.65 + targetWide * 0.35;
    voiceEnergy = Math.min(1.0, (lowAvg + midAvg) / 220);

    for (let b = 0; b < 16; b++) {{
      spectrumBins[b] = Math.max(4, (freqData[b * 2 + 2] / 255) * 34);
    }}
  }} else if (isSpeaking) {{
    const syllWave = Math.abs(Math.sin(t * 11.5)) * Math.abs(Math.cos(t * 4.7));
    mouthOpen = mouthOpen * 0.6 + syllWave * 0.85 * 0.4;
    mouthWide = 0.4 + 0.45 * Math.abs(Math.sin(t * 6.3));
    voiceEnergy = syllWave;
    for (let b = 0; b < 16; b++) {{
      spectrumBins[b] = 4 + Math.abs(Math.sin(t * 8 + b * 0.5)) * 24 * voiceEnergy;
    }}
  }} else {{
    mouthOpen *= 0.75;
    mouthWide = mouthWide * 0.85 + 0.5 * 0.15;
    voiceEnergy *= 0.8;
    for (let b = 0; b < 16; b++) {{
      spectrumBins[b] = Math.max(3, spectrumBins[b] * 0.82);
    }}
  }}
}}

function drawStudioBackground(t) {{
  const W = canvas.width;
  const H = canvas.height;

  // Nền Xanh - Trắng sáng sủa, hiện đại
  const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
  bgGrad.addColorStop(0, '#eff6ff');
  bgGrad.addColorStop(0.65, '#dbeafe');
  bgGrad.addColorStop(1, '#ffffff');
  ctx.fillStyle = bgGrad;
  ctx.fillRect(0, 0, W, H);

  // Vòng tròn sáng trắng sau lưng MC
  const halo = ctx.createRadialGradient(W * 0.5, H * 0.38, 15, W * 0.5, H * 0.38, 210);
  halo.addColorStop(0, 'rgba(255, 255, 255, 0.95)');
  halo.addColorStop(1, 'rgba(219, 234, 254, 0)');
  ctx.fillStyle = halo;
  ctx.fillRect(0, 0, W, H);

  // Sóng âm thanh góc phải màu xanh dương
  const eqX = W - 140;
  const eqY = 50;
  for (let i = 0; i < 16; i++) {{
    const bh = spectrumBins[i] || 3;
    ctx.fillStyle = isSpeaking ? '#2563eb' : '#93c5fd';
    ctx.beginPath();
    ctx.roundRect(eqX + i * 7.5, eqY - bh, 5, bh, 2.5);
    ctx.fill();
  }}
}}

function drawCustomPhotoAvatar(t) {{
  const W = canvas.width;
  const H = canvas.height;
  const cx = W * 0.5;
  const cy = H * 0.42;
  const radius = 122;

  ctx.save();
  ctx.translate(cx, cy + Math.sin(breathPhase) * 2.5);
  ctx.rotate(headTilt * 0.5);

  ctx.beginPath();
  ctx.arc(0, 0, radius + 4, 0, Math.PI * 2);
  ctx.strokeStyle = isSpeaking ? '#2563eb' : '#93c5fd';
  ctx.lineWidth = 4;
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(0, 0, radius, 0, Math.PI * 2);
  ctx.clip();

  const iw = customPhoto.width;
  const ih = customPhoto.height;
  const splitRatio = 0.64;
  const jawDropPx = mouthOpen * 14;

  ctx.drawImage(
    customPhoto,
    0, 0, iw, ih * splitRatio,
    -radius, -radius, radius * 2, radius * 2 * splitRatio
  );

  if (mouthOpen > 0.04) {{
    const mouthY = -radius + radius * 2 * splitRatio;
    const mouthW = radius * 0.36 * (0.75 + mouthWide * 0.35);
    const mouthH = jawDropPx * 0.9;
    ctx.fillStyle = '#2a0810';
    ctx.beginPath();
    ctx.ellipse(0, mouthY + mouthH * 0.35, mouthW, mouthH * 0.65, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(-mouthW * 0.65, mouthY - 1, mouthW * 1.3, Math.min(4, mouthH * 0.4));
  }}

  ctx.drawImage(
    customPhoto,
    0, ih * splitRatio, iw, ih * (1 - splitRatio),
    -radius, -radius + radius * 2 * splitRatio + jawDropPx * 0.65,
    radius * 2, radius * 2 * (1 - splitRatio)
  );

  ctx.restore();
}}

function drawHumanPresenter(t) {{
  const W = canvas.width;
  const H = canvas.height;
  const cx = W * 0.5;
  const baseCy = H * 0.42;

  const isFemale = (characterGender === 'female');
  const breathOffset = Math.sin(breathPhase) * 2.2;
  const jawDrop = mouthOpen * 12.5;

  ctx.save();
  ctx.translate(cx, baseCy + breathOffset);

  if (isFemale) {{
    ctx.save();
    ctx.rotate(headTilt * 0.7);
    ctx.fillStyle = '#1e293b';
    ctx.beginPath();
    ctx.moveTo(-68, -45);
    ctx.bezierCurveTo(-88, 25, -82, 95, -52, 118);
    ctx.lineTo(52, 118);
    ctx.bezierCurveTo(82, 95, 88, 25, 68, -45);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }}

  const skinGrad = ctx.createLinearGradient(-35, -80, 35, 90);
  if (isFemale) {{
    skinGrad.addColorStop(0, '#fde4cf');
    skinGrad.addColorStop(0.6, '#f9c6a2');
    skinGrad.addColorStop(1, '#eab08a');
  }} else {{
    skinGrad.addColorStop(0, '#f5cba7');
    skinGrad.addColorStop(0.6, '#e5b085');
    skinGrad.addColorStop(1, '#d4996a');
  }}

  // Cổ
  ctx.fillStyle = skinGrad;
  ctx.beginPath();
  ctx.roundRect(-24, 52, 48, 54, 12);
  ctx.fill();

  // Áo sơ mi trắng
  ctx.fillStyle = '#ffffff';
  ctx.beginPath();
  ctx.moveTo(-36, 92);
  ctx.lineTo(0, 158);
  ctx.lineTo(36, 92);
  ctx.closePath();
  ctx.fill();

  if (!isFemale) {{
    ctx.fillStyle = '#1d4ed8';
    ctx.beginPath();
    ctx.moveTo(-8, 106);
    ctx.lineTo(8, 106);
    ctx.lineTo(11, 165);
    ctx.lineTo(0, 178);
    ctx.lineTo(-11, 165);
    ctx.closePath();
    ctx.fill();
  }}

  // Áo Vest Xanh Hoàng Gia (Royal Blue Suit) đồng bộ tone Xanh - Trắng
  const suitGrad = ctx.createLinearGradient(-150, 90, 150, 210);
  suitGrad.addColorStop(0, '#1e3a8a');
  suitGrad.addColorStop(0.5, '#1d4ed8');
  suitGrad.addColorStop(1, '#1e3a8a');
  ctx.fillStyle = suitGrad;
  ctx.beginPath();
  ctx.moveTo(-28, 92);
  ctx.bezierCurveTo(-95, 98, -142, 132, -156, 215);
  ctx.lineTo(156, 215);
  ctx.bezierCurveTo(142, 132, 95, 98, 28, 92);
  ctx.lineTo(0, 156);
  ctx.closePath();
  ctx.fill();

  ctx.strokeStyle = 'rgba(255, 255, 255, 0.35)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(-28, 92);
  ctx.lineTo(-48, 135);
  ctx.lineTo(-12, 156);
  ctx.moveTo(28, 92);
  ctx.lineTo(48, 135);
  ctx.lineTo(12, 156);
  ctx.stroke();

  // Đầu & Khuôn mặt
  ctx.save();
  ctx.rotate(headTilt);
  ctx.translate(0, headNod);

  ctx.fillStyle = skinGrad;
  ctx.beginPath();
  ctx.ellipse(-61, -6, 10, 20, -0.1, 0, Math.PI * 2);
  ctx.ellipse(61, -6, 10, 20, 0.1, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = skinGrad;
  ctx.beginPath();
  ctx.moveTo(-58, -32);
  ctx.bezierCurveTo(-60, -92, 60, -92, 58, -32);
  ctx.bezierCurveTo(58, 15, 42, 48 + jawDrop * 0.65, 0, 62 + jawDrop * 0.85);
  ctx.bezierCurveTo(-42, 48 + jawDrop * 0.65, -58, 15, -58, -32);
  ctx.closePath();
  ctx.fill();

  // Má hồng nhẹ
  ctx.fillStyle = isFemale ? 'rgba(244, 114, 182, 0.16)' : 'rgba(239, 68, 68, 0.08)';
  ctx.beginPath();
  ctx.ellipse(-34, 8, 15, 9, 0, 0, Math.PI * 2);
  ctx.ellipse(34, 8, 15, 9, 0, 0, Math.PI * 2);
  ctx.fill();

  // Mắt
  const eyeY = -16;
  const eyeX = 25;
  const eyeOpenH = isBlinking ? 0.8 : 8.5;

  [-1, 1].forEach(dir => {{
    const ex = dir * eyeX;
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.ellipse(ex, eyeY, 13.5, eyeOpenH, 0, 0, Math.PI * 2);
    ctx.fill();

    if (!isBlinking) {{
      const lookX = Math.sin(t * 0.9) * 1.4;
      ctx.fillStyle = '#1e293b';
      ctx.beginPath();
      ctx.arc(ex + lookX, eyeY, 6.2, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = '#09090b';
      ctx.beginPath();
      ctx.arc(ex + lookX, eyeY, 3.2, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(ex + lookX - 2.2, eyeY - 2.2, 1.8, 0, Math.PI * 2);
      ctx.fill();
    }}

    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = isFemale ? 2.6 : 2.0;
    ctx.beginPath();
    ctx.arc(ex, eyeY + 2, 14, Math.PI * 1.12, Math.PI * 1.88);
    ctx.stroke();

    const browLift = voiceEnergy * 3.8;
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = isFemale ? 3.0 : 4.2;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(ex - dir * 14, eyeY - 13 - browLift * 0.5);
    ctx.quadraticCurveTo(ex, eyeY - 19 - browLift, ex + dir * 15, eyeY - 12 - browLift * 0.4);
    ctx.stroke();
  }});

  // Sống mũi
  ctx.strokeStyle = 'rgba(160, 95, 65, 0.45)';
  ctx.lineWidth = 1.8;
  ctx.beginPath();
  ctx.moveTo(0, -14);
  ctx.lineTo(-2, 10);
  ctx.quadraticCurveTo(0, 15, 6, 12);
  ctx.stroke();

  // Miệng nhép môi
  const mouthY = 30 + jawDrop * 0.28;
  const halfW = 14 + mouthWide * 11;
  const openH = Math.max(1.2, mouthOpen * 15.5);

  if (mouthOpen > 0.05) {{
    ctx.fillStyle = '#3b0a14';
    ctx.beginPath();
    ctx.moveTo(-halfW, mouthY);
    ctx.quadraticCurveTo(0, mouthY - openH * 0.35, halfW, mouthY);
    ctx.quadraticCurveTo(0, mouthY + openH * 1.15, -halfW, mouthY);
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = '#e11d48';
    ctx.beginPath();
    ctx.ellipse(0, mouthY + openH * 0.42, halfW * 0.58, openH * 0.36, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.roundRect(-halfW * 0.72, mouthY - openH * 0.15, halfW * 1.44, Math.min(4.8, openH * 0.42), 2);
    ctx.fill();
  }}

  const lipColor = isFemale ? '#e11d48' : '#be5b50';
  const lowerLipColor = isFemale ? '#f43f5e' : '#c86a60';

  ctx.fillStyle = lipColor;
  ctx.beginPath();
  ctx.moveTo(-halfW - 2, mouthY);
  ctx.quadraticCurveTo(-halfW * 0.45, mouthY - 6.5, 0, mouthY - 3.5);
  ctx.quadraticCurveTo(halfW * 0.45, mouthY - 6.5, halfW + 2, mouthY);
  ctx.quadraticCurveTo(0, mouthY - openH * 0.22, -halfW - 2, mouthY);
  ctx.closePath();
  ctx.fill();

  ctx.fillStyle = lowerLipColor;
  ctx.beginPath();
  ctx.moveTo(-halfW - 1, mouthY);
  ctx.quadraticCurveTo(0, mouthY + openH * 1.05, halfW + 1, mouthY);
  ctx.quadraticCurveTo(0, mouthY + openH * 1.45 + 6.5, -halfW - 1, mouthY);
  ctx.closePath();
  ctx.fill();

  // Tóc trước
  ctx.fillStyle = '#0f172a';
  if (isFemale) {{
    ctx.beginPath();
    ctx.moveTo(-62, -25);
    ctx.bezierCurveTo(-68, -98, 68, -98, 62, -25);
    ctx.bezierCurveTo(54, -55, 18, -68, -14, -54);
    ctx.bezierCurveTo(-38, -44, -54, -38, -62, -25);
    ctx.closePath();
    ctx.fill();
  }} else {{
    ctx.beginPath();
    ctx.moveTo(-60, -24);
    ctx.bezierCurveTo(-65, -96, 65, -96, 60, -24);
    ctx.bezierCurveTo(48, -62, -18, -66, -42, -52);
    ctx.bezierCurveTo(-52, -45, -56, -34, -60, -24);
    ctx.closePath();
    ctx.fill();
  }}

  ctx.restore();
  ctx.restore();
}}

let startTime = performance.now();

function animate(now) {{
  const t = (now - startTime) / 1000.0;
  breathPhase = t * 2.1;

  blinkTimer += 0.016;
  if (!isBlinking && blinkTimer > 3.4 + (Math.sin(t) * 0.6)) {{
    isBlinking = true;
    blinkTimer = 0;
  }} else if (isBlinking && blinkTimer > 0.13) {{
    isBlinking = false;
    blinkTimer = 0;
  }}

  if (isSpeaking) {{
    headTilt = Math.sin(t * 1.9) * 0.032;
    headNod = Math.sin(t * 4.2) * 2.2 * (0.3 + voiceEnergy);
  }} else {{
    headTilt = Math.sin(t * 0.9) * 0.012;
    headNod = 0;
  }}

  updateAudioVisemes(t);
  drawStudioBackground(t);

  if (customPhoto) {{
    drawCustomPhotoAvatar(t);
  }} else {{
    drawHumanPresenter(t);
  }}

  requestAnimationFrame(animate);
}}

requestAnimationFrame(animate);

if (CONFIG.autoPlay && CONFIG.spokenText) {{
  setTimeout(() => startSpeaking(), 350);
}}
</script>
</body>
</html>
"""
