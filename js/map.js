window.GL = window.GL || {};

(() => {
  'use strict';

  const { $, toast, log, haptic, fmt } = GL.ui;
  const RADIUS = 700;
  const OVERPASS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter'];

  // Real-world objects from OpenStreetMap, grouped like ctOS layers.
  const CATS = {
    cam: { label: 'Telecamere', one: 'Telecamera', glyph: '◉', test: t => t.man_made === 'surveillance' || t.highway === 'speed_camera' },
    sem: { label: 'Semafori', one: 'Semaforo', glyph: '▮', test: t => t.highway === 'traffic_signals' },
    ant: { label: 'Antenne', one: 'Antenna', glyph: '⟟', test: t => /mast|tower|communications_tower/.test(t.man_made || '') || t['communication:mobile_phone'] === 'yes' },
    wifi: { label: 'Hotspot Wi-Fi', one: 'Hotspot Wi-Fi', glyph: '≋', test: t => /wlan|wifi/.test(t.internet_access || '') },
    aed: { label: 'Defibrillatori', one: 'Defibrillatore', glyph: '✚', test: t => t.emergency === 'defibrillator' },
    ev: { label: 'Ricarica auto', one: 'Colonnina di ricarica', glyph: 'ϟ', test: t => t.amenity === 'charging_station' },
  };

  let map = null, me = null, ring = null, watchId = null, pos = null, layers = {}, counts = {}, scanning = false;
  let selected = null;
  let hackTimer = 0; // analysis animation

  function query(lat, lon) {
    const a = `(around:${RADIUS},${lat},${lon})`;
    return `[out:json][timeout:25];(
      node${a}["man_made"="surveillance"];node${a}["highway"="speed_camera"];
      node${a}["highway"="traffic_signals"];
      node${a}["man_made"~"^(mast|tower|communications_tower)$"];node${a}["communication:mobile_phone"="yes"];
      node${a}["internet_access"~"wlan|wifi"];
      node${a}["emergency"="defibrillator"];
      node${a}["amenity"="charging_station"];
    );out center 500;`;
  }

  function distance(a, b) {
    const R = 6371000, toRad = d => (d * Math.PI) / 180;
    const dLat = toRad(b.lat - a.lat), dLon = toRad(b.lon - a.lon);
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  }

  function ensureMap() {
    if (map) { setTimeout(() => map.invalidateSize(), 50); return true; }
    if (!window.L) { $('#map-status').textContent = 'Mappa non disponibile'; return false; }
    map = L.map('map', { zoomControl: false, attributionControl: false, center: [41.9028, 12.4964], zoom: 15 });
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      subdomains: 'abcd', maxZoom: 20, detectRetina: true,
    }).addTo(map);
    Object.keys(CATS).forEach(k => { layers[k] = L.layerGroup().addTo(map); counts[k] = 0; });
    renderLegend();
    setTimeout(() => map.invalidateSize(), 50);
    return true;
  }

  function onPosition(p) {
    const first = !pos;
    pos = { lat: p.coords.latitude, lon: p.coords.longitude, acc: p.coords.accuracy };
    $('#map-status').textContent = `GPS ± ${Math.round(pos.acc)} m`;
    $('#map-status').className = 'chip on';
    $('#map-coords').textContent = `${pos.lat.toFixed(4)}, ${pos.lon.toFixed(4)}`;
    const ll = [pos.lat, pos.lon];
    if (!me) {
      me = L.marker(ll, { icon: L.divIcon({ className: '', html: '<span class="mk-me"></span>', iconSize: [22, 22] }), interactive: false }).addTo(map);
      ring = L.circle(ll, { radius: RADIUS, color: '#2ef2ff', weight: 1, opacity: 0.5, fillOpacity: 0.04, dashArray: '4 6', interactive: false }).addTo(map);
    } else { me.setLatLng(ll); ring.setLatLng(ll); }
    if (first) { map.setView(ll, 16); log('Mappa: posizione agganciata', 'ok'); }
  }

  function onPositionError(err) {
    $('#map-status').textContent = err.code === 1 ? 'Permesso posizione negato' : 'GPS non disponibile';
    $('#map-status').className = 'chip off';
  }

  function renderLegend() {
    const box = $('#map-legend');
    box.replaceChildren(...Object.entries(CATS).map(([k, c]) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = `legend-chip lg-${k}`;
      b.setAttribute('aria-pressed', 'true');
      b.innerHTML = `<i>${c.glyph}</i><span>${c.label}</span><b>${counts[k] || 0}</b>`;
      b.addEventListener('click', () => {
        const on = b.getAttribute('aria-pressed') !== 'true';
        b.setAttribute('aria-pressed', String(on));
        if (on) layers[k].addTo(map); else layers[k].remove();
        GL.sfx.play('tap');
      });
      return b;
    }));
  }

  async function overpass(q) {
    let lastErr;
    for (const url of OVERPASS) {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 30000);
      try {
        const res = await fetch(url, { method: 'POST', body: new URLSearchParams({ data: q }), signal: ctrl.signal });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
      } catch (e) { lastErr = e; } finally { clearTimeout(timer); }
    }
    throw lastErr;
  }

  async function scanArea() {
    if (scanning) return;
    if (!pos) { toast('Aspetta il segnale GPS (consenti la posizione)'); return; }
    scanning = true;
    const btn = $('#map-start');
    btn.disabled = true;
    btn.textContent = 'Scansione della zona…';
    $('.map-wrap').classList.add('scanning');
    GL.sfx.play('nav');
    try {
      const data = await overpass(query(pos.lat, pos.lon));
      Object.values(layers).forEach(l => l.clearLayers());
      Object.keys(counts).forEach(k => { counts[k] = 0; });
      for (const el of data.elements || []) {
        const lat = el.lat ?? el.center?.lat, lon = el.lon ?? el.center?.lon;
        if (lat == null) continue;
        const t = el.tags || {};
        const cat = Object.keys(CATS).find(k => CATS[k].test(t));
        if (!cat) continue;
        counts[cat]++;
        const item = { id: el.id, type: el.type, lat, lon, tags: t, cat };
        L.marker([lat, lon], { icon: L.divIcon({ className: '', html: `<span class="mk mk-${cat}">${CATS[cat].glyph}</span>`, iconSize: [26, 26] }) })
          .on('click', () => select(item))
          .addTo(layers[cat]);
      }
      renderLegend();
      const total = Object.values(counts).reduce((a, b) => a + b, 0);
      log(`Zona scansionata: ${total} oggetti (${counts.cam} telecamere)`, total ? 'ok' : 'warn');
      toast(total ? `${total} oggetti trovati entro ${RADIUS} m` : 'Nessun oggetto mappato qui vicino');
      GL.sfx.play(total ? 'ok' : 'err');
      GL.app?.xp(20, 'mappa');
      haptic([15, 40, 15]);
    } catch (e) {
      toast('Server delle mappe non raggiungibile: riprova tra poco', 3500);
      GL.sfx.play('err');
    } finally {
      scanning = false;
      btn.disabled = false;
      btn.textContent = 'Scansiona di nuovo';
      $('.map-wrap').classList.remove('scanning');
    }
  }

  const DETAILS = [
    ['operator', 'Gestore'], ['surveillance', 'Zona'], ['surveillance:type', 'Tipo'], ['camera:type', 'Ottica'],
    ['camera:direction', 'Direzione'], ['direction', 'Direzione'], ['surveillance:zone', 'Sorveglia'], ['brand', 'Marchio'],
    ['network', 'Rete'], ['height', 'Altezza'], ['opening_hours', 'Orari'], ['traffic_signals', 'Tipo'],
    ['indoor', 'Al chiuso'], ['access', 'Accesso'], ['defibrillator:location', 'Dove si trova'], ['socket:type2', 'Prese tipo 2'],
    ['capacity', 'Posti'], ['ssid', 'Nome rete'], ['internet_access:fee', 'A pagamento'],
    ['crossing', 'Attraversamento'], ['button_operated', 'A chiamata'], ['maxspeed', 'Limite'], ['fee', 'A pagamento'],
  ];
  const VALUES = { public: 'pubblica', outdoor: 'esterna', indoor: 'interna', camera: 'telecamera', fixed: 'fissa', dome: 'a cupola', panning: 'motorizzata', traffic: 'traffico', town: 'città', yes: 'sì', no: 'no', signals: 'semaforico', traffic_lights: 'semaforo' };

  function select(item) {
    selected = item;
    clearInterval(hackTimer);
    const c = CATS[item.cat];
    const t = item.tags;
    $('#map-target').hidden = false;
    $('#tg-type').textContent = `${c.one} · OSM ${item.type === 'way' ? 'W' : 'N'}${item.id}`;
    $('#tg-name').textContent = t.name || t.operator || t.brand || t.ref || `${c.one} ${String(item.id).slice(-4)}`;
    const rows = [['Distanza', `${fmt.num(distance(pos || item, item), 0)} m`]];
    DETAILS.forEach(([k, label]) => { if (t[k]) rows.push([label, VALUES[t[k]] || t[k]]); });
    rows.push(['Coordinate', `${item.lat.toFixed(5)}, ${item.lon.toFixed(5)}`]);
    $('#tg-rows').replaceChildren(...rows.map(([k, v]) => {
      const d = document.createElement('div');
      d.className = 'kv';
      const s = document.createElement('span'); s.textContent = k;
      const b = document.createElement('b'); b.textContent = v;
      d.append(s, b);
      return d;
    }));
    [...$('#tg-rows').children].forEach((r, i) => { r.hidden = i > 0; });
    $('#tg-bar').style.width = '0';
    $('#tg-log').replaceChildren();
    $('#tg-hack').disabled = false;
    $('#tg-hack').textContent = 'Analizza';
    map.panTo([item.lat, item.lon]);
    GL.sfx.play('lock');
    haptic(15);
    $('#map-target').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  const SUMMARY = {
    cam: t => `Telecamera ${t.surveillance === 'public' ? 'su area pubblica' : 'registrata nella mappa'}${t.operator ? `, gestita da ${t.operator}` : ''}.`,
    sem: () => 'Incrocio regolato da semaforo, parte della rete del traffico cittadino.',
    ant: t => `Stazione radio${t.operator ? ` di ${t.operator}` : ''}: da qui passa il traffico dei telefoni della zona.`,
    wifi: t => `Punto con accesso Wi-Fi${t.internet_access === 'wlan' ? ' pubblico' : ''}${t['internet_access:fee'] === 'no' ? ' gratuito' : ''}.`,
    aed: t => `Defibrillatore pubblico${t.opening_hours ? `, disponibile ${t.opening_hours}` : ''}. In emergenza chiama il 112.`,
    ev: t => `Colonnina di ricarica${t.operator ? ` ${t.operator}` : ''}${t.capacity ? ` con ${t.capacity} posti` : ''}.`,
  };

  // Reveals the public data one row at a time, ctOS style.
  function analyze() {
    if (!selected) return;
    const btn = $('#tg-hack');
    const rows = [...$('#tg-rows').children];
    btn.disabled = true;
    btn.textContent = 'Analisi in corso…';
    $('#tg-log').replaceChildren();
    GL.sfx.play('hack');
    let p = 0;
    clearInterval(hackTimer);
    hackTimer = setInterval(() => {
      p += 4 + Math.random() * 6;
      $('#tg-bar').style.width = `${Math.min(100, p)}%`;
      const show = Math.ceil((Math.min(p, 100) / 100) * rows.length);
      rows.forEach((r, i) => {
        if (i < show && r.hidden) { r.hidden = false; GL.sfx.play('type'); }
      });
      if (p >= 100) {
        clearInterval(hackTimer);
        const done = document.createElement('div');
        done.className = 'ok';
        done.textContent = `✔ ${SUMMARY[selected.cat](selected.tags)}`;
        $('#tg-log').append(done);
        btn.textContent = 'Analisi completata';
        GL.sfx.play('ok');
        haptic([20, 50, 20]);
        log(`Analizzato: ${CATS[selected.cat].one.toLowerCase()}`, 'ok');
        GL.app?.xp(10, 'analisi');
      }
    }, 110);
  }

  function init() {
    $('#map-start').addEventListener('click', scanArea);
    $('#map-locate').addEventListener('click', () => { if (pos && map) map.setView([pos.lat, pos.lon], 17); GL.sfx.play('tap'); });
    $('#tg-hack').addEventListener('click', analyze);
    $('#tg-close').addEventListener('click', () => { $('#map-target').hidden = true; clearInterval(hackTimer); selected = null; });
  }

  function enter() {
    if (!ensureMap()) return;
    if ('geolocation' in navigator && watchId == null) {
      watchId = navigator.geolocation.watchPosition(onPosition, onPositionError, { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 });
    }
  }

  function leave() {
    if (watchId != null) navigator.geolocation.clearWatch(watchId);
    watchId = null;
    clearInterval(hackTimer);
  }

  GL.map = { init, enter, leave };
})();
