'use strict';
/* ════════════════════════════════════════════════════════════════
   OJO DE DEUS v100 — CORE
   Utility, impostazioni, rete con fallback CORS, stato dei feed,
   notifiche, log, voce, suoni, calcoli geografici.
═══════════════════════════════════════════════════════════════════ */
const OJO = { version: '100', started: Date.now() };

/* ═══ DOM ═══ */
const $ = id => document.getElementById(id);
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'style') el.style.cssText = v;
    else if (k === 'text') el.textContent = v;
    else if (k === 'html') el.innerHTML = v;            // solo per markup statico interno
    else if (k === 'dataset') Object.assign(el.dataset, v);
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat(Infinity)) {
    if (c == null || c === false) continue;
    el.append(c && c.nodeType ? c : String(c));
  }
  return el;
}
function setText(id, v) { const e = $(id); if (e) e.textContent = (v ?? '') + ''; }
function setHTMLSafe(id, ...kids) { const e = $(id); if (e) e.replaceChildren(...kids.flat(Infinity).filter(k => k != null)); }
function loadScript(src, timeout = 30000) {
  return new Promise((res, rej) => {
    const s = document.createElement('script');
    const t = setTimeout(() => { s.remove(); rej(new Error('timeout ' + src)); }, timeout);
    s.src = src; s.async = true; s.crossOrigin = 'anonymous';
    s.onload = () => { clearTimeout(t); res(); };
    s.onerror = () => { clearTimeout(t); s.remove(); rej(new Error('load ' + src)); };
    document.head.appendChild(s);
  });
}
function loadCSS(href) {
  return new Promise(res => {
    const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = href; l.crossOrigin = 'anonymous';
    l.onload = () => res(true); l.onerror = () => res(false);
    document.head.appendChild(l);
  });
}

