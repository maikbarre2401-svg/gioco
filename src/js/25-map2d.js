'use strict';
/* ════════════════════════════════════════════════════════════════
   MAPPA 2D DI RISERVA (Leaflet) — usata solo se WebGL/Cesium non
   sono disponibili. Stessa interfaccia del motore 3D.
   + MapCtl: facciata unica, cache dei dati, gestione layer.
═══════════════════════════════════════════════════════════════════ */
const Map2D = (() => {
  let L = null, map = null, ready = false;
  const state = { layers: {} };
  const groups = {};
  const tiles = { base: null, night: null, labels: null, radar: null };
  let cv = null, ctx = null, acData = [], satData = [], sel = null, follow = null, traceLayer = null;
  const BASES = {
    sat: ['🛰 Satellite (Esri)', 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', '© Esri, Maxar', 19],
    dark: ['🌑 Scura (Esri)', 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', '© Esri, HERE, Garmin, OpenStreetMap', 16],
    topo: ['⛰ Topografica (Esri)', 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', '© Esri', 19],
    osm: ['🗺 OpenStreetMap', 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', '© OpenStreetMap contributors', 19],
    night: ['🌃 Luci notturne (NASA)', 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_CityLights_2012/default/2012-01-01/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpg', 'NASA', 8]
  };
  const FILTERS = { nrm: '', nvg: 'grayscale(1) sepia(1) hue-rotate(65deg) saturate(5) brightness(1.15) contrast(1.1)', flir: 'grayscale(1) contrast(1.6) brightness(1.1) sepia(1) hue-rotate(-40deg) saturate(4)', crt: 'grayscale(1) contrast(2.2) sepia(1) hue-rotate(70deg) saturate(3) brightness(.9)' };

  function divIcon(emoji, ring, size = 26) {
    return L.divIcon({ className: '', iconSize: [size, size], iconAnchor: [size / 2, size / 2],
      html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:rgba(0,10,0,.82);border:2px solid ${ring};display:flex;align-items:center;justify-content:center;font-size:${Math.round(size * .52)}px;box-shadow:0 0 6px ${ring}">${emoji}</div>` });
  }
  function grp(key) { if (!groups[key]) { groups[key] = L.layerGroup(); if (state.layers[key] !== false) groups[key].addTo(map); } groups[key].clearLayers(); return groups[key]; }
  const pick = ref => ev => { L.DomEvent.stopPropagation(ev); Bus.emit('map:pick', ref); };

  function draw() {
    if (!ctx) return;
    const s = map.getSize(); if (cv.width !== s.x || cv.height !== s.y) { cv.width = s.x; cv.height = s.y; }
    const tl = map.containerPointToLayerPoint([0, 0]); L.DomUtil.setPosition(cv, tl);
    ctx.clearRect(0, 0, cv.width, cv.height);
    const z = map.getZoom(), S = z < 4 ? 0.55 : z < 7 ? 0.8 : 1.05;
    if (state.layers.sats !== false) for (const st of satData) {
      if (st.show === false) continue;
      const p = map.latLngToContainerPoint([st.lat, st.lon]); if (p.x < -10 || p.y < -10 || p.x > cv.width + 10 || p.y > cv.height + 10) continue;
      ctx.fillStyle = st.col; ctx.beginPath(); ctx.arc(p.x, p.y, st.special ? 5 : 2.4, 0, Math.PI * 2); ctx.fill();
      if (st.special) { ctx.font = '11px "Share Tech Mono"'; ctx.fillText(st.name, p.x + 7, p.y - 5); }
    }
    if (state.layers.adsb !== false) for (const ac of acData) {
      const la = ac.plat ?? ac.lat, lo = ac.plon ?? ac.lon;
      const p = map.latLngToContainerPoint([la, lo]); if (p.x < -10 || p.y < -10 || p.x > cv.width + 10 || p.y > cv.height + 10) continue;
      const c = ac.emerg ? '#ff2244' : (DATA.AC_CLASS[ac.cls] || DATA.AC_CLASS.civil).col;
      ctx.save(); ctx.translate(p.x, p.y); ctx.rotate((ac.trk || 0) * Math.PI / 180); ctx.fillStyle = c;
      ctx.beginPath(); ctx.moveTo(0, -8 * S); ctx.lineTo(5 * S, 5 * S); ctx.lineTo(0, 2.5 * S); ctx.lineTo(-5 * S, 5 * S); ctx.closePath(); ctx.fill(); ctx.restore();
      if (z >= 8 || (ac.cls !== 'civil' && z >= 5)) { ctx.fillStyle = c; ctx.font = '11px "Share Tech Mono"'; ctx.fillText(ac.cs || ac.hex, p.x + 9, p.y - 6); }
      if (sel && sel.kind === 'ac' && sel.id === ac.hex) { ctx.strokeStyle = '#ffee33'; ctx.lineWidth = 2; ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.arc(p.x, p.y, 16, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]); }
    }
    if (sel && sel.kind === 'sat') { const st = satData.find(x => x.id === sel.id); if (st) { const p = map.latLngToContainerPoint([st.lat, st.lon]); ctx.strokeStyle = '#ffee33'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(p.x, p.y, 14, 0, Math.PI * 2); ctx.stroke(); } }
  }
  function hit(pt) {
    let best = null, bd = 14;
    if (state.layers.adsb !== false) for (const ac of acData) { const p = map.latLngToContainerPoint([ac.plat ?? ac.lat, ac.plon ?? ac.lon]); const d = Math.hypot(p.x - pt.x, p.y - pt.y); if (d < bd) { bd = d; best = { kind: 'ac', id: ac.hex }; } }
    if (state.layers.sats !== false) for (const s of satData) { if (s.show === false) continue; const p = map.latLngToContainerPoint([s.lat, s.lon]); const d = Math.hypot(p.x - pt.x, p.y - pt.y); if (d < bd) { bd = d; best = { kind: 'sat', id: s.id }; } }
    return best;
  }

  async function init(container) {
    await loadCSS('https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css');
    await loadScript('https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js');
    L = window.L; if (!L) throw new Error('Leaflet non caricato');
    container.style.display = 'block';
    map = L.map(container, { center: [35, 20], zoom: 3, worldCopyJump: true, zoomControl: true, attributionControl: true, preferCanvas: true, minZoom: 2 });
    map.attributionControl.setPrefix('Leaflet');
    setBase(BASES[Settings.get('base')] ? Settings.get('base') : 'sat');
    tiles.labels = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19, maxNativeZoom: 18, opacity: 0.9, attribution: '© Esri' });
    if (state.layers.labels !== false) tiles.labels.addTo(map);
    const Overlay = L.Layer.extend({
      onAdd(m) { cv = L.DomUtil.create('canvas', 'leaflet-zoom-hide'); cv.style.pointerEvents = 'none'; m.getPanes().overlayPane.appendChild(cv); ctx = cv.getContext('2d'); m.on('move zoom resize viewreset', draw); draw(); },
      onRemove(m) { m.off('move zoom resize viewreset', draw); cv.remove(); ctx = null; }
    });
    new Overlay().addTo(map);
    setInterval(() => { if (follow) { const r = refLL(follow); if (r) map.panTo(r, { animate: false }); } draw(); }, 500);
    map.on('click', e => { const r = hit(e.containerPoint); if (r) Bus.emit('map:pick', r); else Bus.emit('map:click', { lat: e.latlng.lat, lon: e.latlng.lng }); });
    map.on('contextmenu', e => Bus.emit('map:context', { lat: e.latlng.lat, lon: e.latlng.lng, x: e.originalEvent.clientX, y: e.originalEvent.clientY }));
    map.on('mousemove', e => Bus.emit('map:move', { lat: e.latlng.lat, lon: ((e.latlng.lng + 540) % 360) - 180 }));
    map.on('moveend', () => Bus.emit('map:view', getView()));
    map.on('dragstart', () => { follow = null; });
    ready = true;
    return true;
  }
  function refLL(ref) {
    if (ref.kind === 'ac') { const a = acData.find(x => x.hex === ref.id); return a ? [a.plat ?? a.lat, a.plon ?? a.lon] : null; }
    if (ref.kind === 'sat') { const s = satData.find(x => x.id === ref.id); return s ? [s.lat, s.lon] : null; }
    return null;
  }
  const tried = new Set();
  function setBase(key) {
    const b = BASES[key] || BASES.sat;
    const t = L.tileLayer(b[1], { subdomains: 'abcd', maxZoom: 19, maxNativeZoom: b[3], attribution: b[2] });
    let ok = 0, err = 0; t.on('tileload', () => ok++); t.on('tileerror', () => err++);
    t.addTo(map); t.bringToBack();
    if (tiles.base) { const old = tiles.base; setTimeout(() => map.removeLayer(old), 800); }
    tiles.base = t; Settings.set('base', key);
    setTimeout(() => {   // autodiagnosi: se nessun tile arriva, prova un'altra mappa
      if (tiles.base !== t) return;
      if (ok) { Health.ok('imagery', { via: b[0], items: ok }); return; }
      tried.add(key); const next = ['sat', 'topo', 'dark', 'osm'].find(k => !tried.has(k));
      Health.fail('imagery', `${b[0]}: ${err} tile falliti`);
      if (next) { Toast.show(`⚠ Immagini "${b[0]}" non raggiungibili: passo a "${BASES[next][0]}"`, 'orn', 6000); setBase(next); }
      else Bus.emit('map:warn', { text: 'Nessun server di mappe risponde: controlla connessione, firewall o blocco pubblicità.', retry: true });
    }, 12000);
  }
  function getView() { if (!map) return null; const c = map.getCenter(); return { lat: c.lat, lon: ((c.lng + 540) % 360) - 180, alt: Geo.zoomToAlt(map.getZoom()), heading: 0, pitch: -90, centerOnGlobe: true }; }

  function render(kind, data) {
    if (!ready) return;
    try {
      if (kind === 'aircraft') { acData = data; draw(); return; }
      if (kind === 'sats') { satData = data; return; }
      if (kind === 'quakes') {
        const g = grp('quakes');
        data.forEach(q => {
          const c = q.mag >= 6 ? '#ff1744' : q.mag >= 5 ? '#ff6d00' : '#ffb74d';
          L.circleMarker([q.lat, q.lon], { radius: clamp(q.mag * 2, 3, 18), color: c, fillColor: c, fillOpacity: 0.6, weight: 1 }).on('click', pick({ kind: 'eq', id: q.id })).addTo(g);
        });
        return;
      }
      if (kind === 'news') { const g = grp('news'); data.forEach(n => L.marker([n.place.lat + n.jlat, n.place.lon + n.jlon], { icon: divIcon(n.sev >= 0.7 ? '💥' : n.sev >= 0.45 ? '⚠' : '📰', n.sev >= 0.7 ? '#ff2244' : '#00ccff', 22) }).on('click', pick({ kind: 'news', id: n.id })).addTo(g)); return; }
      if (kind === 'eonet') { const g = grp('eonet'); data.forEach(ev => L.marker([ev.lat, ev.lon], { icon: divIcon((DATA.EONET[ev.cat] || ['⚠'])[0], '#ff8c00', 22) }).on('click', pick({ kind: 'eonet', id: ev.id })).addTo(g)); return; }
      if (kind === 'fires') { const g = grp('fires'); data.slice(0, 6000).forEach(f => L.circleMarker([f.lat, f.lon], { radius: 2.5, color: '#ff5500', weight: 0, fillOpacity: 0.85 }).addTo(g)); return; }
      if (kind === 'aurora') { const g = grp('aurora'); data.filter(c => c[2] >= 15).forEach(([lo, la, v]) => L.circleMarker([la, lo > 180 ? lo - 360 : lo], { radius: 3, color: '#00ff88', weight: 0, fillOpacity: v / 160 }).addTo(g)); return; }
      if (kind === 'radar') {
        if (tiles.radar) map.removeLayer(tiles.radar); tiles.radar = null;
        if (data) { tiles.radar = L.tileLayer(data, { opacity: 0.7, maxNativeZoom: 7, maxZoom: 19, attribution: 'RainViewer' }); if (state.layers.radar !== false) tiles.radar.addTo(map); }
        return;
      }
      if (kind === 'trace') {
        if (traceLayer) map.removeLayer(traceLayer); traceLayer = null;
        if (data) traceLayer = L.layerGroup([L.polyline(Geo.gcPath(data.from.lat, data.from.lon, data.to.lat, data.to.lon, 64), { color: '#00ffcc', weight: 2 }),
          L.circleMarker([data.from.lat, data.from.lon], { radius: 6, color: '#00ffcc' }), L.circleMarker([data.to.lat, data.to.lon], { radius: 6, color: '#ff2244' })]).addTo(map);
        return;
      }
      if (kind.startsWith('points:')) {
        const key = kind.slice(7), g = grp(key);
        const ic = { bases: ['🏴', '#ff5500'], nuclear: ['☢', '#c040ff'], choke: ['⚓', '#00ccff'] }[key] || ['•', '#00ff41'];
        data.forEach((p, i) => L.marker([p.lat, p.lon], { icon: divIcon(ic[0], p.risk === 'CRIT' ? '#ff2244' : ic[1]) }).bindTooltip(p.name).on('click', pick({ kind: key, id: String(i) })).addTo(g));
        return;
      }
      if (kind.startsWith('zones:')) {
        const key = kind.slice(6), g = grp(key), c = key === 'gps' ? '#00ffcc' : '#ff2244';
        data.forEach(z => L.circle([z.lat, z.lon], { radius: z.r * 1000, color: c, weight: 1.2, dashArray: '6,6', fillOpacity: 0.1 }).bindTooltip(z.name)
          .on('click', ev => { L.DomEvent.stopPropagation(ev); Bus.emit('map:click', { lat: ev.latlng.lat, lon: ev.latlng.lng }); }).addTo(g));
      }
    } catch (e) { console.warn('[2d render]', kind, e); }
  }
  function setLayer(key, on) {
    state.layers[key] = on;
    if (!ready) return;
    if (key === 'adsb' || key === 'sats') { draw(); return; }
    const lyr = key === 'radar' ? tiles.radar : key === 'labels' ? tiles.labels : groups[key];
    if (!lyr) return;
    if (on && !map.hasLayer(lyr)) lyr.addTo(map); else if (!on && map.hasLayer(lyr)) map.removeLayer(lyr);
  }
  return {
    kind: '2d', get ready() { return ready; },
    bases: () => Object.entries(BASES).map(([k, b]) => ({ key: k, name: b[0] })),
    init, render, setLayer, getView, setBase,
    flyTo(lat, lon, range = 1.5e6) { if (map) map.flyTo([lat, lon], Geo.altToZoom(range), { duration: 1.4 }); },
    setScene() { Toast.show('ℹ Modalità 2D di riserva: il globo 3D richiede WebGL', 'orn'); },
    setVisual(m) { const el = map?.getContainer(); if (el) el.style.filter = FILTERS[m] || ''; },
    setExag() {}, setSpin() {}, get spin() { return false; },
    select(ref) { sel = ref; draw(); },
    setFollow(ref) { follow = ref; Bus.emit('follow', ref); }, setCockpit(ref) { Toast.show('ℹ Vista cockpit disponibile solo in 3D', 'orn'); this.setFollow(ref); },
    stopFollow() { follow = null; Bus.emit('follow', null); }, get following() { return follow; },
    home() { if (map) map.flyTo([30, 15], 2.5); },
    resetMap() { if (!map) return; tried.clear(); setBase('sat'); this.setVisual('nrm'); map.flyTo([30, 15], 2.5); Bus.emit('map:warn', null); },
    terrainHeight() { return null; }, async sampleHeight() { return null; }
  };
})();

/* ═══════════════════════ MapCtl ═══════════════════════ */
const MapCtl = (() => {
  const LAYERS = [
    { key: 'adsb', label: 'Aerei ADS-B', icon: '✈', tag: 'live', grp: 'Dati live', def: true },
    { key: 'sats', label: 'Satelliti in orbita', icon: '🛰', tag: 'live', grp: 'Dati live', def: true },
    { key: 'quakes', label: 'Terremoti USGS', icon: '🌍', tag: 'live', grp: 'Dati live', def: true },
    { key: 'eonet', label: 'Eventi naturali NASA', icon: '🌋', tag: 'live', grp: 'Dati live', def: true },
    { key: 'fires', label: 'Incendi satellitari FIRMS', icon: '🔥', tag: 'key', grp: 'Dati live', def: true },
    { key: 'aurora', label: 'Aurora (NOAA OVATION)', icon: '🌌', tag: 'live', grp: 'Dati live', def: true },
    { key: 'radar', label: 'Radar pioggia (RainViewer)', icon: '🌧', tag: 'live', grp: 'Dati live', def: false },
    { key: 'news', label: 'Notizie geolocalizzate', icon: '📰', tag: 'calc', grp: 'Dati live', def: true },
    { key: 'conflict', label: 'Zone di conflitto', icon: '⚔', tag: 'est', grp: 'Riferimento', def: true },
    { key: 'nuclear', label: 'Siti nucleari', icon: '☢', tag: 'ref', grp: 'Riferimento', def: true },
    { key: 'bases', label: 'Basi militari', icon: '🏴', tag: 'ref', grp: 'Riferimento', def: false },
    { key: 'choke', label: 'Stretti strategici', icon: '⚓', tag: 'ref', grp: 'Riferimento', def: false },
    { key: 'gps', label: 'Interferenze GPS segnalate', icon: '📡', tag: 'est', grp: 'Riferimento', def: false },
    { key: 'terrain', label: 'Terreno 3D', icon: '⛰', tag: 'live', grp: 'Globo 3D', def: true, only3d: true },
    { key: 'lighting', label: 'Luce solare reale (giorno/notte)', icon: '🌗', tag: 'calc', grp: 'Globo 3D', def: true, only3d: true },
    { key: 'night', label: 'Luci notturne delle città', icon: '🌃', tag: 'ref', grp: 'Globo 3D', def: true, only3d: true },
    { key: 'labels', label: 'Nomi e confini', icon: '🔤', tag: 'ref', grp: 'Globo 3D', def: true },
    { key: 'osm3d', label: 'Edifici 3D (OSM)', icon: '🏙', tag: 'key', grp: 'Globo 3D', def: false, only3d: true, ion: true },
    { key: 'photo3d', label: 'Città fotorealistiche 3D', icon: '🏛', tag: 'key', grp: 'Globo 3D', def: false, only3d: true, ion: true }
  ];
  const saved = Settings.get('layers') || {};
  const on = {}; LAYERS.forEach(l => { on[l.key] = saved[l.key] ?? l.def; });
  if (!(Settings.get('ionToken') || '').trim()) { on.osm3d = false; on.photo3d = false; }
  const cache = new Map();
  let eng = null;
  const counts = {};

  function webgl() { try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch { return false; } }
  async function useEngine(E, el) {
    await E.init(el);
    eng = E;
    LAYERS.forEach(l => E.setLayer(l.key, on[l.key]));
    for (const [k, d] of cache) E.render(k, d);
    Bus.emit('engine', E.kind);
  }
  return {
    LAYERS,
    get engine() { return eng; },
    get is3d() { return eng?.kind === '3d'; },
    async start() {
      const msg = t => setText('map-msg-txt', t);
      if (webgl() && Store.get('force2d') !== true) {
        try {
          msg('Caricamento motore 3D CesiumJS…');
          await useEngine(Globe3D, $('globe3d'));
          $('map-msg')?.classList.add('hidden');
          Health.ok('engine', { via: 'CesiumJS 3D', msg: 'WebGL ' + (document.createElement('canvas').getContext('webgl2') ? '2' : '1') });
          return '3d';
        } catch (e) { console.error('3D init', e); Health.fail('engine', e); EventLog.add('Motore 3D non disponibile: ' + e.message, 'var(--orn)'); }
      }
      msg('Carico la mappa 2D di riserva…');
      $('globe3d').style.display = 'none';
      try { await useEngine(Map2D, $('map2d')); Health.ok('engine', { via: 'Leaflet 2D (riserva)' }); }
      catch (e) { msg('⚠ Impossibile caricare la mappa: ' + e.message); Health.fail('engine', e); return null; }
      $('map-msg')?.classList.add('hidden');
      Toast.show('⚠ WebGL non disponibile: uso la mappa 2D', 'orn');
      return '2d';
    },
    render(kind, data) { cache.set(kind, data); eng?.render(kind, data); },
    cached(kind) { return cache.get(kind); },
    isOn(key) { return !!on[key]; },
    setLayer(key, v) {
      const def = LAYERS.find(l => l.key === key);
      if (def?.ion && v && !(Settings.get('ionToken') || '').trim()) { Toast.show('🔑 Questo layer richiede un token Cesium ion (⚙ Impostazioni)', 'orn'); v = false; }
      on[key] = v;
      const s = Object.assign({}, Settings.get('layers') || {}); s[key] = v; Settings.set('layers', s);
      if (key === 'terrain') Settings.set('terrain', v);
      if (key === 'lighting') Settings.set('lighting', v);
      eng?.setLayer(key, v);
      Bus.emit('layer', { key, on: v });
    },
    toggle(key) { this.setLayer(key, !on[key]); return on[key]; },
    setCount(key, n) { counts[key] = n; const el = $('lc-' + key); if (el) el.textContent = n == null ? '' : Fmt.n(n); },
    count(key) { return counts[key]; },
    flyTo(lat, lon, range, opt) { eng?.flyTo(lat, lon, range, opt); },
    getView() { return eng?.getView() || null; }
  };
})();
