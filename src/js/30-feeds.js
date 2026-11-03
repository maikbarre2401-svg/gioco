'use strict';
/* ════════════════════════════════════════════════════════════════
   FEED DI DATI REALI
   Ogni feed: prova diretta → proxy CORS → (eventuale) fonte alternativa.
   Nessun dato viene inventato: se una fonte è giù lo stato lo dice.
═══════════════════════════════════════════════════════════════════ */
const S = {                       // stato condiviso dei dati
  ac: new Map(), acList: [], sats: [], satRecs: [], iss: null, quakes: [], eonet: [], fires: [],
  news: [], space: {}, user: Store.get('userLoc', null)
};

/* ═════════════ ADS-B ═════════════ */
const ADSB = (() => {
  const SRC = {
    'adsb.lol': { mil: 'https://api.adsb.lol/v2/mil', area: (a, o, r) => `https://api.adsb.lol/v2/point/${a}/${o}/${r}` },
    'airplanes.live': { mil: 'https://api.airplanes.live/v2/mil', area: (a, o, r) => `https://api.airplanes.live/v2/point/${a}/${o}/${r}` },
    'adsb.fi': { mil: 'https://opendata.adsb.fi/api/v2/mil', area: (a, o, r) => `https://opendata.adsb.fi/api/v2/lat/${a}/lon/${o}/dist/${r}` },
    'adsb.lol/ll': { mil: 'https://api.adsb.lol/v2/mil', area: (a, o, r) => `https://api.adsb.lol/v2/lat/${a}/lon/${o}/dist/${r}` }
  };
  const pref = { mil: Object.keys(SRC), area: Object.keys(SRC) };
  const used = { mil: '--', area: '--', global: '--' };
  let cycle = 0, lastGlobal = 0, lastUpdate = 0, filter = 'all', query = '';
  const TTL = { area: 120e3, mil: 150e3, global: 420e3 };
  const T = DATA.AC_TYPES;
  const exact = new Set(T.drone);
  const isT = (type, list) => list.some(p => type === p || (p.length >= 3 && type.startsWith(p)));

  function classify(ac) {
    const ty = ac.type, cs = ac.cs.toUpperCase();
    const milCs = /\d/.test(cs) && DATA.MIL_CALLSIGNS.some(p => cs.startsWith(p) && /^\d|^[A-Z]?\d/.test(cs.slice(p.length)));
    let c = 'civil';
    if (/^(SAM|EXEC)\d/.test(cs) || /^AF[12]$/.test(cs)) c = 'vip';
    else if (ac.cat === 'B6' || exact.has(ty)) c = 'drone';
    else if (isT(ty, T.isr) && (ac.mil || milCs || !['P3', 'E2'].includes(ty))) c = 'isr';
    else if (isT(ty, T.tanker)) c = 'tanker';
    else if (isT(ty, T.fighter) && (ac.mil || milCs || !['T38', 'L39', 'HAWK', 'F5'].includes(ty))) c = 'fighter';
    else if (ac.cat === 'A7' || isT(ty, T.helo)) c = 'helo';
    else if (isT(ty, T.transport) && (ac.mil || milCs)) c = 'transport';
    else if (ac.mil || milCs) c = 'mil';
    ac.cls = c;
    ac.isMil = ac.mil || milCs || ['fighter', 'tanker', 'isr', 'transport', 'drone', 'vip'].includes(c);
    ac.emerg = DATA.SQUAWK[ac.sq] || (ac.emergency && !/none|lifeguard/.test(ac.emergency) ? 'Emergenza: ' + ac.emergency : '');
    return c;
  }
  function fromReadsb(a, src, now) {
    if (a.lat == null || a.lon == null || !a.hex) return null;
    const ground = a.alt_baro === 'ground';
    const altFt = ground ? 0 : (+a.alt_baro || +a.alt_geom || 0);
    const age = +(a.seen_pos ?? a.seen ?? 0) || 0;
    return { hex: String(a.hex).toLowerCase().replace('~', ''), cs: (a.flight || '').trim(), reg: a.r || '', type: (a.t || '').toUpperCase(), desc: a.desc || '',
      op: a.ownOp || '', lat: +a.lat, lon: +a.lon, altFt, altM: altFt * 0.3048, gs: +a.gs || 0, trk: +(a.track ?? a.true_heading ?? a.mag_heading ?? 0) || 0,
      vr: +(a.baro_rate ?? a.geom_rate ?? 0) || 0, sq: a.squawk || '', emergency: a.emergency || '', cat: a.category || '', mil: !!((+a.dbFlags || 0) & 1),
      ground, t: now - age * 1000, src, ttl: TTL.area, year: a.year || '', country: '' };
  }
  function fromOpenSky(s, now) {
    if (s[5] == null || s[6] == null) return null;
    const altM = +(s[7] ?? s[13] ?? 0) || 0;
    return { hex: String(s[0]).toLowerCase(), cs: (s[1] || '').trim(), reg: '', type: '', desc: '', op: '', lat: +s[6], lon: +s[5], altFt: altM * 3.28084, altM,
      gs: (+s[9] || 0) * 1.94384, trk: +s[10] || 0, vr: (+s[11] || 0) * 196.85, sq: s[14] || '', emergency: '', cat: '', mil: false, ground: !!s[8],
      t: (s[3] ? s[3] * 1000 : now), src: 'OpenSky', ttl: TTL.global, country: s[2] || '' };
  }
  function merge(list, ttl) {
    const now = Date.now();
    for (const a of list) {
      if (!a || a.ground || a.altFt < 50) continue;
      const old = S.ac.get(a.hex);
      if (old && old.t > a.t + 1000) continue;
      a.ttl = ttl;
      if (old) {
        // conserva info più ricche (tipo, reg) se la nuova fonte non le ha
        for (const k of ['type', 'reg', 'desc', 'op', 'country', 'year', 'cat']) if (!a[k] && old[k]) a[k] = old[k];
        a.mil = a.mil || old.mil; a.hist = old.hist || [];
        const last = a.hist.at(-1);
        if (!last || Geo.dist(last[0], last[1], a.lat, a.lon) > 1.5) { a.hist.push([a.lat, a.lon, a.altM]); if (a.hist.length > 80) a.hist.shift(); }
      } else a.hist = [[a.lat, a.lon, a.altM]];
      classify(a);
      S.ac.set(a.hex, a);
    }
    for (const [k, a] of S.ac) if (now - a.t > a.ttl) S.ac.delete(k);
  }
  async function trySources(kind, urlFn) {
    let lastErr;
    for (const name of pref[kind]) {
      try {
        const r = await Net.get(urlFn(SRC[name]), { timeout: 12000, ptimeout: 25000, validate: d => d && Array.isArray(d.ac ?? d.aircraft) });
        // sposta in testa la fonte funzionante
        pref[kind] = [name, ...pref[kind].filter(n => n !== name)];
        used[kind] = name + (r.via !== 'diretto' ? ' (' + r.via + ')' : '');
        return r.data.ac ?? r.data.aircraft;
      } catch (e) { lastErr = e; }
    }
    throw lastErr || new Error('nessuna fonte');
  }
  function openSkyBudget(cost) {
    const day = new Date().toISOString().slice(0, 10);
    const b = Store.get('osky', { day, credits: 0 });
    if (b.day !== day) { b.day = day; b.credits = 0; }
    if (b.credits + cost > 380) return false;
    b.credits += cost; Store.set('osky', b); return true;
  }
  async function fetchOpenSky(bbox) {
    const cost = bbox ? 1 : 4;
    if (!openSkyBudget(cost)) throw new Error('quota giornaliera OpenSky esaurita');
    const q = bbox ? `?lamin=${bbox[0]}&lomin=${bbox[1]}&lamax=${bbox[2]}&lomax=${bbox[3]}` : '';
    const r = await Net.get('https://opensky-network.org/api/states/all' + q, { timeout: 25000, ptimeout: 40000, validate: d => d && 'states' in d });
    used.global = 'OpenSky' + (r.via !== 'diretto' ? ' (' + r.via + ')' : '');
    const now = Date.now();
    return (r.data.states || []).map(s => fromOpenSky(s, now));
  }
  async function fetch() {
    cycle++;
    const v = MapCtl.getView();
    const now = Date.now(), jobs = [], errs = [];
    if (cycle % 3 === 1) jobs.push(trySources('mil', s => s.mil).then(l => merge(l.map(a => fromReadsb(a, 'mil', now)), TTL.mil)).catch(e => errs.push('mil: ' + e.message)));
    const regional = v && v.centerOnGlobe && v.alt < 5e6;
    if (regional) {
      const r = Math.round(clamp(v.alt / 1852 * 0.9, 40, 250));
      const la = v.lat.toFixed(2), lo = v.lon.toFixed(2);
      jobs.push(trySources('area', s => s.area(la, lo, r)).then(l => merge(l.map(a => fromReadsb(a, 'area', now)), TTL.area))
        .catch(async e => {
          errs.push('area: ' + e.message);
          const d = r / 60; // gradi approssimati
          try { merge(await fetchOpenSky([(v.lat - d).toFixed(2), (v.lon - d * 1.5).toFixed(2), (v.lat + d).toFixed(2), (v.lon + d * 1.5).toFixed(2)]), TTL.area); } catch (e2) { errs.push('opensky: ' + e2.message); }
        }));
    }
    if ((!regional || cycle === 1) && now - lastGlobal > 150e3) {
      lastGlobal = now;
      jobs.push(fetchOpenSky(null).then(l => merge(l, TTL.global)).catch(e => errs.push('globale: ' + e.message)));
    }
    await Promise.all(jobs);
    if (S.ac.size) { lastUpdate = Date.now(); publish(); Health.ok('adsb', { items: S.ac.size, via: [used.area, used.mil, used.global].filter(s => s !== '--').join(' + '), msg: errs.join(' · ') }); }
    else { publish(); Health.fail('adsb', errs.join(' · ') || 'nessun dato'); }
  }
  const PRIO = { vip: 0, isr: 1, fighter: 2, tanker: 3, drone: 4, transport: 5, mil: 6, helo: 7, civil: 9 };
  function publish() {
    const list = [...S.ac.values()].sort((a, b) => (b.emerg ? 1 : 0) - (a.emerg ? 1 : 0) || PRIO[a.cls] - PRIO[b.cls]);
    S.acList = list;
    MapCtl.render('aircraft', list);
    MapCtl.setCount('adsb', list.length);
    Bus.emit('adsb', list);
  }
  function filtered() {
    const q = query.trim().toUpperCase();
    return S.acList.filter(a => {
      if (filter === 'mil' && !a.isMil) return false;
      if (filter === 'emerg' && !a.emerg) return false;
      if (!['all', 'mil', 'emerg'].includes(filter) && a.cls !== filter) return false;
      if (q && !(a.cs.toUpperCase().includes(q) || a.hex.toUpperCase().includes(q) || a.type.includes(q) || a.reg.toUpperCase().includes(q))) return false;
      return true;
    });
  }
  // dettagli extra on demand (rotta, foto)
  async function route(cs) {
    if (!cs || cs.length < 3) return null;
    try {
      const r = await Net.get(`https://api.adsbdb.com/v0/callsign/${encodeURIComponent(cs.toUpperCase())}`, { timeout: 7000 });
      const f = r.data?.response?.flightroute; if (!f) return null;
      return { from: f.origin?.municipality || f.origin?.name, fromC: f.origin?.iata_code || f.origin?.icao_code, to: f.destination?.municipality || f.destination?.name, toC: f.destination?.iata_code || f.destination?.icao_code, airline: f.airline?.name, dest: f.destination };
    } catch { return null; }
  }
  async function info(hex) {
    const out = {};
    try {
      const r = await Net.get(`https://api.adsbdb.com/v0/aircraft/${hex}`, { timeout: 7000 });
      const a = r.data?.response?.aircraft;
      if (a) Object.assign(out, { model: [a.manufacturer, a.type].filter(Boolean).join(' '), owner: a.registered_owner, ownerCountry: a.registered_owner_country_name, reg: a.registration, photo: a.url_photo_thumbnail });
    } catch {}
    if (!out.photo) try {
      const r = await Net.get(`https://api.planespotters.net/pub/photos/hex/${hex}`, { timeout: 7000 });
      const p = r.data?.photos?.[0]; if (p) { out.photo = p.thumbnail_large?.src || p.thumbnail?.src; out.photoBy = p.photographer; out.photoLink = p.link; }
    } catch {}
    return out;
  }
  return {
    fetch, classify, route, info, filtered,
    get lastUpdate() { return lastUpdate; }, get used() { return used; },
    setFilter(f) { filter = f; Bus.emit('adsb:filter'); }, setQuery(q) { query = q; Bus.emit('adsb:filter'); }, get filter() { return filter; },
    find(q) { q = q.toUpperCase().trim(); return S.acList.find(a => a.cs.toUpperCase() === q || a.hex.toUpperCase() === q || a.reg.toUpperCase() === q) || S.acList.find(a => a.cs.toUpperCase().startsWith(q)); }
  };
})();