/* ═══ FORMAT ═══ */
const pad2 = v => String(v).padStart(2, '0');
const Fmt = {
  n(v, d = 0) { return v == null || isNaN(v) ? '--' : Number(v).toLocaleString('it-IT', { minimumFractionDigits: d, maximumFractionDigits: d }); },
  utc(t = Date.now(), sec = false) { const d = new Date(t); return `${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}${sec ? ':' + pad2(d.getUTCSeconds()) : ''}`; },
  local(t = Date.now()) { return new Date(t).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' }); },
  dateTime(t) { return new Date(t).toLocaleString('it-IT', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }); },
  ago(t) {
    if (!t) return '--';
    const s = Math.max(0, (Date.now() - t) / 1000);
    if (s < 60) return Math.round(s) + ' s fa';
    if (s < 3600) return Math.round(s / 60) + ' min fa';
    if (s < 86400) return Math.round(s / 3600) + ' h fa';
    return Math.round(s / 86400) + ' g fa';
  },
  lat(v) { return `${Math.abs(v).toFixed(4)}°${v >= 0 ? 'N' : 'S'}`; },
  lon(v) { return `${Math.abs(v).toFixed(4)}°${v >= 0 ? 'E' : 'O'}`; },
  dms(v, isLat) {
    const a = Math.abs(v), d = Math.floor(a), m = Math.floor((a - d) * 60), s = ((a - d) * 60 - m) * 60;
    return `${d}°${pad2(m)}′${s.toFixed(1).padStart(4, '0')}″${isLat ? (v >= 0 ? 'N' : 'S') : (v >= 0 ? 'E' : 'O')}`;
  },
  alt(m) { if (m == null) return '--'; return m >= 10000 ? Fmt.n(m / 1000, m >= 1e6 ? 0 : 1) + ' km' : Fmt.n(m) + ' m'; },
  price(v) { if (v == null || isNaN(v)) return '--'; return v >= 1000 ? Fmt.n(v, 0) : v >= 10 ? Fmt.n(v, 2) : v >= 1 ? Fmt.n(v, 3) : Fmt.n(v, 4); },
  pct(v) { if (v == null || isNaN(v)) return '--'; return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'; },
  esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
};
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const sleep = ms => new Promise(r => setTimeout(r, ms));

/* ═══ STORE (localStorage sicuro) ═══ */
const Store = {
  get(k, def = null) { try { const v = localStorage.getItem('ojo.' + k); return v == null ? def : JSON.parse(v); } catch { return def; } },
  set(k, v) { try { localStorage.setItem('ojo.' + k, JSON.stringify(v)); return true; } catch { return false; } },
  del(k) { try { localStorage.removeItem('ojo.' + k); } catch {} }
};

/* ═══ SETTINGS ═══ */
const Settings = (() => {
  const DEF = {
    ionToken: '', firmsKey: '', proxy: '',
    tts: false, ttsAlerts: true, sound: true, autoFlyAlerts: false,
    maxAircraft: 15000, labels: true, terrain: true, lighting: true, nightLights: true,
    base: 'sat', exag: 1.5, quality: 'auto', mapH: 58, autostart: false,
    layers: null
  };
  let s = Object.assign({}, DEF, Store.get('settings', {}));
  return {
    get(k) { return s[k]; },
    set(k, v) { s[k] = v; Store.set('settings', s); Bus.emit('settings', { k, v }); },
    all() { return Object.assign({}, s); },
    reset() { s = Object.assign({}, DEF); Store.set('settings', s); }
  };
})();

/* ═══ EVENT BUS ═══ */
const Bus = (() => {
  const m = new Map();
  return {
    on(e, f) { if (!m.has(e)) m.set(e, new Set()); m.get(e).add(f); return () => m.get(e)?.delete(f); },
    emit(e, d) { m.get(e)?.forEach(f => { try { f(d); } catch (err) { console.warn('[bus]', e, err); } }); }
  };
})();

/* ═══ SCHEDULER (non si sovrappone, rallenta quando la scheda è nascosta) ═══ */
const Scheduler = (() => {
  const jobs = new Map();
  function arm(j) { clearTimeout(j.t); j.t = setTimeout(() => run(j), j.ms); }
  async function run(j) {
    if (j.cancelled) return;
    if (document.hidden && !j.bg && Date.now() - j.last < j.ms * 5) { arm(j); return; }
    if (j.busy) { arm(j); return; }
    j.busy = true;
    try { await j.fn(); } catch (e) { console.warn('[sched]', j.name, e); }
    j.busy = false; j.last = Date.now();
    arm(j);
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) return;
    jobs.forEach(j => { if (Date.now() - j.last > j.ms) { clearTimeout(j.t); run(j); } });
  });
  return {
    every(name, fn, ms, { now = true, bg = false, delay = 0 } = {}) {
      this.cancel(name);
      const j = { name, fn, ms, bg, last: 0, busy: false, t: null, cancelled: false };
      jobs.set(name, j);
      if (now) setTimeout(() => run(j), delay); else arm(j);
      return j;
    },
    runNow(name) { const j = jobs.get(name); if (j) { clearTimeout(j.t); run(j); } },
    setInterval(name, ms) { const j = jobs.get(name); if (j) { j.ms = ms; arm(j); } },
    cancel(name) { const j = jobs.get(name); if (j) { j.cancelled = true; clearTimeout(j.t); jobs.delete(name); } }
  };
})();

