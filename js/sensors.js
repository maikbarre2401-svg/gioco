import { $, toast, log, haptic, copyText, fitCanvas, fmt, COLORS } from './ui.js';

const state = { active: false, heading: null, smooth: null, beta: 0, gamma: 0, pos: null, shakes: 0, lastShake: 0 };
let watchId = null;
let raf = 0;
let orientEvent = null;

const CARDINALS = ['N', 'NE', 'E', 'SE', 'S', 'SO', 'O', 'NO'];
const cardinal = deg => CARDINALS[Math.round(deg / 45) % 8];

function onOrientation(e) {
  let h = null;
  if (typeof e.webkitCompassHeading === 'number') h = e.webkitCompassHeading; // iOS: already true heading
  else if (e.absolute && e.alpha != null) h = 360 - e.alpha; // Android absolute event
  if (h != null) {
    h = (h + (screen.orientation?.angle || 0) + 360) % 360;
    if (state.smooth == null) state.smooth = h;
    else {
      const diff = ((h - state.smooth + 540) % 360) - 180; // shortest way round the circle
      state.smooth = (state.smooth + diff * 0.2 + 360) % 360;
    }
    state.heading = state.smooth;
  }
  if (e.beta != null) { state.beta = e.beta; state.gamma = e.gamma; }
}

function onMotion(e) {
  const g = e.accelerationIncludingGravity;
  if (g && g.x != null) {
    const mag = Math.hypot(g.x, g.y, g.z) / 9.81;
    $('#mot-g').textContent = `${fmt.num(mag, 2)} g`;
  }
  const a = e.acceleration;
  const lin = a && a.x != null ? Math.hypot(a.x, a.y, a.z) : 0;
  const now = performance.now();
  if (lin > 14 && now - state.lastShake > 700) {
    state.lastShake = now;
    state.shakes++;
    $('#mot-shakes').textContent = state.shakes;
    log(`Scossone rilevato (${fmt.num(lin, 1)} m/s²)`, 'warn');
    haptic(30);
  }
}

function onPosition(p) {
  const c = p.coords;
  const first = !state.pos;
  state.pos = c;
  $('#gps-lat').textContent = fmt.num(c.latitude, 6);
  $('#gps-lon').textContent = fmt.num(c.longitude, 6);
  $('#gps-acc').textContent = `± ${Math.round(c.accuracy)} m`;
  $('#gps-alt').textContent = c.altitude != null ? `${Math.round(c.altitude)} m` : 'non disponibile';
  $('#gps-spd').textContent = c.speed != null ? `${fmt.num(c.speed * 3.6, 1)} km/h` : '0 km/h';
  const map = $('#gps-map');
  map.href = `https://www.openstreetmap.org/?mlat=${c.latitude}&mlon=${c.longitude}#map=17/${c.latitude}/${c.longitude}`;
  map.removeAttribute('aria-disabled');
  if (first) log(`Posizione agganciata (± ${Math.round(c.accuracy)} m)`, 'ok');
}

function onPositionError(err) {
  const msg = err.code === 1 ? 'Permesso posizione negato' : 'Segnale GPS non disponibile';
  $('#gps-acc').textContent = msg;
  log(msg, 'hot');
}

/* ---------------- drawing ---------------- */
function drawCompass() {
  const { ctx, w, h } = fitCanvas($('#compass'));
  const cx = w / 2, cy = h / 2, R = Math.min(w, h) / 2 - 6;
  ctx.clearRect(0, 0, w, h);
  const heading = state.heading ?? 0;

  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate((-heading * Math.PI) / 180);
  for (let d = 0; d < 360; d += 5) {
    const major = d % 30 === 0;
    const r1 = R - (major ? 14 : d % 10 === 0 ? 8 : 4);
    const a = (d * Math.PI) / 180;
    ctx.strokeStyle = major ? COLORS.cyan : COLORS.dim;
    ctx.lineWidth = major ? 2 : 1;
    ctx.beginPath();
    ctx.moveTo(Math.sin(a) * r1, -Math.cos(a) * r1);
    ctx.lineTo(Math.sin(a) * R, -Math.cos(a) * R);
    ctx.stroke();
  }
  ctx.font = '600 16px "Chakra Petch", sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  [['N', 0], ['E', 90], ['S', 180], ['O', 270]].forEach(([t, d]) => {
    const a = (d * Math.PI) / 180;
    ctx.fillStyle = t === 'N' ? COLORS.magenta : COLORS.fg;
    ctx.fillText(t, Math.sin(a) * (R - 30), -Math.cos(a) * (R - 30));
  });
  ctx.restore();

  ctx.strokeStyle = COLORS.line;
  ctx.beginPath(); ctx.arc(cx, cy, R * 0.5, 0, Math.PI * 2); ctx.stroke();
  ctx.fillStyle = COLORS.magenta;
  ctx.beginPath(); ctx.moveTo(cx, cy - R - 2); ctx.lineTo(cx - 8, cy - R + 14); ctx.lineTo(cx + 8, cy - R + 14); ctx.closePath(); ctx.fill();

  $('#sns-heading').textContent = state.heading == null ? '---' : String(Math.round(heading) % 360).padStart(3, '0');
  $('#sns-card').textContent = state.heading == null ? '' : ` ${cardinal(heading)}`;
}

