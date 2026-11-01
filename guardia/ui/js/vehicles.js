// Mezzi e aeromobili in 3D (Three.js dentro un custom layer di MapLibre) più le
// targhette che li seguono. Tutto quello che si muove a 60 fps sta qui.

import { colore, colore3, eta } from './util.js';
import { mappa, quandoPronta, traccia, scordaUnita, disegnaScie } from './map.js';

export const c3d = typeof THREE !== 'undefined';
const V = { auto: new Map(), eli: new Map(), scena: null, render: null, camera: null };
const targhette = new Map();

// La misura è costante sullo SCHERMO (~11 px), non in metri: con un fattore fisso a zoom
// stretto spariscono e a zoom largo diventano autobus sopra i palazzi. Da 18.1 in su
// sono a misura reale.
export const scala = (min = 1) => Math.min(26, Math.max(min, Math.pow(2, 18.1 - mappa.getZoom())));

function matrice(lng, lat, alt, s) {
  const c = maplibregl.MercatorCoordinate.fromLngLat([lng, lat], alt || 0);
  const k = c.meterInMercatorCoordinateUnits() * s;
  return new THREE.Matrix4().makeTranslation(c.x, c.y, c.z)
    .scale(new THREE.Vector3(k, -k, k))
    .multiply(new THREE.Matrix4().makeRotationAxis(new THREE.Vector3(1, 0, 0), Math.PI / 2));
}

function costruisciAuto(hex, camion) {
  const g = new THREE.Group();
  const L = camion ? 7 : 4.6, H = camion ? 1.8 : .92, W = camion ? 2.4 : 1.9;
  const scocca = new THREE.Mesh(new THREE.BoxGeometry(W, H, L),
    new THREE.MeshStandardMaterial({ color: hex, metalness: .35, roughness: .45 }));
  scocca.position.y = .5 + H / 2; g.add(scocca);
  const abitacolo = new THREE.Mesh(new THREE.BoxGeometry(W * .9, .66, camion ? 2.5 : 2),
    new THREE.MeshStandardMaterial({ color: 0x070b10, metalness: .1, roughness: .2 }));
  abitacolo.position.set(0, .5 + H + .3, camion ? L * .2 : -.2); g.add(abitacolo);
  const lampeggiante = new THREE.Mesh(new THREE.BoxGeometry(W * .66, .2, .42),
    new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0x3366ff, emissiveIntensity: 1.6 }));
  lampeggiante.position.set(0, .5 + H + .7, camion ? L * .2 : 0); g.add(lampeggiante);
  g.userData.lampeggiante = lampeggiante;
  const alone = new THREE.Mesh(new THREE.RingGeometry(2.6, 3.4, 32),
    new THREE.MeshBasicMaterial({ color: hex, transparent: true, opacity: .35, depthWrite: false, side: THREE.DoubleSide }));
  alone.rotation.x = -Math.PI / 2; alone.position.y = .05; g.add(alone); g.userData.alone = alone;
  const gomma = new THREE.MeshStandardMaterial({ color: 0x08080a });
  [[W / 2, L * .3], [-W / 2, L * .3], [W / 2, -L * .3], [-W / 2, -L * .3]].forEach(p => {
    const r = new THREE.Mesh(new THREE.CylinderGeometry(.42, .42, .28, 12), gomma);
    r.rotation.z = Math.PI / 2; r.position.set(p[0], .45, p[1]); g.add(r);
  });
  return g;
}