/* ═══ NETWORK: fetch con timeout + catena di proxy CORS adattiva ═══ */
const Net = (() => {
  const PROXIES = [
    { name: 'allorigins', f: u => `https://api.allorigins.win/raw?url=${encodeURIComponent(u)}` },
    { name: 'corsproxy.io', f: u => `https://corsproxy.io/?url=${encodeURIComponent(u)}` },
    { name: 'codetabs', f: u => `https://api.codetabs.com/v1/proxy?quest=${encodeURIComponent(u)}` },
    { name: 'cors.lol', f: u => `https://api.cors.lol/?url=${encodeURIComponent(u)}` }
  ];
  const fails = new Map();                 // proxy -> fallimenti consecutivi
  const hostMode = new Map(Object.entries(Store.get('hostmode', {})));   // host -> 'direct'|'proxy'
  const saveHost = () => Store.set('hostmode', Object.fromEntries(hostMode));
  let stats = { direct: 0, proxy: 0, fail: 0 };

  async function raw(url, timeout, init = {}) {
    const ac = new AbortController();
    const t = setTimeout(() => ac.abort(), timeout);
    try {
      const r = await fetch(url, Object.assign({ signal: ac.signal, credentials: 'omit', referrerPolicy: 'no-referrer' }, init));
      if (!r.ok) { const e = new Error('HTTP ' + r.status); e.status = r.status; throw e; }
      return r;
    } finally { clearTimeout(t); }
  }
  async function body(r, type) {
    if (type === 'json') { const txt = await r.text(); return JSON.parse(txt); }
    if (type === 'blob') return r.blob();
    return r.text();
  }
  function customProxy() {
    const p = (Settings.get('proxy') || '').trim();
    if (!p) return null;
    return { name: 'personale', f: u => p.includes('{url}') ? p.replace('{url}', encodeURIComponent(u)) : p + encodeURIComponent(u) };
  }
  function proxyList() {
    const list = PROXIES.slice().sort((a, b) => (fails.get(a.name) || 0) - (fails.get(b.name) || 0));
    const c = customProxy();
    return c ? [c, ...list] : list;
  }
  /**
   * get(url, {type, timeout, via, validate, init})
   * via: 'auto' (diretto, poi proxy), 'direct', 'proxy' (proxy subito)
   * Ritorna {data, via, ms}
   */
  async function get(url, opt = {}) {
    const type = opt.type || 'json', timeout = opt.timeout || 12000;
    let via = opt.via || 'auto';
    const host = (() => { try { return new URL(url).host; } catch { return ''; } })();
    if (via === 'auto' && hostMode.get(host) === 'proxy') via = 'proxy-first';
    const t0 = performance.now();
    const errors = [];
    const check = d => { if (opt.validate && !opt.validate(d)) throw new Error('contenuto non valido'); return d; };

    const tryDirect = async () => {
      const r = await raw(url, timeout, opt.init);
      const d = check(await body(r, type));
      if (hostMode.get(host) !== 'direct') { hostMode.set(host, 'direct'); saveHost(); }
      stats.direct++;
      return { data: d, via: 'diretto', ms: Math.round(performance.now() - t0) };
    };
    const tryProxies = async () => {
      for (const p of proxyList()) {
        try {
          const r = await raw(p.f(url), timeout + 3000);
          const d = check(await body(r, type));
          fails.set(p.name, 0); stats.proxy++;
          return { data: d, via: 'proxy ' + p.name, ms: Math.round(performance.now() - t0) };
        } catch (e) { fails.set(p.name, (fails.get(p.name) || 0) + 1); errors.push(p.name + ': ' + e.message); }
      }
      throw new Error('proxy falliti');
    };

    if (via === 'direct') return tryDirect();
    if (via === 'proxy') return tryProxies().catch(() => { stats.fail++; throw new Error(errors.join(' | ') || 'rete'); });
    if (via === 'proxy-first') {
      try { return await tryProxies(); } catch {}
      try { return await tryDirect(); } catch (e) { errors.push('diretto: ' + e.message); stats.fail++; throw new Error(errors.join(' | ')); }
    }
    try { return await tryDirect(); }
    catch (e) {
      errors.push('diretto: ' + (e.name === 'AbortError' ? 'timeout' : e.message));
      // HTTP 4xx dall'origine = errore reale, il proxy non aiuta (tranne 403 anti-bot)
      if (e.status && e.status >= 400 && e.status < 500 && e.status !== 403 && e.status !== 429) { stats.fail++; throw e; }
      if (opt.noProxy) { stats.fail++; throw e; }
      try {
        const res = await tryProxies();
        if (!e.status) { hostMode.set(host, 'proxy'); saveHost(); }   // CORS/rete: ricorda
        return res;
      } catch { stats.fail++; throw new Error(errors.join(' | ')); }
    }
  }
  return { get, raw, get stats() { return stats; }, forget() { hostMode.clear(); saveHost(); } };
})();

