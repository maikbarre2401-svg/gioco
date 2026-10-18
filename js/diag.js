window.GL = window.GL || {};

(() => {
  'use strict';

  const { native, $, toast, copyText, fmt } = GL.ui;
  let running = false;
  const report = [];

  function row(label, state, detail) {
    const d = document.createElement('div');
    d.className = 'diag-row';
    const l = document.createElement('span'); l.className = 'diag-label'; l.textContent = label;
    const b = document.createElement('b'); b.className = `diag-state diag-${state}`;
    b.textContent = { ok: 'OK', warn: 'ATTENZIONE', bad: 'NON VA', info: '—' }[state] || state;
    const n = document.createElement('div'); n.className = 'diag-detail'; n.textContent = detail || '';
    d.append(l, b, n);
    $('#diag-out').append(d);
    report.push(`${label}: ${b.textContent}${detail ? ' — ' + detail : ''}`);
  }

  const wait = ms => new Promise(r => setTimeout(r, ms));

  async function testEnv() {
    row('App', 'info', native ? 'APK Android (ponte nativo attivo)' : (matchMedia('(display-mode: standalone)').matches ? 'PWA installata' : 'browser'));
    row('Connessione sicura', window.isSecureContext ? 'ok' : 'bad',
      window.isSecureContext ? 'https: fotocamera e sensori ammessi' : 'senza https il telefono blocca fotocamera, microfono e GPS');
    row('Sistema', 'info', `${GL.device.detectOS()} · ${GL.device.detectBrowser()}`);
  }

  async function testCamera() {
    if (!navigator.mediaDevices?.getUserMedia) { row('Fotocamera', 'bad', 'il browser non espone la fotocamera'); return; }
    const state = native?.permState ? native.permState('camera') : 'sconosciuto';
    const res = await GL.ui.getCamera();
    if (res.stream) {
      const t = res.stream.getVideoTracks()[0];
      const s = t.getSettings ? t.getSettings() : {};
      const torch = t.getCapabilities?.().torch ? ', LED torcia disponibile' : '';
      row('Fotocamera', 'ok', `${s.width || '?'}×${s.height || '?'}${s.facingMode ? ' · ' + s.facingMode : ''}${torch}`);
      res.stream.getTracks().forEach(x => x.stop());
    } else {
      row('Fotocamera', 'bad', `${res.error}${res.blocked ? ' (negato in modo permanente: apri le impostazioni dell\'app)' : ''}${state === 'granted' ? ' · permesso Android risulta concesso' : ''}`);
    }
    try {
      const devs = await navigator.mediaDevices.enumerateDevices();
      const cams = devs.filter(d => d.kind === 'videoinput').length;
      row('Fotocamere trovate', cams ? 'ok' : 'warn', `${cams}`);
    } catch { /* enumeration blocked */ }
  }

  async function testMic() {
    const res = await GL.ui.getMic();
    if (res.stream) { row('Microfono', 'ok', 'funziona'); res.stream.getTracks().forEach(x => x.stop()); }
    else row('Microfono', 'bad', `${res.error}${res.blocked ? ' (apri le impostazioni dell\'app)' : ''}`);
  }

  function testGps() {
    return new Promise(async res => {
      if (!('geolocation' in navigator)) { row('Posizione GPS', 'bad', 'non supportata'); res(); return; }
      const perm = await GL.ui.askPermission('location');
      if (!perm.ok) { row('Posizione GPS', 'bad', `permesso non concesso (${perm.state})`); res(); return; }
      const t0 = performance.now();
      navigator.geolocation.getCurrentPosition(
        p => {
          row('Posizione GPS', 'ok', `${p.coords.latitude.toFixed(4)}, ${p.coords.longitude.toFixed(4)} · ± ${Math.round(p.coords.accuracy)} m · ${Math.round(performance.now() - t0)} ms`);
          res();
        },
        e => {
          const why = { 1: 'permesso negato', 2: 'posizione non determinabile (GPS spento?)', 3: 'tempo scaduto' }[e.code] || e.message;
          row('Posizione GPS', 'bad', why);
          res();
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
      );
    });
  }

  async function testCompass() {
    const evt = 'ondeviceorientationabsolute' in window ? 'deviceorientationabsolute' : 'deviceorientation';
    let got = null;
    // Some engines fire an empty orientation event even with no sensor: require real angles.
    const h = e => { if (got === null && (e.alpha != null || typeof e.webkitCompassHeading === 'number')) got = e; };
    try {
      if (typeof DeviceOrientationEvent?.requestPermission === 'function') await DeviceOrientationEvent.requestPermission();
    } catch { /* iOS only */ }
    window.addEventListener(evt, h);
    await wait(2200);
    window.removeEventListener(evt, h);
    if (!got) { row('Bussola', 'bad', `nessun dato dal sensore (evento ${evt})`); return; }
    const abs = got.absolute || typeof got.webkitCompassHeading === 'number';
    row('Bussola', abs ? 'ok' : 'warn',
      abs ? `funziona · direzione ${Math.round(got.webkitCompassHeading ?? (360 - got.alpha))}°`
          : 'il sensore risponde ma non dà il Nord assoluto: in Cielo AR usa le frecce');
  }

  async function testAccel() {
    let got = null;
    const h = e => { if (got === null && e.accelerationIncludingGravity?.x != null) got = e; };
    window.addEventListener('devicemotion', h);
    await wait(1500);
    window.removeEventListener('devicemotion', h);
    row('Accelerometro', got ? 'ok' : 'bad', got ? 'funziona' : 'nessun dato (sismografo e livella non funzioneranno)');
  }

  async function head(url, label, ms = 8000) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), ms);
    const t0 = performance.now();
    try {
      const r = await fetch(url, { signal: ctrl.signal, cache: 'no-store', mode: 'no-cors' });
      row(label, 'ok', `raggiungibile · ${Math.round(performance.now() - t0)} ms`);
      return true;
    } catch (e) {
      row(label, 'bad', e.name === 'AbortError' ? 'nessuna risposta entro 8 s' : 'non raggiungibile');
      return false;
    } finally { clearTimeout(timer); }
  }

  async function testNetwork() {
    row('Rete', navigator.onLine ? 'ok' : 'bad', navigator.onLine ? 'online' : 'offline');
    if (!navigator.onLine) return;
    // Reachability only: an opaque no-cors response cannot report the HTTP status.
    await head('https://a.basemaps.cartocdn.com/dark_all/4/8/5.png', 'Tessere mappa (CARTO)');
    await head('https://tile.openstreetmap.org/4/8/5.png', 'Tessere mappa (riserva OSM)');
    try {
      const r = await fetch('https://overpass-api.de/api/interpreter', {
        method: 'POST', body: new URLSearchParams({ data: '[out:json];node(45.46,9.18,45.47,9.19);out 1;' }),
      });
      row('Oggetti mappa (Overpass)', r.ok ? 'ok' : 'warn', r.ok ? 'risponde' : `HTTP ${r.status}`);
    } catch { row('Oggetti mappa (Overpass)', 'bad', 'non raggiungibile'); }
  }

  async function testOther() {
    const kind = GL.face?.platform?.() || 'sconosciuto';
    const detail = native?.bioDetail ? native.bioDetail() : '';
    const words = { face: 'volto disponibile alle app', biometric: 'impronta o volto disponibili', credential: 'solo il codice del telefono', webauthn: 'volto o impronta via browser', none: 'nessuno sblocco disponibile alle app' };
    row('Sblocco biometrico', kind === 'none' ? 'warn' : 'ok', `${words[kind] || kind}${detail ? ' · ' + detail : ''}`);
    const p = GL.prefs.get();
    row('Accesso registrato', (p.lockBio || p.pinHash) ? 'ok' : 'warn',
      `${p.lockBio ? 'volto attivo' : 'volto non attivo'} · ${p.pinHash ? 'codice impostato' : 'nessun codice'}`);
    let ls = false;
    try { localStorage.setItem('gl-t', '1'); localStorage.removeItem('gl-t'); ls = true; } catch { /* blocked */ }
    row('Memoria locale', ls ? 'ok' : 'bad', ls ? 'cassaforte e impostazioni possono salvare' : 'bloccata: niente salvataggi');
    row('Modalità offline', native ? 'info' : ('serviceWorker' in navigator ? 'ok' : 'warn'),
      native ? 'non serve: i file sono dentro l\'app' : ('serviceWorker' in navigator ? 'attiva' : 'non supportata'));
  }

  async function run() {
    if (running) return;
    running = true;
    report.length = 0;
    $('#diag-out').replaceChildren();
    const btn = $('#diag-run');
    btn.disabled = true; btn.textContent = 'Test in corso…';
    const steps = [
      ['Ambiente', testEnv], ['Fotocamera', testCamera], ['Microfono', testMic],
      ['Posizione', testGps], ['Bussola', testCompass], ['Movimento', testAccel],
      ['Rete', testNetwork], ['Altro', testOther],
    ];
    for (const [name, fn] of steps) {
      $('#diag-phase').textContent = `Controllo: ${name}…`;
      try { await fn(); } catch (e) { row(name, 'bad', `errore interno: ${e.message}`); }
    }
    $('#diag-phase').textContent = 'Test completato';
    const bad = report.filter(r => r.includes('NON VA')).length;
    $('#diag-summary').textContent = bad ? `${bad} problemi trovati. Copia il referto e mandamelo.` : 'Tutto a posto su questo telefono.';
    $('#diag-summary').className = bad ? 'lock-msg' : 'center good';
    btn.disabled = false; btn.textContent = 'Ripeti i test';
    running = false;
    GL.sfx?.play(bad ? 'err' : 'ok');
    GL.app?.xp(4, 'diagnostica');
  }

  function init() {
    $('#diag-run').addEventListener('click', run);
    $('#diag-copy').addEventListener('click', () => copyText(
      `GHOSTLINK — referto diagnostica\n${new Date().toLocaleString('it-IT')}\n\n${report.join('\n')}`,
      'Referto copiato: incollalo in chat'));
    $('#diag-settings').addEventListener('click', () => GL.ui.openSettings());
  }

  GL.diag = { init };
})();