function costruisciElicottero() {
  const g = new THREE.Group();
  const mat = new THREE.MeshStandardMaterial({ color: 0xd97706, metalness: .45, roughness: .5 });
  const corpo = new THREE.Mesh(new THREE.SphereGeometry(1.7, 18, 12), mat);
  corpo.scale.set(1, .9, 1.6); corpo.position.y = 1.9; g.add(corpo);
  const trave = new THREE.Mesh(new THREE.CylinderGeometry(.34, .2, 5.2, 12), mat);
  trave.rotation.x = Math.PI / 2; trave.position.set(0, 2.2, -3.7); g.add(trave);
  const coda = new THREE.Mesh(new THREE.BoxGeometry(.18, 1.4, .44), mat);
  coda.position.set(0, 2.5, -6); g.add(coda);
  const rotore = new THREE.Group(); rotore.position.y = 3.3;
  const pm = new THREE.MeshStandardMaterial({ color: 0x14161a });
  const p1 = new THREE.Mesh(new THREE.BoxGeometry(11, .1, .5), pm); rotore.add(p1);
  const p2 = p1.clone(); p2.rotation.y = Math.PI / 2; rotore.add(p2);
  g.add(rotore); g.userData.rotore = rotore;
  const pattino = new THREE.MeshStandardMaterial({ color: 0x08080a });
  [-1.2, 1.2].forEach(x => {
    const s = new THREE.Mesh(new THREE.BoxGeometry(.16, .16, 4.4), pattino);
    s.position.set(x, .2, 0); g.add(s);
  });
  return g;
}

const livello3d = {
  id: 'veicoli', type: 'custom', renderingMode: '3d',
  onAdd(m, gl) {
    V.camera = new THREE.Camera();
    V.scena = new THREE.Scene();
    V.scena.add(new THREE.AmbientLight(0xffffff, .9));
    const d = new THREE.DirectionalLight(0xdce9ff, .7);
    d.position.set(.4, -1, .8); V.scena.add(d);
    V.render = new THREE.WebGLRenderer({ canvas: m.getCanvas(), context: gl, antialias: true });
    V.render.autoClear = false;
  },
  render(gl, arg) {
    let a = arg;   // MapLibre 4 passa un oggetto, le versioni precedenti la matrice
    if (a && !Array.isArray(a)) a = (a.defaultProjectionData && a.defaultProjectionData.mainMatrix) || a;
    anima();
    V.camera.projectionMatrix = new THREE.Matrix4().fromArray(a);
    V.render.resetState();
    V.render.render(V.scena, V.camera);
    mappa.triggerRepaint();
  },
};

function anima() {
  const t = Date.now(), s = scala(1), se = scala(1) * .62;
  V.auto.forEach((v, k) => {
    v.lng += (v.tlng - v.lng) * .12;
    v.lat += (v.tlat - v.lat) * .12;
    const dx = v.tlng - v.lng, dy = v.tlat - v.lat;
    if (Math.hypot(dx, dy) > 1e-6) v.rotta = Math.atan2(dx, dy);
    v.interno.rotation.y = v.rotta;
    v.esterno.matrix.copy(matrice(v.lng, v.lat, 0, s));
    v.esterno.matrixWorldNeedsUpdate = true;
    if (v.lampeggiante) v.lampeggiante.material.emissive.setHex((t % 700) < 350 ? 0x3366ff : 0xff2b2b);
    if (v.alone) {
      const p = 1 + .12 * Math.sin(t / 260);
      v.alone.scale.set(p, p, p);
      v.alone.material.opacity = .22 + .14 * Math.sin(t / 260);
    }
    const tg = targhette.get(k);
    if (tg) tg.setLngLat([v.lng, v.lat]);
  });
  V.eli.forEach(v => {
    v.lng += (v.tlng - v.lng) * .1;
    v.lat += (v.tlat - v.lat) * .1;
    v.esterno.matrix.copy(matrice(v.lng, v.lat, v.alt, se));
    v.esterno.matrixWorldNeedsUpdate = true;
    if (v.rotore) v.rotore.rotation.y += .7;
  });
}

function nuovaAuto(u) {
  const esterno = new THREE.Group(); esterno.matrixAutoUpdate = false;
  const interno = new THREE.Group();
  const modello = costruisciAuto(colore3(u.unit), u.unit === 'VVF');
  interno.add(modello); esterno.add(interno); V.scena.add(esterno);
  const v = { esterno, interno, lampeggiante: modello.userData.lampeggiante, alone: modello.userData.alone,
    lng: u.lon, lat: u.lat, tlng: u.lon, tlat: u.lat, rotta: 0 };
  V.auto.set(u.unit, v);
  return v;
}