/* ═══ HEALTH: stato onesto di ogni feed ═══ */
const Health = (() => {
  const feeds = new Map();
  const ORDER = [];
  const LBL = { live: 'LIVE', err: 'ERRORE', wait: 'ATTESA', off: 'OFF', key: 'CHIAVE', ref: 'REF', calc: 'CALC' };
  let renderT = null;
  function render() {
    renderT = null;
    let ok = 0, tot = 0;
    const list = $('health-list');
    const frag = document.createDocumentFragment();
    ORDER.forEach(id => {
      const f = feeds.get(id);
      if (f.status !== 'off' && f.status !== 'key') tot++;
      if (f.status === 'live') ok++;
      frag.appendChild(h('div', { class: 'hp-item' },
        h('span', { class: 'dstat ' + f.status }, LBL[f.status] || f.status),
        h('div', { class: 'hp-name' }, f.label,
          h('div', { class: 'hp-sub', title: f.msg || '' }, [f.via, f.items != null ? f.items + ' elementi' : null, f.ms ? f.ms + ' ms' : null, f.msg].filter(Boolean).join(' · ') || '--')),
        h('div', { class: 'hp-time' }, f.t ? Fmt.ago(f.t) : '--')));
    });
    if (list) list.replaceChildren(frag);
    setText('st-feeds', `${ok}/${tot}`);
    document.querySelectorAll('[data-h]').forEach(el => {
      const f = feeds.get(el.dataset.h); if (!f) return;
      el.className = 'dstat ' + f.status;
      el.textContent = LBL[f.status] || f.status;
      el.title = [f.label, f.via, f.msg].filter(Boolean).join(' · ');
    });
  }
  const sched = () => { if (!renderT) renderT = setTimeout(render, 120); };
  setInterval(sched, 15000);
  return {
    register(id, label) { if (!feeds.has(id)) { feeds.set(id, { id, label, status: 'wait' }); ORDER.push(id); sched(); } },
    ok(id, info = {}) { const f = feeds.get(id); if (!f) return; Object.assign(f, { status: 'live', t: Date.now(), msg: info.msg || '', via: info.via || f.via, items: info.items ?? f.items, ms: info.ms }); f.errs = 0; sched(); },
    fail(id, err) {
      const f = feeds.get(id); if (!f) return;
      f.errs = (f.errs || 0) + 1;
      // se avevamo dati recenti resta LIVE ma segnala il problema
      f.msg = String(err?.message || err || 'errore').slice(0, 140);
      if (f.status !== 'live' || f.errs >= 3) f.status = 'err';
      sched();
    },
    set(id, status, msg = '') { const f = feeds.get(id); if (!f) return; f.status = status; f.msg = msg; if (status === 'live') f.t = Date.now(); sched(); },
    status(id) { return feeds.get(id)?.status; },
    all() { return [...feeds.values()]; },
    render
  };
})();

/* ═══ TOAST ═══ */
const Toast = {
  show(msg, type = '', ms = 3800) {
    const c = $('alert-pop'); if (!c) return;
    while (c.children.length > 3) c.firstChild.remove();
    const el = h('div', { class: 'apop' + (type ? ' ' + type : '') }, msg);
    c.appendChild(el);
    setTimeout(() => { el.style.transition = 'opacity .4s'; el.style.opacity = '0'; setTimeout(() => el.remove(), 420); }, ms);
  }
};

/* ═══ EVENT LOG ═══ */
const EventLog = (() => {
  const items = [];
  let t = null;
  function render() {
    t = null;
    const c = $('event-log'); if (!c) return;
    setText('log-cnt', items.length);
    c.replaceChildren(...items.slice(0, 60).map(e => h('div', { class: 'wt' }, h('span', { class: 'wt-time' }, e.ts), h('span', { style: `color:${e.col}` }, e.txt))));
  }
  return {
    add(txt, col = 'var(--gm)') {
      items.unshift({ ts: Fmt.utc(Date.now(), true), txt, col });
      if (items.length > 120) items.length = 120;
      if (!t) t = setTimeout(render, 200);
    },
    get items() { return items; }
  };
})();

