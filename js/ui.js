window.GL = window.GL || {};

(() => {
  'use strict';

  // Shared helpers used by every tool module.

  // Bridge exposed by the Android app (MainActivity.NativeBridge); null in a normal browser.
  const native = window.GhostlinkNative || null;

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  const pad = n => String(n).padStart(2, '0');
  const clock = (d = new Date()) => `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;

  let toastTimer;
  function toast(msg, ms = 2200) {
    const el = $('#toast');
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, ms);
  }

  // Home "system log". kind: ok | warn | hot | (empty)
  function log(msg, kind = '') {
    const list = $('#log');
    if (!list) return;
    const li = document.createElement('li');
    const t = document.createElement('time');
    t.textContent = clock();
    const span = document.createElement('span');
    span.textContent = msg;
    if (kind) span.className = `t-${kind}`;
    li.append(t, span);
    list.prepend(li);
    while (list.children.length > 14) list.lastElementChild.remove();
  }

  function haptic(pattern = 12) {
    try {
      if (native) native.vibrate(JSON.stringify(Array.isArray(pattern) ? pattern : [pattern]));
      else navigator.vibrate?.(pattern);
    } catch { /* not supported */ }
  }

  async function copyText(text, okMsg = 'Copiato negli appunti') {
    if (!text) { toast('Niente da copiare'); return false; }
    if (native) { native.copy(text); toast(okMsg); haptic(); return true; }
    try {
      await navigator.clipboard.writeText(text);
      toast(okMsg);
      haptic();
      return true;
    } catch {
      // Fallback for browsers that refuse the async clipboard.
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.append(ta);
      ta.select();
      let ok = false;
      try { ok = document.execCommand('copy'); } catch { ok = false; }
      ta.remove();
      toast(ok ? okMsg : 'Copia non riuscita: tieni premuto sul testo per copiarlo');
      return ok;
    }
  }

  function setPressed(buttons, active) {
    buttons.forEach(b => b.setAttribute('aria-pressed', String(b === active)));
  }

  const fmt = {
    num: (n, d = 0) => Number(n).toLocaleString('it-IT', { minimumFractionDigits: d, maximumFractionDigits: d }),
    bytes: gb => (gb >= 1 ? `${gb} GB` : `${gb * 1024} MB`),
  };

  // Pretty duration for "time to crack" style numbers (seconds in, Italian text out).
  function humanTime(sec) {
    if (!isFinite(sec) || sec > 1e30) return 'praticamente infinito';
    if (sec < 1) return 'istantaneo';
    const units = [
      ['secoli', 3.156e9], ['anni', 3.156e7], ['giorni', 86400], ['ore', 3600], ['minuti', 60], ['secondi', 1],
    ];
    for (const [name, s] of units) {
      if (sec >= s) {
        const v = sec / s;
        if (name === 'secoli' && v >= 1e6) return `${v.toExponential(1).replace('e+', ' × 10^')} secoli`;
        return `${fmt.num(v, v < 10 ? 1 : 0)} ${name}`;
      }
    }
    return 'istantaneo';
  }

  // SHA-256 hex of a string; falls back to a simple FNV hash when SubtleCrypto is unavailable.
  async function sha256(text) {
    try {
      const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
      return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
    } catch {
      let h = 0x811c9dc5;
      for (let i = 0; i < text.length; i++) { h ^= text.charCodeAt(i); h = Math.imul(h, 0x01000193); }
      return (h >>> 0).toString(16).padStart(8, '0').repeat(8);
    }
  }

  // Size a canvas backing store to its CSS box at device pixel ratio; returns the 2D context.
  function fitCanvas(canvas) {
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    const w = canvas.clientWidth || canvas.width;
    const h = canvas.clientHeight || canvas.height;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
    }
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, w, h };
  }

  const COLORS = {
    cyan: '#2ef2ff', magenta: '#ff2d75', amber: '#ffb020', ok: '#4dffb0',
    line: '#1b2c45', dim: '#7489a6', fg: '#d9e6f7', bg: '#05070d',
  };

  // Heavy libraries (map, QR reader) load only when a screen that needs them opens,
  // so start-up stays fast. Each URL is fetched at most once.
  const libCache = new Map();
  function loadScript(src) {
    if (libCache.has(src)) return libCache.get(src);
    const p = new Promise((res, rej) => {
      const el = document.createElement('script');
      el.src = src;
      el.async = false;
      el.onload = () => res(true);
      el.onerror = () => rej(new Error(src));
      document.head.append(el);
    });
    libCache.set(src, p);
    return p;
  }

  const LIBS = {
    leaflet: ['vendor/leaflet/leaflet.js'],
    qr: ['vendor/qr/jsQR.js', 'vendor/qr/qrcode.js'],
  };
  // Resolves once the named bundle is in memory; safe to call repeatedly.
  async function needLib(name) {
    const ready = { leaflet: () => !!window.L, qr: () => !!window.jsQR && !!window.qrcode }[name];
    if (ready && ready()) return true;
    try { await Promise.all(LIBS[name].map(loadScript)); } catch { return false; }
    return !ready || ready();
  }

  // Dark map tiles with a fallback: if CARTO is unreachable the layer switches to plain
  // OpenStreetMap tiles, darkened with a CSS filter, so the map still appears.
  function darkTiles(map, container) {
    const PRIMARY = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png';
    const FALLBACK = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
    let errors = 0, swapped = false;
    const layer = window.L.tileLayer(PRIMARY, { subdomains: 'abcd', maxZoom: 19, crossOrigin: true });
    layer.on('tileerror', () => {
      if (swapped || ++errors < 4) return;
      swapped = true;
      layer.options.subdomains = 'abc';
      layer.setUrl(FALLBACK);
      container?.classList.add('map-fallback');
    });
    layer.addTo(map);
    return layer;
  }

  /* ---------------- device permissions & camera ---------------- */
  // In the APK the WebView only sees a camera/mic/GPS once Android itself has granted the
  // runtime permission, so ask for it first and report precisely what happened.
  const permWaiters = new Map();
  function _perm(kind, ok, state) {
    const w = permWaiters.get(kind);
    permWaiters.delete(kind);
    if (w) w({ ok: !!ok, state: state || (ok ? 'granted' : 'denied') });
  }

  function askPermission(kind) {
    if (!native || !native.ensurePermission) return Promise.resolve({ ok: true, state: 'browser' });
    if (native.permState && native.permState(kind) === 'granted') return Promise.resolve({ ok: true, state: 'granted' });
    return new Promise(res => {
      permWaiters.set(kind, res);
      try { native.ensurePermission(kind); } catch { permWaiters.delete(kind); res({ ok: false, state: 'error' }); }
      setTimeout(() => { if (permWaiters.has(kind)) { permWaiters.delete(kind); res({ ok: false, state: 'timeout' }); } }, 45000);
    });
  }

  function openSettings() { try { native?.openAppSettings?.(); } catch { /* not in the APK */ } }

  const CAM_REASON = {
    NotAllowedError: 'permesso negato',
    NotFoundError: 'nessuna fotocamera trovata',
    NotReadableError: 'la fotocamera è occupata da un\'altra app',
    OverconstrainedError: 'questa fotocamera non supporta la modalità richiesta',
    SecurityError: 'bloccata: serve una connessione sicura',
    AbortError: 'avvio interrotto',
  };

  // Single entry point for every camera screen: { stream } on success, { error, blocked } on failure.
  async function getCamera(constraints = { video: { facingMode: { ideal: 'environment' } }, audio: false }) {
    if (!navigator.mediaDevices?.getUserMedia) {
      return { error: 'questo browser non espone la fotocamera (serve https)' };
    }
    const perm = await askPermission('camera');
    if (!perm.ok) {
      return { error: perm.state === 'blocked' ? 'permesso fotocamera negato in modo permanente' : 'permesso fotocamera non concesso', blocked: perm.state === 'blocked' };
    }
    try {
      return { stream: await navigator.mediaDevices.getUserMedia(constraints) };
    } catch (e) {
      // A device without a rear camera rejects facingMode: retry with whatever exists.
      if (e.name === 'OverconstrainedError' || e.name === 'NotFoundError') {
        try { return { stream: await navigator.mediaDevices.getUserMedia({ video: true, audio: !!constraints.audio }) }; } catch (e2) {
          return { error: CAM_REASON[e2.name] || e2.name };
        }
      }
      return { error: CAM_REASON[e.name] || e.name, blocked: e.name === 'NotAllowedError' };
    }
  }

  async function getMic(constraints = { audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } }) {
    if (!navigator.mediaDevices?.getUserMedia) return { error: 'microfono non disponibile' };
    const perm = await askPermission('mic');
    if (!perm.ok) return { error: 'permesso microfono non concesso', blocked: perm.state === 'blocked' };
    try { return { stream: await navigator.mediaDevices.getUserMedia(constraints) }; }
    catch (e) { return { error: CAM_REASON[e.name] || e.name, blocked: e.name === 'NotAllowedError' }; }
  }

  GL.ui = { native, loadScript, needLib, darkTiles, askPermission, openSettings, getCamera, getMic, _perm, $, $$, clock, toast, log, haptic, copyText, setPressed, fmt, humanTime, sha256, fitCanvas, COLORS };
})();
