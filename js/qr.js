window.GL = window.GL || {};

(() => {
  'use strict';

  const { $, $$, toast, log, haptic, copyText, setPressed } = GL.ui;
  let stream = null, raf = 0, scanning = false, lastCode = '';

  /* ---------------- scanner (jsQR) ---------------- */
  async function startScan() {
    if (stream) { stopScan(); return; }
    if (!window.jsQR) { toast('Scanner non disponibile'); return; }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
      const v = $('#qr-video');
      v.srcObject = stream;
      await v.play();
      $('#qr-cam').textContent = 'Spegni fotocamera';
      scanning = true;
      tick();
      GL.sfx.play('nav');
    } catch { toast('Fotocamera non disponibile'); }
  }

  function stopScan() {
    cancelAnimationFrame(raf);
    stream?.getTracks().forEach(t => t.stop());
    stream = null; scanning = false;
    $('#qr-video').srcObject = null;
    $('#qr-cam').textContent = 'Accendi fotocamera';
  }

  function tick() {
    const v = $('#qr-video');
    if (scanning && v.readyState === v.HAVE_ENOUGH_DATA) {
      const c = document.createElement('canvas');
      const w = c.width = v.videoWidth, h = c.height = v.videoHeight;
      if (w && h) {
        const ctx = c.getContext('2d');
        ctx.drawImage(v, 0, 0, w, h);
        const code = window.jsQR(ctx.getImageData(0, 0, w, h).data, w, h, { inversionAttempts: 'dontInvert' });
        if (code && code.data && code.data !== lastCode) {
          lastCode = code.data;
          found(code.data);
        }
      }
    }
    raf = requestAnimationFrame(tick);
  }

  function found(text) {
    const box = $('#qr-found');
    box.hidden = false;
    $('#qr-found-text').textContent = text;
    const isUrl = /^https?:\/\//i.test(text);
    const open = $('#qr-open');
    open.hidden = !isUrl;
    if (isUrl) open.href = text;
    GL.sfx.play('ok');
    haptic([15, 40, 15]);
    log('QR letto', 'ok');
    GL.app?.xp(4, 'qr');
    box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  /* ---------------- generator (qrcode-generator) ---------------- */
  let mode = 'text';

  function build(text) {
    // auto type number: try increasing versions until the data fits, max EC level M
    for (let type = 4; type <= 20; type++) {
      try {
        const qr = window.qrcode(type, 'M');
        qr.addData(text);
        qr.make();
        return qr;
      } catch { /* too small, grow */ }
    }
    return null;
  }

  function draw(text) {
    const canvas = $('#qr-canvas');
    const qr = build(text);
    if (!qr) { toast('Testo troppo lungo per un QR'); return false; }
    const n = qr.getModuleCount();
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    const size = Math.min(canvas.clientWidth || 280, 320);
    const quiet = 4;
    const scale = Math.floor((size * dpr) / (n + quiet * 2));
    const dim = scale * (n + quiet * 2);
    canvas.width = dim; canvas.height = dim;
    canvas.style.width = canvas.style.height = `${dim / dpr}px`;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#e8f6ff';
    ctx.fillRect(0, 0, dim, dim);
    ctx.fillStyle = '#05070d';
    for (let r = 0; r < n; r++) for (let col = 0; col < n; col++) {
      if (qr.isDark(r, col)) ctx.fillRect((col + quiet) * scale, (r + quiet) * scale, scale, scale);
    }
    canvas.hidden = false;
    return true;
  }

  function wifiString() {
    const ssid = $('#qr-wifi-ssid').value.trim();
    const pass = $('#qr-wifi-pass').value;
    const type = $('#qr-wifi-type').value;
    if (!ssid) return '';
    const esc = s => s.replace(/([\\;,":])/g, '\\$1');
    return `WIFI:T:${type};S:${esc(ssid)};${type === 'nopass' ? '' : `P:${esc(pass)};`};`;
  }

  function generate() {
    let text;
    if (mode === 'wifi') { text = wifiString(); if (!text) { toast('Scrivi almeno il nome della rete'); return; } }
    else { text = $('#qr-gen-in').value; if (!text) { toast('Scrivi il testo o il link'); return; } }
    if (draw(text)) { GL.sfx.play('ok'); GL.app?.xp(4, 'qr'); haptic(15); }
  }

  function setMode(next) {
    mode = next;
    setPressed([$('#qr-mode-text'), $('#qr-mode-wifi')], next === 'text' ? $('#qr-mode-text') : $('#qr-mode-wifi'));
    $('#qr-gen-text').hidden = next !== 'text';
    $('#qr-gen-wifi').hidden = next !== 'wifi';
  }

  function init() {
    $('#qr-cam').addEventListener('click', startScan);
    $('#qr-copy').addEventListener('click', () => copyText($('#qr-found-text').textContent));
    $('#qr-rescan').addEventListener('click', () => { lastCode = ''; $('#qr-found').hidden = true; });
    $('#qr-mode-text').addEventListener('click', () => setMode('text'));
    $('#qr-mode-wifi').addEventListener('click', () => setMode('wifi'));
    $('#qr-generate').addEventListener('click', generate);
    $$('#qr-gen-wifi input, #qr-gen-wifi select').forEach(el => el.addEventListener('keydown', e => { if (e.key === 'Enter') generate(); }));
  }

  function leave() { stopScan(); }

  GL.qr = { init, leave };
})();
