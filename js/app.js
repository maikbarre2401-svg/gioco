window.GL = window.GL || {};

(() => {
  'use strict';

  const { native, $, $$, clock, log, toast, haptic, sha256, fitCanvas, COLORS } = GL.ui;
  const device = GL.device;
  const scan = GL.scan;
  const cifra = GL.cipher;
  const password = GL.password;
  const sensori = GL.sensors;
  const audio = GL.audio;
  const torcia = GL.torch;

  const modules = { scan, cifra, password, sensori, audio, torcia };
  let current = null;

  /* ---------------- router ---------------- */
  function route() {
    const name = (location.hash || '#home').slice(1);
    const target = $(`.screen[data-screen="${name}"]`) ? name : 'home';
    if (target === current) return;
    if (current && modules[current]?.leave) modules[current].leave();
    $$('.screen').forEach(s => s.classList.toggle('active', s.dataset.screen === target));
    current = target;
    $('#app').scrollTop = 0;
    if (target === 'home') startRadar(); else stopRadar();
    if (modules[target]?.enter) modules[target].enter();
    if (navigator.userActivation?.hasBeenActive) haptic(8);
  }

  /* ---------------- status bar ---------------- */
  function tickClock() {
    $('#st-clock').textContent = clock().slice(0, 5);
  }

  function updateNet() {
    const chip = $('#st-net');
    const c = device.connection();
    const online = navigator.onLine;
    chip.textContent = online ? (c?.effective ? c.effective.toUpperCase() : 'NET') : 'OFFLINE';
    chip.className = `chip ${online ? 'on' : 'off'}`;
  }

  async function watchBattery() {
    const b = await device.battery();
    const chip = $('#st-bat');
    if (!b) { chip.hidden = true; return; }
    const paint = () => {
      const pct = Math.round(b.level * 100);
      chip.textContent = `${b.charging ? '⚡' : 'BAT'} ${pct}%`;
      chip.className = `chip ${pct <= 15 && !b.charging ? 'off' : 'on'}`;
    };
    paint();
    b.addEventListener('levelchange', () => { paint(); log(`Batteria al ${Math.round(b.level * 100)}%`); });
    b.addEventListener('chargingchange', () => {
      paint();
      log(b.charging ? 'Alimentazione collegata' : 'Alimentazione scollegata', b.charging ? 'ok' : 'warn');
    });
  }

  /* ---------------- home profiler ---------------- */
  async function fillProfiler() {
    const parts = device.fingerprintParts();
    const hash = await sha256(parts.map(p => String(p[1])).join('|'));
    const id = hash.slice(0, 8).toUpperCase();
    $('#node-id').textContent = `NODO ${id.slice(0, 4)}-${id.slice(4)}`;
    $('#p-os').textContent = device.detectOS();
    $('#p-browser').textContent = device.detectBrowser();
    const s = device.screenInfo();
    $('#p-screen').textContent = `${s.real} px`;
    const risk = device.exposureLabel(device.exposureScore());
    const el = $('#p-risk');
    el.textContent = risk.text;
    el.className = risk.cls;
    return id;
  }

  let radarRaf = 0;
  const blips = Array.from({ length: 6 }, () => ({ a: Math.random() * Math.PI * 2, r: .25 + Math.random() * .65, life: 0 }));

  function drawRadar(t) {
    const canvas = $('#radar');
    const { ctx, w, h } = fitCanvas(canvas);
    const cx = w / 2, cy = h / 2, R = Math.min(w, h) / 2 - 2;
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = COLORS.line;
    ctx.lineWidth = 1;
    for (let i = 1; i <= 3; i++) { ctx.beginPath(); ctx.arc(cx, cy, (R * i) / 3, 0, Math.PI * 2); ctx.stroke(); }
    ctx.beginPath(); ctx.moveTo(cx - R, cy); ctx.lineTo(cx + R, cy); ctx.moveTo(cx, cy - R); ctx.lineTo(cx, cy + R); ctx.stroke();

    const sweep = (t / 1400) % (Math.PI * 2);
    const grad = ctx.createConicGradient ? ctx.createConicGradient(sweep - Math.PI / 2.2, cx, cy) : null;
    if (grad) {
      grad.addColorStop(0, 'rgba(46,242,255,0)');
      grad.addColorStop(0.12, 'rgba(46,242,255,0.28)');
      grad.addColorStop(0.121, 'rgba(46,242,255,0)');
      ctx.fillStyle = grad;
      ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fill();
    }
    ctx.strokeStyle = COLORS.cyan;
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(sweep) * R, cy + Math.sin(sweep) * R); ctx.stroke();

    for (const b of blips) {
      const diff = (sweep - b.a + Math.PI * 4) % (Math.PI * 2);
      if (diff < 0.05) b.life = 1;
      if (b.life > 0) {
        ctx.fillStyle = `rgba(255,45,117,${b.life})`;
        ctx.beginPath(); ctx.arc(cx + Math.cos(b.a) * b.r * R, cy + Math.sin(b.a) * b.r * R, 2.6, 0, Math.PI * 2); ctx.fill();
        b.life -= 0.008;
        if (b.life <= 0) { b.a = Math.random() * Math.PI * 2; b.r = .25 + Math.random() * .65; }
      }
    }
    ctx.fillStyle = COLORS.cyan;
    ctx.beginPath(); ctx.arc(cx, cy, 2.5, 0, Math.PI * 2); ctx.fill();
  }

  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  function startRadar() {
    if (reduceMotion) { drawRadar(900); return; }
    if (radarRaf) return;
    const loop = t => { drawRadar(t); radarRaf = requestAnimationFrame(loop); };
    radarRaf = requestAnimationFrame(loop);
  }
  function stopRadar() { cancelAnimationFrame(radarRaf); radarRaf = 0; }

  /* ---------------- periodic heartbeat in the log ---------------- */
  const started = Date.now();
  function heartbeat() {
    const c = device.connection();
    const up = Math.floor((Date.now() - started) / 1000);
    const msgs = [
      () => `Sessione attiva da ${Math.floor(up / 60)}m ${up % 60}s`,
      () => (c ? `Rete ${c.effective?.toUpperCase() ?? '?'} · latenza ${c.rtt ?? '?'} ms · ${c.down ?? '?'} Mbps` : `Rete ${navigator.onLine ? 'online' : 'offline'}`),
      () => `Orientamento ${screen.orientation?.type?.startsWith('landscape') ? 'orizzontale' : 'verticale'}`,
      () => (performance.memory ? `Memoria app ${Math.round(performance.memory.usedJSHeapSize / 1048576)} MB` : `Core CPU disponibili: ${navigator.hardwareConcurrency ?? '?'}`),
      () => `Fuso orario ${Intl.DateTimeFormat().resolvedOptions().timeZone}`,
    ];
    log(msgs[Math.floor(up / 7) % msgs.length]());
  }

  /* ---------------- boot sequence ---------------- */
  function boot(nodeId) {
    const el = $('#boot');
    const pre = $('#boot-lines');
    let seen = false;
    try { seen = sessionStorage.getItem('gl-booted') === '1'; sessionStorage.setItem('gl-booted', '1'); } catch { /* storage blocked */ }
    if (seen || reduceMotion) { el.remove(); return; }
    const lines = [
      ['GHOSTLINK v1.0 // kernel mobile', ''],
      ['> verifica integrità ........ ', 'OK', 'ok'],
      [`> identificazione nodo ...... `, nodeId, 'hot'],
      ['> collegamento sensori ...... ', 'OK', 'ok'],
      ['> cifratura AES-256 ......... ', 'PRONTA', 'ok'],
      ['> accesso ................... ', 'CONCESSO', 'ok'],
    ];
    let i = 0;
    const done = () => { el.classList.add('done'); setTimeout(() => el.remove(), 450); };
    el.addEventListener('click', done, { once: true });
    const next = () => {
      if (i >= lines.length) { setTimeout(done, 380); return; }
      const [txt, val, cls] = lines[i++];
      pre.append(txt);
      if (val) { const s = document.createElement('span'); s.className = cls; s.textContent = val; pre.append(s); }
      pre.append('\n');
      setTimeout(next, 170);
    };
    next();
  }

  /* ---------------- install (PWA) ---------------- */
  let deferredPrompt = null;
  function setupInstall() {
    const btn = $('#install-btn');
    if (native || device.isStandalone()) return;
    window.addEventListener('beforeinstallprompt', e => {
      e.preventDefault();
      deferredPrompt = e;
      btn.hidden = false;
    });
    const isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent);
    if (isIOS) { btn.hidden = false; btn.textContent = 'Come installare su iPhone'; }
    btn.addEventListener('click', async () => {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        if (outcome === 'accepted') { log('App installata sul telefono', 'ok'); btn.hidden = true; }
        deferredPrompt = null;
      } else {
        toast('Safari: tocca Condividi, poi "Aggiungi alla schermata Home"', 5000);
      }
    });
    window.addEventListener('appinstalled', () => { btn.hidden = true; });
  }

  function registerSW() {
    try {
      if (native || !('serviceWorker' in navigator)) return;
      navigator.serviceWorker.register('sw.js').then(
        () => log('Modalità offline pronta', 'ok'),
        () => { /* not available here (e.g. opened as a file) */ },
      );
    } catch { /* sandboxed frame: service workers are disabled */ }
  }

  /* ---------------- start ---------------- */
  async function start() {
    for (const m of Object.values(modules)) {
      try { m.init?.(); } catch (err) { console.error(err); }
    }
    tickClock();
    setInterval(tickClock, 1000);
    updateNet();
    window.addEventListener('online', () => { updateNet(); log('Connessione ripristinata', 'ok'); });
    window.addEventListener('offline', () => { updateNet(); log('Connessione persa', 'hot'); });
    device.connection()?.raw.addEventListener?.('change', () => { updateNet(); log('Cambio di rete rilevato', 'warn'); });
    document.addEventListener('visibilitychange', () => { if (!document.hidden) log('App riaperta'); });
    watchBattery();

    const nodeId = await fillProfiler();
    boot(nodeId);
    log(`Nodo ${nodeId} online`, 'ok');
    log(`${device.detectOS()} · ${device.detectBrowser()}`);
    setInterval(heartbeat, 7000);

    window.addEventListener('hashchange', route);
    route();
    setupInstall();
    registerSW();
  }

  start();
})();