/* ═══ TTS (voce italiana) ═══ */
const TTS = (() => {
  let on = !!Settings.get('tts'), speaking = false, voice = null;
  const q = [], recent = new Map();
  function loadVoice() {
    if (!window.speechSynthesis) return;
    const vs = speechSynthesis.getVoices();
    voice = vs.find(v => v.lang === 'it-IT' && /google|neural|natural|online/i.test(v.name))
      || vs.find(v => v.lang === 'it-IT') || vs.find(v => v.lang?.toLowerCase().startsWith('it')) || null;
  }
  function next() {
    if (speaking || !q.length || !window.speechSynthesis) return;
    speaking = true; if (!voice) loadVoice();
    const u = new SpeechSynthesisUtterance(q.shift());
    u.lang = 'it-IT'; u.rate = 1.02; u.pitch = 0.95; u.volume = 0.95; if (voice) u.voice = voice;
    const done = () => { speaking = false; setTimeout(next, 180); };
    u.onend = done; u.onerror = done;
    try { speechSynthesis.speak(u); } catch { done(); }
    setTimeout(() => { if (speaking && !speechSynthesis.speaking) done(); }, 15000);
  }
  if (window.speechSynthesis) { speechSynthesis.onvoiceschanged = loadVoice; loadVoice(); }
  function badge() { const b = $('btn-tts'); if (b) { b.textContent = on ? '🔊' : '🔇'; b.classList.toggle('on', on); } }
  return {
    get enabled() { return on; },
    get available() { return !!window.speechSynthesis; },
    speak(text, { prio = false, key = null } = {}) {
      if (!on || !window.speechSynthesis || !text) return;
      if (key) { const last = recent.get(key); if (last && Date.now() - last < 90000) return; recent.set(key, Date.now()); }
      if (prio) { q.unshift(text); } else { q.push(text); if (q.length > 6) q.splice(0, q.length - 6); }
      next();
    },
    stop() { q.length = 0; try { speechSynthesis.cancel(); } catch {} speaking = false; },
    toggle(force) {
      on = force ?? !on; Settings.set('tts', on); badge();
      if (!on) this.stop();
      if (on && !this.available) Toast.show('⚠ Sintesi vocale non disponibile in questo browser', 'orn');
      else if (on) this.speak('Sistema vocale attivo.', { prio: true });
      Toast.show(on ? '🔊 Voce italiana attiva' : '🔇 Voce disattivata', on ? 'ok' : '');
    },
    badge
  };
})();

/* ═══ SOUND (WebAudio, nessun file esterno) ═══ */
const Sound = (() => {
  let ctx = null;
  function c() { if (!ctx) { try { ctx = new (window.AudioContext || window.webkitAudioContext)(); } catch { ctx = null; } } return ctx; }
  function tone(freq, dur, type = 'sine', vol = 0.05, delay = 0) {
    const a = c(); if (!a || !Settings.get('sound')) return;
    if (a.state === 'suspended') a.resume().catch(() => {});
    const o = a.createOscillator(), g = a.createGain();
    o.type = type; o.frequency.value = freq;
    const t = a.currentTime + delay;
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(vol, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g).connect(a.destination); o.start(t); o.stop(t + dur + 0.05);
  }
  return {
    unlock() { c(); },
    ping() { tone(1320, 0.12, 'sine', 0.04); },
    lock() { tone(880, 0.08, 'square', 0.03); tone(1760, 0.1, 'square', 0.03, 0.09); },
    alert() { tone(660, 0.18, 'sawtooth', 0.05); tone(440, 0.25, 'sawtooth', 0.05, 0.2); },
    ok() { tone(520, 0.1, 'triangle', 0.04); tone(780, 0.14, 'triangle', 0.04, 0.1); }
  };
})();