/* ═════════════ SATELLITI (CelesTrak + SGP4) ═════════════ */
const Sats = (() => {
  const groupOn = Object.fromEntries(DATA.SAT_GROUPS.map(g => [g.id, (Store.get('satGroups') || {})[g.id] ?? g.on]));
  const loaded = new Set();
  const SPECIAL = { 25544: 'ISS', 48274: 'TIANGONG', 20580: 'HUBBLE' };
  let tickT = null, lastPub = [];
  function parseTLE(txt, g) {
    const L = txt.split(/\r?\n/).map(s => s.trimEnd()).filter(Boolean), out = [];
    for (let i = 0; i < L.length - 2; i++) {
      if (L[i + 1].startsWith('1 ') && L[i + 2].startsWith('2 ')) {
        try {
          const rec = satellite.twoline2satrec(L[i + 1], L[i + 2]);
          if (rec.error) continue;
          const id = L[i + 1].slice(2, 7).trim();
          out.push({ id, name: L[i].replace(/^0 /, '').trim(), group: g.id, col: g.col, rec, period: (2 * Math.PI) / rec.no, special: !!SPECIAL[+id] });
        } catch {}
        i += 2;
      }
    }
    return out;
  }
  async function loadGroup(g) {
    const key = 'tle.' + g.id, cached = Store.get(key);
    let txt = null, via = 'cache';
    if (cached && Date.now() - cached.t < 8 * 3600e3) txt = cached.txt;
    else {
      try {
        const r = await Net.get(`https://celestrak.org/NORAD/elements/gp.php?GROUP=${g.id}&FORMAT=tle`, { type: 'text', timeout: 20000, validate: t => /^1 \d/m.test(t) });
        txt = r.data; via = r.via;
        if (txt.length < 1.5e6) Store.set(key, { t: Date.now(), txt });
      } catch (e) { if (cached) { txt = cached.txt; via = 'cache scaduta'; } else throw e; }
    }
    const recs = parseTLE(txt, g);
    const have = new Set(S.satRecs.map(r => r.id));
    recs.forEach(r => { if (!have.has(r.id)) S.satRecs.push(r); });
    loaded.add(g.id);
    return { n: recs.length, via };
  }
  async function loadAll() {
    if (!window.satellite) { try { await loadScript('https://cdn.jsdelivr.net/npm/satellite.js@5.0.0/dist/satellite.min.js'); } catch (e) { Health.fail('sats', 'satellite.js non caricato'); return; } }
    const groups = DATA.SAT_GROUPS.filter(g => groupOn[g.id] && !loaded.has(g.id));
    const vias = new Set(), errs = [];
    for (const g of groups) { try { const r = await loadGroup(g); vias.add(r.via); } catch (e) { errs.push(g.label + ': ' + e.message); } }
    if (S.satRecs.length) Health.ok('sats', { items: S.satRecs.length, via: 'CelesTrak (' + [...vias].join(', ') + ')', msg: errs.join(' · ') });
    else Health.fail('sats', errs.join(' · ') || 'nessun TLE');
    start();
  }
  function posAt(r, date) {
    const pv = satellite.propagate(r.rec, date); if (!pv || !pv.position) return null;
    const gm = satellite.gstime(date), ecf = satellite.eciToEcf(pv.position, gm), gd = satellite.eciToGeodetic(pv.position, gm);
    const v = pv.velocity ? Math.hypot(pv.velocity.x, pv.velocity.y, pv.velocity.z) : 0;
    return { x: ecf.x, y: ecf.y, z: ecf.z, lat: satellite.degreesLat(gd.latitude), lon: satellite.degreesLong(gd.longitude), altKm: gd.height, vel: v };
  }
  function tick() {
    const now = new Date(), out = [];
    for (const r of S.satRecs) {
      const p = posAt(r, now); if (!p || isNaN(p.x)) continue;
      out.push(Object.assign(p, { id: r.id, name: r.name, group: r.group, col: r.col, special: r.special, show: groupOn[r.group] !== false }));
    }
    S.sats = out; lastPub = out;
    MapCtl.render('sats', out);
    MapCtl.setCount('sats', out.filter(s => s.show).length);
    Bus.emit('sats', out);
  }
  function start() { clearInterval(tickT); tick(); tickT = setInterval(tick, S.satRecs.length > 2500 ? 2000 : 1000); }
  function orbit(id) {
    const r = S.satRecs.find(x => x.id === id); if (!r) return null;
    const P = r.period, now = Date.now(), pts = [], ground = [];
    const N = 180;
    for (let i = 0; i <= N; i++) {
      const t = new Date(now + (i / N - 0.5) * P * 60000), p = posAt(r, t); if (!p) continue;
      pts.push([p.x, p.y, p.z]); ground.push([p.lat, p.lon]);
    }
    return { orbit: pts, ground };
  }
  function sunlit(p, date) {   // ombra cilindrica della Terra
    const s = Geo.sun(date), sl = Geo.rad(s.lat), so = Geo.rad(s.lon);
    const sx = Math.cos(sl) * Math.cos(so), sy = Math.cos(sl) * Math.sin(so), sz = Math.sin(sl);
    const dot = p.x * sx + p.y * sy + p.z * sz;
    if (dot > 0) return true;
    const px = p.x - dot * sx, py = p.y - dot * sy, pz = p.z - dot * sz;
    return Math.hypot(px, py, pz) > 6371;
  }
  function passes(id, obs, hours = 24, minEl = 10) {
    const r = S.satRecs.find(x => x.id === id); if (!r || !window.satellite) return [];
    const og = { latitude: Geo.rad(obs.lat), longitude: Geo.rad(obs.lon), height: (obs.h || 0) / 1000 };
    const out = []; let cur = null; const step = 20000, t0 = Date.now();
    for (let t = t0; t < t0 + hours * 3600e3; t += step) {
      const d = new Date(t), pv = satellite.propagate(r.rec, d); if (!pv.position) continue;
      const ecf = satellite.eciToEcf(pv.position, satellite.gstime(d));
      const la = satellite.ecfToLookAngles(og, ecf), el = Geo.deg(la.elevation), az = (Geo.deg(la.azimuth) + 360) % 360;
      if (el >= minEl) {
        if (!cur) cur = { start: t, azStart: az, maxEl: el, tMax: t, lit: false };
        if (el > cur.maxEl) { cur.maxEl = el; cur.tMax = t; }
        if (!cur.lit && sunlit(ecf, d)) cur.lit = true;
        cur.end = t; cur.azEnd = az;
      } else if (cur) { cur.dark = Geo.sunElev(obs.lat, obs.lon, new Date(cur.tMax)) < -6; cur.visible = cur.dark && cur.lit; out.push(cur); cur = null; if (out.length >= 5) break; }
    }
    return out;
  }
  return {
    loadAll, orbit, passes, posAt,
    get groupOn() { return groupOn; },
    setGroup(id, on) {
      groupOn[id] = on; Store.set('satGroups', groupOn);
      if (on && !loaded.has(id)) loadAll(); else tick();
    },
    find(q) { q = q.toUpperCase().trim(); return S.sats.find(s => s.id === q) || S.sats.find(s => s.name.toUpperCase() === q) || S.sats.find(s => s.name.toUpperCase().includes(q)); },
    get(id) { return lastPub.find(s => s.id === id); },
    rec(id) { return S.satRecs.find(r => r.id === id); }
  };
})();

