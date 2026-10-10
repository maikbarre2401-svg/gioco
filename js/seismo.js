window.GL = window.GL || {};

(() => {
  'use strict';

  const { $, toast, log, haptic, fmt, fitCanvas, COLORS } = GL.ui;
  let running = false, raf = 0;
  const history = new Array(300).fill(0);
  let gravity = { x: 0, y: 0, z: 9.81 };
  let peak = 0, lastQuake = 0, events = 0;

  function onMotion(e) {
    const a = e.accelerationIncludingGravity;
    if (!a || a.x == null) return;
    // high-pass filter to drop gravity and keep only movement
    const alpha = 0.8;
    gravity.x = alpha * gravity.x + (1 - alpha) * a.x;
    gravity.y = alpha * gravity.y + (1 - alpha) * a.y;
    gravity.z = alpha * gravity.z + (1 - alpha) * a.z;
    const lin = Math.hypot(a.x - gravity.x, a.y - gravity.y, a.z - gravity.z);
    history.push(lin); history.shift();
    peak = Math.max(peak, lin);
    const now = performance.now();
    if (lin > 3 && now - lastQuake > 500) { lastQuake = now; events++; GL.sfx.play('blip'); haptic(20); }
  }

  // Playful local "Richter-like" value from peak ground acceleration; clearly not a real seismograph.
  function magnitude(a) { return a < 0.05 ? 0 : Math.max(0, Math.min(9.9, Math.log10(a * 100 + 1) * 2.2)); }

  function draw() {
    const { ctx, w, h } = fitCanvas($('#seis-canvas'));
    ctx.clearRect(0, 0, w, h);
    const mid = h / 2;
    ctx.strokeStyle = COLORS.line; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, mid); ctx.lineTo(w, mid); ctx.stroke();
    for (let i = 1; i < 4; i++) { const y = (h / 4) * i; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.strokeStyle = 'rgba(27,44,69,.5)'; ctx.stroke(); }

    const cur = history[history.length - 1];
    const col = cur > 3 ? COLORS.magenta : cur > 1 ? COLORS.amber : COLORS.cyan;
    ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.beginPath();
    const scale = h / 2 / 8; // 8 m/s² full scale
    for (let i = 0; i < history.length; i++) {
      const x = (i / history.length) * w;
      const y = mid - Math.min(mid, history[i] * scale) * (i % 2 ? 1 : -1);
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    }
    ctx.stroke();

    const mag = magnitude(peak);
    $('#seis-mag').textContent = fmt.num(mag, 1);
    $('#seis-now').textContent = `${fmt.num(cur, 2)} m/s²`;
    $('#seis-peak').textContent = `${fmt.num(peak, 2)} m/s²`;
    $('#seis-events').textContent = events;
    const label = mag < 1 ? 'Fermo' : mag < 2 ? 'Vibrazioni lievi' : mag < 4 ? 'Movimento netto' : 'Scossa forte';
    $('#seis-label').textContent = label;
    $('#seis-label').className = `center ${cur > 3 ? 'hot' : cur > 1 ? 'warn' : 'dim'}`;
    if (running) raf = requestAnimationFrame(draw);
  }

  async function start() {
    if (running) { stop(); return; }
    try { if (typeof DeviceMotionEvent?.requestPermission === 'function') { const r = await DeviceMotionEvent.requestPermission(); if (r !== 'granted') { toast('Permesso sensori negato'); return; } } } catch {}
    window.addEventListener('devicemotion', onMotion);
    running = true; peak = 0; events = 0; history.fill(0);
    $('#seis-start').textContent = 'Ferma';
    $('#seis-start').classList.add('danger');
    GL.sfx.play('nav');
    log('Sismografo attivo', 'ok');
    GL.app?.xp(4, 'sismografo');
    cancelAnimationFrame(raf); draw();
    setTimeout(() => { if (running && peak < 0.02) toast('Nessun movimento rilevato: il sensore potrebbe non essere disponibile', 3000); }, 2500);
  }

  function stop() {
    window.removeEventListener('devicemotion', onMotion);
    running = false;
    cancelAnimationFrame(raf);
    $('#seis-start').textContent = 'Avvia sismografo';
    $('#seis-start').classList.remove('danger');
  }

  function init() { $('#seis-start').addEventListener('click', start); $('#seis-reset').addEventListener('click', () => { peak = 0; events = 0; toast('Azzerato'); }); }
  function leave() { stop(); }

  GL.seismo = { init, leave };
})();
