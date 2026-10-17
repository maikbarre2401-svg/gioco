window.GL = window.GL || {};

(() => {
  'use strict';

  const ui = GL.ui || {};
  const { $, toast, log, haptic, fitCanvas } = ui;
  const D2R = Math.PI / 180, R2D = 180 / Math.PI;
  const norm360 = a => ((a % 360) + 360) % 360;
  const sind = a => Math.sin(a * D2R), cosd = a => Math.cos(a * D2R), tand = a => Math.tan(a * D2R);

  /* ===================== astronomy core ===================== */

  function julianDate(date) { return date.getTime() / 86400000 + 2440587.5; }

  // Local Apparent Sidereal Time (degrees) for a longitude (east positive).
  function lstDeg(jd, lonEast) {
    const d = jd - 2451545.0;
    const gmst = 280.46061837 + 360.98564736629 * d;
    return norm360(gmst + lonEast);
  }

  // Equatorial (RA/Dec deg) → horizontal (azimuth from North clockwise, altitude), both deg.
  function equatorialToHorizontal(ra, dec, lat, lst) {
    const H = norm360(lst - ra);
    const alt = Math.asin(sind(dec) * sind(lat) + cosd(dec) * cosd(lat) * cosd(H)) * R2D;
    // azimuth measured from South, positive to the West, then shift to North-based clockwise
    const az = Math.atan2(sind(H), cosd(H) * sind(lat) - tand(dec) * cosd(lat)) * R2D;
    return { az: norm360(az + 180), alt };
  }

  const obliquity = jd => 23.439291 - 0.0000003563 * (jd - 2451545.0);

  function eclipticToEquatorial(lon, lat, eps) {
    const ra = Math.atan2(sind(lon) * cosd(eps) - tand(lat) * sind(eps), cosd(lon)) * R2D;
    const dec = Math.asin(sind(lat) * cosd(eps) + cosd(lat) * sind(eps) * sind(lon)) * R2D;
    return { ra: norm360(ra), dec };
  }

  // Low-precision Sun (Meeus ch.25): returns RA/Dec deg and ecliptic longitude.
  function sunPos(jd) {
    const d = jd - 2451545.0;
    const L = norm360(280.460 + 0.9856474 * d);
    const g = norm360(357.528 + 0.9856003 * d);
    const lambda = L + 1.915 * sind(g) + 0.020 * sind(2 * g);
    const eps = obliquity(jd);
    const eq = eclipticToEquatorial(lambda, 0, eps);
    return { ...eq, lambda, mag: -26.7 };
  }

  // Low-precision Moon (Meeus ch.47 truncated): ~0.3° accuracy, enough to point at it.
  function moonPos(jd) {
    const d = jd - 2451545.0;
    const Lp = norm360(218.316 + 13.176396 * d);
    const M = norm360(134.963 + 13.064993 * d);
    const Mp = norm360(357.529 + 0.985600 * d);     // Sun mean anomaly
    const D = norm360(297.850 + 12.190749 * d);     // mean elongation
    const F = norm360(93.272 + 13.229350 * d);      // argument of latitude
    const lon = Lp + 6.289 * sind(M) + 1.274 * sind(2 * D - M) + 0.658 * sind(2 * D)
      + 0.214 * sind(2 * M) - 0.186 * sind(Mp) - 0.114 * sind(2 * F);
    const lat = 5.128 * sind(F) + 0.281 * sind(M + F) + 0.278 * sind(F - M)
      + 0.173 * sind(2 * D - F);
    const eps = obliquity(jd);
    const eq = eclipticToEquatorial(norm360(lon), lat, eps);
    // illuminated fraction from Sun-Moon elongation
    const elong = Math.acos(cosd(lon - sunPos(jd).lambda) * cosd(lat)) * R2D;
    const phase = (1 - cosd(elong)) / 2;
    return { ...eq, phase, elong, mag: -12.5 };
  }

  // Keplerian elements (Standish, J2000 + rate per century) for naked-eye planets and Earth.
  const ELEM = {
    Mercurio: [0.38709927, 0.20563593, 7.00497902, 252.25032350, 77.45779628, 48.33076593, 0.00000037, 0.00001906, -0.00594749, 149472.67411175, 0.16047689, -0.12534081, -0.4],
    Venere: [0.72333566, 0.00677672, 3.39467605, 181.97909950, 131.60246718, 76.67984255, 0.00000390, -0.00004107, -0.00078890, 58517.81538729, 0.00268329, -0.27769418, -4.4],
    Terra: [1.00000261, 0.01671123, -0.00001531, 100.46457166, 102.93768193, 0.0, 0.00000562, -0.00004392, -0.01294668, 35999.37244981, 0.32327364, 0.0, 0],
    Marte: [1.52371034, 0.09339410, 1.84969142, -4.55343205, -23.94362959, 49.55953891, 0.00001847, 0.00007882, -0.00813131, 19140.30268499, 0.44441088, -0.29257343, -1.5],
    Giove: [5.20288700, 0.04838624, 1.30439695, 34.39644051, 14.72847983, 100.47390909, -0.00011607, -0.00013253, -0.00183714, 3034.74612775, 0.21252668, 0.20469106, -2.2],
    Saturno: [9.53667594, 0.05386179, 2.48599187, 49.95424423, 92.59887831, 113.66242448, -0.00125060, -0.00050991, 0.00193609, 1222.49362201, -0.41897216, -0.28867794, 0.5],
  };

  function heliocentric(name, T) {
    const e0 = ELEM[name];
    const a = e0[0] + e0[6] * T, e = e0[1] + e0[7] * T, I = e0[2] + e0[8] * T;
    const L = e0[3] + e0[9] * T, peri = e0[4] + e0[10] * T, node = e0[5] + e0[11] * T;
    const w = peri - node;
    let M = norm360(L - peri); if (M > 180) M -= 360;
    // solve Kepler
    let E = M + (e * R2D) * sind(M);
    for (let i = 0; i < 8; i++) { const dE = (M - (E - (e * R2D) * sind(E))) / (1 - e * cosd(E)); E += dE; if (Math.abs(dE) < 1e-7) break; }
    const xp = a * (cosd(E) - e), yp = a * Math.sqrt(1 - e * e) * sind(E);
    const xecl = (cosd(w) * cosd(node) - sind(w) * sind(node) * cosd(I)) * xp + (-sind(w) * cosd(node) - cosd(w) * sind(node) * cosd(I)) * yp;
    const yecl = (cosd(w) * sind(node) + sind(w) * cosd(node) * cosd(I)) * xp + (-sind(w) * sind(node) + cosd(w) * cosd(node) * cosd(I)) * yp;
    const zecl = (sind(w) * sind(I)) * xp + (cosd(w) * sind(I)) * yp;
    return { x: xecl, y: yecl, z: zecl };
  }

  function planetPos(name, jd) {
    const T = (jd - 2451545.0) / 36525;
    const p = heliocentric(name, T), earth = heliocentric('Terra', T);
    const x = p.x - earth.x, y = p.y - earth.y, z = p.z - earth.z;
    const lon = norm360(Math.atan2(y, x) * R2D);
    const lat = Math.atan2(z, Math.hypot(x, y)) * R2D;
    const eq = eclipticToEquatorial(lon, lat, obliquity(jd));
    return { ...eq, mag: ELEM[name][12], dist: Math.hypot(x, y, z) };
  }

  function solarSystem(jd) {
    const out = [];
    const s = sunPos(jd); out.push({ id: 'sun', name: 'Sole', kind: 'sun', ...s });
    const m = moonPos(jd); out.push({ id: 'moon', name: 'Luna', kind: 'moon', ...m });
    for (const name of ['Mercurio', 'Venere', 'Marte', 'Giove', 'Saturno']) {
      out.push({ id: name.toLowerCase(), name, kind: 'planet', ...planetPos(name, jd) });
    }
    return out;
  }

  /* ===================== AR rendering ===================== */

  const state = {
    active: false, lat: null, lon: null, heading: null, pitch: 0, roll: 0,
    fov: 65, sky: [], raf: 0, orientEvt: null, watchId: null, stream: null,
    selected: null, hasOrient: false, manual: 0, lastHeading: 0,
  };
  const C = GL.ui ? GL.ui.COLORS : {};

  function buildSky() {
    const jd = julianDate(new Date());
    const lst = lstDeg(jd, state.lon ?? 12);
    const lat = state.lat ?? 42;
    const items = [];
    for (const st of GL.skydata.stars) {
      const h = equatorialToHorizontal(st.ra, st.dec, lat, lst);
      items.push({ ...st, kind: 'star', az: h.az, alt: h.alt });
    }
    for (const body of solarSystem(jd)) {
      const h = equatorialToHorizontal(body.ra, body.dec, lat, lst);
      items.push({ ...body, az: h.az, alt: h.alt });
    }
    const byId = Object.fromEntries(items.map(i => [i.id, i]));
    state.lines = GL.skydata.lines.map(([name, segs]) => [name, segs
      .map(([a, b]) => [byId[a], byId[b]]).filter(([a, b]) => a && b)]);
    state.sky = items;
    state.byId = byId;
  }

  // Project an (az,alt) point to screen using the phone's look direction (heading, pitch).
  // Gnomonic-ish projection around the view centre; returns null if behind the viewer.
  function project(az, alt, w, h) {
    const f = (0.5 * h) / tand(state.fov / 2);
    const dAz = ((az - state.heading + 540) % 360) - 180;   // -180..180
    const dAlt = alt - state.pitch;
    const x = dAz * D2R, y = dAlt * D2R;
    // simple spherical-to-plane; clamp field so only the forward hemisphere shows
    const cosc = Math.cos(y) * Math.cos(x);
    if (cosc < 0.12) return null;
    const px = w / 2 + f * (Math.cos(y) * Math.sin(x)) / cosc;
    const py = h / 2 - f * (Math.sin(y)) / cosc;
    return { x: px, y: py, cosc };
  }

  function starRadius(mag) { return Math.max(0.8, 3.4 - mag * 0.55); }
  function starColor(con, mag) {
    if (mag < 0.5) return '#cfe8ff';
    return '#dfefff';
  }

  let _skyLast = 0;
  function draw(t) {
    state.raf = requestAnimationFrame(draw);
    if (document.hidden || (t && t - _skyLast < 40)) return;   // ~25fps is smooth for a star field
    _skyLast = t || 0;
    const canvas = $('#sky-canvas');
    const { ctx, w, h } = fitCanvas(canvas);
    ctx.clearRect(0, 0, w, h);
    if (!state.stream) { ctx.fillStyle = '#02040a'; ctx.fillRect(0, 0, w, h); }

    // horizon band + cardinal marks
    const horizon = project(state.heading, 0, w, h);
    drawCardinals(ctx, w, h);

    // constellation lines
    ctx.strokeStyle = 'rgba(46,242,255,0.35)';
    ctx.lineWidth = 1;
    for (const [, segs] of state.lines) {
      for (const [a, b] of segs) {
        if (a.alt < -2 || b.alt < -2) continue;
        const pa = project(a.az, a.alt, w, h), pb = project(b.az, b.alt, w, h);
        if (!pa || !pb) continue;
        ctx.beginPath(); ctx.moveTo(pa.x, pa.y); ctx.lineTo(pb.x, pb.y); ctx.stroke();
      }
    }

    // stars
    for (const s of state.sky) {
      if (s.kind !== 'star') continue;
      s._sx = null;
      if (s.alt < -2) continue;
      const p = project(s.az, s.alt, w, h);
      if (!p) continue;
      const r = starRadius(s.mag);
      ctx.fillStyle = starColor(s.con, s.mag);
      ctx.globalAlpha = s.alt < 2 ? Math.max(0.2, (s.alt + 2) / 4) : 1;
      ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, Math.PI * 2); ctx.fill();
      if (s.mag < 1.6) {
        ctx.globalAlpha *= 0.4; ctx.beginPath(); ctx.arc(p.x, p.y, r + 2.5, 0, Math.PI * 2); ctx.fill();
        ctx.globalAlpha = s.alt < 2 ? Math.max(0.2, (s.alt + 2) / 4) : 1;
      }
      if (s.mag < 1.5) { ctx.fillStyle = 'rgba(223,239,255,0.8)'; ctx.font = '11px "JetBrains Mono", monospace'; ctx.fillText(s.name, p.x + r + 4, p.y + 3); }
      s._sx = p.x; s._sy = p.y; s._r = r;
    }
    ctx.globalAlpha = 1;

    // solar system bodies
    for (const b of state.sky) {
      if (b.kind === 'star') continue;
      b._sx = null;
      if (b.alt < -2) continue;
      const p = project(b.az, b.alt, w, h);
      if (!p) continue;
      drawBody(ctx, b, p);
      b._sx = p.x; b._sy = p.y; b._r = 14;
    }

    // crosshair + selected label
    drawReticle(ctx, w, h);
  }

  function drawBody(ctx, b, p) {
    if (b.kind === 'sun') {
      const g = ctx.createRadialGradient(p.x, p.y, 2, p.x, p.y, 22);
      g.addColorStop(0, '#fff6c8'); g.addColorStop(0.4, '#ffd24d'); g.addColorStop(1, 'rgba(255,176,32,0)');
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(p.x, p.y, 22, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#fff2b0'; ctx.beginPath(); ctx.arc(p.x, p.y, 10, 0, Math.PI * 2); ctx.fill();
    } else if (b.kind === 'moon') {
      ctx.fillStyle = '#20283a'; ctx.beginPath(); ctx.arc(p.x, p.y, 13, 0, Math.PI * 2); ctx.fill();
      ctx.save(); ctx.beginPath(); ctx.arc(p.x, p.y, 13, 0, Math.PI * 2); ctx.clip();
      ctx.fillStyle = '#e8eefc';
      const k = b.phase; // 0 new .. 1 full
      const off = (k - 0.5) * 2 * 13;
      ctx.beginPath(); ctx.arc(p.x + (b.elong < 180 ? off : -off) * 0 + 0, p.y, 13, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#20283a';
      ctx.beginPath(); ctx.ellipse(p.x + (1 - k) * 26 * (b.elong > 180 ? 1 : -1), p.y, 13, 13, 0, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
      ctx.strokeStyle = 'rgba(232,238,252,0.6)'; ctx.beginPath(); ctx.arc(p.x, p.y, 13, 0, Math.PI * 2); ctx.stroke();
    } else {
      const col = { Mercurio: '#c9b79c', Venere: '#fff0c0', Marte: '#ff6b4a', Giove: '#e8c89a', Saturno: '#ffe9b0' }[b.name] || '#fff';
      ctx.fillStyle = col;
      const r = Math.max(3, 6 - b.mag * 0.6);
      ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = 0.35; ctx.beginPath(); ctx.arc(p.x, p.y, r + 3, 0, Math.PI * 2); ctx.fill(); ctx.globalAlpha = 1;
    }
    ctx.fillStyle = '#2ef2ff'; ctx.font = '600 12px "JetBrains Mono", monospace';
    ctx.fillText(b.name, p.x + 16, p.y + 4);
  }

  function drawCardinals(ctx, w, h) {
    const dirs = [[0, 'N'], [45, 'NE'], [90, 'E'], [135, 'SE'], [180, 'S'], [225, 'SO'], [270, 'O'], [315, 'NO']];
    ctx.textAlign = 'center';
    for (const [az, label] of dirs) {
      const p = project(az, 0, w, h);
      if (!p) continue;
      ctx.strokeStyle = 'rgba(46,242,255,0.25)'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(p.x, p.y - 8); ctx.lineTo(p.x, p.y + 8); ctx.stroke();
      ctx.fillStyle = label.length === 1 ? '#ff2d75' : 'rgba(46,242,255,0.7)';
      ctx.font = `${label.length === 1 ? '700 15' : '600 11'}px "Chakra Petch", sans-serif`;
      ctx.fillText(label, p.x, p.y + 24);
    }
    ctx.textAlign = 'left';
  }

  function drawReticle(ctx, w, h) {
    ctx.strokeStyle = 'rgba(46,242,255,0.5)'; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(w / 2, h / 2, 16, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(w / 2 - 24, h / 2); ctx.lineTo(w / 2 - 18, h / 2);
    ctx.moveTo(w / 2 + 18, h / 2); ctx.lineTo(w / 2 + 24, h / 2);
    ctx.moveTo(w / 2, h / 2 - 24); ctx.lineTo(w / 2, h / 2 - 18);
    ctx.moveTo(w / 2, h / 2 + 18); ctx.lineTo(w / 2, h / 2 + 24); ctx.stroke();
  }

  /* ===================== orientation & lifecycle ===================== */

  function onOrient(e) {
    let heading = null;
    if (typeof e.webkitCompassHeading === 'number') heading = e.webkitCompassHeading;
    else if (e.absolute && e.alpha != null) heading = 360 - e.alpha;
    if (heading != null) { state.heading = norm360(heading + (screen.orientation?.angle || 0)); state.hasOrient = true; }
    if (e.beta != null) {
      // pitch: how far up/down the phone points (beta ~90 when upright pointing forward)
      state.pitch = Math.max(-90, Math.min(90, e.beta - 90));
      state.roll = e.gamma || 0;
    }
  }

  function onPos(p) {
    state.lat = p.coords.latitude; state.lon = p.coords.longitude;
    $('#sky-loc').textContent = `${state.lat.toFixed(2)}, ${state.lon.toFixed(2)}`;
    buildSky();
  }

  function hud() {
    $('#sky-head').textContent = state.heading == null ? '—' : `${Math.round(state.heading)}°`;
    $('#sky-pitch').textContent = `${Math.round(state.pitch)}°`;
    const up = state.sky.filter(s => s.alt > 0).length;
    $('#sky-count').textContent = up;
  }

  async function start() {
    if (state.active) { stop(); return; }
    try {
      if (typeof DeviceOrientationEvent?.requestPermission === 'function') {
        const r = await DeviceOrientationEvent.requestPermission();
        if (r !== 'granted') toast('Serve il permesso sensori per la bussola');
      }
    } catch {}
    // camera as background (optional)
    try {
      state.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
      const v = $('#sky-video'); v.srcObject = state.stream; await v.play(); v.hidden = false;
    } catch { state.stream = null; $('#sky-video').hidden = true; }

    state.orientEvt = 'ondeviceorientationabsolute' in window ? 'deviceorientationabsolute' : 'deviceorientation';
    window.addEventListener(state.orientEvt, onOrient);
    if ('geolocation' in navigator) state.watchId = navigator.geolocation.watchPosition(onPos, () => { buildSky(); }, { enableHighAccuracy: true, maximumAge: 10000, timeout: 15000 });

    state.active = true;
    if (state.heading == null) state.heading = 0;
    buildSky();
    $('#sky-start').textContent = 'Chiudi';
    $('#sky-start').classList.add('danger');
    GL.sfx?.play('nav');
    log?.('Cielo AR attivo', 'ok');
    GL.app?.xp(6, 'cielo');
    cancelAnimationFrame(state.raf); draw();
    state.hudTimer = setInterval(hud, 300);
    setTimeout(() => { if (state.active && !state.hasOrient) { $('#sky-manual').hidden = false; toast('Bussola non disponibile: usa le frecce per guardarti attorno', 4000); } }, 2500);
  }

  function stop() {
    cancelAnimationFrame(state.raf);
    clearInterval(state.hudTimer);
    if (state.orientEvt) window.removeEventListener(state.orientEvt, onOrient);
    if (state.watchId != null) navigator.geolocation.clearWatch(state.watchId);
    state.stream?.getTracks().forEach(t => t.stop());
    state.stream = null; state.active = false;
    $('#sky-video').hidden = true;
    $('#sky-start').textContent = 'Attiva Cielo AR';
    $('#sky-start').classList.remove('danger');
  }

  function tap(e) {
    if (!state.active) return;
    const canvas = $('#sky-canvas');
    const rect = canvas.getBoundingClientRect();
    const x = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
    const y = (e.touches ? e.touches[0].clientY : e.clientY) - rect.top;
    let best = null, bestD = 36 * 36;
    for (const s of state.sky) {
      if (s._sx == null) continue;
      const d = (s._sx - x) ** 2 + (s._sy - y) ** 2;
      if (d < bestD) { bestD = d; best = s; }
    }
    if (best) showInfo(best);
  }

  const CON_NAMES = { Ori: 'Orione', UMa: 'Orsa Maggiore', UMi: 'Orsa Minore', Cas: 'Cassiopea', Cru: 'Croce del Sud', Sco: 'Scorpione', Leo: 'Leone', Cyg: 'Cigno', Lyr: 'Lira', Aql: 'Aquila', Tau: 'Toro', Gem: 'Gemelli', CMa: 'Cane Maggiore', CMi: 'Cane Minore', Boo: 'Boote', Vir: 'Vergine', Aur: 'Auriga', Peg: 'Pegaso', And: 'Andromeda', Per: 'Perseo', Car: 'Carena', Cen: 'Centauro', Sgr: 'Sagittario', Oph: 'Ofiuco', Cet: 'Balena', Ari: 'Ariete', Hya: 'Idra', Gru: 'Gru', Pav: 'Pavone', PsA: 'Pesce Australe', CrB: 'Corona Boreale', Eri: 'Eridano' };

  function showInfo(obj) {
    GL.sfx?.play('lock'); haptic?.(12);
    const card = $('#sky-info'); card.hidden = false;
    $('#sky-info-name').textContent = obj.name || 'Oggetto';
    const rows = [];
    if (obj.kind === 'star') { rows.push(['Tipo', 'Stella']); rows.push(['Costellazione', CON_NAMES[obj.con] || obj.con]); }
    else if (obj.kind === 'planet') { rows.push(['Tipo', 'Pianeta']); rows.push(['Distanza', `${(obj.dist * 149.6).toFixed(0)} milioni di km`]); }
    else if (obj.kind === 'sun') rows.push(['Tipo', 'La nostra stella']);
    else if (obj.kind === 'moon') { rows.push(['Tipo', 'Satellite']); rows.push(['Fase', `${Math.round(obj.phase * 100)}% illuminata`]); }
    rows.push(['Luminosità', `magnitudine ${obj.mag.toFixed(1)}`]);
    rows.push(['Altezza', obj.alt < 0 ? `${obj.alt.toFixed(0)}° (sotto l'orizzonte)` : `${obj.alt.toFixed(0)}° sull'orizzonte`]);
    rows.push(['Direzione', `${Math.round(obj.az)}° ${azName(obj.az)}`]);
    $('#sky-info-rows').replaceChildren(...rows.map(([k, v]) => {
      const d = document.createElement('div'); d.className = 'kv';
      const s = document.createElement('span'); s.textContent = k; const b = document.createElement('b'); b.textContent = v;
      if (obj.alt < 0 && k === 'Altezza') b.className = 'warn';
      d.append(s, b); return d;
    }));
    GL.app?.xp(3, 'cielo');
  }
  function azName(az) { return ['Nord', 'Nord-Est', 'Est', 'Sud-Est', 'Sud', 'Sud-Ovest', 'Ovest', 'Nord-Ovest'][Math.round(az / 45) % 8]; }

  function init() {
    if (!$) return;
    $('#sky-start').addEventListener('click', start);
    $('#sky-canvas').addEventListener('pointerdown', tap);
    $('#sky-info-close').addEventListener('click', () => { $('#sky-info').hidden = true; });
    // manual look controls when no compass
    const nudge = (dh, dp) => { state.heading = norm360((state.heading ?? 0) + dh); state.pitch = Math.max(-80, Math.min(80, state.pitch + dp)); };
    document.querySelectorAll('[data-sky-nudge]').forEach(btn => btn.addEventListener('click', () => {
      const [dh, dp] = btn.dataset.skyNudge.split(',').map(Number); nudge(dh, dp); GL.sfx?.play('tap');
    }));
  }

  function leave() { stop(); }

  GL.sky = { init, leave };
  // test hooks (used by the node harness, harmless in the browser)
  GL.sky._astro = { julianDate, lstDeg, equatorialToHorizontal, sunPos, moonPos, planetPos, solarSystem, obliquity };
})();
