window.GL = window.GL || {};

(() => {
  'use strict';

  const { $, $$, toast, log, haptic, setPressed } = GL.ui;
  let stream = null, raf = 0, mode = 'notturna', torchTrack = null;
  const work = document.createElement('canvas');

  const MODES = ['notturna', 'termica', 'contorni', 'raggix', 'nitido'];
  const LABELS = { notturna: 'Notturna', termica: 'Termica', contorni: 'Contorni', raggix: 'Raggi-X', nitido: 'Nitido' };

  // Thermal lookup: cold → hot across the visible spectrum.
  const THERMAL = (() => {
    const lut = new Uint8Array(256 * 3);
    for (let i = 0; i < 256; i++) {
      const t = i / 255;
      let r, g, b;
      if (t < 0.25) { r = 0; g = 0; b = t * 4 * 255; }
      else if (t < 0.5) { r = 0; g = (t - 0.25) * 4 * 255; b = 255; }
      else if (t < 0.75) { r = (t - 0.5) * 4 * 255; g = 255; b = (0.75 - t) * 4 * 255; }
      else { r = 255; g = (1 - t) * 4 * 255; b = 0; }
      lut[i * 3] = r; lut[i * 3 + 1] = g; lut[i * 3 + 2] = b;
    }
    return lut;
  })();

  function process(src, w, h) {
    const d = src.data;
    if (mode === 'notturna') {
      for (let i = 0; i < d.length; i += 4) {
        let lum = (d[i] * 0.3 + d[i + 1] * 0.59 + d[i + 2] * 0.11);
        lum = Math.min(255, Math.pow(lum / 255, 0.55) * 255 * 1.4); // brighten shadows
        d[i] = lum * 0.25; d[i + 1] = lum; d[i + 2] = lum * 0.25;
      }
    } else if (mode === 'termica') {
      for (let i = 0; i < d.length; i += 4) {
        const lum = (d[i] * 0.3 + d[i + 1] * 0.59 + d[i + 2] * 0.11) | 0;
        d[i] = THERMAL[lum * 3]; d[i + 1] = THERMAL[lum * 3 + 1]; d[i + 2] = THERMAL[lum * 3 + 2];
      }
    } else if (mode === 'raggix') {
      for (let i = 0; i < d.length; i += 4) {
        const lum = 255 - (d[i] * 0.3 + d[i + 1] * 0.59 + d[i + 2] * 0.11);
        d[i] = lum * 0.6; d[i + 1] = lum * 0.85; d[i + 2] = lum;
      }
    } else if (mode === 'nitido') {
      return sharpen(src, w, h);
    } else if (mode === 'contorni') {
      return sobel(src, w, h);
    }
    return src;
  }

  // Sobel edge detection → cyan outlines on black (classic HUD scanner look).
  function sobel(src, w, h) {
    const d = src.data;
    const gray = new Float32Array(w * h);
    for (let i = 0, p = 0; i < d.length; i += 4, p++) gray[p] = d[i] * 0.3 + d[i + 1] * 0.59 + d[i + 2] * 0.11;
    const out = new ImageData(w, h);
    const o = out.data;
    for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) {
      const p = y * w + x;
      const gx = -gray[p - w - 1] - 2 * gray[p - 1] - gray[p + w - 1] + gray[p - w + 1] + 2 * gray[p + 1] + gray[p + w + 1];
      const gy = -gray[p - w - 1] - 2 * gray[p - w] - gray[p - w + 1] + gray[p + w - 1] + 2 * gray[p + w] + gray[p + w + 1];
      const mag = Math.min(255, Math.hypot(gx, gy));
      const idx = p * 4;
      o[idx] = mag * 0.18; o[idx + 1] = mag; o[idx + 2] = mag * 0.95; o[idx + 3] = 255;
    }
    return out;
  }

  function sharpen(src, w, h) {
    const d = src.data;
    const copy = new Uint8ClampedArray(d);
    const k = [0, -1, 0, -1, 5, -1, 0, -1, 0];
    for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) {
      for (let c = 0; c < 3; c++) {
        let sum = 0, ki = 0;
        for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
          sum += copy[((y + dy) * w + (x + dx)) * 4 + c] * k[ki++];
        }
        d[(y * w + x) * 4 + c] = sum;
      }
    }
    return src;
  }

  function loop() {
    const v = $('#vis-video');
    const out = $('#vis-canvas');
    if (stream && v.readyState >= v.HAVE_CURRENT_DATA) {
      const w = Math.min(v.videoWidth, 480), scale = w / v.videoWidth, h = Math.round(v.videoHeight * scale);
      if (w && h) {
        work.width = w; work.height = h;
        out.width = w; out.height = h;
        const wc = work.getContext('2d', { willReadFrequently: true });
        wc.drawImage(v, 0, 0, w, h);
        const processed = process(wc.getImageData(0, 0, w, h), w, h);
        out.getContext('2d').putImageData(processed, 0, 0);
      }
    }
    raf = requestAnimationFrame(loop);
  }

  async function toggle() {
    if (stream) { stop(); return; }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
      const v = $('#vis-video');
      v.srcObject = stream; await v.play();
      torchTrack = stream.getVideoTracks()[0];
      $('#vis-torch').hidden = !(torchTrack.getCapabilities?.().torch);
      $('#vis-cam').textContent = 'Spegni';
      GL.sfx.play('nav');
      log('Visione attiva', 'ok');
      GL.app?.xp(4, 'visione');
      cancelAnimationFrame(raf); loop();
    } catch { toast('Fotocamera non disponibile'); }
  }

  function stop() {
    cancelAnimationFrame(raf);
    stream?.getTracks().forEach(t => t.stop());
    stream = null; torchTrack = null;
    $('#vis-video').srcObject = null;
    $('#vis-cam').textContent = 'Accendi';
    $('#vis-torch').hidden = true;
  }

  async function torch() {
    if (!torchTrack) return;
    const on = $('#vis-torch').getAttribute('aria-pressed') !== 'true';
    try { await torchTrack.applyConstraints({ advanced: [{ torch: on }] }); $('#vis-torch').setAttribute('aria-pressed', String(on)); } catch {}
  }

  function init() {
    $('#vis-cam').addEventListener('click', toggle);
    $('#vis-torch').addEventListener('click', torch);
    const box = $('#vis-modes');
    box.replaceChildren(...MODES.map(m => {
      const b = document.createElement('button');
      b.type = 'button'; b.textContent = LABELS[m]; b.className = 'chip-btn'; b.dataset.m = m;
      b.setAttribute('aria-pressed', String(m === mode));
      b.addEventListener('click', () => { mode = m; setPressed($$('#vis-modes button'), b); GL.sfx.play('tap'); haptic(8); });
      return b;
    }));
  }

  function leave() { stop(); }

  GL.vision = { init, leave };
})();