function nuovoElicottero(a) {
  const esterno = new THREE.Group(); esterno.matrixAutoUpdate = false;
  const modello = costruisciElicottero(); esterno.add(modello); V.scena.add(esterno);
  const v = { esterno, rotore: modello.userData.rotore, lng: a.lon, lat: a.lat, tlng: a.lon, tlat: a.lat, alt: 120 };
  V.eli.set(a.hex, v);
  return v;
}

// targhetta: marker DOM, nitido a ogni zoom e leggibile anche dietro un palazzo
function targhetta(u) {
  let m = targhette.get(u.unit);
  if (!m) {
    const e = document.createElement('div');
    e.className = 'targhetta';
    e.style.borderLeftColor = colore(u.unit);
    e.append(document.createElement('span'), document.createElement('i'));
    m = new maplibregl.Marker({ element: e, anchor: 'bottom', offset: [0, -18] })
      .setLngLat([u.lon, u.lat]).addTo(mappa);
    targhette.set(u.unit, m);
  }
  const e = m.getElement();
  e.firstChild.textContent = u.unit;
  e.lastChild.textContent = eta(u.age);
  e.style.opacity = Math.max(.35, 1 - u.age / 320);
  return m;
}

// ripiego 2D: se Three.js non è disponibile restano i segnaposto
const dom = { auto: new Map(), eli: new Map() };
function aggiornaDOM(units, air) {
  units.forEach(u => {
    let m = dom.auto.get(u.unit);
    if (!m) { m = new maplibregl.Marker({ color: colore(u.unit) }).setLngLat([u.lon, u.lat]).addTo(mappa); dom.auto.set(u.unit, m); }
    m.setLngLat([u.lon, u.lat]);
    m.getElement().style.opacity = Math.max(.3, 1 - u.age / 300);
  });
  air.forEach(a => {
    let m = dom.eli.get(a.hex);
    if (!m) { m = new maplibregl.Marker({ color: '#d97706' }).setLngLat([a.lon, a.lat]).addTo(mappa); dom.eli.set(a.hex, m); }
    m.setLngLat([a.lon, a.lat]);
  });
}

export function installa() {
  if (!c3d) return false;
  quandoPronta(() => { if (!mappa.getLayer('veicoli')) mappa.addLayer(livello3d); });
  return true;
}

export function aggiorna(units, air) {
  const conPos = (units || []).filter(u => u.lat != null);
  const aerei = (air || []).filter(a => a.lat != null && a.lon != null);
  if (c3d && V.scena) {
    const vive = new Set();
    conPos.forEach(u => {
      vive.add(u.unit);
      const v = V.auto.get(u.unit) || nuovaAuto(u);
      v.tlng = u.lon; v.tlat = u.lat;
    });
    V.auto.forEach((v, k) => { if (!vive.has(k)) { V.scena.remove(v.esterno); V.auto.delete(k); } });
    const volano = new Set();
    aerei.forEach(a => {
      volano.add(a.hex);
      const v = V.eli.get(a.hex) || nuovoElicottero(a);
      v.tlng = a.lon; v.tlat = a.lat; v.alt = Math.min(a.alt || 120, 300);
    });
    V.eli.forEach((v, k) => { if (!volano.has(k)) { V.scena.remove(v.esterno); V.eli.delete(k); } });
  } else {
    aggiornaDOM(conPos, aerei);
  }
  const vive = new Set(conPos.map(u => u.unit));
  conPos.forEach(u => { targhetta(u); traccia(u.unit, u.lon, u.lat); });
  targhette.forEach((m, k) => { if (!vive.has(k)) { m.remove(); targhette.delete(k); scordaUnita(k); } });
  disegnaScie();
}

/** Le unità che stanno trasmettendo pulsano sulla mappa. */
export function inOnda(unita) {
  targhette.forEach((m, k) => m.getElement().classList.toggle('onda', unita.has(k)));
}

export function posizione(unita) {
  const v = V.auto.get(unita);
  return v ? [v.tlng, v.tlat] : null;
}