/* ═════════════ ISS telemetria ═════════════ */
async function fetchISS() {
  try {
    const r = await Net.get('https://api.wheretheiss.at/v1/satellites/25544', { timeout: 8000, validate: d => d && isFinite(d.latitude) });
    const d = r.data;
    S.iss = { lat: d.latitude, lon: d.longitude, alt: d.altitude, vel: d.velocity, vis: d.visibility, src: 'wheretheiss.at' };
    Health.ok('iss', { via: 'wheretheiss.at' + (r.via !== 'diretto' ? ' · ' + r.via : '') });
  } catch (e) {
    const p = Sats.get('25544');
    if (p) { S.iss = { lat: p.lat, lon: p.lon, alt: p.altKm, vel: p.vel * 3600, vis: null, src: 'calcolato da TLE' }; Health.ok('iss', { via: 'calcolato da TLE (SGP4)', msg: 'API offline' }); }
    else Health.fail('iss', e);
  }
  if (S.iss) Bus.emit('iss', S.iss);
}

/* ═════════════ TERREMOTI USGS ═════════════ */
const Quakes = (() => {
  const seen = new Set(); let first = true;
  async function fetch() {
    const feed = $('eq-feed')?.value || 'all_day';
    try {
      const r = await Net.get(`https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/${feed}.geojson`, { timeout: 15000, validate: d => d && Array.isArray(d.features) });
      const list = r.data.features.filter(f => f.geometry && f.properties.mag != null).map(f => ({
        id: f.id, mag: +f.properties.mag, place: f.properties.place || '—', time: f.properties.time, lat: f.geometry.coordinates[1], lon: f.geometry.coordinates[0],
        depth: f.geometry.coordinates[2], tsunami: f.properties.tsunami === 1, url: f.properties.url, alert: f.properties.alert, felt: f.properties.felt, sig: f.properties.sig, type: f.properties.type
      })).sort((a, b) => b.time - a.time);
      S.quakes = list;
      MapCtl.render('quakes', list.filter(q => q.mag >= 2.5 || list.length < 400));
      MapCtl.setCount('quakes', list.length);
      Health.ok('quakes', { items: list.length, via: 'USGS ' + feed + (r.via !== 'diretto' ? ' · ' + r.via : '') });
      for (const q of list) {
        if (seen.has(q.id)) continue; seen.add(q.id);
        const fresh = Date.now() - q.time < (first ? 2 : 6) * 3600e3;
        if (fresh && (q.mag >= 6 || (q.tsunami && q.mag >= 5) || q.alert === 'red' || q.alert === 'orange'))
          Intel.alert({ key: 'eq' + q.id, level: q.mag >= 6.5 || q.alert === 'red' ? 'war' : 'orn', icon: '🌍', title: `Terremoto M${q.mag.toFixed(1)}`, text: `${q.place}${q.tsunami ? ' · ⚠ possibile tsunami' : ''} · prof. ${Math.round(q.depth)} km`, lat: q.lat, lon: q.lon, ref: { kind: 'eq', id: q.id }, speak: `Terremoto di magnitudo ${q.mag.toFixed(1).replace('.', ' virgola ')}, ${q.place}.` });
      }
      first = false;
      Bus.emit('quakes', list);
    } catch (e) { Health.fail('quakes', e); }
  }
  return { fetch, get: id => S.quakes.find(q => q.id === id) };
})();

