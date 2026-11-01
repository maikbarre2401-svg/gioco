// Mappa: stile scuro costruito sulle tile VETTORIALI di OpenFreeMap (nessuna API key,
// stesso fornitore degli edifici 3D) e livelli di servizio: scie, anelli di chiamata.

import { CFG, colore } from './util.js';

const OFM = 'https://tiles.openfreemap.org';
const ATTR = '&copy; OpenStreetMap &middot; OpenFreeMap';
const LW = (a, b) => ['interpolate', ['exponential', 1.5], ['zoom'], 10, a, 18, b];
const IS = (...c) => ['match', ['get', 'class'], c, true, false];
const FONT = ['Noto Sans Regular'];
const VIA = (id, filtro, minzoom, c, w) => ({
  id, source: 'ofm', 'source-layer': 'transportation', type: 'line', minzoom, filter: filtro,
  layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': c, 'line-width': w },
});
const MIN = ['!', IS('motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'rail', 'transit')];
const SEC = IS('secondary', 'tertiary');
const MAIN = IS('motorway', 'trunk', 'primary');

export const STILE_SCURO = {
  version: 8, glyphs: OFM + '/fonts/{fontstack}/{range}.pbf',
  light: { anchor: 'viewport', color: '#dce9ff', intensity: .35, position: [1.3, 200, 35] },
  sources: { ofm: { type: 'vector', url: OFM + '/planet', attribution: ATTR } },
  layers: [
    { id: 'bg', type: 'background', paint: { 'background-color': '#060a0f' } },
    { id: 'uso', source: 'ofm', 'source-layer': 'landuse', type: 'fill',
      paint: { 'fill-color': ['match', ['get', 'class'], 'residential', '#0b1119', 'industrial', '#0f1117', '#0a1015'], 'fill-opacity': .55 } },
    { id: 'verde', source: 'ofm', 'source-layer': 'landcover', type: 'fill',
      paint: { 'fill-color': '#0c1a14', 'fill-opacity': .65 } },
    { id: 'parco', source: 'ofm', 'source-layer': 'park', type: 'fill',
      paint: { 'fill-color': '#0c1a14', 'fill-opacity': .45 } },
    { id: 'acqua', source: 'ofm', 'source-layer': 'water', type: 'fill', paint: { 'fill-color': '#07203a' } },
    { id: 'fiume', source: 'ofm', 'source-layer': 'waterway', type: 'line',
      paint: { 'line-color': '#07203a', 'line-width': LW(.6, 4) } },
    VIA('min-b', MIN, 12, '#0a1017', LW(.9, 8)), VIA('min', MIN, 12, '#1a2430', LW(.35, 5)),
    VIA('sec-b', SEC, 9, '#0a1017', LW(1.4, 11)), VIA('sec', SEC, 9, '#27384a', LW(.7, 7.5)),
    VIA('main-b', MAIN, 5, '#0a1017', LW(1.9, 16)), VIA('main', MAIN, 5, '#38506b', LW(1, 11)),
    { id: 'ferrovia', source: 'ofm', 'source-layer': 'transportation', type: 'line', minzoom: 11,
      filter: IS('rail', 'transit'),
      paint: { 'line-color': '#2a3444', 'line-width': LW(.4, 2), 'line-dasharray': [3, 2.5] } },
    { id: 'confine', source: 'ofm', 'source-layer': 'boundary', type: 'line',
      filter: ['<=', ['get', 'admin_level'], 6],
      paint: { 'line-color': '#28384a', 'line-dasharray': [2, 2], 'line-width': 1 } },
    { id: 'nome-strada', source: 'ofm', 'source-layer': 'transportation_name', type: 'symbol', minzoom: 14,
      layout: { 'text-field': ['get', 'name'], 'text-font': FONT, 'text-size': 11, 'symbol-placement': 'line' },
      paint: { 'text-color': '#718599', 'text-halo-color': '#060a0f', 'text-halo-width': 1.3 } },
    { id: 'nome-luogo', source: 'ofm', 'source-layer': 'place', type: 'symbol',
      filter: ['match', ['get', 'class'], ['city', 'town', 'suburb', 'neighbourhood'], true, false],
      layout: { 'text-field': ['get', 'name'], 'text-font': FONT, 'text-letter-spacing': .08,
        'text-transform': 'uppercase', 'text-size': ['match', ['get', 'class'], 'city', 15, 'town', 13, 11] },
      paint: { 'text-color': '#9fb3c8', 'text-halo-color': '#060a0f', 'text-halo-width': 1.5 } },
  ],
};

const EDIFICI = {
  id: 'b3d', source: 'ofm', 'source-layer': 'building', type: 'fill-extrusion', minzoom: 14,
  paint: {
    'fill-extrusion-color': ['interpolate', ['linear'], ['coalesce', ['get', 'render_height'], 10],
      0, '#141d2a', 40, '#1d2b40', 120, '#2a3f5c', 250, '#375178'],
    'fill-extrusion-height': ['coalesce', ['get', 'render_height'], 8],
    'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0],
    'fill-extrusion-vertical-gradient': true, 'fill-extrusion-opacity': .9,
  },
};

function stileRaster(tpl) {
  const t = tpl === 'osm' ? ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'] : [tpl];
  return { version: 8, sources: { r: { type: 'raster', tileSize: 256, tiles: t, attribution: ATTR } },
    layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#060a0f' } },
      { id: 'r', type: 'raster', source: 'r' }] };
}

export const base = CFG.basemap || 'vector';
export const mappa = new maplibregl.Map({
  container: 'mappa', center: [CFG.lon, CFG.lat], zoom: CFG.zoom || 15,
  pitch: 56, bearing: -18, maxPitch: 82, antialias: true,
  style: base === 'vector' ? STILE_SCURO : stileRaster(base),
});
mappa.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
mappa.on('error', () => { });   // le tile che mancano non devono fermare nulla

// I livelli NON si agganciano all'evento 'load': MapLibre lo emette solo quando anche le
// sorgenti hanno risposto, quindi con le tile lente o irraggiungibili non arriverebbe mai e
// i veicoli non comparirebbero più. Si prova e si ritenta finché non attecchisce.
function vuoto() { return { type: 'FeatureCollection', features: [] }; }

const inAttesa = [];
let pronta = false;
export function quandoPronta(fn) { inAttesa.push(fn); tenta(); }

function tenta() {
  let prima;
  try {
    if (!mappa.getSource('ofm')) mappa.addSource('ofm', { type: 'vector', url: OFM + '/planet', attribution: ATTR });
    prima = ((mappa.getStyle().layers || []).find(l => l.type === 'symbol') || {}).id;
    if (!mappa.getLayer('b3d')) mappa.addLayer(EDIFICI, prima);     // edifici sotto le etichette
    if (!mappa.getSource('scie')) mappa.addSource('scie', { type: 'geojson', data: vuoto() });
    if (!mappa.getLayer('scie')) mappa.addLayer({
      id: 'scie', type: 'line', source: 'scie',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': ['get', 'c'], 'line-width': 2, 'line-opacity': .5, 'line-dasharray': [1, 1.7] },
    }, prima);
    if (!mappa.getSource('anelli')) mappa.addSource('anelli', { type: 'geojson', data: vuoto() });
    if (!mappa.getLayer('anelli')) mappa.addLayer({
      id: 'anelli', type: 'circle', source: 'anelli',
      paint: { 'circle-radius': ['get', 'r'], 'circle-color': ['get', 'c'], 'circle-opacity': .07,
        'circle-stroke-color': ['get', 'c'], 'circle-stroke-width': 2, 'circle-stroke-opacity': ['get', 'o'] },
    }, prima);
  } catch (e) { setTimeout(tenta, 500); return; }
  pronta = true;
  while (inAttesa.length) {
    const fn = inAttesa.shift();
    try { fn(); } catch (e) { console.error('livello non installato', e); }
  }
}
mappa.on('load', tenta);
mappa.on('styledata', tenta);
const ritenta = setInterval(() => { tenta(); if (pronta) clearInterval(ritenta); }, 600);

// Se OpenFreeMap non risponde si resterebbe su uno sfondo nero: base di riserva OSM,
// scurita per non sfondare il tema. Una sorgente vettoriale irraggiungibile emette UN solo
// errore (il TileJSON), quindi non si contano gli errori: si guarda se è viva.
let controllata = false;
mappa.on('error', e => {
  if (base !== 'vector' || !e || e.sourceId !== 'ofm' || controllata) return;
  controllata = true;
  setTimeout(() => {
    try {
      if (mappa.getSource('riserva') || mappa.isSourceLoaded('ofm')) return;
      mappa.addSource('riserva', { type: 'raster', tileSize: 256, attribution: ATTR,
        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'] });
      const sotto = mappa.getLayer('uso') ? 'uso' : (mappa.getLayer('b3d') ? 'b3d' : undefined);
      mappa.addLayer({ id: 'riserva', type: 'raster', source: 'riserva',
        paint: { 'raster-opacity': .6, 'raster-saturation': -.85, 'raster-brightness-max': .5 } }, sotto);
      console.warn('OpenFreeMap non raggiungibile: uso la base di riserva OSM');
    } catch (err) { }
  }, 5000);
});

// ───── scie delle unità
const storico = new Map();
export function traccia(unita, lon, lat) {
  const s = storico.get(unita) || [];
  const ultimo = s[s.length - 1];
  if (!ultimo || Math.abs(ultimo[0] - lon) > 1e-6 || Math.abs(ultimo[1] - lat) > 1e-6) {
    s.push([lon, lat]);
    if (s.length > 14) s.shift();
  }
  storico.set(unita, s);
}
export function scordaUnita(unita) { storico.delete(unita); }
export function disegnaScie() {
  const src = mappa.getSource('scie'); if (!src) return;
  const f = [];
  storico.forEach((s, u) => { if (s.length > 1) f.push({ type: 'Feature', properties: { c: colore(u) }, geometry: { type: 'LineString', coordinates: s } }); });
  src.setData({ type: 'FeatureCollection', features: f });
}

// ───── anelli delle chiamate
const anelli = [];
let anelliVuoti = true;
export function anello(lon, lat, c) { anelli.push({ lon, lat, c, t0: performance.now() }); }
function animaAnelli() {
  const src = mappa.getSource('anelli'); if (!src) return;
  const t = performance.now();
  for (let i = anelli.length - 1; i >= 0; i--) if (t - anelli[i].t0 > 2600) anelli.splice(i, 1);
  if (!anelli.length) {
    if (!anelliVuoti) { src.setData(vuoto()); anelliVuoti = true; }
    return;
  }
  anelliVuoti = false;
  src.setData({ type: 'FeatureCollection', features: anelli.map(p => {
    const k = (t - p.t0) / 2600;
    return { type: 'Feature', properties: { r: 7 + k * 46, o: Math.max(0, .85 - k), c: p.c },
      geometry: { type: 'Point', coordinates: [p.lon, p.lat] } };
  }) });
}
setInterval(animaAnelli, 70);

// ───── telecamera che rispetta l'utente
let toccata = 0;
['dragstart', 'wheel', 'touchstart'].forEach(ev => mappa.on(ev, () => { toccata = Date.now(); }));
export const mossaDaPoco = () => Date.now() - toccata < 25000;
export function azzeraTocco() { toccata = 0; }
export function inquadra(lon, lat, zoom) {
  if (mossaDaPoco()) return false;
  mappa.easeTo({ center: [lon, lat], zoom: zoom || Math.max(mappa.getZoom(), 15.5), duration: 1600 });
  return true;
}