/* ═══ GEO ═══ */
const Geo = (() => {
  const R = 6371.0088;
  const rad = d => d * Math.PI / 180, deg = r => r * 180 / Math.PI;
  function dist(a1, o1, a2, o2) {
    const dA = rad(a2 - a1), dO = rad(o2 - o1);
    const x = Math.sin(dA / 2) ** 2 + Math.cos(rad(a1)) * Math.cos(rad(a2)) * Math.sin(dO / 2) ** 2;
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(x)));
  }
  function bearing(a1, o1, a2, o2) {
    const y = Math.sin(rad(o2 - o1)) * Math.cos(rad(a2));
    const x = Math.cos(rad(a1)) * Math.sin(rad(a2)) - Math.sin(rad(a1)) * Math.cos(rad(a2)) * Math.cos(rad(o2 - o1));
    return (deg(Math.atan2(y, x)) + 360) % 360;
  }
  function dest(lat, lon, brg, km) {
    const d = km / R, b = rad(brg), a1 = rad(lat), o1 = rad(lon);
    const a2 = Math.asin(Math.sin(a1) * Math.cos(d) + Math.cos(a1) * Math.sin(d) * Math.cos(b));
    const o2 = o1 + Math.atan2(Math.sin(b) * Math.sin(d) * Math.cos(a1), Math.cos(d) - Math.sin(a1) * Math.sin(a2));
    return [deg(a2), ((deg(o2) + 540) % 360) - 180];
  }
  function gcPath(a1, o1, a2, o2, n = 64) {
    const d = dist(a1, o1, a2, o2), b = bearing(a1, o1, a2, o2), out = [];
    // interpolazione sferica precisa
    const p1 = [rad(a1), rad(o1)], p2 = [rad(a2), rad(o2)], dd = d / R;
    if (dd < 1e-9) return [[a1, o1], [a2, o2]];
    for (let i = 0; i <= n; i++) {
      const f = i / n, A = Math.sin((1 - f) * dd) / Math.sin(dd), B = Math.sin(f * dd) / Math.sin(dd);
      const x = A * Math.cos(p1[0]) * Math.cos(p1[1]) + B * Math.cos(p2[0]) * Math.cos(p2[1]);
      const y = A * Math.cos(p1[0]) * Math.sin(p1[1]) + B * Math.cos(p2[0]) * Math.sin(p2[1]);
      const z = A * Math.sin(p1[0]) + B * Math.sin(p2[0]);
      out.push([deg(Math.atan2(z, Math.hypot(x, y))), deg(Math.atan2(y, x))]);
    }
    void b; return out;
  }
  const DIRS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSO', 'SO', 'OSO', 'O', 'ONO', 'NO', 'NNO'];
  const dir = d => DIRS[Math.round(((d % 360) + 360) % 360 / 22.5) % 16];
  // posizione del sole (algoritmo NOAA semplificato, precisione ~0.1°)
  function sun(date = new Date()) {
    const jd = date.getTime() / 86400000 + 2440587.5, n = jd - 2451545.0;
    const L = (280.460 + 0.9856474 * n) % 360, g = rad((357.528 + 0.9856003 * n) % 360);
    const lambda = rad(L + 1.915 * Math.sin(g) + 0.020 * Math.sin(2 * g));
    const eps = rad(23.439 - 0.0000004 * n);
    const decl = Math.asin(Math.sin(eps) * Math.sin(lambda));
    const ra = Math.atan2(Math.cos(eps) * Math.sin(lambda), Math.cos(lambda));
    const gmst = (280.46061837 + 360.98564736629 * n) % 360;
    let lon = deg(ra) - gmst; lon = ((lon + 540) % 360) - 180;
    return { lat: deg(decl), lon };
  }
  function sunElev(lat, lon, date = new Date()) {
    const s = sun(date);
    const c = Math.sin(rad(lat)) * Math.sin(rad(s.lat)) + Math.cos(rad(lat)) * Math.cos(rad(s.lat)) * Math.cos(rad(lon - s.lon));
    return deg(Math.asin(clamp(c, -1, 1)));
  }
  function parseCoords(s) {
    const m = String(s).trim().match(/^(-?\d{1,2}(?:\.\d+)?)\s*°?\s*([NS])?[,;\s]+(-?\d{1,3}(?:\.\d+)?)\s*°?\s*([EWO])?$/i);
    if (!m) return null;
    let lat = parseFloat(m[1]), lon = parseFloat(m[3]);
    if (m[2] && /s/i.test(m[2])) lat = -Math.abs(lat);
    if (m[4] && /[wo]/i.test(m[4])) lon = -Math.abs(lon);
    if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
    return { lat, lon };
  }
  // quota camera <-> zoom web mercator (approssimazione per Leaflet)
  const altToZoom = alt => clamp(Math.log2(35200000 / Math.max(alt, 50)), 1, 19);
  const zoomToAlt = z => 35200000 / Math.pow(2, z);
  return { R, rad, deg, dist, bearing, dest, gcPath, dir, sun, sunElev, parseCoords, altToZoom, zoomToAlt };
})();