/* ═════════════ NASA EONET + FIRMS ═════════════ */
async function fetchEONET() {
  try {
    const r = await Net.get('https://eonet.gsfc.nasa.gov/api/v3/events?status=open&days=30&limit=400', { timeout: 20000, validate: d => d && Array.isArray(d.events) });
    const list = [];
    for (const ev of r.data.events) {
      const g = ev.geometry?.at(-1); if (!g) continue;
      let lat, lon;
      if (g.type === 'Point') [lon, lat] = g.coordinates;
      else if (g.type === 'Polygon') { const ring = g.coordinates[0]; lon = ring.reduce((s, p) => s + p[0], 0) / ring.length; lat = ring.reduce((s, p) => s + p[1], 0) / ring.length; }
      if (!isFinite(lat) || !isFinite(lon)) continue;
      list.push({ id: ev.id, title: ev.title, cat: ev.categories?.[0]?.id || 'manmade', catTitle: ev.categories?.[0]?.title || '', lat, lon, date: Date.parse(g.date) || 0,
        mag: g.magnitudeValue ? `${g.magnitudeValue} ${g.magnitudeUnit || ''}` : '', link: ev.sources?.[0]?.url || ev.link });
    }
    S.eonet = list.sort((a, b) => b.date - a.date);
    MapCtl.render('eonet', S.eonet); MapCtl.setCount('eonet', S.eonet.length);
    Health.ok('eonet', { items: list.length, via: 'NASA EONET' + (r.via !== 'diretto' ? ' · ' + r.via : '') });
    Bus.emit('eonet', S.eonet);
  } catch (e) { Health.fail('eonet', e); }
}
async function fetchFIRMS() {
  const key = (Settings.get('firmsKey') || '').trim();
  if (!key) { Health.set('firms', 'key', 'inserisci la MAP_KEY in ⚙'); MapCtl.setCount('fires', null); return; }
  for (const src of ['VIIRS_NOAA20_NRT', 'VIIRS_SNPP_NRT', 'MODIS_NRT']) {
    try {
      const r = await Net.get(`https://firms.modaps.eosdis.nasa.gov/api/area/csv/${encodeURIComponent(key)}/${src}/world/1`, { type: 'text', timeout: 40000, validate: t => /latitude/i.test(t.slice(0, 200)) });
      const lines = r.data.trim().split('\n'), hd = lines[0].split(',');
      const iLa = hd.indexOf('latitude'), iLo = hd.indexOf('longitude'), iF = hd.indexOf('frp'), iC = hd.indexOf('confidence'), iD = hd.indexOf('acq_date'), iT = hd.indexOf('acq_time');
      const pts = [];
      for (let i = 1; i < lines.length; i++) {
        const c = lines[i].split(','); const lat = +c[iLa], lon = +c[iLo]; if (!isFinite(lat) || !isFinite(lon)) continue;
        pts.push({ id: String(i), lat, lon, frp: +c[iF] || 0, conf: c[iC], when: (c[iD] || '') + ' ' + (c[iT] || '') });
      }
      pts.sort((a, b) => b.frp - a.frp);
      S.fires = pts.slice(0, 20000);
      MapCtl.render('fires', S.fires); MapCtl.setCount('fires', pts.length);
      Health.ok('firms', { items: pts.length, via: 'FIRMS ' + src + (r.via !== 'diretto' ? ' · ' + r.via : '') });
      return;
    } catch (e) { Health.fail('firms', e); }
  }
}

