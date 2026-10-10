window.GL = window.GL || {};

(() => {
  'use strict';

  const { $, toast, log, haptic, fmt } = GL.ui;
  const APIS = ['https://api.wheretheiss.at/v1/satellites/25544', 'https://api.open-notify.org/iss-now.json'];
  let map = null, marker = null, trail = null, me = null, timer = 0, trailPts = [];

  function ensureMap() {
    if (map) { setTimeout(() => map.invalidateSize(), 50); return true; }
    if (!window.L) { toast('Mappa non disponibile'); return false; }
    map = L.map('iss-map', { zoomControl: false, attributionControl: false, worldCopyJump: true, center: [20, 0], zoom: 2 });
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { subdomains: 'abcd', maxZoom: 7, detectRetina: true }).addTo(map);
    trail = L.polyline([], { color: '#2ef2ff', weight: 2, opacity: 0.6 }).addTo(map);
    setTimeout(() => map.invalidateSize(), 50);
    return true;
  }

  function distance(a, b) {
    const R = 6371, toRad = d => d * Math.PI / 180;
    const dLat = toRad(b.lat - a.lat), dLon = toRad(b.lon - a.lon);
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  }

  async function fetchISS() {
    try {
      const r = await fetch(APIS[0], { cache: 'no-store' });
      if (!r.ok) throw 0;
      const d = await r.json();
      return { lat: d.latitude, lon: d.longitude, alt: d.altitude, vel: d.velocity, vis: d.visibility };
    } catch {
      const r = await fetch(APIS[1], { cache: 'no-store' });
      const d = await r.json();
      return { lat: +d.iss_position.latitude, lon: +d.iss_position.longitude, alt: 420, vel: 27600, vis: null };
    }
  }

  async function update() {
    try {
      const iss = await fetchISS();
      const ll = [iss.lat, iss.lon];
      if (!marker) {
        marker = L.marker(ll, { icon: L.divIcon({ className: '', html: '<span class="iss-mk">🛰</span>', iconSize: [34, 34] }) }).addTo(map);
        map.setView(ll, 3);
      } else marker.setLatLng(ll);
      trailPts.push(ll);
      if (trailPts.length > 60) trailPts.shift();
      trail.setLatLngs(trailPts);

      $('#iss-lat').textContent = fmt.num(iss.lat, 4);
      $('#iss-lon').textContent = fmt.num(iss.lon, 4);
      $('#iss-alt').textContent = `${fmt.num(iss.alt, 0)} km`;
      $('#iss-vel').textContent = `${fmt.num(iss.vel, 0)} km/h`;
      $('#iss-vis').textContent = iss.vis ? (iss.vis === 'daylight' ? 'alla luce del sole' : 'in ombra') : '—';
      $('#iss-status').textContent = 'in diretta'; $('#iss-status').className = 'chip on';

      GL.map && navigator.geolocation?.getCurrentPosition(p => {
        const d = distance({ lat: p.coords.latitude, lon: p.coords.longitude }, iss);
        $('#iss-dist').textContent = `${fmt.num(d, 0)} km da te`;
        if (!me) me = L.circleMarker([p.coords.latitude, p.coords.longitude], { radius: 5, color: '#ff2d75', fillOpacity: 1 }).addTo(map);
      }, () => {}, { maximumAge: 60000, timeout: 8000 });
    } catch {
      $('#iss-status').textContent = 'non raggiungibile'; $('#iss-status').className = 'chip off';
    }
  }

  function init() { /* nothing until the screen opens */ }

  function enter() {
    if (!ensureMap()) return;
    update();
    GL.app?.xp(4, 'iss');
    log('Tracker ISS avviato', 'ok');
    timer = setInterval(update, 5000);
  }
  function leave() { clearInterval(timer); timer = 0; }

  GL.iss = { init, enter, leave };
})();
