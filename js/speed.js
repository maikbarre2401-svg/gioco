window.GL = window.GL || {};

(() => {
  'use strict';

  const { $, toast, log, haptic, fitCanvas, fmt, COLORS } = GL.ui;
  const BASE = 'https://speed.cloudflare.com';
  let running = false, shown = 0, target = 0, raf = 0;

  // Log scale gauge from 0.5 to 1000 Mbps.
  const TICKS = [1, 5, 10, 50, 100, 500, 1000];
  const pos = v => Math.max(0, Math.min(1, Math.log10(Math.max(v, 0.5) / 0.5) / Math.log10(2000)));

  function drawGauge() {
    const { ctx, w, h } = fitCanvas($('#spd-gauge'));
    ctx.clearRect(0, 0, w, h);
    const cx = w / 2, cy = h * 0.92, R = Math.min(w / 2, h) * 0.85;
    const a0 = Math.PI, a1 = Math.PI * 2;
    ctx.lineCap = 'butt';
    ctx.lineWidth = 12;
    ctx.strokeStyle = COLORS.line;
    ctx.beginPath(); ctx.arc(cx, cy, R, a0, a1); ctx.stroke();
    shown += (target - shown) * 0.12;
    const p = pos(shown);
    const grad = ctx.createLinearGradient(cx - R, 0, cx + R, 0);
    grad.addColorStop(0, COLORS.cyan);
    grad.addColorStop(0.7, COLORS.amber);
    grad.addColorStop(1, COLORS.magenta);
    ctx.strokeStyle = grad;
    if (shown > 0.05) { ctx.beginPath(); ctx.arc(cx, cy, R, a0, a0 + Math.PI * p); ctx.stroke(); }
    ctx.font = '600 11px "JetBrains Mono", monospace';
    ctx.fillStyle = COLORS.dim;
    ctx.textAlign = 'center';
    TICKS.forEach(v => {
      const a = a0 + Math.PI * pos(v);
      ctx.fillText(v >= 1000 ? '1G' : String(v), cx + Math.cos(a) * (R - 24), cy + Math.sin(a) * (R - 24) + 4);
    });
    const a = a0 + Math.PI * p;
    ctx.strokeStyle = COLORS.fg;
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(a) * (R - 6), cy + Math.sin(a) * (R - 6)); ctx.stroke();
    ctx.fillStyle = COLORS.magenta;
    ctx.beginPath(); ctx.arc(cx, cy, 5, 0, Math.PI * 2); ctx.fill();
    $('#spd-value').textContent = shown < 0.05 ? '--' : fmt.num(shown, shown < 10 ? 1 : 0);
    raf = requestAnimationFrame(drawGauge);
  }

  async function timed(url, opts) {
    const t0 = performance.now();
    const res = await fetch(url, { cache: 'no-store', ...opts });
    await res.arrayBuffer();
    return performance.now() - t0;
  }

  async function ping() {
    const times = [];
    await timed(`${BASE}/__down?bytes=0`); // warm-up: opens the connection
    for (let i = 0; i < 8; i++) {
      times.push(await timed(`${BASE}/__down?bytes=0&r=${Math.random()}`));
      GL.sfx.play('blip');
    }
    times.sort((a, b) => a - b);
    const median = times[Math.floor(times.length / 2)];
    let jitter = 0;
    for (let i = 1; i < times.length; i++) jitter += Math.abs(times[i] - times[i - 1]);
    return { ping: median, jitter: jitter / (times.length - 1) };
  }

  // Streams the body so the gauge moves while data arrives; stops after ~7 s or 40 MB.
  async function download() {
    const sizes = [1e6, 5e6, 10e6, 25e6];
    let bytes = 0;
    const t0 = performance.now();
    for (const size of sizes) {
      const res = await fetch(`${BASE}/__down?bytes=${size}&r=${Math.random()}`, { cache: 'no-store' });
      const reader = res.body.getReader();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        bytes += value.length;
        const secs = (performance.now() - t0) / 1000;
        if (secs > 0.2) target = (bytes * 8) / secs / 1e6;
      }
      if (performance.now() - t0 > 7000) break;
    }
    return (bytes * 8) / ((performance.now() - t0) / 1000) / 1e6;
  }

  async function upload() {
    const sizes = [5e5, 2e6, 5e6];
    let bytes = 0, ms = 0;
    for (const size of sizes) {
      const body = new Uint8Array(size);
      const t = await timed(`${BASE}/__up?r=${Math.random()}`, { method: 'POST', body });
      bytes += size; ms += t;
      target = (bytes * 8) / (ms / 1000) / 1e6;
      if (ms > 6000) break;
    }
    return (bytes * 8) / (ms / 1000) / 1e6;
  }

  function verdict(down, up, pingMs) {
    const rows = [
      ['Video 4K in streaming', down >= 25], ['Videochiamate HD', down >= 3 && up >= 1.5], ['Giochi online', pingMs < 60],
      ['Dirette streaming in HD', up >= 6], ['Lavoro da remoto', down >= 10 && up >= 3],
    ];
    const box = $('#spd-verdict');
    box.replaceChildren();
    const h = document.createElement('div'); h.className = 'eyebrow'; h.textContent = 'Cosa puoi fare con questa linea';
    box.append(h);
    rows.forEach(([label, ok]) => {
      const d = document.createElement('div'); d.className = 'kv';
      const s = document.createElement('span'); s.textContent = label;
      const b = document.createElement('b'); b.textContent = ok ? 'SÌ' : 'A FATICA'; b.className = ok ? 'good' : 'warn';
      d.append(s, b); box.append(d);
    });
    const game = (50 * 8000) / Math.max(down, 0.1); // 50 GB game in seconds
    const p = document.createElement('p'); p.className = 'note';
    p.textContent = `Un gioco da 50 GB si scarica in circa ${GL.ui.humanTime(game)}.`;
    box.append(p);
    box.hidden = false;
  }

  async function run() {
    if (running) return;
    if (!navigator.onLine) { toast('Sei offline'); return; }
    running = true;
    const btn = $('#spd-run');
    btn.disabled = true;
    $('#spd-verdict').hidden = true;
    ['#spd-ping', '#spd-jitter', '#spd-down', '#spd-up'].forEach(id => { $(id).textContent = '…'; });
    GL.sfx.play('nav');
    try {
      fetch(`${BASE}/meta`, { cache: 'no-store' }).then(r => r.json()).then(m => {
        $('#spd-server').textContent = [m.colo, m.city, m.asOrganization].filter(Boolean).join(' · ') || 'Cloudflare';
      }).catch(() => { $('#spd-server').textContent = 'Cloudflare'; });

      $('#spd-phase').textContent = 'Misuro la latenza…';
      const p = await ping();
      $('#spd-ping').textContent = `${Math.round(p.ping)} ms`;
      $('#spd-jitter').textContent = `${fmt.num(p.jitter, 1)} ms`;

      $('#spd-phase').textContent = 'Download…';
      const down = await download();
      $('#spd-down').textContent = `${fmt.num(down, 1)} Mbps`;
      GL.sfx.play('ok');

      $('#spd-phase').textContent = 'Upload…';
      target = 0;
      let up = 0;
      try { up = await upload(); $('#spd-up').textContent = `${fmt.num(up, 1)} Mbps`; } catch { $('#spd-up').textContent = 'non misurabile'; }
      target = down;
      $('#spd-phase').textContent = 'Completato';
      verdict(down, up, p.ping);
      GL.sfx.play('ok');
      haptic([20, 40, 20]);
      log(`Velocità: ${fmt.num(down, 1)} Mbps giù · ping ${Math.round(p.ping)} ms`, 'ok');
      GL.app?.xp(15, 'test velocità');
    } catch {
      $('#spd-phase').textContent = 'Server non raggiungibile';
      GL.sfx.play('err');
      toast('Test non riuscito: controlla la connessione');
    } finally {
      running = false;
      btn.disabled = false;
      btn.textContent = 'Ripeti test';
    }
  }

  function init() { $('#spd-run').addEventListener('click', run); }
  function enter() { cancelAnimationFrame(raf); raf = requestAnimationFrame(drawGauge); }
  function leave() { cancelAnimationFrame(raf); }

  GL.speed = { init, enter, leave };
})();