/* ═════════════ METEO SPAZIALE NOAA SWPC ═════════════ */
const Space = (() => {
  const B = 'https://services.swpc.noaa.gov/';
  // SWPC sta passando (SCN 26-21, 2026) da "prima riga = intestazioni" a oggetti JSON: gestiamo entrambi
  const objs = d => {
    if (!Array.isArray(d) || !d.length) return [];
    if (Array.isArray(d[0])) { const hd = d[0].map(x => String(x).toLowerCase()); return d.slice(1).map(r => Object.fromEntries(hd.map((k, i) => [k, r[i]]))); }
    return d.map(o => Object.fromEntries(Object.entries(o || {}).map(([k, v]) => [k.toLowerCase(), v])));
  };
  const val = (o, ...ks) => { for (const k of ks) { const v = o?.[k]; if (v != null && v !== '' && isFinite(+v)) return +v; } return null; };
  const flare = f => { if (!(f > 0)) return '--'; const cl = f < 1e-7 ? ['A', 1e-8] : f < 1e-6 ? ['B', 1e-7] : f < 1e-5 ? ['C', 1e-6] : f < 1e-4 ? ['M', 1e-5] : ['X', 1e-4]; return cl[0] + (f / cl[1]).toFixed(1); };
  async function fetch() {
    const get = u => Net.get(B + u, { timeout: 12000 }).then(r => r.data);
    const [kp1, kp3, pl, mg, sc, xr] = await Promise.allSettled([
      get('json/planetary_k_index_1m.json'), get('products/noaa-planetary-k-index.json'), get('products/solar-wind/plasma-5-minute.json'),
      get('products/solar-wind/mag-5-minute.json'), get('products/noaa-scales.json'), get('json/goes/primary/xrays-6-hour.json')]);
    const sp = S.space; let ok = 0;
    if (kp1.status === 'fulfilled') { const v = val(objs(kp1.value).at(-1), 'estimated_kp', 'kp_index', 'kp'); if (v != null) { sp.kp = v; ok++; } }
    if (kp3.status === 'fulfilled') { const h = objs(kp3.value).map(r => val(r, 'kp', 'kp_index', 'estimated_kp')).filter(v => v != null).slice(-24); if (h.length) { sp.kpHist = h; ok++; if (sp.kp == null) sp.kp = h.at(-1); } }
    if (pl.status === 'fulfilled') { const r = objs(pl.value).filter(x => val(x, 'speed') != null).at(-1); if (r) { sp.wind = val(r, 'speed'); sp.dens = val(r, 'density'); ok++; } }
    if (mg.status === 'fulfilled') { const r = objs(mg.value).filter(x => val(x, 'bz_gsm', 'bz') != null).at(-1); if (r) { sp.bz = val(r, 'bz_gsm', 'bz'); sp.bt = val(r, 'bt'); ok++; } }
    if (sc.status === 'fulfilled') { const n = sc.value?.['0'] || (Array.isArray(sc.value) ? sc.value[0] : null); if (n) { sp.scales = { R: n.R?.Scale ?? 0, S: n.S?.Scale ?? 0, G: n.G?.Scale ?? 0 }; ok++; } }
    if (xr.status === 'fulfilled') { const l = objs(xr.value).filter(x => String(x.energy || '').startsWith('0.1-0.8') && val(x, 'flux') > 0).at(-1); if (l) { sp.xflux = val(l, 'flux'); sp.flare = flare(sp.xflux); ok++; } }
    if (ok) Health.ok('space', { items: ok, via: 'NOAA SWPC' }); else Health.fail('space', 'NOAA SWPC non raggiungibile');
    if (sp.kp >= 7) Intel.alert({ key: 'kp' + new Date().toISOString().slice(0, 13), level: 'orn', icon: '☀', title: `Tempesta geomagnetica Kp ${sp.kp.toFixed(1)}`, text: 'Possibili disturbi a GPS, radio HF e reti elettriche; aurore a basse latitudini.', speak: `Tempesta geomagnetica in corso, indice K p ${Math.round(sp.kp)}.` });
    if (/^X/.test(sp.flare || '')) Intel.alert({ key: 'xf' + new Date().toISOString().slice(0, 13), level: 'orn', icon: '☀', title: `Brillamento solare classe ${sp.flare}`, text: 'Possibile blackout radio sul lato diurno.' });
    Bus.emit('space', sp);
  }
  async function aurora() {
    try {
      const r = await Net.get(B + 'json/ovation_aurora_latest.json', { timeout: 20000, validate: d => d && Array.isArray(d.coordinates) });
      const g = r.data.coordinates; let mx = 0; for (const c of g) if (c[2] > mx) mx = c[2];
      S.space.auroraMax = mx; S.space.auroraTime = r.data['Forecast Time'];
      MapCtl.render('aurora', g.filter(c => c[2] >= 8)); MapCtl.setCount('aurora', g.filter(c => c[2] >= 8).length);
      Health.ok('aurora', { via: 'NOAA OVATION', items: g.length });
      Bus.emit('space', S.space);
    } catch (e) { Health.fail('aurora', e); }
  }
  return { fetch, aurora };
})();

/* ═════════════ RADAR RAINVIEWER ═════════════ */
async function fetchRadar() {
  if (!MapCtl.isOn('radar')) { Health.set('radar', 'off', 'layer spento'); return; }
  try {
    const r = await Net.get('https://api.rainviewer.com/public/weather-maps.json', { timeout: 10000, validate: d => d && d.radar });
    const f = r.data.radar.past?.at(-1); if (!f) throw new Error('nessun frame');
    MapCtl.render('radar', `${r.data.host}${f.path}/256/{z}/{x}/{y}/2/1_1.png`);
    Health.ok('radar', { via: 'RainViewer', msg: 'frame ' + Fmt.utc(f.time * 1000) + ' UTC' });
  } catch (e) { Health.fail('radar', e); }
}

