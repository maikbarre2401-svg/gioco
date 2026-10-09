import { $, $$, toast, log, haptic, setPressed } from './ui.js';

const MORSE = {
  A: '.-', B: '-...', C: '-.-.', D: '-..', E: '.', F: '..-.', G: '--.', H: '....', I: '..', J: '.---',
  K: '-.-', L: '.-..', M: '--', N: '-.', O: '---', P: '.--.', Q: '--.-', R: '.-.', S: '...', T: '-',
  U: '..-', V: '...-', W: '.--', X: '-..-', Y: '-.--', Z: '--..',
  0: '-----', 1: '.----', 2: '..---', 3: '...--', 4: '....-', 5: '.....', 6: '-....', 7: '--...', 8: '---..', 9: '----.',
  '.': '.-.-.-', ',': '--..--', '?': '..--..', '!': '-.-.--', '/': '-..-.', '@': '.--.-.',
};
const UNIT = 180; // ms per Morse unit

let track = null;      // camera track with torch, when the phone supports it
let source = null;     // 'led' | 'screen'
let mode = 'fixed';
let on = false;
let runId = 0;         // bumps to cancel a running pattern
let wakeLock = null;

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function detectSource() {
  if (source) return source;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } } });
    const t = stream.getVideoTracks()[0];
    if (t?.getCapabilities?.().torch) { track = t; source = 'led'; }
    else { stream.getTracks().forEach(x => x.stop()); source = 'screen'; }
  } catch { source = 'screen'; }
  $('#trc-src').textContent = source === 'led' ? 'Sorgente: LED posteriore' : 'Sorgente: schermo (il LED non è accessibile da qui)';
  return source;
}

async function setLight(state) {
  if (source === 'led' && track) {
    try { await track.applyConstraints({ advanced: [{ torch: state }] }); } catch { /* ignore */ }
  } else {
    const flash = $('#flash');
    flash.hidden = false;
    flash.classList.toggle('dark', !state);
  }
}

async function keepAwake() {
  try { wakeLock = await navigator.wakeLock?.request('screen'); } catch { wakeLock = null; }
}

function morseOf(text) {
  return text.toUpperCase().split('').map(ch => (ch === ' ' ? '/' : MORSE[ch] || '')).filter(Boolean);
}

function renderMorse(codes, activeIndex = -1) {
  const out = $('#trc-morse');
  out.replaceChildren(...codes.map((c, i) => {
    const s = document.createElement('span');
    s.textContent = `${c} `;
    if (i === activeIndex) s.className = 'cur';
    return s;
  }));
}

async function playMorse(codes, id, loop) {
  do {
    for (let i = 0; i < codes.length; i++) {
      if (id !== runId) return;
      renderMorse(codes, i);
      if (codes[i] === '/') { await sleep(UNIT * 4); continue; } // word gap (7 total with letter gaps)
      for (const sym of codes[i]) {
        if (id !== runId) return;
        await setLight(true);
        await sleep(sym === '.' ? UNIT : UNIT * 3);
        await setLight(false);
        await sleep(UNIT);
      }
      await sleep(UNIT * 2); // letter gap
    }
    await sleep(UNIT * 4);
  } while (loop && id === runId);
}

async function playStrobe(id) {
  while (id === runId) {
    const half = 500 / Number($('#trc-hz').value);
    await setLight(true);
    await sleep(half);
    if (id !== runId) return;
    await setLight(false);
    await sleep(half);
  }
}

async function turnOn() {
  await detectSource();
  on = true;
  const id = ++runId;
  $('#trc-power').setAttribute('aria-pressed', 'true');
  if (source === 'screen') keepAwake();
  haptic(20);
  log(`Luce accesa · ${mode === 'fixed' ? 'fissa' : mode === 'strobe' ? 'strobo' : 'SOS'}`, 'ok');
  if (mode === 'fixed') await setLight(true);
  else if (mode === 'strobe') playStrobe(id);
  else { const codes = morseOf('SOS'); renderMorse(codes); playMorse(codes, id, true); }
}

async function turnOff() {
  runId++;
  on = false;
  $('#trc-power').setAttribute('aria-pressed', 'false');
  await setLight(false);
  $('#flash').hidden = true;
  try { await wakeLock?.release(); } catch { /* already released */ }
  wakeLock = null;
}

async function sendMessage() {
  const text = $('#trc-msg').value.trim();
  const codes = morseOf(text);
  if (!codes.length) { toast('Scrivi lettere o numeri da trasmettere'); return; }
  await turnOff();
  await detectSource();
  const id = ++runId;
  on = true;
  $('#trc-power').setAttribute('aria-pressed', 'true');
  if (source === 'screen') keepAwake();
  log(`Trasmissione Morse: ${text.toUpperCase()}`, 'warn');
  await playMorse(codes, id, false);
  if (id === runId) { await turnOff(); renderMorse(codes); toast('Trasmissione completata'); }
}

export function init() {
  $('#trc-power').addEventListener('click', () => (on ? turnOff() : turnOn()));
  $('#flash').addEventListener('click', turnOff);
  $$('[data-trc-mode]').forEach(btn => btn.addEventListener('click', () => {
    mode = btn.dataset.trcMode;
    setPressed($$('[data-trc-mode]'), btn);
    if (on) { turnOff().then(turnOn); }
  }));
  $('#trc-hz').addEventListener('input', e => { $('#trc-hz-val').textContent = e.target.value; });
  $('#trc-send').addEventListener('click', sendMessage);
  $('#trc-msg').addEventListener('input', e => {
    const codes = morseOf(e.target.value);
    if (codes.length) renderMorse(codes); else $('#trc-morse').textContent = '—';
  });
}

export function leave() {
  turnOff();
  track?.stop();
  track = null;
  source = null;
}
