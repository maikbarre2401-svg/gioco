'use strict';
/* ════════════════════════════════════════════════════════════════
   INTEL — analisi automatica trasparente (regole, non magia):
   · punteggio delle zone calde da notizie + attività aerea + sismi
   · indice globale OJO (non ufficiale) → livello di allerta 1-5
   · rilevamento anomalie e briefing in italiano
═══════════════════════════════════════════════════════════════════ */
const Intel = (() => {
  const alerts = [];
  const keys = new Map(Object.entries(Store.get('alertKeys', {})));
  let scores = {}, glob = { idx: 0, lvl: 5, parts: {} }, lastFlash = 0, lastSpeak = 0, lastToast = 0, booted = Date.now();
  const H = 3600e3;

  function alert(a) {
    const now = Date.now();
    if (keys.has(a.key) && now - keys.get(a.key) < 6 * H) return false;
    keys.set(a.key, now);
    if (keys.size > 400) [...keys.keys()].slice(0, 100).forEach(k => keys.delete(k));
    Store.set('alertKeys', Object.fromEntries(keys));
    a.t = now; alerts.unshift(a); if (alerts.length > 80) alerts.length = 80;
    // popup solo per le allerte gravi; le altre al massimo una ogni 25 s (restano tutte nell'elenco 🚨)
    if (a.level === 'war' || (a.level === 'orn' && now - lastToast > 25e3)) {
      lastToast = now; Toast.show(`${a.icon || '🚨'} ${a.title}${a.text ? ' — ' + a.text : ''}`, a.level || 'orn', 6000);
      if (a.level === 'war') Sound.alert(); else Sound.ping();
    }
    if (Settings.get('ttsAlerts') !== false && a.speak && (a.level === 'war' || now - lastSpeak > 25e3)) { lastSpeak = now; TTS.speak(a.speak, { key: a.key, prio: a.level === 'war' }); }
    EventLog.add(`${a.icon || '🚨'} ${a.title} ${a.text || ''}`, a.level === 'war' ? 'var(--red)' : 'var(--orn)');
    if (Settings.get('autoFlyAlerts') && a.lat != null && a.level === 'war') MapCtl.flyTo(a.lat, a.lon, 900000, { pitch: -45 });
    Bus.emit('alerts', alerts);
    return true;
  }

  function placeOf(lat, lon) {
    const hs = DATA.HOTSPOTS.find(h => Geo.dist(h.lat, h.lon, lat, lon) < h.r);
    if (hs) return hs.name;
    return Intel.nearest(lat, lon).label;
  }

  /* ── anomalie traffico aereo ── */
  function analyzeAir(list) {
    if (!list.length) return;
    for (const a of list) {
      if (!a.emerg) continue;
      alert({ key: 'sq' + a.hex + a.sq, level: a.sq === '7500' ? 'war' : 'orn', icon: '🆘', title: a.emerg,
        text: `${a.cs || a.hex}${a.type ? ' (' + a.type + ')' : ''} · ${Fmt.n(a.altFt)} ft · ${placeOf(a.lat, a.lon)}`, lat: a.lat, lon: a.lon, ref: { kind: 'ac', id: a.hex },
        speak: `Attenzione. Aereo ${(a.cs || a.hex).split('').join(' ')} segnala ${a.emerg.replace(/\(\d+\)/, '')}.` });
    }
    const mil = list.filter(a => a.isMil);
    for (const h of DATA.HOTSPOTS) {
      for (const a of mil) {
        if (!['isr', 'tanker', 'drone'].includes(a.cls)) continue;
        if (Geo.dist(h.lat, h.lon, a.lat, a.lon) > h.r) continue;
        alert({ key: 'isr' + a.hex + h.id, level: 'orn', icon: a.cls === 'drone' ? '🔻' : '📡', title: `${DATA.AC_CLASS[a.cls].label} vicino a ${h.name}`,
          text: `${a.cs || a.hex}${a.type ? ' · ' + a.type : ''} · ${Fmt.n(a.altFt)} ft`, lat: a.lat, lon: a.lon, ref: { kind: 'ac', id: a.hex },
          speak: `Velivolo ${a.cls === 'drone' ? 'senza pilota' : 'da sorveglianza'} rilevato vicino a ${h.name}.` });
      }
    }
    // concentrazioni militari (griglia 3°)
    const cells = new Map();
    for (const a of mil) { const k = Math.floor(a.lat / 3) + ',' + Math.floor(a.lon / 3); cells.set(k, (cells.get(k) || 0) + 1); }
    for (const [k, n] of cells) {
      if (n < 14) continue;
      const [ci, cj] = k.split(',').map(Number), lat = ci * 3 + 1.5, lon = cj * 3 + 1.5;
      alert({ key: 'cl' + k + new Date().toISOString().slice(0, 12), level: 'ok', icon: '⚔', title: `Concentrazione aerei militari: ${n}`, text: `area ≈ ${placeOf(lat, lon)}`, lat, lon });
    }
  }

  /* ── flash notizie gravi ── */
  function analyzeNews(list) {
    const now = Date.now();
    // "urgente" solo per eventi davvero eccezionali (non ogni titolo con "missile" o "killed")
    const BIG = /nuclear (?:attack|strike|test|explosion)|test nucleare|attacco nucleare|invasion|invade[sd]?\b|invasione|coup\b|golpe|declares? war|dichiara(?:to)? guerra|martial law|legge marziale|state of emergency|stato di emergenza|tsunami warning|allerta tsunami|ballistic missile|missile balistico|assassinat|assassinio|hijack|dirottat/i;
    for (const n of list.slice(0, 60)) {
      if (n.sev < 0.7 || !BIG.test(n.title) || now - n.date > 40 * 60e3 || now - lastFlash < 5 * 60e3) continue;
      if (alert({ key: 'nf' + n.id, level: 'war', icon: '⚡', title: 'Notizia urgente', text: `${n.title.slice(0, 110)} (${n.src})`, lat: n.place?.lat, lon: n.place?.lon, ref: { kind: 'news', id: n.id }, speak: 'Notizia urgente. ' + n.title.slice(0, 140) })) lastFlash = now;
    }
  }

  /* ── punteggio zone calde e indice globale ── */
  function score() {
    const now = Date.now(), out = {};
    for (const h of DATA.HOTSPOTS) {
      const news = S.news.filter(n => n.hs.includes(h.id) && now - n.date < 24 * H);
      const nw = news.reduce((s, n) => s + (0.3 + n.sev) * (now - n.date < 6 * H ? 1 : 0.5), 0);
      const newsS = Math.min(100, nw * 9);
      const mil = S.acList.filter(a => a.isMil && Geo.dist(h.lat, h.lon, a.lat, a.lon) < h.r);
      const isr = mil.filter(a => ['isr', 'tanker', 'drone'].includes(a.cls));
      const airS = Math.min(100, mil.length * 4 + isr.length * 14);
      const eqs = S.quakes.filter(q => q.mag >= 5 && now - q.time < 24 * H && Geo.dist(h.lat, h.lon, q.lat, q.lon) < h.r);
      const sc = Math.round(clamp(h.base * 0.5 + newsS * 0.32 + airS * 0.18 + eqs.length * 5, 0, 100));
      out[h.id] = { id: h.id, score: sc, base: h.base, newsS: Math.round(newsS), airS: Math.round(airS), news, mil, isr, eqs, grave: news.filter(n => n.sev >= 0.6).length };
    }
    scores = out;
    const top = Object.values(out).sort((a, b) => b.score - a.score);
    const emerg = S.acList.filter(a => a.emerg).length;
    const kp = S.space.kp || 0;
    const bigEq = S.quakes.filter(q => q.mag >= 7 && now - q.time < 24 * H).length;
    const parts = { zone: top[0]?.score || 0, media: top.length ? Math.round(top.slice(0, 3).reduce((s, x) => s + x.score, 0) / Math.min(3, top.length)) : 0, emerg, kp, bigEq };
    const idx = Math.round(clamp(0.55 * parts.zone + 0.25 * parts.media + Math.min(12, emerg * 3) + (kp >= 7 ? 6 : kp >= 5 ? 3 : 0) + bigEq * 6, 0, 100));
    const lvl = idx >= 80 ? 1 : idx >= 65 ? 2 : idx >= 50 ? 3 : idx >= 35 ? 4 : 5;
    const prev = glob.lvl;
    glob = { idx, lvl, parts, top };
    if (lvl < prev && Date.now() - booted > 120e3) alert({ key: 'lvl' + lvl + new Date().toISOString().slice(0, 13), level: lvl <= 2 ? 'war' : 'orn', icon: '🚨', title: `Indice OJO salito: ALLERTA ${lvl}`, text: `${idx}/100 · zona più calda: ${DATA.HOTSPOTS.find(x => x.id === top[0]?.id)?.name || '--'}`, speak: `Livello di allerta salito a ${lvl}.` });
    Bus.emit('intel', { scores, glob });
    return glob;
  }

  /* ── briefing in italiano ── */
  function briefing() {
    const now = Date.now(), sp = S.space, ac = S.acList;
    const mil = ac.filter(a => a.isMil), isr = mil.filter(a => ['isr', 'tanker', 'drone'].includes(a.cls)), em = ac.filter(a => a.emerg);
    const top = (glob.top || []).slice(0, 3).map(t => ({ t, h: DATA.HOTSPOTS.find(x => x.id === t.id) }));
    const q24 = S.quakes.filter(q => now - q.time < 24 * H), q5 = q24.filter(q => q.mag >= 5), qmax = q24.reduce((m, q) => !m || q.mag > m.mag ? q : m, null);
    const grave = S.news.filter(n => n.sev >= 0.6 && now - n.date < 12 * H).slice(0, 4);
    const eoCats = {}; S.eonet.forEach(e => { eoCats[e.cat] = (eoCats[e.cat] || 0) + 1; });
    const eoTop = Object.entries(eoCats).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([c, n]) => `${(DATA.EONET[c] || ['', c])[1].toLowerCase()} ${n}`);
    const mk = Markets.Q, vix = mk['^VIX'], brent = mk['BZ=F'], gold = mk['GC=F'];
    const parts = [];
    parts.push([`Situazione alle ${Fmt.utc(now)} UTC — indice OJO `, h('b', null, `${glob.idx}/100`), ` (allerta ${glob.lvl}, calcolato, non ufficiale).`]);
    if (top.length && top[0].h) parts.push(['Zone più attive: ', ...top.flatMap(({ t, h: hh }, i) => [i ? ', ' : '', h('b', null, `${hh.flag} ${hh.name} ${t.score}`), ` (${t.news.length} notizie${t.grave ? ', ' + t.grave + ' gravi' : ''}${t.mil.length ? ', ' + t.mil.length + ' mil. ADS-B' : ''})`]), '.']);
    if (ac.length) parts.push([`Spazio aereo: `, h('b', null, Fmt.n(ac.length)), ` aerei tracciati, ${Fmt.n(mil.length)} militari, ${isr.length} ISR/rifornitori/droni.`,
      em.length ? h('span', { class: 'hot' }, ` Emergenze: ${em.slice(0, 3).map(a => (a.cs || a.hex) + ' ' + a.sq).join(', ')}.`) : ' Nessuno squawk di emergenza.']);
    else parts.push(['Spazio aereo: fonti ADS-B non raggiungibili al momento.']);
    if (q24.length) parts.push([`Sismicità 24h: ${q24.length} eventi, ${q5.length} di M5+`, qmax ? [', massimo ', h('b', null, `M${qmax.mag.toFixed(1)}`), ` ${qmax.place}`] : '', '.']);
    if (S.eonet.length) parts.push([`Eventi naturali NASA aperti: ${S.eonet.length} (${eoTop.join(', ')}).`]);
    if (sp.kp != null) parts.push([`Meteo spaziale: Kp ${sp.kp.toFixed(1)} (${sp.kp >= 7 ? 'tempesta forte' : sp.kp >= 5 ? 'tempesta' : sp.kp >= 4 ? 'attivo' : 'quieto'})${sp.wind ? ', vento solare ' + Math.round(sp.wind) + ' km/s' : ''}${sp.flare ? ', raggi X ' + sp.flare : ''}.`]);
    if (vix || brent || gold) {
      const bits = [vix && `VIX ${Fmt.pct(vix.chg)}`, brent && `Brent ${Fmt.pct(brent.chg)}`, gold && `oro ${Fmt.pct(gold.chg)}`].filter(Boolean);
      const risk = vix && gold && vix.chg > 5 && gold.chg > 0.5;
      parts.push([`Mercati: ${bits.join(', ')}.`, risk ? h('span', { class: 'hot' }, ' Segnale di avversione al rischio.') : '']);
    }
    if (grave.length) parts.push(['Titoli rilevanti: ', ...grave.flatMap((n, i) => [i ? ' · ' : '', h('span', { class: n.sev >= 0.8 ? 'hot' : '' }, `“${n.title.slice(0, 95)}” (${n.src})`)])]);
    const speech = [`Briefing delle ${Fmt.utc(now)}.`, `Indice di allerta ${glob.idx} su 100, livello ${glob.lvl}.`,
      top[0]?.h ? `Zona più attiva: ${top[0].h.name}.` : '', ac.length ? `${ac.length} aerei tracciati, di cui ${mil.length} militari.` : '',
      em.length ? `${em.length} emergenze in volo.` : '', qmax ? `Terremoto più forte: magnitudo ${qmax.mag.toFixed(1).replace('.', ' virgola ')}, ${qmax.place}.` : '',
      sp.kp != null ? `Indice K p ${sp.kp.toFixed(0)}.` : ''].filter(Boolean).join(' ');
    return { parts, speech, t: now };
  }

  /* ── luogo più vicino (terra/oceano) ── */
  const LAND = [...DATA.PLACES_COUNTRY.map(p => [p[3], p[1], p[2]]), ...DATA.LAND_EXTRA];
  function nearest(lat, lon) {
    let bl = null, bd = 1e9, bo = null, bdo = 1e9;
    for (const [label, a, o] of LAND) { const d = Geo.dist(lat, lon, a, o); if (d < bd) { bd = d; bl = label; } }
    for (const [label, a, o] of DATA.OCEANS) { const d = Geo.dist(lat, lon, a, o); if (d < bdo) { bdo = d; bo = label; } }
    if (bdo < bd * 0.75) return { label: bo, water: true, d: bdo };
    return { label: bd < 900 ? bl : bdo < bd ? bo : bl, water: bdo < bd, d: Math.min(bd, bdo) };
  }

  Bus.on('adsb', list => { analyzeAir(list); });
  Bus.on('news', list => analyzeNews(list));
  return { alert, score, briefing, nearest, get alerts() { return alerts; }, get scores() { return scores; }, get glob() { return glob; } };
})();