/* ═════════════ NOTIZIE (RSS + GDELT) geolocalizzate ═════════════ */
const News = (() => {
  const items = new Map();
  const CITY = DATA.PLACES_CITY.map(([n, lat, lon, label, hs]) => ({ rx: new RegExp('\\b(?:' + n + ')\\b', 'i'), lat, lon, label, hs }));
  const COUNTRY = DATA.PLACES_COUNTRY.map(([n, lat, lon, label, hs]) => ({ rx: new RegExp('\\b(?:' + n + ')', 'i'), lat, lon, label, hs }));
  let filterA = 'all', q = '', rr = 0;
  const feedState = {};
  function geocode(t) { for (const p of CITY) if (p.rx.test(t)) return p; for (const p of COUNTRY) if (p.rx.test(t)) return p; return null; }
  function hash(s) { let x = 2166136261; for (let i = 0; i < s.length; i++) { x ^= s.charCodeAt(i); x = Math.imul(x, 16777619); } return (x >>> 0).toString(36); }
  function strip(s) { return String(s || '').replace(/<!\[CDATA\[|\]\]>/g, '').replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#0?39;|&apos;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/\s+/g, ' ').trim(); }
  function enrich(it) {
    let sev = 0; const cats = new Set();
    for (const [rx, w, c] of DATA.SEVERITY) if (rx.test(it.title)) { sev += w * (sev ? 0.45 : 1); cats.add(c); }
    it.sev = Math.min(1, sev); it.cats = [...cats]; it.hot = it.sev >= 0.5;
    it.place = geocode(it.title) || (it.desc ? geocode(it.desc.slice(0, 160)) : null);
    it.hs = DATA.HOTSPOTS.filter(h => h.rx.test(it.title) || (it.place && it.place.hs === h.id)).map(h => h.id);
    const hh = parseInt(hash(it.id), 36); it.jlat = ((hh % 1000) / 1000 - 0.5) * 0.5; it.jlon = (((hh >> 10) % 1000) / 1000 - 0.5) * 0.5;
    return it;
  }
  function add(raw, f) {
    const title = strip(raw.title); if (title.length < 12) return;
    const key = title.toLowerCase().replace(/[^a-z0-9à-ü]+/g, '').slice(0, 70);
    const id = hash(key);
    if (items.has(id)) return;
    const date = Date.parse(raw.date) || Date.now();
    if (Date.now() - date > 48 * 3600e3) return;
    items.set(id, enrich({ id, title, link: raw.link, desc: strip(raw.desc).slice(0, 260), src: f.src, flag: f.flag, cc: f.cc, date }));
  }
  function parseXML(xml) {
    const doc = new DOMParser().parseFromString(xml, 'text/xml');
    const nodes = [...doc.querySelectorAll('item, entry')].slice(0, 30);
    return nodes.map(el => ({
      title: el.querySelector('title')?.textContent || '',
      link: (el.querySelector('link')?.getAttribute('href') || el.querySelector('link')?.textContent || '').trim(),
      date: el.querySelector('pubDate, published, updated, date')?.textContent || '',
      desc: el.querySelector('description, summary, content')?.textContent || ''
    }));
  }
  async function fetchFeed(f) {
    try {
      const r = await Net.get(f.url, { type: 'text', timeout: 12000, via: 'auto', validate: t => /<(item|entry)[\s>]/i.test(t) });
      parseXML(r.data).forEach(x => add(x, f)); feedState[f.id] = { ok: true, via: r.via, t: Date.now() };
      return true;
    } catch (e) {
      try {
        const r = await Net.get(`https://api.rss2json.com/v1/api.json?rss_url=${encodeURIComponent(f.url)}`, { timeout: 12000, noProxy: true, validate: d => d && d.status === 'ok' });
        r.data.items.forEach(x => add({ title: x.title, link: x.link, date: x.pubDate, desc: x.description }, f)); feedState[f.id] = { ok: true, via: 'rss2json', t: Date.now() };
        return true;
      } catch (e2) { feedState[f.id] = { ok: false, err: e.message }; return false; }
    }
  }
  async function fetchGDELT() {
    try {
      const qy = '(airstrike OR missile OR drone OR shelling OR troops OR explosion OR navy) sourcelang:english';
      const r = await Net.get(`https://api.gdeltproject.org/api/v2/doc/doc?query=${encodeURIComponent(qy)}&mode=artlist&maxrecords=60&format=json&sort=datedesc&timespan=6h`, { timeout: 15000, validate: d => d && Array.isArray(d.articles) });
      const f = { src: 'GDELT', flag: '🌐', cc: 'gl' };
      r.data.articles.forEach(a => {
        const m = (a.seendate || '').match(/^(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)(\d\d)Z$/);
        add({ title: a.title, link: a.url, date: m ? `${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}Z` : '', desc: '' }, Object.assign({}, f, { src: a.domain || 'GDELT' }));
      });
      feedState.gdelt = { ok: true, via: r.via, t: Date.now() };
    } catch (e) { feedState.gdelt = { ok: false, err: e.message }; }
  }
  function publish() {
    const now = Date.now();
    for (const [k, v] of items) if (now - v.date > 48 * 3600e3) items.delete(k);
    const list = [...items.values()].sort((a, b) => b.date - a.date);
    if (list.length > 500) list.slice(500).forEach(x => items.delete(x.id));
    S.news = list.slice(0, 500);
    const geo = S.news.filter(n => n.place && now - n.date < 24 * 3600e3).slice(0, 220);
    MapCtl.render('news', geo); MapCtl.setCount('news', geo.length);
    const ok = Object.values(feedState).filter(s => s.ok).length, tot = DATA.FEEDS.length + 1;
    if (ok) Health.ok('news', { items: S.news.length, via: `${ok}/${tot} fonti`, msg: Object.entries(feedState).filter(([, s]) => !s.ok).map(([k]) => k).join(', ') ? 'offline: ' + Object.entries(feedState).filter(([, s]) => !s.ok).map(([k]) => k).join(', ') : '' });
    else Health.fail('news', 'tutte le fonti RSS non raggiungibili (proxy CORS giù?)');
    Bus.emit('news', S.news);
  }
  async function fetchAll() {
    const batches = [];
    for (let i = 0; i < DATA.FEEDS.length; i += 4) batches.push(DATA.FEEDS.slice(i, i + 4));
    for (const b of batches) { await Promise.all(b.map(fetchFeed)); publish(); }
    await fetchGDELT(); publish();
  }
  async function fetchNext() {   // rotazione: un feed per volta
    const f = DATA.FEEDS[rr++ % DATA.FEEDS.length]; await fetchFeed(f);
    if (rr % DATA.FEEDS.length === 0) await fetchGDELT();
    publish();
  }
  function filtered() {
    const qq = q.trim().toLowerCase();
    return S.news.filter(n => {
      if (filterA === 'war' && !n.hot) return false;
      if (filterA === 'geo' && !n.place) return false;
      if (['it', 'uk', 'us', 'eu', 'gl'].includes(filterA) && n.cc !== filterA) return false;
      if (qq && !(n.title.toLowerCase().includes(qq) || (n.place && n.place.label.toLowerCase().includes(qq)) || n.src.toLowerCase().includes(qq))) return false;
      return true;
    });
  }
  return {
    fetchAll, fetchNext, geocode, filtered, get feedState() { return feedState; },
    setFilter(f) { filterA = f; Bus.emit('news:filter'); }, setQuery(x) { q = x; Bus.emit('news:filter'); },
    get: id => items.get(id)
  };
})();

/* ═════════════ MERCATI / CRYPTO / VALUTE ═════════════ */
const Markets = (() => {
  const Q = {};   // simbolo -> {price, chg, spark, src}
  const fx = {}, cry = {};
  function parseSpark(d) {
    const out = {};
    if (d?.spark?.result) for (const r of d.spark.result) {
      const resp = r.response?.[0]; if (!resp) continue;
      const cl = resp.indicators?.quote?.[0]?.close || [];
      out[r.symbol] = { close: cl, prev: resp.meta?.chartPreviousClose ?? resp.meta?.previousClose, price: resp.meta?.regularMarketPrice };
    } else if (d && typeof d === 'object') for (const [k, v] of Object.entries(d)) if (v && Array.isArray(v.close)) out[k] = { close: v.close, prev: v.chartPreviousClose ?? v.previousClose, price: null };
    return out;
  }
  async function fetchYahoo(syms) {
    const r = await Net.get(`https://query1.finance.yahoo.com/v8/finance/spark?symbols=${encodeURIComponent(syms.join(','))}&range=1d&interval=30m`, { timeout: 15000, via: 'proxy-first', validate: d => d && (d.spark || Object.keys(d).length) });
    const p = parseSpark(r.data); let n = 0;
    for (const [s, v] of Object.entries(p)) {
      const cl = v.close.filter(x => x != null && isFinite(x)); const price = v.price ?? cl.at(-1);
      if (price == null) continue;
      Q[s] = { price, chg: v.prev ? (price - v.prev) / v.prev * 100 : null, spark: cl, src: 'Yahoo' }; n++;
    }
    return { n, via: r.via };
  }
  async function fetchStooq(pairs) {
    const r = await Net.get(`https://stooq.com/q/l/?s=${pairs.map(p => p[2]).join('+')}&f=sd2t2ohlc&h&e=csv`, { type: 'text', timeout: 12000, via: 'proxy-first', validate: t => /symbol/i.test(t) });
    const lines = r.data.trim().split('\n'), hd = lines[0].toLowerCase().split(',');
    const iS = hd.indexOf('symbol'), iC = hd.indexOf('close'), iO = hd.indexOf('open'); let n = 0;
    for (const l of lines.slice(1)) {
      const c = l.split(','), pr = pairs.find(p => p[2] === (c[iS] || '').toLowerCase()); if (!pr) continue;
      const cl = +c[iC], op = +c[iO]; if (!isFinite(cl)) continue;
      if (!Q[pr[0]]) { Q[pr[0]] = { price: cl, chg: op ? (cl - op) / op * 100 : null, spark: null, src: 'Stooq (vs apertura)' }; n++; }
    }
    return n;
  }
  async function fetchStocks() {
    const all = [...DATA.MARKETS.idx, ...DATA.MARKETS.com, ...DATA.MARKETS.def];
    const syms = all.map(x => x[0]); let n = 0, via = '', errs = [];
    for (let i = 0; i < syms.length; i += 12) { try { const r = await fetchYahoo(syms.slice(i, i + 12)); n += r.n; via = r.via; } catch (e) { errs.push(e.message); } }
    const missing = all.filter(x => !Q[x[0]] && x[2]);
    if (missing.length) try { n += await fetchStooq(missing); } catch (e) { errs.push('stooq: ' + e.message); }
    if (n) Health.ok('markets', { items: Object.keys(Q).length, via: 'Yahoo/Stooq ' + via }); else Health.fail('markets', errs.join(' · ') || 'nessun dato');
    Bus.emit('markets');
  }
  async function fetchCrypto() {
    try {
      const ids = DATA.CRYPTO.map(c => c[0]).join(',');
      const r = await Net.get(`https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=${ids}&sparkline=true&price_change_percentage=24h`, { timeout: 12000, validate: d => Array.isArray(d) && d.length });
      r.data.forEach(c => { cry[c.id] = { price: c.current_price, chg: c.price_change_percentage_24h, spark: (c.sparkline_in_7d?.price || []).filter((_, i, a) => i > a.length - 49), mcap: c.market_cap, src: 'CoinGecko' }; });
      Health.ok('crypto', { items: r.data.length, via: 'CoinGecko' });
    } catch (e) {
      try {
        const syms = JSON.stringify(DATA.CRYPTO.map(c => c[2]));
        const r = await Net.get(`https://api.binance.com/api/v3/ticker/24hr?symbols=${encodeURIComponent(syms)}`, { timeout: 10000, validate: d => Array.isArray(d) });
        r.data.forEach(t => { const c = DATA.CRYPTO.find(x => x[2] === t.symbol); if (c) cry[c[0]] = { price: +t.lastPrice, chg: +t.priceChangePercent, spark: cry[c[0]]?.spark || null, src: 'Binance' }; });
        Health.ok('crypto', { items: r.data.length, via: 'Binance (CoinGecko offline)' });
      } catch (e2) { Health.fail('crypto', e.message + ' · ' + e2.message); }
    }
    Bus.emit('markets');
  }
  async function fetchFX() {
    const syms = DATA.FX.map(f => f[0]).join(',');
    const d0 = new Date(Date.now() - 9 * 86400e3).toISOString().slice(0, 10);
    const urls = [`https://api.frankfurter.dev/v1/${d0}..?base=USD&symbols=${syms}`, `https://api.frankfurter.app/${d0}..?from=USD&to=${syms}`];
    for (const u of urls) {
      try {
        const r = await Net.get(u, { timeout: 10000, validate: d => d && d.rates });
        const days = Object.keys(r.data.rates).sort();
        for (const [cc, , inv] of DATA.FX) {
          const series = days.map(d => r.data.rates[d][cc]).filter(Boolean).map(v => inv ? 1 / v : v);
          if (!series.length) continue;
          const last = series.at(-1), prev = series.at(-2);
          fx[cc] = { price: last, chg: prev ? (last - prev) / prev * 100 : null, spark: series, date: days.at(-1), src: 'BCE' };
        }
        Health.ok('fx', { items: Object.keys(fx).length, via: 'Frankfurter/BCE ' + days.at(-1) });
        Bus.emit('markets'); return;
      } catch (e) { Health.fail('fx', e); }
    }
  }
  return { fetchStocks, fetchCrypto, fetchFX, Q, fx, cry };
})();

/* ═════════════ METEO, GEOCODING, QUOTA, IP ═════════════ */
const Weather = {
  WMO: { 0: 'Sereno', 1: 'Prevalentemente sereno', 2: 'Parzialmente nuvoloso', 3: 'Coperto', 45: 'Nebbia', 48: 'Nebbia con brina', 51: 'Pioviggine leggera', 53: 'Pioviggine', 55: 'Pioviggine intensa',
    56: 'Pioviggine gelata', 57: 'Pioviggine gelata', 61: 'Pioggia debole', 63: 'Pioggia', 65: 'Pioggia forte', 66: 'Pioggia gelata', 67: 'Pioggia gelata forte', 71: 'Neve debole', 73: 'Neve', 75: 'Neve forte',
    77: 'Granelli di neve', 80: 'Rovesci deboli', 81: 'Rovesci', 82: 'Rovesci violenti', 85: 'Rovesci di neve', 86: 'Rovesci di neve forti', 95: 'Temporale', 96: 'Temporale con grandine', 99: 'Temporale con grandine forte' },
  ICON: c => c === 0 ? '☀' : c <= 2 ? '🌤' : c === 3 ? '☁' : c <= 48 ? '🌫' : c <= 67 ? '🌧' : c <= 77 ? '❄' : c <= 82 ? '🌦' : c <= 86 ? '🌨' : '⛈',
  async geocode(name) {
    const r = await Net.get(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(name)}&count=5&language=it&format=json`, { timeout: 8000 });
    return (r.data.results || []).map(x => ({ name: x.name, lat: x.latitude, lon: x.longitude, cc: x.country_code, country: x.country, admin: x.admin1, pop: x.population }));
  },
  async at(lat, lon) {
    const u = `https://api.open-meteo.com/v1/forecast?latitude=${lat.toFixed(3)}&longitude=${lon.toFixed(3)}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,cloud_cover,pressure_msl,wind_speed_10m,wind_direction_10m,wind_gusts_10m,is_day&hourly=temperature_2m,precipitation_probability&forecast_hours=24&timezone=auto`;
    const r = await Net.get(u, { timeout: 9000, validate: d => d && d.current });
    Health.ok('weather', { via: 'Open-Meteo' });
    return r.data;
  },
  async air(lat, lon) {
    try { const r = await Net.get(`https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${lat.toFixed(3)}&longitude=${lon.toFixed(3)}&current=european_aqi,pm2_5,pm10`, { timeout: 8000 }); return r.data.current; } catch { return null; }
  },
  async reverse(lat, lon) {
    try {
      const r = await Net.get(`https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${lat.toFixed(4)}&longitude=${lon.toFixed(4)}&localityLanguage=it`, { timeout: 8000 });
      const d = r.data; return { name: d.city || d.locality || '', region: d.principalSubdivision || '', country: d.countryName || '', cc: d.countryCode || '', ocean: !d.countryCode ? (d.locality || '') : '' };
    } catch { return null; }
  },
  async elevation(lat, lon) {
    try { const r = await Net.get(`https://api.open-meteo.com/v1/elevation?latitude=${lat.toFixed(4)}&longitude=${lon.toFixed(4)}`, { timeout: 7000 }); return r.data.elevation?.[0]; } catch { return null; }
  }
};
const GeoIP = {
  async resolve(host) {
    const tries = [
      () => Net.get(`https://dns.google/resolve?name=${encodeURIComponent(host)}&type=A`, { timeout: 7000, noProxy: true }),
      () => Net.get(`https://cloudflare-dns.com/dns-query?name=${encodeURIComponent(host)}&type=A`, { timeout: 7000, noProxy: true, init: { headers: { accept: 'application/dns-json' } } })
    ];
    for (const t of tries) { try { const r = await t(); const a = (r.data.Answer || []).filter(x => x.type === 1).map(x => x.data); if (a.length) return a; } catch {} }
    throw new Error('DNS: dominio non risolto');
  },
  async lookup(ip = '') {
    try {
      const r = await Net.get(`https://ipwho.is/${encodeURIComponent(ip)}`, { timeout: 8000, validate: d => d && d.success !== false });
      const d = r.data; Health.ok('geoip', { via: 'ipwho.is' });
      return { ip: d.ip, city: d.city, region: d.region, country: d.country, cc: d.country_code, lat: d.latitude, lon: d.longitude, org: d.connection?.org || d.connection?.isp, asn: d.connection?.asn ? 'AS' + d.connection.asn : '', isp: d.connection?.isp, tz: d.timezone?.id, type: d.type };
    } catch (e) {
      const r = await Net.get(`https://ipapi.co/${ip ? encodeURIComponent(ip) + '/' : ''}json/`, { timeout: 8000, validate: d => d && !d.error });
      const d = r.data; Health.ok('geoip', { via: 'ipapi.co' });
      return { ip: d.ip, city: d.city, region: d.region, country: d.country_name, cc: d.country_code, lat: d.latitude, lon: d.longitude, org: d.org, asn: d.asn, isp: d.org, tz: d.timezone, type: d.version };
    }
  }
};

/* ═════════════ Astronomia (calcolata) ═════════════ */
const Astro = {
  moon(date = new Date()) {
    const syn = 29.530588853, ref = Date.UTC(2000, 0, 6, 18, 14) ;
    const age = (((date - ref) / 86400000) % syn + syn) % syn, f = age / syn;
    const illum = (1 - Math.cos(2 * Math.PI * f)) / 2;
    const names = ['🌑 Luna nuova', '🌒 Crescente', '🌓 Primo quarto', '🌔 Gibbosa crescente', '🌕 Luna piena', '🌖 Gibbosa calante', '🌗 Ultimo quarto', '🌘 Calante'];
    return { age, illum, name: names[Math.round(f * 8) % 8] };
  }
};