function drawLevel() {
  const { ctx, w, h } = fitCanvas($('#level'));
  const cx = w / 2, cy = h / 2, R = Math.min(w, h) / 2 - 6;
  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = COLORS.line;
  ctx.lineWidth = 1;
  [1, 0.66, 0.33].forEach(k => { ctx.beginPath(); ctx.arc(cx, cy, R * k, 0, Math.PI * 2); ctx.stroke(); });
  ctx.beginPath(); ctx.moveTo(cx - R, cy); ctx.lineTo(cx + R, cy); ctx.moveTo(cx, cy - R); ctx.lineTo(cx, cy + R); ctx.stroke();

  const clamp = v => Math.max(-45, Math.min(45, v));
  const x = cx + (clamp(state.gamma) / 45) * (R - 18);
  const y = cy + (clamp(state.beta) / 45) * (R - 18);
  const tilt = Math.hypot(state.beta, state.gamma);
  const flat = tilt < 1.5;
  ctx.strokeStyle = flat ? COLORS.ok : COLORS.cyan;
  ctx.fillStyle = flat ? 'rgba(77,255,176,.18)' : 'rgba(46,242,255,.14)';
  ctx.lineWidth = 2;
  ctx.beginPath(); ctx.arc(x, y, 16, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
  if (state.active) $('#mot-tilt').textContent = flat ? 'in bolla' : `${fmt.num(tilt, 1)}°`;
}

function loop() {
  drawCompass();
  drawLevel();
  raf = requestAnimationFrame(loop);
}

/* ---------------- lifecycle ---------------- */
async function start() {
  // iOS 13+ needs an explicit permission request from a tap.
  try {
    if (typeof DeviceOrientationEvent?.requestPermission === 'function') {
      const r = await DeviceOrientationEvent.requestPermission();
      if (r !== 'granted') toast('Bussola e livella richiedono il permesso sensori');
    }
    if (typeof DeviceMotionEvent?.requestPermission === 'function') await DeviceMotionEvent.requestPermission();
  } catch { /* permission prompt unavailable */ }

  orientEvent = 'ondeviceorientationabsolute' in window ? 'deviceorientationabsolute' : 'deviceorientation';
  window.addEventListener(orientEvent, onOrientation);
  window.addEventListener('devicemotion', onMotion);

  if ('geolocation' in navigator) {
    $('#gps-acc').textContent = 'ricerca satelliti…';
    watchId = navigator.geolocation.watchPosition(onPosition, onPositionError, { enableHighAccuracy: true, maximumAge: 2000, timeout: 20000 });
  } else {
    $('#gps-acc').textContent = 'GPS non supportato';
  }

  state.active = true;
  const btn = $('#sns-start');
  btn.textContent = 'Spegni sensori';
  btn.classList.add('danger');
  log('Sensori attivati', 'ok');
  haptic(15);
  setTimeout(() => {
    if (state.active && state.heading == null) $('#sns-card').textContent = ' bussola non disponibile';
  }, 2500);
}

function stop() {
  if (orientEvent) window.removeEventListener(orientEvent, onOrientation);
  window.removeEventListener('devicemotion', onMotion);
  if (watchId != null) navigator.geolocation.clearWatch(watchId);
  watchId = null;
  if (state.active) log('Sensori spenti');
  state.active = false;
  const btn = $('#sns-start');
  btn.textContent = 'Attiva sensori';
  btn.classList.remove('danger');
}

export function init() {
  $('#sns-start').addEventListener('click', () => (state.active ? stop() : start()));
  $('#gps-copy').addEventListener('click', () => {
    if (!state.pos) { toast('Attiva i sensori e aspetta il segnale GPS'); return; }
    copyText(`${state.pos.latitude.toFixed(6)}, ${state.pos.longitude.toFixed(6)}`, 'Coordinate copiate');
  });
}

export function enter() {
  cancelAnimationFrame(raf);
  raf = requestAnimationFrame(loop);
}

export function leave() {
  cancelAnimationFrame(raf);
  stop();
}
