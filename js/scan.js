window.GL = window.GL || {};

(() => {
  'use strict';

  const { $, log, haptic, sha256, fmt } = GL.ui;
  const device = GL.device;

  let running = false;

  function card(title, rows, note) {
    const el = document.createElement('div');
    el.className = 'card';
    const h = document.createElement('div');
    h.className = 'eyebrow';
    h.textContent = title;
    el.append(h);
    for (const [label, value, cls] of rows) {
      const kv = document.createElement('div');
      kv.className = 'kv';
      const s = document.createElement('span');
      s.textContent = label;
      const b = document.createElement('b');
      b.textContent = value ?? '—';
      if (cls) b.className = cls;
      kv.append(s, b);
      el.append(kv);
    }
    if (note) {
      const p = document.createElement('p');
      p.className = 'note';
      p.textContent = note;
      el.append(p);
    }
    return el;
  }

  const wait = ms => new Promise(r => setTimeout(r, ms));

  async function fetchJSON(url, ms = 6000) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), ms);
    try {
      const res = await fetch(url, { signal: ctrl.signal, cache: 'no-store' });
      if (!res.ok) throw new Error(res.status);
      return await res.json();
    } finally { clearTimeout(timer); }
  }

  async function publicIP() {
    const t0 = performance.now();
    try {
      const d = await fetchJSON('https://ipapi.co/json/');
      if (d.error) throw new Error(d.reason);
      return { ip: d.ip, place: [d.city, d.region, d.country_name].filter(Boolean).join(', '), isp: d.org, ms: performance.now() - t0 };
    } catch { /* try the next provider */ }
    try {
      const d = await fetchJSON('https://ipwho.is/');
      if (d.success === false) throw new Error(d.message);
      return { ip: d.ip, place: [d.city, d.region, d.country].filter(Boolean).join(', '), isp: d.connection?.isp, ms: performance.now() - t0 };
    } catch { return null; }
  }

  async function permissions() {
    const names = [['geolocation', 'Posizione'], ['camera', 'Fotocamera'], ['microphone', 'Microfono'], ['notifications', 'Notifiche']];
    const label = { granted: ['concesso', 'hot'], denied: ['negato', 'good'], prompt: ['da chiedere', ''] };
    const out = [];
    for (const [name, it] of names) {
      try {
        const st = await navigator.permissions.query({ name });
        const [txt, cls] = label[st.state] || [st.state, ''];
        out.push([it, txt, cls]);
      } catch { out.push([it, 'non verificabile', '']); }
    }
    return out;
  }

  async function run() {
    if (running) return;
    running = true;
    const btn = $('#scan-run');
    const out = $('#scan-out');
    const bar = $('#scan-bar');
    btn.disabled = true;
    btn.textContent = 'Scansione in corso…';
    out.replaceChildren();
    $('.scan-progress').classList.add('run');
    const step = pct => { bar.style.width = `${pct}%`; };
    log('Scansione del dispositivo avviata', 'warn');

    try {
      // 1. fingerprint
      step(15);
      const parts = device.fingerprintParts();
      const hash = await sha256(parts.map(p => String(p[1])).join('|'));
      const score = device.exposureScore();
      const risk = device.exposureLabel(score);
      await wait(350);
      out.append(card('Impronta digitale', [
        ['Codice', hash.slice(0, 16).toUpperCase()],
        ['Riconoscibilità', risk.text, risk.cls],
        ['Segnali usati', `${parts.filter(p => p[1]).length} su ${parts.length}`],
      ], 'Questo codice si ricalcola uguale ogni volta: un sito può riconoscerti anche se cancelli i cookie o usi la navigazione in incognito.'));
      haptic(10);

      // 2. device
      step(40);
      await wait(300);
      const s = device.screenInfo();
      out.append(card('Dispositivo', [
        ['Sistema', device.detectOS()],
        ['Browser', device.detectBrowser()],
        ['Schermo', `${s.real} px · densità ${fmt.num(s.dpr, 2)}x`],
        ['Processore', navigator.hardwareConcurrency ? `${navigator.hardwareConcurrency} core` : null],
        ['Memoria RAM', navigator.deviceMemory ? `≈ ${fmt.bytes(navigator.deviceMemory)}` : 'nascosta'],
        ['Scheda grafica', device.gpuInfo() || 'nascosta', device.gpuInfo() ? 'warn' : 'good'],
        ['Punti touch', navigator.maxTouchPoints],
        ['Lingue', (navigator.languages || [navigator.language]).join(', ')],
        ['Fuso orario', Intl.DateTimeFormat().resolvedOptions().timeZone],
        ['Modalità', device.isStandalone() ? 'app installata' : 'browser'],
      ]));
      haptic(10);

      // 3. battery + network
      step(65);
      const b = await device.battery();
      const c = device.connection();
      const ip = navigator.onLine ? await publicIP() : null;
      const net = [
        ['Stato', navigator.onLine ? 'online' : 'offline', navigator.onLine ? 'good' : 'hot'],
        ['Tipo', c?.type || c?.effective?.toUpperCase() || 'non dichiarato'],
        ['Banda stimata', c?.down ? `${c.down} Mbps` : null],
        ['Latenza stimata', c?.rtt != null ? `${c.rtt} ms` : null],
        ['Risparmio dati', c ? (c.saveData ? 'attivo' : 'spento') : null],
        ['IP pubblico', ip?.ip || 'non raggiungibile', ip ? 'hot' : ''],
        ['Zona dell\'IP', ip?.place || null],
        ['Operatore', ip?.isp || null],
      ];
      if (ip) net.push(['Risposta server', `${Math.round(ip.ms)} ms`]);
      if (b) net.push(['Batteria', `${Math.round(b.level * 100)}% ${b.charging ? '· in carica' : ''}`]);
      out.append(card('Rete', net, ip ? 'Il tuo IP rivela la zona e l\'operatore a ogni sito che visiti. Una VPN lo nasconde.' : null));
      haptic(10);

      // 4. permissions
      step(90);
      if (navigator.permissions) out.append(card('Permessi concessi a Ghostlink', await permissions()));
      step(100);
      log(`Scansione completata · riconoscibilità ${score}/100`, 'ok');
      haptic([20, 40, 20]);
    } catch (err) {
      console.error(err);
      log('Scansione interrotta', 'hot');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Ripeti scansione';
      setTimeout(() => { $('.scan-progress').classList.remove('run'); step(0); }, 700);
      running = false;
    }
  }

  function init() {
    $('#scan-run').addEventListener('click', run);
  }

  GL.scan = { init };
})();
