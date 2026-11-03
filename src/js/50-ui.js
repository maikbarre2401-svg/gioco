'use strict';
/* ════════════════════════════════════════════════════════════════
   UI — pannelli, bersaglio, ricerca, terminale, media, avvio
═══════════════════════════════════════════════════════════════════ */
const UI = (() => {
  let sel = null, selCache = new Map(), trkTimer = null;
  const LVL_CLS = ['', 'lv1', 'lv2', 'lv3', 'lv4', 'lv5'];
  const sevCls = s => s >= 70 ? 's-crit' : s >= 55 ? 's-high' : s >= 40 ? 's-med' : 's-low';
  const sevBadge = s => s >= 70 ? ['b-crit', 'CRIT'] : s >= 55 ? ['b-high', 'ALTO'] : s >= 40 ? ['b-med', 'MEDIO'] : ['b-low', 'BASSO'];
  const ext = (url, label) => h('a', { href: url, target: '_blank', rel: 'noopener noreferrer', class: 'abtn', style: 'text-decoration:none' }, label);
  const view = () => MapCtl.getView() || { lat: 30, lon: 15, alt: 2e7 };

  /* ═════ PANNELLO BERSAGLIO ═════ */
  function openPanel({ title = '🎯 TARGET', icon = '', name = '', nameCol = 'var(--g)', tags = [], kv = [], extra = [], buttons = [] }) {
    const p = $('trkp');
    const head = h('div', { class: 'trk-h' }, h('span', null, title), h('button', { class: 'trk-x', type: 'button', title: 'Chiudi (Esc)', onclick: closePanel }, '✕'));
    const top = h('div', { class: 'trk-title' }, h('div', { class: 'trk-ico', style: `color:${nameCol}` }, icon),
      h('div', { style: 'min-width:0' }, h('div', { class: 'trk-name', style: `color:${nameCol}` }, name),
        h('div', null, tags.map(([t, c]) => h('span', { class: 'trk-tag', style: `background:${c}22;border:1px solid ${c}66;color:${c};margin-right:4px` }, t)))));
    p.replaceChildren(head, top, h('div', { class: 'kv', id: 'trk-kv' }, kvNodes(kv)), h('div', { id: 'trk-extra' }, extra),
      h('div', { class: 'trk-btns', id: 'trk-btns' }, buttons.map(b => b.nodeType ? b : h('button', { class: 'abtn' + (b[2] ? ' on' : ''), type: 'button', onclick: b[1] }, b[0]))));
    p.classList.remove('hidden');
  }
  function kvNodes(kv) { return kv.filter(Boolean).map(([l, v, full]) => h('div', { class: full ? 'full' : '' }, h('div', { class: 'kv-l' }, l), h('div', { class: 'kv-v' }, v ?? '--'))); }
  function updateKV(kv) { const el = $('trk-kv'); if (el) el.replaceChildren(...kvNodes(kv)); }
  function closePanel() {
    $('trkp').classList.add('hidden'); clearInterval(trkTimer); sel = null;
    MapCtl.engine?.select(null);
  }
  function followBtns(ref) {
    const f = MapCtl.engine?.following, isF = f && !f.cockpit && f.kind === ref.kind && f.id === ref.id, isC = f && f.cockpit && f.id === ref.id;
    const out = [['🎯 ' + (isF ? 'STOP' : 'SEGUI'), () => { MapCtl.engine.setFollow(isF ? null : ref); select(ref, true); }, isF]];
    if (ref.kind === 'ac' && MapCtl.is3d) out.push(['🎥 ' + (isC ? 'ESCI' : 'COCKPIT'), () => { MapCtl.engine.setCockpit(isC ? null : ref); select(ref, true); }, isC]);
    return out;
  }

  function select(ref, keepCam = false) {
    if (!ref) return closePanel();
    if (ref.kind === 'many') return showMany(ref.items);
    sel = ref; clearInterval(trkTimer);
    const r = RENDER[ref.kind];
    if (!r) return;
    const ok = r(ref.id, keepCam);
    if (ok === false) { Toast.show('Elemento non più disponibile', 'orn'); return; }
    Sound.lock();
    if (innerWidth <= 700) { const m = $('map-section'); if (m.getBoundingClientRect().top < -40 || m.getBoundingClientRect().bottom > innerHeight + 40) m.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  }

  const RENDER = {
    ac(id, keep) {
      const a = S.ac.get(id); if (!a) return false;
      const c = DATA.AC_CLASS[a.cls] || DATA.AC_CLASS.civil, col = a.emerg ? '#ff2244' : c.col;
      const kv = () => {
        const x = S.ac.get(id) || a, lat = x.plat ?? x.lat, lon = x.plon ?? x.lon;
        return [['Quota', [Fmt.n(x.altFt) + ' ft ', h('small', null, Fmt.n(x.altM) + ' m')]], ['Velocità', [Fmt.n(x.gs) + ' kt ', h('small', null, Fmt.n(x.gs * 1.852) + ' km/h')]],
          ['Rotta', `${Math.round(x.trk)}° ${Geo.dir(x.trk)}`], ['Variometro', x.vr ? `${x.vr > 0 ? '▲' : '▼'} ${Fmt.n(Math.abs(x.vr))} ft/min` : 'livellato'],
          ['Tipo', x.type || '--'], ['Registrazione', x.reg || '--'], ['Squawk', x.sq ? (x.emerg ? h('span', { class: 'red' }, x.sq) : x.sq) : '--'], ['ICAO hex', x.hex.toUpperCase()],
          ['Posizione', `${lat.toFixed(3)}, ${lon.toFixed(3)}`], ['Sopra', Intel.nearest(lat, lon).label],
          ['Fonte', `${x.src === 'mil' ? 'feed militare' : x.src === 'area' ? 'feed area' : x.src}${x.country ? ' · ' + x.country : ''}`], ['Dato', Fmt.ago(x.t) + (x.gs > 40 ? ' · stimato ora' : '')]];
      };
      const extra = h('div', { class: 'trk-sec', id: 'ac-extra' }, h('span', { class: 'spinner' }), ' rotta e dettagli…');
      openPanel({ title: (a.emerg ? '🆘 ' : '') + 'AEREO · TARGET LOCK', icon: c.icon, name: a.cs || a.hex.toUpperCase(), nameCol: col,
        tags: [[c.label, c.col], a.emerg ? [a.emerg, '#ff2244'] : null, a.isMil && a.cls === 'civil' ? ['MIL', '#ff7a1a'] : null].filter(Boolean), kv: kv(), extra: [extra],
        buttons: [...followBtns({ kind: 'ac', id }), ['🔍 ZOOM', () => MapCtl.flyTo(a.plat ?? a.lat, a.plon ?? a.lon, 60000, { pitch: -35 })], ['🔊 VOCE', () => speakAc(a)],
          ext(`https://globe.adsb.lol/?icao=${a.hex}`, '↗ adsb.lol'), ext(`https://globe.adsbexchange.com/?icao=${a.hex}`, '↗ ADSBx'), a.cs ? ext(`https://www.flightradar24.com/${encodeURIComponent(a.cs)}`, '↗ FR24') : null].filter(Boolean) });
      MapCtl.engine?.select({ kind: 'ac', id });
      if (!keep && !MapCtl.engine?.following) MapCtl.flyTo(a.plat ?? a.lat, a.plon ?? a.lon, 350000, { pitch: -50, duration: 1.6 });
      trkTimer = setInterval(() => { if (!S.ac.get(id)) { $('ac-extra')?.replaceChildren('⚠ segnale perso'); clearInterval(trkTimer); return; } updateKV(kv()); }, 1500);
      const cached = selCache.get('ac' + id);
      const fill = d => {
        const el = $('ac-extra'); if (!el || sel?.id !== id) return;
        const nodes = [];
        if (d.route) nodes.push(h('div', { style: 'font-size:13px;color:var(--gd)' }, `🛫 ${d.route.from || '?'} (${d.route.fromC || '?'}) → 🛬 ${d.route.to || '?'} (${d.route.toC || '?'})`));
        if (d.route?.airline || DATA.AIRLINES[(a.cs || '').slice(0, 3)]) nodes.push(h('div', null, '✈ ' + (d.route?.airline || DATA.AIRLINES[a.cs.slice(0, 3)])));
        if (d.info?.model) nodes.push(h('div', null, '🛩 ' + d.info.model + (d.info.owner ? ' · ' + d.info.owner : '') + (d.info.ownerCountry ? ' (' + d.info.ownerCountry + ')' : '')));
        if (d.info?.photo) nodes.push(h('a', { href: d.info.photoLink || '#', target: '_blank', rel: 'noopener' }, h('img', { src: d.info.photo, alt: 'foto aereo', referrerpolicy: 'no-referrer', style: 'width:100%;margin-top:6px;border:1px solid var(--border2)', onerror: e => e.target.remove() })),
          d.info.photoBy ? h('div', { style: 'font-size:9px;color:var(--gf)' }, '📷 ' + d.info.photoBy + ' · planespotters.net') : null);
        if (!nodes.length) nodes.push(h('span', { class: 'dim' }, 'Nessun dettaglio di rotta pubblico per questo volo.'));
        el.replaceChildren(...nodes.filter(Boolean));
      };
      if (cached) fill(cached);
      else Promise.all([ADSB.route(a.cs), ADSB.info(a.hex)]).then(([route, info]) => { const d = { route, info }; selCache.set('ac' + id, d); fill(d); if (TTS.enabled) speakAc(a, d); });
    },
    sat(id, keep) {
      const s = Sats.get(id), rec = Sats.rec(id); if (!s || !rec) return false;
      const kv = () => {
        const x = Sats.get(id) || s;
        return [['Quota', Fmt.n(x.altKm) + ' km'], ['Velocità', [Fmt.n(x.vel, 2) + ' km/s ', h('small', null, Fmt.n(x.vel * 3600) + ' km/h')]], ['Lat / Lon', `${x.lat.toFixed(2)}, ${x.lon.toFixed(2)}`],
          ['Sopra', Intel.nearest(x.lat, x.lon).label], ['Periodo', Fmt.n(rec.period, 1) + ' min'], ['Inclinazione', Fmt.n(Geo.deg(rec.rec.inclo), 1) + '°'],
          ['NORAD', id], ['Gruppo', (DATA.SAT_GROUPS.find(g => g.id === s.group) || {}).label || s.group], ['Illuminato', Sats.posAt && (() => { const p = Sats.posAt(rec, new Date()); return p ? (p && sunlitTxt(p)) : '--'; })()],
          ['Epoca TLE', (() => { const e = rec.rec.epochyr, d = rec.rec.epochdays; const y = e < 57 ? 2000 + e : 1900 + e; return new Date(Date.UTC(y, 0, 1) + (d - 1) * 86400e3).toISOString().slice(0, 16).replace('T', ' '); })()]];
      };
      const orb = Sats.orbit(id);
      openPanel({ title: '🛰 SATELLITE', icon: '🛰', name: s.name, nameCol: s.col, tags: [[(DATA.SAT_GROUPS.find(g => g.id === s.group) || {}).label || s.group, s.col], ['SGP4 · CelesTrak', '#00ffcc']], kv: kv(),
        extra: [h('div', { class: 'trk-sec', id: 'sat-pass' }, S.user ? 'Calcolo passaggi…' : 'Passaggi sopra di te: imposta la tua posizione (📍 IO).')],
        buttons: [...followBtns({ kind: 'sat', id }), ['🔍 ZOOM', () => MapCtl.flyTo(s.lat, s.lon, (s.altKm * 1000) + 3e6)], ext(`https://www.n2yo.com/satellite/?s=${id}`, '↗ N2YO'), ext(`https://celestrak.org/satcat/table-satcat.php?CATNR=${id}`, '↗ CelesTrak')] });
      MapCtl.engine?.select({ kind: 'sat', id }, orb || {});
      if (!keep && !MapCtl.engine?.following) MapCtl.flyTo(s.lat, s.lon, s.altKm * 1000 + 6e6);
      trkTimer = setInterval(() => updateKV(kv()), 1000);
      if (S.user) setTimeout(() => {
        const ps = Sats.passes(id, S.user, 36, 10), el = $('sat-pass'); if (!el) return;
        el.replaceChildren(h('div', { style: 'color:var(--gd);margin-bottom:3px' }, `📡 Passaggi sopra ${S.user.label || 'di te'} (>10°):`),
          ...(ps.length ? ps.map(p => h('div', null, `${Fmt.dateTime(p.start)} · max ${Math.round(p.maxEl)}° · ${Geo.dir(p.azStart)}→${Geo.dir(p.azEnd)} · ${Math.round((p.end - p.start) / 60000)} min ${p.visible ? '👁 visibile' : ''}`)) : [h('div', { class: 'dim' }, 'Nessun passaggio nelle prossime 36 ore.')]));
      }, 50);
    },
    eq(id) {
      const q = Quakes.get(id); if (!q) return false;
      const c = q.mag >= 6 ? '#ff1744' : q.mag >= 5 ? '#ff6d00' : '#ffb74d';
      openPanel({ title: '🌍 TERREMOTO · USGS', icon: '🌍', name: `M${q.mag.toFixed(1)}`, nameCol: c, tags: [[q.type || 'earthquake', c], q.tsunami ? ['⚠ TSUNAMI', '#ff2244'] : null, q.alert ? ['PAGER ' + q.alert.toUpperCase(), q.alert === 'red' ? '#ff2244' : '#ff8c00'] : null].filter(Boolean),
        kv: [['Luogo', q.place, true], ['Ora', Fmt.dateTime(q.time)], ['Quanto fa', Fmt.ago(q.time)], ['Profondità', Fmt.n(q.depth, 1) + ' km'], ['Coordinate', `${q.lat.toFixed(3)}, ${q.lon.toFixed(3)}`],
          ['Risentito', q.felt ? Fmt.n(q.felt) + ' segnalazioni' : '--'], ['Significatività', q.sig ?? '--']],
        buttons: [['🔍 ZOOM 3D', () => MapCtl.flyTo(q.lat, q.lon, 250000, { pitch: -40 })], ['🌡 ANALISI PUNTO', () => analyzePoint(q.lat, q.lon)], ext(q.url, '↗ USGS')] });
      MapCtl.engine?.select({ kind: 'eq', id, lat: q.lat, lon: q.lon });
      MapCtl.flyTo(q.lat, q.lon, 1200000, { pitch: -60 });
    },
    eonet(id) {
      const e = S.eonet.find(x => x.id === id); if (!e) return false;
      const [ic, nm] = DATA.EONET[e.cat] || ['⚠', e.catTitle];
      openPanel({ title: '🛰 NASA EONET', icon: ic, name: e.title, nameCol: '#ffcc80', tags: [[nm, '#ff8c00'], ['APERTO', '#00ff41']],
        kv: [['Ultimo aggiornamento', Fmt.dateTime(e.date)], ['Quanto fa', Fmt.ago(e.date)], ['Coordinate', `${e.lat.toFixed(3)}, ${e.lon.toFixed(3)}`], ['Intensità', e.mag || '--']],
        buttons: [['🔍 ZOOM 3D', () => MapCtl.flyTo(e.lat, e.lon, 120000, { pitch: -40 })], ['🌦 METEO QUI', () => analyzePoint(e.lat, e.lon)], e.link ? ext(e.link, '↗ FONTE') : null, ext(`https://worldview.earthdata.nasa.gov/?v=${e.lon - 3},${e.lat - 2},${e.lon + 3},${e.lat + 2}`, '↗ Worldview')].filter(Boolean) });
      MapCtl.engine?.select({ kind: 'eonet', id, lat: e.lat, lon: e.lon });
      MapCtl.flyTo(e.lat, e.lon, 900000, { pitch: -55 });
    },
    news(id) {
      const n = News.get(id); if (!n) return false;
      openPanel({ title: '📰 NOTIZIA', icon: n.flag, name: n.title, nameCol: n.sev >= 0.7 ? '#ff6680' : 'var(--gd)', tags: [[n.src, '#00ccff'], n.hot ? ['⚡ CRISI', '#ff2244'] : null, n.place ? ['📍 ' + n.place.label, '#00ffcc'] : null].filter(Boolean),
        kv: [['Pubblicata', Fmt.dateTime(n.date) + ' · ' + Fmt.ago(n.date), true], ['Gravità stimata', h('span', null, h('span', { class: 'sevbar', style: 'width:80px' }, h('i', { style: `width:${n.sev * 100}%;background:${n.sev >= 0.7 ? 'var(--red)' : n.sev >= 0.45 ? 'var(--orn)' : 'var(--blu)'}` })), ' ' + Math.round(n.sev * 100) + '/100'), true],
          ['Categorie', n.cats.join(', ') || '--', true], n.desc ? ['Sommario', n.desc, true] : null],
        buttons: [n.link ? ext(n.link, '↗ APRI ARTICOLO') : null, n.link ? ext(`https://translate.google.com/translate?sl=auto&tl=it&u=${encodeURIComponent(n.link)}`, '🌐 TRADUCI') : null,
          ['🔊 LEGGI', () => TTS.enabled ? TTS.speak(n.title, { prio: true }) : Toast.show('Attiva prima la voce (T)', 'orn')], n.place ? ['📍 LUOGO', () => MapCtl.flyTo(n.place.lat, n.place.lon, 600000, { pitch: -50 })] : null].filter(Boolean) });
      if (n.place) MapCtl.engine?.select({ kind: 'news', id, lat: n.place.lat + n.jlat, lon: n.place.lon + n.jlon });
    },
    bases(i) { staticPanel('bases', DATA.BASES[+i], '🏴', 'BASE MILITARE', '#ff5500'); },
    nuclear(i) { staticPanel('nuclear', DATA.NUCLEAR[+i], '☢', 'SITO NUCLEARE', '#c040ff'); },
    choke(i) { staticPanel('choke', DATA.CHOKEPOINTS[+i], '⚓', 'STRETTO STRATEGICO', '#00ccff'); },
    conflict(i) { zonePanel(DATA.CONFLICT_ZONES[parseInt(i)], '⚔ ZONA DI CONFLITTO', '#ff2244'); },
    gps(i) { zonePanel(DATA.GPS_ZONES[parseInt(i)], '📡 INTERFERENZE GNSS', '#00ffcc'); },
    fire(i) {
      const f = S.fires[+i]; if (!f) return false;
      openPanel({ title: '🔥 INCENDIO · NASA FIRMS', icon: '🔥', name: `FRP ${Fmt.n(f.frp, 1)} MW`, nameCol: '#ff6a00', tags: [['satellitare', '#ff8c00']],
        kv: [['Rilevato', f.when + ' UTC'], ['Confidenza', f.conf || '--'], ['Coordinate', `${f.lat.toFixed(3)}, ${f.lon.toFixed(3)}`, true]],
        buttons: [['🔍 ZOOM', () => MapCtl.flyTo(f.lat, f.lon, 40000, { pitch: -40 })], ['🌡 ANALISI PUNTO', () => analyzePoint(f.lat, f.lon)]] });
    }
  };
  function sunlitTxt(p) { const s = Geo.sun(), sl = Geo.rad(s.lat), so = Geo.rad(s.lon); const sx = Math.cos(sl) * Math.cos(so), sy = Math.cos(sl) * Math.sin(so), sz = Math.sin(sl); const dot = p.x * sx + p.y * sy + p.z * sz; const lit = dot > 0 || Math.hypot(p.x - dot * sx, p.y - dot * sy, p.z - dot * sz) > 6371; return lit ? '☀ al sole' : '🌑 in ombra'; }
  function staticPanel(kind, p, icon, label, col) {
    if (!p) return false;
    const rc = p.risk === 'CRIT' ? '#ff2244' : p.risk === 'HIGH' ? '#ff8c00' : col;
    const near = S.acList.filter(a => a.isMil && Geo.dist(p.lat, p.lon, a.lat, a.lon) < 150);
    openPanel({ title: icon + ' ' + label + ' · REF', icon, name: p.name, nameCol: rc, tags: [[p.type, col], p.cc ? [p.cc, '#00ccff'] : null, p.risk ? ['RISCHIO ' + p.risk, rc] : null].filter(Boolean),
      kv: [['Coordinate', `${p.lat.toFixed(4)}, ${p.lon.toFixed(4)}`, true], ['Aerei militari entro 150 km (ADS-B)', near.length ? near.slice(0, 6).map(a => a.cs || a.hex).join(', ') + (near.length > 6 ? ` +${near.length - 6}` : '') : 'nessuno visibile', true],
        ['Notizie collegate (24h)', String(S.news.filter(n => n.place && Geo.dist(p.lat, p.lon, n.place.lat, n.place.lon) < 120).length)], ['Dato', 'pubblico, statico']],
      buttons: [['🛩 VISTA 3D', () => MapCtl.flyTo(p.lat, p.lon, 9000, { pitch: -30, heading: 20 })], ['🌡 ANALISI PUNTO', () => analyzePoint(p.lat, p.lon)],
        ext(`https://earth.google.com/web/@${p.lat},${p.lon},800a,3000d,35y`, '↗ Google Earth'), ext(`https://www.openstreetmap.org/?mlat=${p.lat}&mlon=${p.lon}#map=13/${p.lat}/${p.lon}`, '↗ OSM')] });
    MapCtl.engine?.select({ kind, id: p.name, lat: p.lat, lon: p.lon });
    MapCtl.flyTo(p.lat, p.lon, 60000, { pitch: -40 });
  }
  function zonePanel(z, title, col) {
    if (!z) return false;
    const news = S.news.filter(n => n.place && Geo.dist(z.lat, z.lon, n.place.lat, n.place.lon) < z.r + 50).slice(0, 5);
    openPanel({ title, icon: '◎', name: z.name, nameCol: col, tags: [['STIMA · area indicativa', '#ffd700']],
      kv: [['Centro', `${z.lat.toFixed(2)}, ${z.lon.toFixed(2)}`], ['Raggio', z.r + ' km']],
      extra: [h('div', { class: 'trk-sec' }, news.length ? [h('div', { style: 'color:var(--gd)' }, 'Ultime notizie dall\'area:'), news.map(n => h('div', { class: 'ni', onclick: () => select({ kind: 'news', id: n.id }) }, h('div', { class: 'ni-title' }, n.title), h('div', { class: 'ni-meta' }, n.src + ' · ' + Fmt.ago(n.date))))] : 'Nessuna notizia geolocalizzata nell\'area nelle ultime 48 ore.')],
      buttons: [['🔍 ZOOM', () => MapCtl.flyTo(z.lat, z.lon, z.r * 4000, { pitch: -50 })]] });
  }
  function showMany(items) {
    const list = items.map(r => r.kind === 'news' ? News.get(r.id) : null).filter(Boolean).sort((a, b) => b.sev - a.sev);
    if (!list.length) return;
    openPanel({ title: `📰 ${list.length} NOTIZIE IN QUEST'AREA`, icon: '📰', name: list[0].place?.label || 'Area', nameCol: '#00ffcc',
      extra: [h('div', null, list.slice(0, 40).map(n => h('div', { class: 'ni', onclick: () => select({ kind: 'news', id: n.id }) }, h('div', { class: 'ni-title', style: n.sev >= 0.7 ? 'color:#ff6680' : '' }, n.title), h('div', { class: 'ni-meta' }, `${n.src} · ${Fmt.ago(n.date)}`))))] });
  }
  function speakAc(a, d) {
    const c = DATA.AC_CLASS[a.cls] || DATA.AC_CLASS.civil;
    let t = `Bersaglio agganciato. ${c.label.toLowerCase()}`;
    if (a.cs) t += `, ${a.cs.split('').join(' ')}`;
    if (d?.route?.airline) t += `, ${d.route.airline}`;
    t += `. Quota ${Fmt.n(a.altM)} metri, velocità ${Fmt.n(a.gs * 1.852)} chilometri orari`;
    if (d?.route?.to) t += `. Diretto a ${d.route.to}`;
    if (!TTS.enabled) return Toast.show('Attiva la voce con 🔇 o tasto T', 'orn');
    TTS.speak(t + '.', { prio: true });
  }

  /* ═════ ANALISI DI UN PUNTO ═════ */
  async function analyzePoint(lat, lon) {
    sel = { kind: 'pt' }; clearInterval(trkTimer);
    const near = (list, f, km) => list.filter(x => Geo.dist(lat, lon, ...f(x)) < km);
    const se = Geo.sunElev(lat, lon), moon = Astro.moon();
    const nAc = near(S.acList, a => [a.lat, a.lon], 150), nEq = near(S.quakes, q => [q.lat, q.lon], 300), nNews = near(S.news.filter(n => n.place), n => [n.place.lat, n.place.lon], 200);
    const hs = DATA.HOTSPOTS.map(x => ({ x, d: Geo.dist(lat, lon, x.lat, x.lon) })).sort((a, b) => a.d - b.d)[0];
    const th = MapCtl.engine?.terrainHeight?.(lat, lon);
    const zones = [...DATA.CONFLICT_ZONES.map((z, i) => ['conflict', i, z, '⚔']), ...DATA.GPS_ZONES.map((z, i) => ['gps', i, z, '📡'])]
      .filter(([k, , z]) => MapCtl.isOn(k) && Geo.dist(lat, lon, z.lat, z.lon) <= z.r);
    openPanel({ title: '⌖ ANALISI PUNTO', icon: '⌖', name: '≈ ' + Intel.nearest(lat, lon).label, nameCol: '#00ffcc', tags: [['CALCOLO + DATI LIVE', '#00ffcc']],
      kv: [['Lat / Lon', `${lat.toFixed(5)}, ${lon.toFixed(5)}`, true], ['DMS', `${Fmt.dms(lat, true)} ${Fmt.dms(lon, false)}`, true],
        ['Quota terreno', h('span', { id: 'pt-elev' }, th != null && isFinite(th) ? Fmt.n(th) + ' m' : '…')], ['Sole', `${se.toFixed(1)}° ${se > 0 ? '☀ giorno' : se > -6 ? '🌆 crepuscolo civile' : se > -18 ? '🌌 crepuscolo' : '🌑 notte'}`],
        ['Luna', `${moon.name} ${Math.round(moon.illum * 100)}%`], ['Zona calda più vicina', `${hs.x.flag} ${hs.x.name} · ${Fmt.n(hs.d)} km`],
        zones.length ? ['Dentro le zone (stima)', zones.map(([, , z, ic]) => ic + ' ' + z.name).join(' · '), true] : null,
        ['Entro 150 km', `${nAc.length} aerei (${nAc.filter(a => a.isMil).length} mil.)`], ['Entro 300 km (sismi)', `${nEq.length} terremoti`], ['Notizie entro 200 km', String(nNews.length)]],
      extra: [h('div', { class: 'trk-sec', id: 'pt-geo' }, h('span', { class: 'spinner' }), ' luogo e meteo…')],
      buttons: [...zones.map(([k, i, z, ic]) => [ic + ' ' + z.name.split(' ')[0].toUpperCase(), () => select({ kind: k, id: String(i) })]),
        ['🛩 VISTA 3D', () => MapCtl.flyTo(lat, lon, 15000, { pitch: -30 })], ['🌬 WINDY', () => setWindy('wind', lat, lon)], ['📍 MIA POS.', () => setUserLoc({ lat, lon, label: 'punto scelto' })],
        ['📋 COPIA', () => navigator.clipboard?.writeText(`${lat.toFixed(5)}, ${lon.toFixed(5)}`).then(() => Toast.show('📋 Coordinate copiate', 'ok'))],
        ext(`https://earth.google.com/web/@${lat},${lon},500a,5000d,35y`, '↗ Google Earth')] });
    MapCtl.engine?.select({ kind: 'pt', id: 'pt', lat, lon });
    const [geo, wx, air, el] = await Promise.all([Weather.reverse(lat, lon), Weather.at(lat, lon).catch(() => null), Weather.air(lat, lon), th == null ? Weather.elevation(lat, lon) : Promise.resolve(null)]);
    if (sel?.kind !== 'pt') return;
    if (el != null) setText('pt-elev', Fmt.n(el) + ' m');
    const box = $('pt-geo'); if (!box) return;
    const nodes = [];
    if (geo) {
      nodes.push(h('div', { style: 'font-size:13px;color:var(--gd)' }, '📍 ' + ([geo.name, geo.region, geo.country].filter(Boolean).join(', ') || geo.ocean || 'Acque internazionali')));
      const nm = document.querySelector('#trkp .trk-name');   // titolo preciso dal geocoding inverso (non dal paese “più vicino”)
      if (nm) nm.textContent = geo.country ? (geo.name ? `${geo.name}, ${geo.country}` : geo.country) : (geo.ocean || 'Acque internazionali');
    }
    if (wx?.current) {
      const c = wx.current;
      nodes.push(h('div', null, `${Weather.ICON(c.weather_code)} ${Weather.WMO[c.weather_code] || '--'} · ${c.temperature_2m}°C (percepiti ${c.apparent_temperature}°C) · 💧${c.relative_humidity_2m}% · 💨 ${c.wind_speed_10m} km/h ${Geo.dir(c.wind_direction_10m)} (raff. ${c.wind_gusts_10m}) · ${c.pressure_msl} hPa · ☁ ${c.cloud_cover}%`),
        h('div', { class: 'dim' }, `Ora locale: ${new Date(Date.now() + (wx.utc_offset_seconds || 0) * 1000).toISOString().slice(11, 16)} (${wx.timezone || 'UTC'})`));
    }
    if (air) nodes.push(h('div', null, `🌫 Qualità aria (EAQI): ${air.european_aqi ?? '--'} · PM2.5 ${air.pm2_5 ?? '--'} · PM10 ${air.pm10 ?? '--'} µg/m³`));
    if (!nodes.length) nodes.push(h('span', { class: 'dim' }, 'Servizi meteo/geocoding non raggiungibili.'));
    box.replaceChildren(...nodes);
  }
  function setUserLoc(loc) { S.user = loc; Store.set('userLoc', loc); Toast.show(`📍 Posizione impostata: ${loc.label || loc.lat.toFixed(2) + ', ' + loc.lon.toFixed(2)}`, 'ok'); Bus.emit('userLoc', loc); }
  function locateMe() {
    return new Promise(res => {
      const viaIP = () => GeoIP.lookup('').then(d => { const l = { lat: d.lat, lon: d.lon, label: `${d.city} (da IP)` }; setUserLoc(l); res(l); }).catch(() => { Toast.show('⚠ Posizione non disponibile', 'orn'); res(null); });
      if (!navigator.geolocation) return viaIP();
      navigator.geolocation.getCurrentPosition(p => { const l = { lat: p.coords.latitude, lon: p.coords.longitude, h: p.coords.altitude || 0, label: 'la tua posizione (GPS)' }; setUserLoc(l); res(l); }, viaIP, { timeout: 8000, maximumAge: 600000 });
    });
  }

  /* ═════ MENU CONTESTUALE ═════ */
  function contextMenu(ll) {
    $('ctx-menu')?.remove();
    const items = [['⌖', 'Analizza questo punto', () => analyzePoint(ll.lat, ll.lon)], ['🛩', 'Vista 3D inclinata qui', () => MapCtl.flyTo(ll.lat, ll.lon, 20000, { pitch: -30 })],
      ['🔍', 'Zoom dall\'alto', () => MapCtl.flyTo(ll.lat, ll.lon, 80000)], ['🌬', 'Windy qui', () => setWindy('wind', ll.lat, ll.lon)],
      ['📍', 'Imposta come mia posizione', () => setUserLoc({ lat: ll.lat, lon: ll.lon, label: 'punto scelto' })],
      ['📋', 'Copia coordinate', () => navigator.clipboard?.writeText(`${ll.lat.toFixed(5)}, ${ll.lon.toFixed(5)}`).then(() => Toast.show('📋 Copiato', 'ok'))],
      ['🌍', 'Apri in Google Earth', () => window.open(`https://earth.google.com/web/@${ll.lat},${ll.lon},500a,8000d,35y`, '_blank', 'noopener')],
      ['🔊', 'Pronuncia posizione', () => TTS.speak(`Latitudine ${ll.lat.toFixed(2)}, longitudine ${ll.lon.toFixed(2)}, ${Intel.nearest(ll.lat, ll.lon).label}.`, { prio: true })]];
    const m = h('div', { id: 'ctx-menu' }, h('div', { id: 'ctx-menu-hdr' }, `📍 ${ll.lat.toFixed(4)}°, ${ll.lon.toFixed(4)}° · ${Intel.nearest(ll.lat, ll.lon).label}`),
      items.map(([i, l, f]) => h('div', { class: 'ctx-item', onclick: () => { m.remove(); f(); } }, h('span', null, i), h('span', null, l))));
    m.style.left = Math.min(ll.x, innerWidth - 230) + 'px'; m.style.top = Math.min(ll.y, innerHeight - 300) + 'px';
    document.body.appendChild(m);
    setTimeout(() => document.addEventListener('click', () => m.remove(), { once: true }), 50);
  }

  /* ═════ MODALI ═════ */
  function modal(title, body, foot = [], wide = false) {
    setText('modal-title', title);
    $('modal-box').style.width = wide ? 'min(900px,100%)' : '';
    setHTMLSafe('modal-body', body); setHTMLSafe('modal-foot', foot);
    $('modal').classList.add('open');
  }
  const closeModal = () => $('modal').classList.remove('open');

  function openBriefing() {
    const b = Intel.briefing();
    modal('🧠 BRIEFING AUTOMATICO · ' + Fmt.utc(b.t) + ' UTC', [
      h('div', { class: 'note warn', style: 'margin:-14px -14px 10px' }, 'Analisi automatica a regole su dati pubblici reali. L\'indice OJO non è un livello ufficiale (non è DEFCON).'),
      ...b.parts.map(p => h('p', { style: 'margin-bottom:8px' }, p)),
      h('h4', null, 'Composizione dell\'indice'),
      h('div', null, `Zona più calda ${Intel.glob.parts.zone} × 0,55 + media top-3 ${Intel.glob.parts.media} × 0,25 + emergenze aeree ${Intel.glob.parts.emerg} + meteo spaziale (Kp ${S.space.kp ?? '--'}) + sismi M7+ ${Intel.glob.parts.bigEq} = ${Intel.glob.idx}/100`),
      h('h4', null, 'Allerte recenti'),
      Intel.alerts.length ? Intel.alerts.slice(0, 15).map(a => h('div', { class: 'al-row al-' + a.level, onclick: () => { closeModal(); if (a.ref) select(a.ref); else if (a.lat != null) MapCtl.flyTo(a.lat, a.lon, 800000); } }, h('span', { class: 'al-t' }, Fmt.utc(a.t)), h('span', { class: 'al-x' }, `${a.icon || ''} ${a.title} — ${a.text || ''}`))) : h('div', { class: 'dim' }, 'Nessuna allerta.')
    ], [h('button', { class: 'btn', type: 'button', onclick: () => { TTS.enabled ? TTS.speak(b.speech, { prio: true }) : (TTS.toggle(true), setTimeout(() => TTS.speak(b.speech, { prio: true }), 600)); } }, '🔊 LEGGI AD ALTA VOCE'), h('button', { class: 'btn', type: 'button', onclick: closeModal }, 'CHIUDI')], true);
  }
  function openDossier(id) {
    const hsp = DATA.HOTSPOTS.find(x => x.id === id), sc = Intel.scores[id]; if (!hsp || !sc) return;
    MapCtl.flyTo(hsp.lat, hsp.lon, hsp.range, { pitch: -55 });
    const [bc, bl] = sevBadge(sc.score);
    modal(`${hsp.flag} DOSSIER · ${hsp.name.toUpperCase()}`, [
      h('div', { class: 'sg' }, [['Punteggio', sc.score, bc === 'b-crit' ? 'red' : bc === 'b-high' ? 'orn' : 'yel'], ['Base storica', sc.base, ''], ['Notizie (0-100)', sc.newsS, 'cyn'], ['Aria (0-100)', sc.airS, 'pur']]
        .map(([l, v, c]) => h('div', { class: 'sc' }, h('div', { class: 'sc-l' }, l), h('div', { class: 'sc-v ' + c }, String(v))))),
      h('p', { style: 'margin:8px 0' }, h('span', { class: 'badge ' + bc }, bl), ` Formula: base×0,5 + notizie×0,32 + attività aerea×0,18 + sismi M5+ ×5. Raggio di analisi ${hsp.r} km.`),
      h('div', { class: 'dossier-grid' },
        h('div', null, h('h4', null, `📰 Notizie 24h (${sc.news.length})`), sc.news.length ? sc.news.slice(0, 14).map(n => h('div', { class: 'ni', onclick: () => { closeModal(); select({ kind: 'news', id: n.id }); } }, h('div', { class: 'ni-title', style: n.sev >= 0.7 ? 'color:#ff6680' : '' }, n.title), h('div', { class: 'ni-meta' }, `${n.src} · ${Fmt.ago(n.date)}`))) : h('div', { class: 'dim' }, 'Nessuna')),
        h('div', null, h('h4', null, `✈ Militari ADS-B nell'area (${sc.mil.length})`), sc.mil.length ? sc.mil.slice(0, 20).map(a => h('div', { class: 'row', onclick: () => { closeModal(); select({ kind: 'ac', id: a.hex }); } }, h('span', { class: 'row-ico' }, DATA.AC_CLASS[a.cls].icon), h('div', { class: 'row-info' }, h('div', { class: 'row-name' }, a.cs || a.hex), h('div', { class: 'row-sub' }, `${DATA.AC_CLASS[a.cls].label} · ${a.type || '?'} · ${Fmt.n(a.altFt)} ft`)))) : h('div', { class: 'dim' }, 'Nessun militare con transponder visibile (molti voli militari non trasmettono).'),
          sc.eqs.length ? [h('h4', null, '🌍 Sismi M5+ 24h'), sc.eqs.map(q => h('div', { class: 'row', onclick: () => { closeModal(); select({ kind: 'eq', id: q.id }); } }, h('span', { class: 'eq-mag eq-hi' }, 'M' + q.mag.toFixed(1)), h('div', { class: 'row-info' }, h('div', { class: 'row-name' }, q.place))))] : null))
    ], [h('button', { class: 'btn', type: 'button', onclick: () => { closeModal(); MapCtl.flyTo(hsp.lat, hsp.lon, hsp.range * 0.6, { pitch: -35 }); } }, '🛩 VISTA 3D'), h('button', { class: 'btn', type: 'button', onclick: closeModal }, 'CHIUDI')], true);
  }
  function openSettings() {
    const inp = (id, val, type = 'text', ph = '') => h('input', { id, type, value: val || '', placeholder: ph, autocomplete: 'off', spellcheck: 'false' });
    const chk = (id, label, on) => h('label', { class: 'chk' }, h('input', { type: 'checkbox', id, checked: !!on }), label);
    modal('⚙ IMPOSTAZIONI', [
      h('h4', null, 'Chiavi (opzionali, salvate solo nel tuo browser)'),
      h('label', null, 'Cesium ion token'), h('div', { class: 'hint' }, 'Terreno mondiale HD, edifici 3D OSM, città fotorealistiche, Bing Aerial. Richiede ricarica.'), inp('st-ion', Settings.get('ionToken'), 'password'),
      h('label', null, 'NASA FIRMS map key'), inp('st-firms', Settings.get('firmsKey'), 'password'),
      h('label', null, 'Proxy CORS personale'), h('div', { class: 'hint' }, 'Es. il tuo Cloudflare Worker (vedi proxy/cloudflare-worker.js nel repo): https://tuo.workers.dev/?url={url} — rende affidabili notizie, mercati e ADS-B.'), inp('st-proxy', Settings.get('proxy'), 'text', 'https://…/?url={url}'),
      h('h4', null, 'Comportamento'),
      chk('st-tts', 'Voce italiana attiva', Settings.get('tts')), chk('st-ttsal', 'Leggi ad alta voce le allerte', Settings.get('ttsAlerts') !== false), chk('st-sound', 'Suoni di sistema', Settings.get('sound') !== false),
      chk('st-fly', 'Vola automaticamente sulle allerte gravi', Settings.get('autoFlyAlerts')), chk('st-labels', 'Etichette degli aerei militari', Settings.get('labels') !== false),
      chk('st-auto', 'Avvio automatico (salta la schermata iniziale)', Settings.get('autostart')),
      h('h4', null, 'Prestazioni'),
      h('label', null, 'Qualità grafica'), h('select', { id: 'st-q' }, [['auto', 'Normale (consigliata)'], ['high', 'Alta (GPU potenti: antialiasing 4×)'], ['low', 'Bassa (PC lenti)']].map(([v, l]) => h('option', { value: v, selected: Settings.get('quality') === v }, l))),
      h('label', null, 'Numero massimo di aerei disegnati'), inp('st-max', String(Settings.get('maxAircraft')), 'number'),
      chk('st-2d', 'Forza la mappa 2D (per computer senza GPU)', Store.get('force2d'))
    ], [
      h('button', { class: 'btn red', type: 'button', onclick: () => { if (confirm('Cancellare tutte le impostazioni e la cache di OJO?')) { Object.keys(localStorage).filter(k => k.startsWith('ojo.')).forEach(k => localStorage.removeItem(k)); location.reload(); } } }, 'RESET TOTALE'),
      h('button', { class: 'btn', type: 'button', onclick: () => { Net.forget(); Toast.show('Instradamento rete azzerato', 'ok'); } }, 'AZZERA ROTTE RETE'),
      h('button', { class: 'btn', type: 'button', onclick: () => {
        const needReload = $('st-ion').value.trim() !== (Settings.get('ionToken') || '') || !!$('st-2d').checked !== !!Store.get('force2d') || $('st-q').value !== Settings.get('quality');
        Settings.set('ionToken', $('st-ion').value.trim()); Settings.set('firmsKey', $('st-firms').value.trim()); Settings.set('proxy', $('st-proxy').value.trim());
        if (!!$('st-tts').checked !== TTS.enabled) TTS.toggle($('st-tts').checked);
        Settings.set('ttsAlerts', $('st-ttsal').checked); Settings.set('sound', $('st-sound').checked); Settings.set('autoFlyAlerts', $('st-fly').checked);
        Settings.set('labels', $('st-labels').checked); Settings.set('autostart', $('st-auto').checked); Settings.set('quality', $('st-q').value);
        Settings.set('maxAircraft', clamp(parseInt($('st-max').value) || 15000, 500, 60000)); Store.set('force2d', $('st-2d').checked);
        closeModal(); Toast.show('✓ Impostazioni salvate', 'ok'); Scheduler.runNow('firms');
        if (needReload && confirm('Alcune modifiche richiedono di ricaricare la pagina. Ricaricare ora?')) location.reload();
      } }, '💾 SALVA')
    ]);
  }
  function openHelp() {
    const K = [['/', 'Ricerca universale'], ['1 2 3', 'Globo 3D / 2.5D / 2D'], ['L', 'Layer'], ['S', 'Stato feed'], ['B', 'Briefing'], ['T', 'Voce on/off'], ['F', 'Mappa a schermo intero'], ['H', 'Vista orbitale'],
      ['R', 'Rotazione automatica'], ['G', 'La mia posizione'], ['V', 'Cambia visore (NRM/NVG/FLIR/CRT)'], ['A', 'Aerei on/off'], ['Esc', 'Chiudi / smetti di seguire'], ['?', 'Questo aiuto'], ['🛠', 'Ripristina la mappa']];
    modal('? AIUTO · OJO DE DEUS v100', [
      h('h4', null, 'Scorciatoie'), h('div', { class: 'sg g2' }, K.map(([k, d]) => h('div', { class: 'sc' }, h('kbd', null, k), ' ', d))),
      h('h4', null, 'Come si usa'),
      h('p', null, 'Clicca un oggetto sul globo (aereo, satellite, terremoto, notizia, base…) per il pannello bersaglio: puoi seguirlo, entrare in cockpit (aerei), vedere orbite e passaggi (satelliti). Clic su un punto vuoto = analisi del punto (meteo, quota, luogo, sole). Tasto destro = menu. Rotella/trascina = zoom e rotazione; Ctrl+trascina o tasto centrale = inclinazione 3D.'),
      h('h4', null, 'Video, aerei o borse non arrivano? Mappa nera?'),
      h('p', null, 'Apri OJO con l\'avviatore (AVVIA-OJO.bat su Windows, ojo-server.py su Mac/Linux): serve la pagina su http://localhost con un proxy integrato. Se la mappa è nera premi 🛠 o scrivi “reset” nel terminale. ', h('a', { href: '#', onclick: e => { e.preventDefault(); howToServe(); } }, 'Istruzioni dettagliate')),
      h('h4', null, 'Onestà dei dati'),
      h('p', null, 'LIVE = dato reale da API pubblica. CALC = calcolato da dati reali (orbite SGP4, indice OJO, sole). REF = riferimento statico pubblico. STIMA = area indicativa. Molti voli militari non trasmettono ADS-B: l\'assenza di un aereo non significa che non ci sia.'),
      h('h4', null, 'Fonti'),
      h('p', null, 'ADS-B: adsb.lol, airplanes.live, adsb.fi, OpenSky · Satelliti: CelesTrak + satellite.js · Terremoti: USGS · Eventi: NASA EONET/FIRMS · Spazio: NOAA SWPC · Radar: RainViewer · Notizie: BBC, Al Jazeera, ANSA, RaiNews, DW, Guardian, France24, NYT, NPR, Sky, Defense News, Times of Israel, GDELT · Mercati: Yahoo/Stooq, CoinGecko, BCE · Meteo: Open-Meteo · Geocoding: BigDataCloud · Mappe: Esri, OSM, NASA GIBS · Terreno: AWS Terrain Tiles / Cesium ion · Motore: CesiumJS.')
    ], [h('button', { class: 'btn', type: 'button', onclick: closeModal }, 'OK')], true);
  }

  /* ═════ TOPBAR ═════ */
  function clock() {
    const n = new Date();
    $('t-clk').replaceChildren(`${pad2(n.getUTCHours())}:${pad2(n.getUTCMinutes())}:${pad2(n.getUTCSeconds())} UTC`, h('small', null, n.toLocaleTimeString('it-IT') + ' locale'));
  }
  function renderThreat() {
    const g = Intel.glob, b = $('threat-badge');
    b.className = 'threat ' + LVL_CLS[g.lvl];
    b.replaceChildren(`ALLERTA ${g.lvl}`, h('small', null, `${g.idx}/100`));
    $('hotnav').replaceChildren(...DATA.HOTSPOTS.map(x => {
      const s = Intel.scores[x.id]?.score;
      return h('button', { class: 'tnav', type: 'button', title: `${x.name} — indice ${s ?? '--'}/100`, onclick: () => MapCtl.flyTo(x.lat, x.lon, x.range, { pitch: -55 }) },
        h('span', null, x.flag), h('span', { class: 'lbl' }, x.id), s != null ? h('span', { class: 'sc ' + sevCls(s) }, String(s)) : null);
    }));
    $('hot-list').replaceChildren(...Object.values(Intel.scores).sort((a, b) => b.score - a.score).map(s => {
      const x = DATA.HOTSPOTS.find(z => z.id === s.id), [bc, bl] = sevBadge(s.score), colr = s.score >= 70 ? 'var(--red)' : s.score >= 55 ? 'var(--orn)' : s.score >= 40 ? 'var(--yel)' : 'var(--g)';
      return h('div', { class: 'ci-item', title: `base ${s.base} · notizie ${s.newsS} · aria ${s.airS}`, onclick: () => openDossier(s.id) },
        h('span', null, x.flag), h('span', { style: 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap' }, x.name, h('div', { class: 'row-sub' }, `${s.news.length} notizie · ${s.mil.length} mil.`)),
        h('div', { class: 'ci-bar-wrap' }, h('div', { class: 'ci-bar', style: `width:${s.score}%;background:${colr}` })), h('span', { class: 'ci-score', style: `color:${colr}` }, String(s.score)), h('span', { class: 'badge ' + bc }, bl));
    }));
  }

  /* ═════ PANNELLI DASHBOARD ═════ */
  function renderAdsb() {
    const l = S.acList, mil = l.filter(a => a.isMil);
    setText('ac-tot', Fmt.n(l.length)); setText('ac-mil', Fmt.n(mil.length)); setText('ac-isr', Fmt.n(mil.filter(a => ['isr', 'tanker', 'drone'].includes(a.cls)).length)); setText('ac-emg', l.filter(a => a.emerg).length);
    setText('ac-hdr', Fmt.n(l.length)); setText('st-ac', Fmt.n(l.length)); setText('sb-ac', Fmt.n(l.length));
    const u = ADSB.used; setText('ac-src', [u.area, u.mil, u.global].filter(x => x !== '--').join(' + ') || 'offline'); setText('ac-upd', ADSB.lastUpdate ? Fmt.utc(ADSB.lastUpdate, true) : '--');
    const f = ADSB.filtered().slice(0, 80);
    $('ac-list').replaceChildren(...(f.length ? f.map(a => { const c = DATA.AC_CLASS[a.cls] || DATA.AC_CLASS.civil; return h('div', { class: 'row', onclick: () => select({ kind: 'ac', id: a.hex }) },
      h('span', { class: 'row-ico', style: `color:${a.emerg ? '#ff2244' : c.col}` }, a.emerg ? '🆘' : c.icon),
      h('div', { class: 'row-info' }, h('div', { class: 'row-name', style: `color:${a.emerg ? '#ff6680' : c.col}` }, a.cs || a.hex.toUpperCase()), h('div', { class: 'row-sub' }, `${a.emerg || c.label} · ${a.type || '?'}${a.reg ? ' · ' + a.reg : ''}`)),
      h('span', { class: 'row-r' }, Fmt.n(a.altFt) + ' ft', h('div', { class: 'row-sub' }, Fmt.n(a.gs) + ' kt'))); }) : [S.acList.length ? h('div', { class: 'empty' }, 'Nessun aereo con questo filtro')
      : Health.status('adsb') === 'err' ? h('div', { class: 'empty', style: 'text-align:left;color:var(--orn)' }, '⚠ Le fonti ADS-B non permettono la lettura diretta dal browser e i proxy pubblici ora non rispondono. ',
        h('a', { href: '#', onclick: e => { e.preventDefault(); howToServe(); } }, 'Apri OJO con l\'avviatore (proxy integrato)'), ' oppure imposta un proxy personale in ⚙.')
      : h('div', { class: 'empty' }, 'In attesa dei dati ADS-B…')]));
  }
  function renderNuke() {
    $('nuke-list').replaceChildren(...DATA.NUCLEAR.map((p, i) => { const [bc] = p.risk === 'CRIT' ? ['b-crit'] : p.risk === 'HIGH' ? ['b-high'] : p.risk === 'MED' ? ['b-med'] : ['b-low'];
      return h('div', { class: 'row', onclick: () => select({ kind: 'nuclear', id: String(i) }) }, h('span', { class: 'row-ico' }, '☢'), h('div', { class: 'row-info' }, h('div', { class: 'row-name' }, p.name), h('div', { class: 'row-sub' }, `${p.cc} · ${p.type}`)), h('span', { class: 'badge ' + bc }, p.risk)); }));
  }
  function renderBrief() {
    const b = Intel.briefing();
    $('brief-text').replaceChildren(...b.parts.slice(0, 4).map(p => h('div', { style: 'margin-bottom:4px' }, p)));
    setText('brief-time', 'agg. ' + Fmt.utc(b.t) + ' UTC');
  }
  function renderAlerts() {
    const a = Intel.alerts; setText('alert-cnt', a.length);
    $('alert-list').replaceChildren(...(a.length ? a.slice(0, 30).map(x => h('div', { class: 'al-row al-' + x.level, onclick: () => { if (x.ref) select(x.ref); else if (x.lat != null) MapCtl.flyTo(x.lat, x.lon, 800000, { pitch: -50 }); } },
      h('span', { class: 'al-t' }, Fmt.utc(x.t)), h('span', { class: 'al-x' }, `${x.icon || ''} ${x.title}`, h('div', { class: 'row-sub', style: 'white-space:normal' }, x.text || '')))) : [h('div', { class: 'empty' }, 'Nessuna anomalia rilevata')]));
  }
  function renderISS(d) {
    setText('iss-lat', d.lat.toFixed(2) + '°'); setText('iss-lon', d.lon.toFixed(2) + '°'); setText('iss-alt', Fmt.n(d.alt)); setText('iss-vel', Fmt.n(d.vel));
    const dot = $('iss-dot'); if (dot) { dot.style.left = ((d.lon + 180) / 360 * 84) + 'px'; dot.style.top = ((90 - d.lat) / 180 * 84) + 'px'; }
    setText('iss-over', 'Sopra: ' + Intel.nearest(d.lat, d.lon).label);
    setText('iss-vis', (d.vis === 'daylight' ? '☀ alla luce del sole' : d.vis === 'eclipsed' ? '🌑 nell\'ombra della Terra' : '') + ' · ' + d.src);
  }
  function renderPasses(list, loc) {
    $('iss-pass').replaceChildren(...(list.length ? [h('div', { class: 'note' }, `Da ${loc.label || 'posizione'} (${loc.lat.toFixed(2)}, ${loc.lon.toFixed(2)}) · elevazione > 10°`), ...list.map(p => h('div', { class: 'row', style: 'cursor:default' },
      h('span', { class: 'row-ico' }, p.visible ? '👁' : '📡'), h('div', { class: 'row-info' }, h('div', { class: 'row-name' }, Fmt.dateTime(p.start)), h('div', { class: 'row-sub' }, `${Geo.dir(p.azStart)} → ${Geo.dir(p.azEnd)} · ${Math.round((p.end - p.start) / 60000)} min`)),
      h('span', { class: 'row-r' }, `max ${Math.round(p.maxEl)}°`, h('div', { class: 'row-sub' }, p.visible ? 'visibile a occhio nudo' : p.dark ? 'in ombra' : 'di giorno'))))] : [h('div', { class: 'empty' }, 'Nessun passaggio nelle prossime 36 ore')]));
  }
  let satQ = '';
  function renderSats(list) {
    const on = Sats.groupOn;
    setText('sat-tot', Fmt.n(list.filter(s => s.show).length)); setText('st-sat', Fmt.n(list.filter(s => s.show).length)); setText('sb-sat', Fmt.n(list.length));
    const cnt = {}; list.forEach(s => { cnt[s.group] = (cnt[s.group] || 0) + 1; });
    $('sat-groups').replaceChildren(...DATA.SAT_GROUPS.map(g => h('div', { class: 'sc', style: `cursor:pointer;opacity:${on[g.id] ? 1 : 0.4}`, title: 'Clic per attivare/disattivare', onclick: () => { Sats.setGroup(g.id, !on[g.id]); setTimeout(() => renderSats(S.sats), 300); } },
      h('div', { class: 'sc-l', style: `color:${g.col}` }, (on[g.id] ? '● ' : '○ ') + g.label), h('div', { class: 'sc-v', style: 'font-size:13px' }, on[g.id] ? (cnt[g.id] != null ? Fmt.n(cnt[g.id]) : '…') : 'off'))));
    const q = satQ.trim().toUpperCase();
    const res = (q ? list.filter(s => s.name.toUpperCase().includes(q) || s.id === q) : list.filter(s => s.special)).slice(0, 30);
    $('sat-list').replaceChildren(...res.map(s => h('div', { class: 'row', onclick: () => select({ kind: 'sat', id: s.id }) }, h('span', { class: 'row-ico', style: `color:${s.col}` }, '🛰'),
      h('div', { class: 'row-info' }, h('div', { class: 'row-name' }, s.name), h('div', { class: 'row-sub' }, `NORAD ${s.id} · ${(DATA.SAT_GROUPS.find(g => g.id === s.group) || {}).label}`)), h('span', { class: 'row-r' }, Fmt.n(s.altKm) + ' km'))));
  }
  function spark(cv, data, color) {
    if (!cv || !data || data.length < 2) return;
    const W = cv.width, H = cv.height, x = cv.getContext('2d'); x.clearRect(0, 0, W, H);
    const mn = Math.min(...data), mx = Math.max(...data), rg = mx - mn || 1;
    x.strokeStyle = color; x.lineWidth = 1.4; x.beginPath();
    data.forEach((v, i) => { const px = i / (data.length - 1) * (W - 2) + 1, py = H - 2 - (v - mn) / rg * (H - 4); i ? x.lineTo(px, py) : x.moveTo(px, py); });
    x.stroke();
  }
  function renderSpace(sp) {
    const kp = $('kp-v'); if (sp.kp != null && kp) { kp.textContent = sp.kp.toFixed(1) + (sp.kp >= 7 ? ' · forte' : sp.kp >= 5 ? ' · tempesta' : sp.kp >= 4 ? ' · attivo' : ' · quieto'); kp.style.color = sp.kp >= 7 ? 'var(--red)' : sp.kp >= 5 ? 'var(--orn)' : sp.kp >= 4 ? 'var(--yel)' : 'var(--g)'; }
    if (sp.kpHist) spark($('kp-spark'), sp.kpHist, '#ffd700');
    if (sp.scales) setText('scale-v', `R${sp.scales.R} / S${sp.scales.S} / G${sp.scales.G}`);
    if (sp.wind) setText('sw-v', `${Math.round(sp.wind)} km/s · ${sp.dens?.toFixed?.(1) ?? '--'} p/cm³`);
    if (sp.bt != null && isFinite(sp.bt)) setText('bz-v', `${sp.bt.toFixed(1)} / ${sp.bz.toFixed(1)} nT${sp.bz < -10 ? ' ⚠' : ''}`);
    if (sp.flare) setText('xr-v', sp.flare);
    if (sp.auroraMax != null) setText('aur-v', `${sp.auroraMax}%`);
  }
  function renderNews() {
    const list = News.filtered();
    setText('news-cnt', Fmt.n(list.length));
    $('news-list').replaceChildren(...(list.length ? list.slice(0, 90).map(n => {
      const meta = h('div', { class: 'ni-meta' }, h('span', { class: 'ni-src' }, n.src), h('span', null, Fmt.ago(n.date)),
        h('span', { class: 'sevbar', title: 'gravità stimata' }, h('i', { style: `width:${n.sev * 100}%;background:${n.sev >= 0.7 ? 'var(--red)' : n.sev >= 0.45 ? 'var(--orn)' : 'var(--blu)'}` })),
        n.hot ? h('span', { class: 'ni-hot' }, '⚡') : null,
        n.place ? h('span', { class: 'ni-geo', title: 'Vola sul luogo', onclick: e => { e.stopPropagation(); select({ kind: 'news', id: n.id }); MapCtl.flyTo(n.place.lat, n.place.lon, 700000, { pitch: -50 }); } }, '📍 ' + n.place.label) : null,
        n.link ? h('a', { class: 'ni-tr', href: `https://translate.google.com/translate?sl=auto&tl=it&u=${encodeURIComponent(n.link)}`, target: '_blank', rel: 'noopener', onclick: e => e.stopPropagation() }, 'traduci') : null);
      return h('div', { class: 'ni', onclick: () => select({ kind: 'news', id: n.id }) }, h('div', { class: 'ni-title', style: n.sev >= 0.7 ? 'color:#ff7a90' : '' }, `${n.flag} ${n.title}`), meta);
    }) : [h('div', { class: 'empty' }, S.news.length ? 'Nessuna notizia con questo filtro' : 'Nessuna notizia ancora (le fonti RSS passano da proxy CORS: possono essere lente)')]));
    const hot = S.news.filter(n => n.hot).slice(0, 14);
    const track = $('ticker-track');
    if (track && hot.length) {
      const mk = () => hot.map(n => h('span', { class: 'tk', onclick: () => select({ kind: 'news', id: n.id }) }, h('b', null, `[${n.src}] `), n.title));
      track.replaceChildren(...mk(), ...mk());
    }
  }
  function renderQuakes() {
    const l = S.quakes, now = Date.now();
    const d24 = l.filter(q => now - q.time < 24 * 3600e3);
    setText('eq-m5', l.filter(q => q.mag >= 5).length); setText('eq-tot', Fmt.n(l.length)); setText('eq-tsu', l.filter(q => q.tsunami).length);
    const mx = l.reduce((m, q) => Math.max(m, q.mag), 0); setText('eq-max', l.length ? 'M' + mx.toFixed(1) : '--');
    setText('eq-hdr', Fmt.n(l.length)); setText('st-eq', Fmt.n(d24.length || l.length)); setText('sb-eqn', Fmt.n(l.length));
    const sorted = l.slice().sort((a, b) => (b.mag >= 4.5) - (a.mag >= 4.5) || b.time - a.time).slice(0, 60);
    $('eq-list').replaceChildren(...sorted.map(q => h('div', { class: 'row', onclick: () => select({ kind: 'eq', id: q.id }) },
      h('span', { class: 'eq-mag ' + (q.mag >= 6 ? 'eq-hi' : q.mag >= 4.5 ? 'eq-md' : 'eq-lo') }, 'M' + q.mag.toFixed(1)),
      h('div', { class: 'row-info' }, h('div', { class: 'row-name' }, q.place), h('div', { class: 'row-sub' }, `${Fmt.ago(q.time)} · prof. ${Math.round(q.depth)} km${q.tsunami ? ' · ⚠ tsunami' : ''}`)))));
  }
  let eoFilter = 'all';
  function renderEonet() {
    const l = S.eonet; setText('eo-hdr', Fmt.n(l.length));
    const cats = {}; l.forEach(e => { cats[e.cat] = (cats[e.cat] || 0) + 1; });
    $('eo-filter').replaceChildren(h('button', { class: 'fp-btn' + (eoFilter === 'all' ? ' act' : ''), type: 'button', onclick: () => { eoFilter = 'all'; renderEonet(); } }, 'TUTTI'),
      ...Object.entries(cats).sort((a, b) => b[1] - a[1]).map(([c, n]) => h('button', { class: 'fp-btn' + (eoFilter === c ? ' act' : ''), type: 'button', title: (DATA.EONET[c] || ['', c])[1], onclick: () => { eoFilter = c; renderEonet(); } }, `${(DATA.EONET[c] || ['⚠'])[0]} ${n}`)));
    const f = l.filter(e => eoFilter === 'all' || e.cat === eoFilter).slice(0, 80);
    $('eo-list').replaceChildren(...f.map(e => h('div', { class: 'row', onclick: () => select({ kind: 'eonet', id: e.id }) }, h('span', { class: 'row-ico' }, (DATA.EONET[e.cat] || ['⚠'])[0]),
      h('div', { class: 'row-info' }, h('div', { class: 'row-name' }, e.title), h('div', { class: 'row-sub' }, `${(DATA.EONET[e.cat] || ['', e.catTitle])[1]} · ${Fmt.ago(e.date)}${e.mag ? ' · ' + e.mag : ''}`)))));
  }
  function mkRow(name, sub, q, id) {
    const cv = h('canvas', { class: 'spark', width: 54, height: 18 });
    const row = h('div', { class: 'mk', id }, h('div', { class: 'mk-n' }, name, sub ? h('small', null, sub) : null), cv,
      h('div', { class: 'mk-p' }, q ? Fmt.price(q.price) : '--'), h('div', { class: 'mk-c ' + (q?.chg == null ? '' : q.chg >= 0 ? 'up' : 'dn') }, q ? Fmt.pct(q.chg) : 'N/D'));
    if (q?.spark) spark(cv, q.spark, q.chg >= 0 ? '#00ff41' : '#ff2244');
    return row;
  }
  function renderMarkets() {
    const Q = Markets.Q;
    for (const [tab, list] of [['mkt-idx', DATA.MARKETS.idx], ['mkt-com', DATA.MARKETS.com], ['mkt-def', DATA.MARKETS.def]])
      $(tab).replaceChildren(...list.map(([s, n]) => mkRow(n, s + (Q[s]?.src && Q[s].src !== 'Yahoo' ? ' · ' + Q[s].src : ''), Q[s])));
    $('mkt-cry').replaceChildren(...DATA.CRYPTO.map(([id, sym]) => mkRow(sym, Markets.cry[id]?.src || '', Markets.cry[id])));
    $('mkt-fx').replaceChildren(...DATA.FX.map(([cc, lbl]) => mkRow(lbl, Markets.fx[cc]?.date ? 'BCE ' + Markets.fx[cc].date : '', Markets.fx[cc])));
    const b = Markets.cry.bitcoin; if (b) setText('sb-btc', '$' + Fmt.n(b.price));
  }
  function renderSky() {
    const s = Geo.sun(), v = view(), el = Geo.sunElev(v.lat, v.lon), m = Astro.moon();
    setText('sun-sub', `${Fmt.lat(s.lat).replace(/\.\d+/, m2 => m2.slice(0, 3))} ${Fmt.lon(s.lon).replace(/\.\d+/, m2 => m2.slice(0, 3))}`);
    setText('sun-here', `${el.toFixed(1)}° ${el > 0 ? '☀ giorno' : el > -6 ? '🌆 crepuscolo' : '🌑 notte'}`);
    setText('sun-dark', `${m.name} · ${Math.round(m.illum * 100)}% · ${m.age.toFixed(1)} giorni`);
  }
  async function weatherCity() {
    const q = $('wx-inp').value.trim(); if (!q) return;
    const out = $('wx-result'); out.replaceChildren(h('div', { class: 't-line' }, h('span', { class: 'spinner' }), ' cerco ' + q + '…'));
    try {
      const pl = (await Weather.geocode(q))[0]; if (!pl) { out.replaceChildren(h('div', { class: 't-line red' }, 'Città non trovata')); return; }
      await weatherAt(pl.lat, pl.lon, `${pl.name}${pl.admin ? ', ' + pl.admin : ''} (${pl.cc})`);
      MapCtl.flyTo(pl.lat, pl.lon, 60000, { pitch: -35 });
    } catch (e) { out.replaceChildren(h('div', { class: 't-line red' }, 'Errore meteo: ' + e.message)); Health.fail('weather', e); }
  }
  async function weatherAt(lat, lon, label) {
    const out = $('wx-result');
    const [wx, air] = await Promise.all([Weather.at(lat, lon), Weather.air(lat, lon)]);
    const c = wx.current, hr = wx.hourly;
    const cv = h('canvas', { width: 260, height: 40, style: 'width:100%;height:40px;margin-top:4px' });
    out.replaceChildren(
      h('div', { style: 'font-size:14px;color:var(--g)' }, `${Weather.ICON(c.weather_code)} ${label || lat.toFixed(2) + ', ' + lon.toFixed(2)} — ${c.temperature_2m}°C`),
      h('div', { class: 't-line' }, `${Weather.WMO[c.weather_code] || '--'} · percepiti ${c.apparent_temperature}°C · 💧 ${c.relative_humidity_2m}% · ☁ ${c.cloud_cover}%`),
      h('div', { class: 't-line' }, `💨 ${c.wind_speed_10m} km/h da ${Geo.dir(c.wind_direction_10m)} (raffiche ${c.wind_gusts_10m}) · ${c.pressure_msl} hPa · 🌧 ${c.precipitation} mm`),
      air ? h('div', { class: 't-line' }, `🌫 EAQI ${air.european_aqi ?? '--'} · PM2.5 ${air.pm2_5 ?? '--'} µg/m³`) : null,
      h('div', { class: 't-line dim' }, `Prossime 24h: min ${Math.min(...hr.temperature_2m)}°C · max ${Math.max(...hr.temperature_2m)}°C · pioggia max ${Math.max(...(hr.precipitation_probability || [0]))}%`), cv);
    spark(cv, hr.temperature_2m, '#00aaff');
  }
  async function traceIP() {
    const raw = $('ip-inp').value.trim(); if (!raw) return;
    const out = $('geo-result'); const line = (...k) => h('div', { class: 't-line' }, ...k);
    out.replaceChildren(line(h('span', { class: 'spinner' }), ` trace ${raw}…`));
    try {
      let ip = raw, host = '';
      if (!/^[\d.]+$|:/.test(raw)) { host = raw.replace(/^https?:\/\//, '').split('/')[0]; const ips = await GeoIP.resolve(host); ip = ips[0]; out.appendChild(line(h('span', { class: 'ok' }, 'DNS: '), `${host} → ${ips.join(', ')}`)); }
      const d = await GeoIP.lookup(ip);
      [['IP', d.ip], ['LUOGO', [d.city, d.region, d.country].filter(Boolean).join(', ')], ['RETE', [d.asn, d.org].filter(Boolean).join(' · ')], ['FUSO', d.tz]].forEach(([l, v]) => out.appendChild(line(h('span', { class: 'ok' }, l + ': '), v || '--')));
      if (isFinite(d.lat)) {
        let me = S.user; if (!me) { try { const m = await GeoIP.lookup(''); me = { lat: m.lat, lon: m.lon }; } catch {} }
        if (me) { MapCtl.render('trace', { from: me, to: { lat: d.lat, lon: d.lon, label: host || d.ip } }); out.appendChild(line(h('span', { class: 'ok' }, 'DISTANZA: '), Fmt.n(Geo.dist(me.lat, me.lon, d.lat, d.lon)) + ' km dalla tua posizione')); }
        MapCtl.flyTo(d.lat, d.lon, 1.8e6, { pitch: -60 });
      }
    } catch (e) { out.appendChild(line(h('span', { class: 'red' }, '// errore: ' + e.message))); Health.fail('geoip', e); }
  }

  /* ═════ TV / WEBCAM / WINDY ═════ */
  const tvList = () => Store.get('tvList') || DATA.TV;
  const camList = () => Store.get('camList') || DATA.WEBCAMS;
  let tvActive = null;
  const FROM_FILE = location.protocol === 'file:';
  const ytPage = c => c.video ? `https://www.youtube.com/watch?v=${c.video}` : c.ch ? `https://www.youtube.com/channel/${c.ch}/live` : `https://www.youtube.com/watch?v=${c.yt}`;
  function ytPopup(c) { const w = window.open(ytPage(c), 'ojo-yt', 'popup,width=1000,height=600'); if (!w) window.open(ytPage(c), '_blank', 'noopener'); }
  function fileNotice(ph, c, name) {
    ph.classList.remove('hidden');
    ph.replaceChildren(h('div', { style: 'font-size:22px' }, '⚠'),
      h('div', null, h('b', null, 'YouTube blocca i video nelle pagine aperte come file'), ' (Errore 153). ', name, ' è stato aperto in una finestra a parte.'),
      h('div', null, h('button', { class: 'pl-btn', type: 'button', onclick: () => ytPopup(c) }, '▶ RIAPRI IN FINESTRA'), ' ', h('button', { class: 'pl-btn', type: 'button', onclick: howToServe }, 'ℹ COME RISOLVERE')));
  }
  function howToServe() {
    modal('ℹ VIDEO, AEREI E BORSE: APRI OJO CON L\'AVVIATORE', [
      h('p', null, 'Quando apri ', h('code', null, 'index.html'), ' con un doppio clic, il browser lo tratta come “file” e: YouTube rifiuta i video (Errore 153) e varie fonti (aerei ADS-B, borse) non si possono leggere.'),
      h('h4', null, 'Soluzione 1 — Windows (consigliata)'),
      h('p', null, 'Metti ', h('b', null, 'AVVIA-OJO.bat'), ' nella stessa cartella di index.html e fai doppio clic. Si apre il browser su ', h('code', null, 'http://localhost:8765'), ' con un proxy integrato: video, notizie, aerei e borse funzionano. Se Windows mostra “PC protetto”, clicca “Ulteriori informazioni → Esegui comunque”.'),
      h('h4', null, 'Soluzione 2 — Mac / Linux'),
      h('p', null, 'Nella cartella di index.html: ', h('code', null, 'python3 ojo-server.py')),
      h('h4', null, 'Soluzione 3 — online'),
      h('p', null, 'Su GitHub: Settings → Pages → Branch ', h('code', null, 'claude/happy-tesla-ov2h7v'), ' → cartella /root → Save. Dopo un minuto OJO è su https://maikbarre2401-svg.github.io/gioco/ (video OK; per aerei e borse affidabili aggiungi il proxy personale in ⚙).'),
      h('p', null, 'File scaricabili dal repository: ', h('a', { href: 'https://github.com/maikbarre2401-svg/gioco/tree/claude/happy-tesla-ov2h7v', target: '_blank', rel: 'noopener' }, 'github.com/maikbarre2401-svg/gioco'))
    ], [h('button', { class: 'btn', type: 'button', onclick: closeModal }, 'OK')]);
  }
  const tvURL = (c, mute = 1) => c.video ? `https://www.youtube.com/embed/${c.video}?autoplay=1&mute=${mute}&rel=0&playsinline=1` : `https://www.youtube.com/embed/live_stream?channel=${c.ch}&autoplay=1&mute=${mute}&rel=0&playsinline=1`;
  function buildTV() {
    const grids = { news: $('tv-grid-news'), war: $('tv-grid-war'), sci: $('tv-grid-sci') };
    Object.values(grids).forEach(g => g.replaceChildren());
    tvList().forEach(c => (grids[c.cat] || grids.news).appendChild(h('button', { class: 'tv-btn' + (tvActive === c.id ? ' act' : ''), type: 'button', dataset: { tv: c.id }, onclick: () => playTV(c.id) }, h('span', { class: 'tv-live-dot' }), `${c.flag || '📺'} ${c.label}`)));
  }
  function playTV(id) {
    const c = tvList().find(x => x.id === id); if (!c) return false;
    tvActive = id;
    document.querySelectorAll('.tv-btn').forEach(b => b.classList.toggle('act', b.dataset.tv === id));
    setText('tv-name', `${c.flag || ''} ${c.label}`);
    if (FROM_FILE) { ytPopup(c); fileNotice($('tv-ph'), c, c.label); return true; }
    $('tv-ph').classList.add('hidden');
    $('tv-iframe').src = tvURL(c, 1);
    Toast.show(`📺 ${c.label} (audio disattivato: attivalo dal player)`, 'ok');
    if (c.ch) checkChannel(c.ch).then(r => {
      if (tvActive !== id) return;
      if (r.ok && r.title) setText('tv-name', `${c.flag || ''} ${r.title} ✓`);
      if (r.ok === false) deadNotice($('tv-ph'), $('tv-iframe'), `Il canale “${c.label}” non esiste su YouTube`, 'l\'ID ' + c.ch + ' è sbagliato o il canale è stato chiuso', 'tv');
    });
    return true;
  }
  function deadNotice(ph, frame, title, why, kind) {
    frame.src = 'about:blank'; ph.classList.remove('hidden');
    ph.replaceChildren(h('div', { style: 'font-size:22px' }, kind === 'tv' ? '📺' : '📹'), h('div', null, h('b', null, title), ` (${why}).`),
      h('div', null, h('button', { class: 'pl-btn', type: 'button', onclick: () => kind === 'tv' ? $('tv-yt').click() : $('wc-search').click() }, '🔎 CERCA SU YOUTUBE'), ' ',
        h('button', { class: 'pl-btn', type: 'button', onclick: () => editList(kind === 'tv' ? 'tv' : 'cam') }, '✎ CORREGGI')));
  }
  const chCache = new Map();
  async function checkChannel(ch) {    // feed RSS ufficiale del canale: {ok:true,title} | {ok:false} | {ok:null}
    if (chCache.has(ch)) return chCache.get(ch);
    let res = { ok: null };
    try {
      const r = await Net.get(`https://www.youtube.com/feeds/videos.xml?channel_id=${encodeURIComponent(ch)}`, { type: 'text', timeout: 9000, validate: t => /<feed[\s>]/.test(t) });
      const m = r.data.match(/<title>([^<]{1,120})<\/title>/); res = { ok: true, title: m ? m[1].replace(/&amp;/g, '&') : '' };
    } catch (e) { if (e.status === 404 || e.status === 410) res = { ok: false }; }
    chCache.set(ch, res); return res;
  }
  function editList(kind) {
    const isTV = kind === 'tv';
    const lines = isTV ? tvList().map(c => [c.cat, c.label, c.video ? 'video:' + c.video : c.ch, c.flag || ''].join(' | ')) : camList().map(c => [c.city, c.lat, c.lon, c.ch ? 'channel:' + c.ch : c.yt, c.flag || ''].join(' | '));
    const ta = h('textarea', { id: 'ed-ta', style: 'min-height:260px' }); ta.value = lines.join('\n');
    modal(isTV ? '✎ CANALI TV' : '✎ WEBCAM', [
      h('div', { class: 'hint' }, isTV ? 'Una riga per canale: categoria (news|war|sci) | nome | ID canale YouTube (UC…) oppure video:ID | emoji. Con l\'ID canale viene caricata la diretta attuale.' : 'Una riga per webcam: città | lat | lon | link o ID del video YouTube (oppure channel:UC… per la diretta di un canale) | emoji. Trovi webcam nuove con 🔎 (filtro “Dal vivo”): copia il link e incollalo qui.'), ta
    ], [h('button', { class: 'btn red', type: 'button', onclick: () => { Store.del(isTV ? 'tvList' : 'camList'); closeModal(); isTV ? buildTV() : buildCams(); Toast.show('Elenco ripristinato', 'ok'); } }, 'RIPRISTINA'),
      h('button', { class: 'btn', type: 'button', onclick: () => {
        const rows = $('ed-ta').value.split('\n').map(l => l.split('|').map(s => s.trim())).filter(r => r.length >= 3 && r[0]);
        if (isTV) Store.set('tvList', rows.map((r, i) => { const v = /^video:/i.test(r[2]) ? r[2].slice(6) : null; return { id: 'c' + i, cat: ['news', 'war', 'sci'].includes(r[0]) ? r[0] : 'news', label: r[1], ch: v ? '' : r[2].replace(/.*channel\//, ''), video: v ? v.replace(/.*[?&]v=|.*youtu\.be\//, '').slice(0, 11) : null, flag: r[3] || '📺' }; }));
        else Store.set('camList', rows.map(r => { const id = (r[3] || '').trim(), chm = id.match(/(?:channel[:/])?(UC[\w-]{22})/);
          return { city: r[0], lat: +r[1] || 0, lon: +r[2] || 0, ch: chm ? chm[1] : undefined, yt: chm ? undefined : id.replace(/.*[?&]v=|.*youtu\.be\/|.*\/live\//, '').slice(0, 11), flag: r[4] || '📹' }; }));
        closeModal(); isTV ? buildTV() : buildCams(); Toast.show('✓ Elenco salvato', 'ok');
      } }, '💾 SALVA')]);
  }
  function buildCams() {
    $('wc-grid').replaceChildren(...camList().map((c, i) => h('button', { class: 'wc-m', type: 'button', dataset: { cam: String(i) }, onclick: () => loadCam(i) }, `${c.flag || '📹'} ${c.city}`)));
  }
  let camActive = -1;
  function loadCam(i) {
    const c = camList()[i]; if (!c) return false;
    camActive = i;
    document.querySelectorAll('.wc-m').forEach(b => b.classList.toggle('act', +b.dataset.cam === i));
    setText('wc-name', `${c.flag || ''} ${c.city}`);
    if (c.lat || c.lon) MapCtl.flyTo(c.lat, c.lon, 6000, { pitch: -28, heading: 30 });
    if (FROM_FILE) { ytPopup(c); fileNotice($('wc-ph'), c, 'La webcam'); return true; }
    $('wc-ph').classList.add('hidden');
    if (c.ch) {      // canale con dirette 24/7: si carica la diretta attuale, non scade
      $('wc-iframe').src = `https://www.youtube.com/embed/live_stream?channel=${c.ch}&autoplay=1&mute=1&rel=0&playsinline=1`;
      checkChannel(c.ch).then(r => { if (camActive === i && r.ok === false) deadNotice($('wc-ph'), $('wc-iframe'), `Il canale di ${c.city} non esiste su YouTube`, 'ID errato', 'cam'); });
      return true;
    }
    $('wc-iframe').src = `https://www.youtube.com/embed/${c.yt}?autoplay=1&mute=1&rel=0&playsinline=1`;
    checkVideo(c.yt).then(alive => {         // gli ID delle webcam scadono: lo verifichiamo e lo diciamo chiaramente
      if (alive !== false || camActive !== i) return;
      $('wc-iframe').src = 'about:blank';
      const ph = $('wc-ph'); ph.classList.remove('hidden');
      ph.replaceChildren(h('div', { style: 'font-size:22px' }, '📹'), h('div', null, h('b', null, `La webcam di ${c.city} non esiste più su YouTube`), ' (l\'ID ', h('code', null, c.yt), ' è scaduto).'),
        h('div', null, h('button', { class: 'pl-btn', type: 'button', onclick: () => $('wc-search').click() }, '🔎 CERCA UNA WEBCAM LIVE'), ' ', h('button', { class: 'pl-btn', type: 'button', onclick: () => editList('cam') }, '✎ INCOLLA IL NUOVO LINK')));
    });
    return true;
  }
  const vidCache = new Map();
  async function checkVideo(id) {   // true = esiste, false = rimosso/privato, null = non verificabile
    if (!id) return false;
    if (vidCache.has(id)) return vidCache.get(id);
    const u = encodeURIComponent(`https://www.youtube.com/watch?v=${id}`);
    let res = null;
    try {
      const r = await Net.get(`https://noembed.com/embed?url=${u}`, { timeout: 7000, noProxy: true });
      res = r.data && !r.data.error ? true : /not found|unauthorized|private|404|401|403/i.test(r.data?.error || '') ? false : null;
    } catch {}
    if (res === null) try { await Net.get(`https://www.youtube.com/oembed?url=${u}&format=json`, { timeout: 7000 }); res = true; } catch (e) { if (e.status === 404 || e.status === 401 || e.status === 403) res = false; }
    vidCache.set(id, res); return res;
  }
  function setWindy(overlay, lat, lon) {
    const v = view(); lat = lat ?? v.lat; lon = lon ?? v.lon;
    const z = Math.round(clamp(Geo.altToZoom(v.alt), 3, 10));
    document.querySelectorAll('[data-windy]').forEach(b => b.classList.toggle('act', b.dataset.windy === overlay));
    $('windy-frame').src = `https://embed.windy.com/embed2.html?lat=${lat.toFixed(2)}&lon=${lon.toFixed(2)}&detailLat=${lat.toFixed(2)}&detailLon=${lon.toFixed(2)}&zoom=${z}&level=surface&overlay=${overlay}&product=ecmwf&menu=&message=true&marker=true&calendar=now&type=map&location=coordinates&metricWind=km%2Fh&metricTemp=%C2%B0C&radarRange=-1`;
  }
  function openMedia(kind) {
    if (FROM_FILE) { howToServe(); return; }
    const m = $('media-modal'); m.classList.add('open');
    const isTV = kind === 'tv', list = isTV ? tvList() : camList();
    setText('media-title', isTV ? '📺 LIVE TV · YouTube' : '📹 WEBCAM');
    $('media-list').replaceChildren(...list.map((c, i) => h('button', { class: 'tv-btn', type: 'button', style: 'width:100%', onclick: e => {
      document.querySelectorAll('#media-list .tv-btn').forEach(b => b.classList.remove('act')); e.currentTarget.classList.add('act');
      $('media-iframe').src = isTV ? tvURL(c, 0) : `https://www.youtube.com/embed/${c.yt}?autoplay=1&mute=0&rel=0`;
    } }, h('span', { class: 'tv-live-dot' }), `${c.flag || ''} ${c.label || c.city}`)));
    const first = isTV ? Math.max(0, list.findIndex(c => c.id === tvActive)) : Math.max(0, camActive);
    $('media-list').children[first]?.click();
    $('tv-iframe').src = 'about:blank'; $('tv-ph').classList.remove('hidden');
  }
  function closeMedia() { $('media-modal').classList.remove('open'); $('media-iframe').src = 'about:blank'; }

  /* ═════ TERMINALE ═════ */
  const CMDS = {
    help: () => 'comandi: status · goto <luogo> · flyto <lat> <lon> [km] · find <volo> · sat <nome> · iss · follow · unfollow · cockpit · layer <nome> [on|off] · layers · base <nome> · vis nrm|nvg|flir|crt · exag <1-5> · spin · brief · alerts · eq · news <testo> · ip <ip|dominio> · me · tts · tv <n> · cam <n> · clear',
    status: () => `motore ${MapCtl.engine?.kind || '--'} · aerei ${S.acList.length} · satelliti ${S.sats.length} · sismi ${S.quakes.length} · notizie ${S.news.length} · feed ${$('st-feeds').textContent} · indice ${Intel.glob.idx}/100 (allerta ${Intel.glob.lvl})`,
    layers: () => MapCtl.LAYERS.map(l => `${l.key}:${MapCtl.isOn(l.key) ? 'on' : 'off'}`).join(' '),
    iss: () => { select({ kind: 'sat', id: '25544' }); return 'ISS selezionata'; },
    follow: () => { if (!sel || !['ac', 'sat'].includes(sel.kind)) return 'ERR: seleziona prima un aereo o un satellite'; MapCtl.engine.setFollow(sel); return 'inseguimento attivo'; },
    unfollow: () => { MapCtl.engine.stopFollow(); return 'inseguimento terminato'; },
    cockpit: () => { if (sel?.kind !== 'ac') return 'ERR: seleziona prima un aereo'; MapCtl.engine.setCockpit(sel); return 'vista cockpit (Esc per uscire)'; },
    brief: () => { openBriefing(); return 'briefing aperto'; },
    alerts: () => Intel.alerts.slice(0, 5).map(a => `${Fmt.utc(a.t)} ${a.title}`).join(' | ') || 'nessuna allerta',
    eq: () => { Scheduler.runNow('quakes'); return 'aggiorno terremoti…'; },
    spin: () => { toggleSpin(); return 'spin ' + (MapCtl.engine?.spin ? 'on' : 'off'); },
    tts: () => { TTS.toggle(); return 'voce ' + (TTS.enabled ? 'on' : 'off'); },
    me: () => { locateMe().then(l => l && MapCtl.flyTo(l.lat, l.lon, 80000, { pitch: -45 })); return 'localizzo…'; },
    reset: () => { resetMap(); return 'mappa ripristinata'; },
    diag: () => { const d = MapCtl.engine?.diag; return d ? JSON.stringify(d) : 'motore 2D'; },
    clear: () => '__CLEAR__'
  };
  async function runCmd(raw) {
    const out = $('hk-out'); raw = (raw ?? $('hk-inp').value).trim(); if (!raw) return; $('hk-inp').value = '';
    out.appendChild(h('div', { class: 't-line' }, h('span', { class: 'red' }, 'ojo'), h('span', { class: 'dim' }, '$ '), raw));
    const [verb, ...args] = raw.split(/\s+/), v = verb.toLowerCase(), a = args.join(' ');
    let res = '';
    try {
      if (v === 'flyto' && args.length >= 2) { const la = +args[0], lo = +args[1], km = +args[2] || 300; if (isFinite(la) && isFinite(lo)) { MapCtl.flyTo(la, lo, km * 1000); res = `flyto ${la}, ${lo} · ${km} km`; } else res = 'ERR: flyto <lat> <lon> [km]'; }
      else if (v === 'goto' && a) { const r = await omniGo(a); res = r || 'ERR: luogo non trovato'; }
      else if (v === 'find' && a) { const f = ADSB.find(a); if (f) { select({ kind: 'ac', id: f.hex }); res = `trovato ${f.cs || f.hex} (${f.type || '?'})`; } else res = 'ERR: volo non visibile ora'; }
      else if (v === 'sat' && a) { const s = Sats.find(a); if (s) { select({ kind: 'sat', id: s.id }); res = `satellite ${s.name}`; } else res = 'ERR: satellite non trovato (gruppo attivo?)'; }
      else if (v === 'layer' && args[0]) { const k = args[0].toLowerCase(); if (!MapCtl.LAYERS.find(l => l.key === k)) res = 'ERR: layer sconosciuto — vedi "layers"'; else { const on = args[1] ? /on|1|si/.test(args[1]) : !MapCtl.isOn(k); MapCtl.setLayer(k, on); res = `${k}: ${on ? 'on' : 'off'}`; } }
      else if (v === 'base' && args[0]) { const b = (MapCtl.engine.bases() || []).find(x => x.key === args[0].toLowerCase()); if (b) { MapCtl.engine.setBase(b.key); $('base-sel').value = b.key; res = 'base: ' + b.name; } else res = 'basi: ' + MapCtl.engine.bases().map(x => x.key).join(', '); }
      else if (v === 'vis' && args[0]) { setVis(args[0].toLowerCase()); res = 'visore: ' + args[0]; }
      else if (v === 'exag' && args[0]) { const e = clamp(+args[0] || 1, 1, 5); MapCtl.engine.setExag(e); $('exag').value = e; setText('exag-v', e + '×'); res = 'esagerazione rilievo ' + e + '×'; }
      else if (v === 'news' && a) { News.setQuery(a); $('news-q').value = a; res = `filtro notizie: "${a}" (${News.filtered().length})`; }
      else if (v === 'ip' && a) { $('ip-inp').value = a; traceIP(); res = 'trace avviato'; }
      else if (v === 'tv') { const n = parseInt(args[0]); const l = tvList(); const c = isFinite(n) ? l[n] : l.find(x => x.label.toLowerCase().includes(a.toLowerCase())); res = c && playTV(c.id) ? 'TV: ' + c.label : 'canali: ' + l.map((x, i) => i + '=' + x.label).join(', '); }
      else if (v === 'cam') { const n = parseInt(args[0]) || 0; res = loadCam(n) ? 'webcam: ' + camList()[n].city : 'ERR: webcam ' + n; }
      else if (CMDS[v]) res = CMDS[v]();
      else res = 'ERR: comando sconosciuto — digita help';
    } catch (e) { res = 'ERR: ' + e.message; }
    if (res === '__CLEAR__') { out.replaceChildren(); return; }
    out.appendChild(h('div', { class: 't-line' }, h('span', { class: /^ERR/.test(res) ? 'red' : 'ok' }, res)));
    out.scrollTop = out.scrollHeight;
  }

  /* ═════ RICERCA UNIVERSALE ═════ */
  let sugIdx = -1, sugs = [];
  function suggestions(q) {
    const s = [], Q = q.trim().toUpperCase(), ql = q.trim().toLowerCase();
    if (!Q) return s;
    const c = Geo.parseCoords(q); if (c) s.push({ icon: '⌖', label: `Vai a ${c.lat.toFixed(4)}, ${c.lon.toFixed(4)}`, k: 'coordinate', go: () => { MapCtl.flyTo(c.lat, c.lon, 50000, { pitch: -40 }); analyzePoint(c.lat, c.lon); } });
    if (q.startsWith('>')) return [{ icon: '💻', label: 'Esegui: ' + q.slice(1), k: 'comando', go: () => runCmd(q.slice(1)) }];
    DATA.HOTSPOTS.filter(x => x.name.toLowerCase().includes(ql) || x.id === Q).forEach(x => s.push({ icon: x.flag, label: x.name, k: 'zona calda', go: () => { MapCtl.flyTo(x.lat, x.lon, x.range, { pitch: -55 }); openDossier(x.id); } }));
    if (Q.length >= 2) S.acList.filter(a => a.cs.toUpperCase().startsWith(Q) || a.hex.toUpperCase() === Q || (a.reg && a.reg.toUpperCase().startsWith(Q))).slice(0, 5)
      .forEach(a => s.push({ icon: (DATA.AC_CLASS[a.cls] || DATA.AC_CLASS.civil).icon, label: `${a.cs || a.hex} · ${a.type || '?'} · ${Fmt.n(a.altFt)} ft`, k: 'volo', go: () => select({ kind: 'ac', id: a.hex }) }));
    if (Q.length >= 3) S.sats.filter(x => x.name.toUpperCase().includes(Q) || x.id === Q).slice(0, 5).forEach(x => s.push({ icon: '🛰', label: `${x.name} · ${Fmt.n(x.altKm)} km`, k: 'satellite', go: () => select({ kind: 'sat', id: x.id }) }));
    for (const [key, list, ic] of [['nuclear', DATA.NUCLEAR, '☢'], ['bases', DATA.BASES, '🏴'], ['choke', DATA.CHOKEPOINTS, '⚓']])
      list.forEach((p, i) => { if (ql.length >= 3 && p.name.toLowerCase().includes(ql) && s.length < 14) s.push({ icon: ic, label: p.name, k: 'riferimento', go: () => select({ kind: key, id: String(i) }) }); });
    [...DATA.PLACES_CITY, ...DATA.PLACES_COUNTRY].filter(p => ql.length >= 3 && p[3].toLowerCase().startsWith(ql)).slice(0, 4).forEach(p => s.push({ icon: '📍', label: p[3], k: 'luogo', go: () => MapCtl.flyTo(p[1], p[2], p[0].length > 30 ? 1.5e6 : 400000, { pitch: -45 }) }));
    if (ql.length >= 2) s.push({ icon: '🔎', label: `Cerca “${q.trim()}” nel mondo`, k: 'geocoding', go: () => omniGo(q.trim()) });
    return s.slice(0, 14);
  }
  async function omniGo(q) {
    try {
      const r = await Weather.geocode(q);
      if (!r.length) { Toast.show('Luogo non trovato: ' + q, 'orn'); return null; }
      const p = r[0]; MapCtl.flyTo(p.lat, p.lon, p.pop > 1e6 ? 60000 : 25000, { pitch: -35 });
      Toast.show(`📍 ${p.name}${p.admin ? ', ' + p.admin : ''} · ${p.country || p.cc}`, 'ok');
      return `${p.name} (${p.cc})`;
    } catch (e) { Toast.show('⚠ Geocoding non disponibile', 'orn'); return null; }
  }
  function renderSug() {
    const box = $('omni-sug');
    if (!sugs.length) { box.classList.add('hidden'); return; }
    box.replaceChildren(...sugs.map((s, i) => h('div', { class: 'sug' + (i === sugIdx ? ' act' : ''), onmousedown: e => { e.preventDefault(); pickSug(i); } }, h('span', null, s.icon), h('span', null, s.label), h('span', { class: 'sug-k' }, s.k))));
    box.classList.remove('hidden');
  }
  function pickSug(i) { const s = sugs[i]; if (!s) return; $('omni').value = ''; sugs = []; renderSug(); $('omni').blur(); s.go(); }

  /* ═════ LAYER / STATO ═════ */
  function buildLayers() {
    const groups = {}; MapCtl.LAYERS.forEach(l => (groups[l.grp] = groups[l.grp] || []).push(l));
    const ion = !!(Settings.get('ionToken') || '').trim();
    $('layer-list').replaceChildren(...Object.entries(groups).flatMap(([g, ls]) => [h('div', { class: 'lgrp' }, g), ...ls.map(l => {
      const dis = (l.only3d && !MapCtl.is3d) || (l.ion && !ion);
      const tag = l.key === 'fires' ? ((Settings.get('firmsKey') || '').trim() ? 'live' : 'key') : l.tag;
      return h('div', { class: 'layer-item' + (MapCtl.isOn(l.key) ? ' active' : '') + (dis ? ' disabled' : ''), dataset: { layer: l.key }, title: dis ? (l.ion ? 'Richiede token Cesium ion (⚙)' : 'Solo nel globo 3D') : '',
        onclick: () => { if (dis) { Toast.show(l.ion ? '🔑 Serve un token Cesium ion (⚙ Impostazioni)' : 'Disponibile solo nel globo 3D', 'orn'); return; } const on = MapCtl.toggle(l.key); Toast.show(`${on ? '☑' : '☐'} ${l.label}`, on ? 'ok' : ''); } },
        h('div', { class: 'layer-cb' }), h('span', { class: 'layer-ico' }, l.icon), h('span', { class: 'layer-name' }, l.label, ' ', h('span', { class: 'dstat ' + tag }, { live: 'LIVE', calc: 'CALC', ref: 'REF', est: 'STIMA', key: 'KEY' }[tag])),
        h('span', { class: 'layer-count', id: 'lc-' + l.key }, MapCtl.count(l.key) != null ? Fmt.n(MapCtl.count(l.key)) : ''));
    })]));
  }
  function setVis(m) {
    if (!['nrm', 'nvg', 'flir', 'crt'].includes(m)) return;
    MapCtl.engine?.setVisual(m);
    document.querySelectorAll('[data-vis]').forEach(b => b.classList.toggle('act', b.dataset.vis === m));
  }
  function toggleSpin(force) {
    const on = force ?? !MapCtl.engine?.spin; MapCtl.engine?.setSpin(on);
    $('btn-spin').classList.toggle('act', on);
  }
  function resetMap() {
    for (const k of ['photo3d', 'osm3d']) if (MapCtl.isOn(k)) MapCtl.setLayer(k, false);
    setVis('nrm'); $('exag').value = 1.5; setText('exag-v', '1.5×');
    document.querySelectorAll('[data-scene]').forEach(b => b.classList.toggle('act', b.dataset.scene === '3d'));
    MapCtl.engine?.resetMap?.();
    Toast.show('🛠 Mappa ripristinata: satellite, terreno, vista orbitale', 'ok');
  }
  function togglePanel(id) { const p = $(id); p.classList.toggle('open'); if (id === 'health-panel') Health.render(); $(id === 'layer-panel' ? 'btn-layers' : 'btn-health').classList.toggle('act', p.classList.contains('open')); }

  /* ═════ EVENTI ═════ */
  function bind() {
    document.addEventListener('click', e => {
      const t = e.target;
      const sh = t.closest('.sh[data-sec]'); if (sh) { const b = $(sh.dataset.sec); if (b) { b.classList.toggle('coll'); sh.classList.toggle('coll', b.classList.contains('coll')); } return; }
      const tab = t.closest('.tab[data-tab]'); if (tab) { const grp = tab.parentElement; grp.querySelectorAll('.tab').forEach(x => { x.classList.toggle('act', x === tab); $(x.dataset.tab)?.classList.toggle('act', x === tab); }); return; }
      const sc = t.closest('[data-scene]'); if (sc) { if (!MapCtl.is3d) return MapCtl.engine?.setScene(); MapCtl.engine.setScene(sc.dataset.scene); document.querySelectorAll('[data-scene]').forEach(b => b.classList.toggle('act', b === sc)); return; }
      const vb = t.closest('[data-vis]'); if (vb) return setVis(vb.dataset.vis);
      const af = t.closest('[data-acf]'); if (af) { ADSB.setFilter(af.dataset.acf); document.querySelectorAll('[data-acf]').forEach(b => b.classList.toggle('act', b === af)); return; }
      const nf = t.closest('[data-nf]'); if (nf) { News.setFilter(nf.dataset.nf); document.querySelectorAll('[data-nf]').forEach(b => b.classList.toggle('act', b === nf)); return; }
      const wb = t.closest('[data-windy]'); if (wb) return setWindy(wb.dataset.windy);
      const cl = t.closest('[data-close]'); if (cl) { $(cl.dataset.close).classList.remove('open'); $(cl.dataset.close === 'layer-panel' ? 'btn-layers' : 'btn-health').classList.remove('act'); return; }
      if (t.closest('[data-close-modal]') || t.id === 'modal') return closeModal();
      if (t.id === 'media-modal') return closeMedia();
    });
    const on = (id, f, ev = 'click') => $(id)?.addEventListener(ev, f);
    on('btn-layers', () => togglePanel('layer-panel')); on('btn-health', () => togglePanel('health-panel'));
    on('btn-brief', openBriefing); on('threat-badge', openBriefing); on('btn-settings', openSettings); on('btn-help', openHelp);
    on('btn-tts', () => TTS.toggle()); on('btn-full', () => { $('app').classList.toggle('mapfull'); window.dispatchEvent(new Event('resize')); });
    on('btn-home', () => MapCtl.engine?.home()); on('btn-spin', () => toggleSpin());
    on('btn-reset', resetMap);
    Bus.on('map:warn', w => {
      const el = $('map-warn');
      if (!w) { el.classList.add('hidden'); return; }
      el.replaceChildren(h('div', null, '⚠ ', w.text), h('div', { class: 'btns' },
        h('button', { class: 'abtn', type: 'button', onclick: resetMap }, '🛠 RIPRISTINA MAPPA'),
        h('button', { class: 'abtn', type: 'button', onclick: () => location.reload() }, '↻ RICARICA'),
        MapCtl.is3d ? h('button', { class: 'abtn', type: 'button', onclick: () => { Store.set('force2d', true); location.reload(); } }, '▦ USA MAPPA 2D') : null,
        h('button', { class: 'abtn', type: 'button', onclick: () => el.classList.add('hidden') }, '✕')));
      el.classList.remove('hidden');
    });
    on('btn-me', async () => { const l = S.user || await locateMe(); if (l) { MapCtl.flyTo(l.lat, l.lon, 60000, { pitch: -45 }); analyzePoint(l.lat, l.lon); } });
    on('base-sel', e => MapCtl.engine?.setBase(e.target.value), 'change');
    on('exag', e => { const v = +e.target.value; setText('exag-v', v + '×'); MapCtl.engine?.setExag(v); }, 'input');
    on('ac-q', e => ADSB.setQuery(e.target.value), 'input'); on('news-q', e => News.setQuery(e.target.value), 'input');
    on('sat-q', e => { satQ = e.target.value; renderSats(S.sats); }, 'input');
    on('eq-feed', () => Scheduler.runNow('quakes'), 'change');
    on('ip-btn', traceIP); on('ip-me', async () => { try { const d = await GeoIP.lookup(''); $('ip-inp').value = d.ip; traceIP(); } catch (e) { Toast.show('⚠ ' + e.message, 'orn'); } });
    on('wx-btn', weatherCity); on('wx-here', () => { const v = view(); $('wx-result').replaceChildren(h('span', { class: 'spinner' })); weatherAt(v.lat, v.lon, Intel.nearest(v.lat, v.lon).label + ' (centro mappa)').catch(e => $('wx-result').replaceChildren(h('div', { class: 't-line red' }, 'Errore: ' + e.message))); });
    on('hk-btn', () => runCmd());
    on('brief-read', () => { const b = Intel.briefing(); if (!TTS.enabled) TTS.toggle(true); setTimeout(() => TTS.speak(b.speech, { prio: true }), 400); });
    on('brief-open', openBriefing);
    on('iss-follow', () => { select({ kind: 'sat', id: '25544' }); MapCtl.engine?.setFollow({ kind: 'sat', id: '25544' }); select({ kind: 'sat', id: '25544' }, true); });
    on('iss-pass-btn', async () => { $('iss-pass').replaceChildren(h('div', { class: 'empty' }, h('span', { class: 'spinner' }), ' calcolo…')); const l = S.user || await locateMe(); if (!l) return; renderPasses(Sats.passes('25544', l, 36, 10), l); });
    on('tv-edit', () => editList('tv')); on('wc-edit', () => editList('cam')); on('tv-expand', () => openMedia('tv'));
    on('tv-yt', () => { const c = tvList().find(x => x.id === tvActive); window.open(c ? (c.video ? `https://www.youtube.com/watch?v=${c.video}` : `https://www.youtube.com/channel/${c.ch}/live`) : 'https://www.youtube.com/results?search_query=news+live&sp=EgJAAQ%253D%253D', '_blank', 'noopener'); });
    on('wc-search', () => { const c = camList()[camActive]; window.open(`https://www.youtube.com/results?search_query=${encodeURIComponent((c ? c.city : 'city') + ' live webcam')}&sp=EgJAAQ%253D%253D`, '_blank', 'noopener'); });
    on('media-close', closeMedia);
    // omnibox
    const omni = $('omni');
    omni.addEventListener('input', () => { sugs = suggestions(omni.value); sugIdx = sugs.length ? 0 : -1; renderSug(); });
    omni.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown') { sugIdx = Math.min(sugs.length - 1, sugIdx + 1); renderSug(); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { sugIdx = Math.max(0, sugIdx - 1); renderSug(); e.preventDefault(); }
      else if (e.key === 'Enter') { if (sugs.length) pickSug(Math.max(0, sugIdx)); else if (omni.value.trim()) omniGo(omni.value.trim()); }
      else if (e.key === 'Escape') { omni.value = ''; sugs = []; renderSug(); omni.blur(); }
    });
    omni.addEventListener('blur', () => setTimeout(() => { sugs = []; renderSug(); }, 150));
    // tastiera
    document.addEventListener('keydown', e => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
        if (e.key === 'Enter') { if (e.target.id === 'hk-inp') runCmd(); if (e.target.id === 'ip-inp') traceIP(); if (e.target.id === 'wx-inp') weatherCity(); }
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const k = e.key;
      const map = {
        '/': () => { e.preventDefault(); omni.focus(); }, '1': () => MapCtl.is3d && $('mode-bar').querySelector('[data-scene="3d"]').click(), '2': () => MapCtl.is3d && $('mode-bar').querySelector('[data-scene="cv"]').click(),
        '3': () => MapCtl.is3d && $('mode-bar').querySelector('[data-scene="2d"]').click(), l: () => togglePanel('layer-panel'), s: () => togglePanel('health-panel'), b: openBriefing, t: () => TTS.toggle(),
        f: () => $('btn-full').click(), h: () => MapCtl.engine?.home(), r: () => toggleSpin(), g: () => $('btn-me').click(), '?': openHelp,
        v: () => { const m = ['nrm', 'nvg', 'flir', 'crt'], cur = document.querySelector('[data-vis].act')?.dataset.vis || 'nrm'; setVis(m[(m.indexOf(cur) + 1) % 4]); },
        a: () => { const on = MapCtl.toggle('adsb'); Toast.show(on ? '✈ Aerei ON' : '✈ Aerei OFF'); },
        Escape: () => { $('ctx-menu')?.remove(); if ($('modal').classList.contains('open')) return closeModal(); if ($('media-modal').classList.contains('open')) return closeMedia(); if (MapCtl.engine?.following) { MapCtl.engine.stopFollow(); return; } closePanel(); }
      };
      const f = map[k] || map[k.toLowerCase()]; if (f) f();
    });
    // ridimensionamento mappa
    const rz = $('resizer'); let drag = false;
    rz.addEventListener('pointerdown', e => { drag = true; rz.setPointerCapture(e.pointerId); });
    rz.addEventListener('pointermove', e => { if (!drag) return; const top = $('map-section').getBoundingClientRect().top; const vh = clamp((e.clientY - top) / innerHeight * 100, 25, 85); document.documentElement.style.setProperty('--map-h', vh + 'vh'); });
    rz.addEventListener('pointerup', () => { if (!drag) return; drag = false; Settings.set('mapH', parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--map-h'))); window.dispatchEvent(new Event('resize')); });
    // eventi dalla mappa
    Bus.on('map:pick', ref => select(ref));
    Bus.on('map:click', ll => analyzePoint(ll.lat, ll.lon));
    Bus.on('map:context', ll => contextMenu(ll));
    Bus.on('map:move', ll => { const th = MapCtl.engine?.terrainHeight?.(ll.lat, ll.lon); setText('m-coords', `${Fmt.lat(ll.lat)} ${Fmt.lon(ll.lon)}${th != null && isFinite(th) && th > 1 ? ' · ⛰ ' + Fmt.n(th) + ' m' : ''}`); });
    let lastArea = null, areaT = null;
    Bus.on('map:view', v => {
      if (!v) return;
      setText('m-info', `${MapCtl.is3d ? '🌍 3D' : '🗺 2D'} · ${Fmt.lat(v.lat)} ${Fmt.lon(v.lon)} · quota ${Fmt.alt(v.alt)}${MapCtl.is3d && isFinite(v.pitch) ? ' · inclin. ' + Math.round(v.pitch) + '°' : ''}`);
      setText('sb-cam', Fmt.alt(v.alt));
      clearTimeout(areaT);
      areaT = setTimeout(() => {   // nuova area inquadrata → ricarica traffico aereo locale
        if (!v.centerOnGlobe || v.alt > 5e6) return;
        if (!lastArea || Geo.dist(lastArea.lat, lastArea.lon, v.lat, v.lon) > Math.max(60, v.alt / 3000) || Math.abs(Math.log(lastArea.alt / v.alt)) > 0.9) { lastArea = v; Scheduler.runNow('adsb'); }
      }, 1800);
    });
    Bus.on('follow', f => { setText('sb-engine', (MapCtl.is3d ? '3D' : '2D') + (f ? (f.cockpit ? ' · COCKPIT' : ' · SEGUI') : '')); if (sel && ['ac', 'sat'].includes(sel.kind) && f !== undefined) { const b = $('trk-btns'); if (b) { const keep = [...b.children].slice(followBtns(sel).length); b.replaceChildren(...followBtns(sel).map(x => h('button', { class: 'abtn' + (x[2] ? ' on' : ''), type: 'button', onclick: x[1] }, x[0])), ...keep); } } });
    Bus.on('spin', on => $('btn-spin').classList.toggle('act', on));
    Bus.on('engine:fatal', () => modal('⚠ ERRORE GRAFICO', [h('p', null, 'Il motore 3D ha avuto un errore WebGL (driver o memoria GPU). Puoi ricaricare, oppure usare la mappa 2D.')],
      [h('button', { class: 'btn', type: 'button', onclick: () => location.reload() }, 'RICARICA'), h('button', { class: 'btn', type: 'button', onclick: () => { Store.set('force2d', true); location.reload(); } }, 'RICARICA IN 2D')]));
    // dati → pannelli (con throttling)
    const thr = (fn, ms) => { let t = null; return (...a) => { if (t) return; t = setTimeout(() => { t = null; fn(...a); }, ms); }; };
    const rAdsb = thr(renderAdsb, 600), rNews = thr(renderNews, 500), rSats = thr(() => renderSats(S.sats), 4000), rMk = thr(renderMarkets, 400);
    const rScore = thr(() => { Intel.score(); }, 1500);
    Bus.on('adsb', () => { rAdsb(); rScore(); }); Bus.on('adsb:filter', renderAdsb);
    Bus.on('news', () => { rNews(); rScore(); }); Bus.on('news:filter', renderNews);
    Bus.on('quakes', () => { renderQuakes(); rScore(); }); Bus.on('eonet', renderEonet);
    Bus.on('sats', rSats); Bus.on('iss', renderISS); Bus.on('space', renderSpace); Bus.on('markets', rMk);
    Bus.on('alerts', renderAlerts); Bus.on('intel', renderThreat);
    Bus.on('layer', ({ key, on: v }) => { buildLayers(); if (key === 'radar' && v) Scheduler.runNow('radar'); if (key === 'fires' && v) Scheduler.runNow('firms'); if (key === 'sats' || key === 'adsb') { } });
    Bus.on('engine', kind => {
      setText('sb-engine', kind === '3d' ? '3D CESIUM' : '2D LEAFLET');
      const bs = MapCtl.engine.bases(), ion = !!(Settings.get('ionToken') || '').trim();
      $('base-sel').replaceChildren(...bs.filter(b => !b.ion || ion).map(b => h('option', { value: b.key, selected: b.key === Settings.get('base') }, b.name)));
      if (kind !== '3d') { document.querySelectorAll('[data-scene="cv"],[data-scene="3d"],#btn-spin,#exag').forEach(b => b.disabled = true); }
      buildLayers();
    });
  }

  /* ═════ AVVIO ═════ */
  async function start() {
    const boot = $('boot'), lines = $('boot-lines'), bar = $('boot-bar'), status = $('boot-status');
    const log = (m, cls = '') => { lines.appendChild(h('div', { class: cls }, (cls === 'ok' ? '✓ ' : cls === 'warn' ? '⚠ ' : cls === 'bad' ? '✕ ' : '> ') + m)); lines.scrollTop = lines.scrollHeight; status.textContent = m; };
    const prog = p => bar.style.width = p + '%';
    $('boot-start').disabled = true; $('boot-cfg').style.display = 'none';
    const ion = $('cfg-ion').value.trim(), firms = $('cfg-firms').value.trim();
    if (ion !== (Settings.get('ionToken') || '')) Settings.set('ionToken', ion);
    if (firms !== (Settings.get('firmsKey') || '')) Settings.set('firmsKey', firms);
    Store.set('booted', true);
    Sound.unlock(); TTS.badge();
    document.documentElement.style.setProperty('--map-h', (Settings.get('mapH') || 58) + 'vh');
    ['engine:Motore grafico', 'terrain:Terreno 3D', 'adsb:Aerei ADS-B', 'sats:Satelliti CelesTrak', 'iss:Telemetria ISS', 'quakes:Terremoti USGS', 'eonet:NASA EONET', 'firms:NASA FIRMS incendi',
      'space:Meteo spaziale NOAA', 'aurora:Aurora NOAA OVATION', 'radar:Radar RainViewer', 'news:Notizie RSS + GDELT', 'markets:Borse (Yahoo/Stooq)', 'crypto:Crypto (CoinGecko)', 'fx:Valute (BCE)',
      'weather:Meteo Open-Meteo', 'geoip:GeoIP / DNS', 'osm3d:Edifici 3D (ion)', 'photo3d:Città 3D (ion)'].forEach(s => { const [id, l] = s.split(':'); Health.register(id, l); });
    if (!ion) { Health.set('osm3d', 'key', 'serve token Cesium ion'); Health.set('photo3d', 'key', 'serve token Cesium ion'); }
    Health.set('weather', 'wait', 'su richiesta'); Health.set('geoip', 'wait', 'su richiesta');
    Health.register('imagery', 'Immagini del globo'); Health.register('proxy', 'Proxy CORS');
    bind(); clock(); setInterval(clock, 1000);
    document.querySelector('.t-logo-sub').textContent = `v${OJO.version} · build ${OJO.build}`;
    document.querySelector('.t-logo').title = `OJO DE DEUS v${OJO.version} · build ${OJO.build}`;
    const local = await Net.detectLocal();
    const pm = Net.proxyMode;
    Health.set('proxy', pm === 'pubblici' ? 'wait' : 'live', pm === 'locale' ? 'proxy integrato dell\'avviatore (affidabile)' : pm === 'personale' ? 'proxy personale (⚙)' : 'solo proxy pubblici gratuiti (lenti/instabili)');
    if (local) log('Proxy locale dell\'avviatore attivo: notizie, aerei e borse senza blocchi CORS', 'ok');
    else if (FROM_FILE) log('Aperto da file: i video YouTube si apriranno in una finestra separata', 'warn');
    buildTV(); buildCams(); renderNuke(); renderMarkets(); buildLayers();
    prog(10); log('Interfaccia pronta');
    log('Caricamento motore 3D CesiumJS (≈ 4 MB, la prima volta può richiedere qualche secondo)…'); prog(20);
    const kind = await MapCtl.start();
    if (kind === '3d') log('Globo 3D online · WebGL · sole reale' + (Settings.get('terrain') !== false ? ' · terreno 3D' : ''), 'ok');
    else if (kind === '2d') log('WebGL non disponibile: mappa 2D di riserva', 'warn');
    else log('Mappa non caricabile (rete?)', 'bad');
    prog(60);
    // dati di riferimento sulla mappa
    MapCtl.render('points:nuclear', DATA.NUCLEAR); MapCtl.render('points:bases', DATA.BASES); MapCtl.render('points:choke', DATA.CHOKEPOINTS);
    MapCtl.render('zones:conflict', DATA.CONFLICT_ZONES); MapCtl.render('zones:gps', DATA.GPS_ZONES);
    MapCtl.setCount('nuclear', DATA.NUCLEAR.length); MapCtl.setCount('bases', DATA.BASES.length); MapCtl.setCount('choke', DATA.CHOKEPOINTS.length);
    MapCtl.setCount('conflict', DATA.CONFLICT_ZONES.length); MapCtl.setCount('gps', DATA.GPS_ZONES.length);
    log('Avvio dei feed di dati reali (lo stato di ciascuno è nel pannello 📊)…'); prog(75);
    Scheduler.every('adsb', () => ADSB.fetch(), 12000, { delay: 300 });
    Scheduler.every('iss', fetchISS, 5000, { delay: 600 });
    Scheduler.every('quakes', () => Quakes.fetch(), 60000, { delay: 200 });
    Scheduler.every('space', () => Space.fetch(), 120000, { delay: 900 });
    Scheduler.every('aurora', () => Space.aurora(), 600000, { delay: 2500 });
    Scheduler.every('eonet', fetchEONET, 900000, { delay: 1500 });
    Scheduler.every('firms', fetchFIRMS, 1800000, { delay: 4000 });
    Scheduler.every('radar', fetchRadar, 600000, { delay: 3000 });
    Scheduler.every('crypto', () => Markets.fetchCrypto(), 90000, { delay: 1200 });
    Scheduler.every('markets', () => Markets.fetchStocks(), 300000, { delay: 5000 });
    Scheduler.every('fx', () => Markets.fetchFX(), 3600000, { delay: 2000 });
    Scheduler.every('sats', () => Sats.loadAll(), 6 * 3600e3, { delay: 800 });
    setTimeout(() => News.fetchAll().then(() => Scheduler.every('news', () => News.fetchNext(), 15000, { now: false })), 1000);
    Scheduler.every('intel', () => Intel.score(), 20000, { delay: 3000 });
    Scheduler.every('brief', renderBrief, 60000, { delay: 15000 });
    Scheduler.every('sky', renderSky, 30000, { delay: 500 });
    setWindy('wind', 45, 12);
    if (!S.user) setTimeout(() => GeoIP.lookup('').then(d => { if (!S.user && isFinite(d.lat)) { S.user = { lat: d.lat, lon: d.lon, label: `${d.city} (da IP)` }; } }).catch(() => {}), 6000);
    const pulses = ['● Dati reali etichettati: LIVE · CALC · REF · STIMA', '● Clic su un oggetto = pannello bersaglio · tasto destro = menu', '● Tasto / = ricerca universale · ? = aiuto', '● Molti voli militari non trasmettono ADS-B: assenza ≠ inattività'];
    let pi = 0; setInterval(() => setText('sb-pulse', pulses[pi++ % pulses.length]), 9000);
    prog(100); log('Tutti i sistemi avviati', 'ok');
    EventLog.add('OJO DE DEUS v100 avviato · motore ' + (kind || 'n/d'), 'var(--g)');
    await sleep(450);
    boot.classList.add('fade-out'); setTimeout(() => boot.remove(), 650);
    if (kind === '3d') setTimeout(() => toggleSpin(true), 2500);
    TTS.speak('Ojo de Deus online. Dati reali in arrivo.', { prio: true });
  }
  function initBoot() {
    $('cfg-ion').value = Settings.get('ionToken') || ''; $('cfg-firms').value = Settings.get('firmsKey') || '';
    if (FROM_FILE) {
      const b = $('boot-file'); b.classList.remove('hidden');
      b.replaceChildren(h('b', null, '⚠ Hai aperto la pagina come file.'), ' Il globo funziona, ma YouTube blocca i video (Errore 153) e alcune fonti (aerei, borse) possono non arrivare. Per avere tutto: su Windows fai doppio clic su ',
        h('code', null, 'AVVIA-OJO.bat'), ' (nella stessa cartella di index.html); su Mac/Linux esegui ', h('code', null, 'python3 ojo-server.py'), '.');
    }
    $('boot-start').addEventListener('click', start);
    ['cfg-ion', 'cfg-firms'].forEach(id => $(id).addEventListener('keydown', e => { if (e.key === 'Enter') start(); }));
    if (Settings.get('autostart') && Store.get('booted')) {
      let n = 3; const t = setInterval(() => { setText('boot-auto', `avvio automatico tra ${n}s…`); if (n-- <= 0) { clearInterval(t); if (!$('boot-start').disabled) start(); } }, 1000);
      $('boot-cfg').addEventListener('pointerdown', () => { clearInterval(t); setText('boot-auto', ''); }, { once: true });
    }
  }
  return { initBoot, select, analyzePoint, openBriefing, runCmd, get sel() { return sel; } };
})();

UI.initBoot();
