// Run: node tests/presenter_player.test.cjs (no browser or npm dependencies).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const template = fs.readFileSync('src/rag/presenter.html', 'utf8');

function mount(config, voices = []) {
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      textContent: '', src: '', dataset: {}, style: {}, classList: { add() {} },
      appendChild() {}, setAttribute(name, value) { this[name] = value; },
      removeAttribute(name) { this[name] = ''; },
      async play() { this.onplay?.(); }, pause() { this.onpause?.(); },
    });
    return elements.get(id);
  }
  const spoken = [];
  const speechSynthesis = { getVoices: () => voices, cancel() {}, pause() {}, resume() {},
    speak(utterance) { spoken.push(utterance); utterance.onstart?.(); } };
  const window = { speechSynthesis, addEventListener() {} };
  const html = template.replace('__PRESENTER_CONFIG__', JSON.stringify({
    spokenText: 'Nội dung một. Nội dung hai.', sentences: ['Nội dung một.', 'Nội dung hai.'],
    segments: [], gender: 'female', rate: 1, showAvatar: true, ...config,
  }));
  const code = html.match(/<script>([\s\S]*?)<\/script>/)[1];
  vm.runInNewContext(code, { window,
    document: { getElementById: element, createElement: () => ({ style: {} }) },
    SpeechSynthesisUtterance: class { constructor(text) { this.text = text; } },
    setTimeout, clearTimeout, requestAnimationFrame: () => 1, cancelAnimationFrame() {},
  });
  return { element, spoken };
}

const flush = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  const { element: el } = mount({ provider: 'piper', segments: [
    { text: 'Đoạn một.', audio_b64: 'YQ==', mime: 'audio/wav' },
    { text: 'Đoạn hai.', audio_b64: 'Yg==', mime: 'audio/wav' },
  ] });
  el('play').onclick(); await flush();
  assert.match(el('audio').src, /^data:audio\/wav;base64,/);
  assert.equal(el('state').textContent, 'Đang đọc');
  el('play').onclick();
  assert.equal(el('state').textContent, 'Tạm dừng');
  el('play').onclick(); await flush();
  assert.equal(el('state').textContent, 'Đang đọc');
  el('speed').onchange({ target: { value: '1.15' } });
  assert.equal(el('audio').playbackRate, 1.15);
  el('audio').onended(); await flush();
  assert.equal(el('subtitle').textContent, 'Đoạn hai.');
  assert.equal(el('count').textContent, 'Đoạn 2 / 2');
  el('audio').onended();
  assert.equal(el('state').textContent, 'Đã đọc xong');
  el('restart').onclick(); await flush();
  assert.equal(el('subtitle').textContent, 'Đoạn một.');
  assert.equal(el('state').textContent, 'Đang đọc');
  const noVietnamese = mount({}, [{ lang: 'en-US', localService: true }]);
  noVietnamese.element('play').onclick(); await flush();
  assert.equal(noVietnamese.spoken.length, 0);
  assert.equal(noVietnamese.element('state').textContent, 'Thiết bị chưa có giọng Việt');
  const remoteOnly = mount({ deviceLocalOnly: true }, [{ lang: 'vi-VN', localService: false }]);
  remoteOnly.element('play').onclick(); await flush();
  assert.equal(remoteOnly.spoken.length, 0);
  console.log('PASS: WAV playback, pause/resume, speed, subtitles, completion, replay, Vietnamese/local voice checks.');
})().catch(error => { console.error(error); process.exitCode = 1; });
