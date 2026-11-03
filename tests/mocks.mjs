// Risposte simulate (realistiche) per tutte le API usate da OJO DE DEUS.
// Servono a testare l'app offline in Chromium headless con Playwright.
import zlib from 'node:zlib';
import { readFileSync, existsSync } from 'node:fs';
import { join, extname } from 'node:path';

/* ── PNG minimale ── */
const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
const crc32 = b => { let c = 0xffffffff; for (const x of b) c = CRC[(c ^ x) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
function chunk(type, data) { const l = Buffer.alloc(4); l.writeUInt32BE(data.length); const td = Buffer.concat([Buffer.from(type), data]); const c = Buffer.alloc(4); c.writeUInt32BE(crc32(td)); return Buffer.concat([l, td, c]); }
export function png(w, h, px) {               // px(x,y) -> [r,g,b,a]
  const raw = Buffer.alloc((w * 4 + 1) * h);
  for (let y = 0; y < h; y++) { raw[y * (w * 4 + 1)] = 0; for (let x = 0; x < w; x++) { const [r, g, b, a] = px(x, y); const o = y * (w * 4 + 1) + 1 + x * 4; raw[o] = r; raw[o + 1] = g; raw[o + 2] = b; raw[o + 3] = a; } }
  const ih = Buffer.alloc(13); ih.writeUInt32BE(w, 0); ih.writeUInt32BE(h, 4); ih[8] = 8; ih[9] = 6;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ih), chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}
const tileCache = new Map();
function imageryTile(kind, z, x, y) {
  const k = kind + (z % 4); if (tileCache.has(k)) return tileCache.get(k);
  const base = { sat: [18, 52, 30], dark: [12, 14, 16], gibs: [20, 40, 70], night: [0, 0, 0], label: [0, 0, 0], radar: [0, 0, 0] }[kind] || [30, 30, 30];
  const b = png(64, 64, (px, py) => {
    if (kind === 'label' || kind === 'radar') return (px + py) % 29 === 0 ? [255, 255, 255, 160] : [0, 0, 0, 0];
    if (kind === 'night') return (px * 7 + py * 3 + z) % 53 === 0 ? [255, 220, 140, 255] : [0, 0, 0, 255];
    const g = px % 16 === 0 || py % 16 === 0;
    return g ? [base[0] + 30, base[1] + 40, base[2] + 30, 255] : [base[0] + ((px * py) % 9), base[1] + (z * 5) % 40, base[2], 255];
  });
  tileCache.set(k, b); return b;
}
function terrariumTile(z, x, y) {
  const k = `t${z}/${x}/${y}`; if (tileCache.has(k)) return tileCache.get(k);
  const n = 2 ** z;
  const b = png(256, 256, (px, py) => {
    const lon = (x + px / 256) / n * 360 - 180, my = Math.PI * (1 - 2 * (y + py / 256) / n), lat = Math.atan(Math.sinh(my)) * 180 / Math.PI;
    const hgt = Math.max(-200, 2500 * Math.sin(lat / 9) * Math.cos(lon / 13) + 800) + 32768;
    return [Math.floor(hgt / 256), Math.floor(hgt) % 256, Math.floor((hgt % 1) * 256), 255];
  });
  tileCache.set(k, b); return b;
}

/* ── TLE ── */
function tleChk(l) { let s = 0; for (const c of l.slice(0, 68)) { if (c >= '0' && c <= '9') s += +c; else if (c === '-') s += 1; } return s % 10; }
function tle(name, id, inc, raan, ecc, argp, ma, mm) {
  const d = new Date(), start = Date.UTC(d.getUTCFullYear(), 0, 1), doy = (d - start) / 86400e3 + 1;
  const yy = String(d.getUTCFullYear() % 100).padStart(2, '0'), ep = yy + doy.toFixed(8).padStart(12, '0');
  let l1 = `1 ${String(id).padStart(5, '0')}U 98067A   ${ep} -.00002182  00000-0 -11606-4 0  292`;
  l1 = l1 + tleChk(l1);
  let l2 = `2 ${String(id).padStart(5, '0')} ${inc.toFixed(4).padStart(8)} ${raan.toFixed(4).padStart(8)} ${String(Math.round(ecc * 1e7)).padStart(7, '0')} ${argp.toFixed(4).padStart(8)} ${ma.toFixed(4).padStart(8)} ${mm.toFixed(8).padStart(11)}${'56353'}`;
  l2 = l2 + tleChk(l2);
  return `${name}\n${l1}\n${l2}`;
}
const GROUPS = {
  stations: [['ISS (ZARYA)', 25544, 51.64, 15.50], ['CSS (TIANHE)', 48274, 41.47, 15.60], ['HST', 20580, 28.47, 15.09]],
  visual: Array.from({ length: 40 }, (_, i) => [`VISUAL-${i}`, 30000 + i, 50 + (i % 40), 14.2 + (i % 10) * 0.12]),
  'gps-ops': Array.from({ length: 24 }, (_, i) => [`GPS BIIF-${i}`, 40000 + i, 55, 2.0056]),
  galileo: Array.from({ length: 20 }, (_, i) => [`GSAT0${100 + i}`, 41000 + i, 56, 1.7048]),
  'glo-ops': Array.from({ length: 18 }, (_, i) => [`COSMOS 2${400 + i}`, 42000 + i, 64.8, 2.1316]),
  weather: Array.from({ length: 12 }, (_, i) => [`NOAA ${15 + i}`, 43000 + i, 98.7, 14.12]),
  military: Array.from({ length: 30 }, (_, i) => [`USA ${200 + i}`, 44000 + i, 63 + i % 30, 14 + (i % 5) * 0.3]),
  geo: Array.from({ length: 30 }, (_, i) => [`GEO-${i}`, 45000 + i, 0.05, 1.0027]),
  beidou: Array.from({ length: 10 }, (_, i) => [`BEIDOU-${i}`, 46000 + i, 55, 1.86]),
  starlink: Array.from({ length: 300 }, (_, i) => [`STARLINK-${1000 + i}`, 47000 + i, 53, 15.06])
};
function tleGroup(g) { return (GROUPS[g] || []).map(([n, id, inc, mm], i) => tle(n, id, inc, (i * 37) % 360, 0.0006, 90, (i * 53) % 360, mm)).join('\n') + '\n'; }

/* ── ADS-B ── */
const R = (a, b) => a + Math.random() * (b - a);
function readsb(a) { return Object.assign({ hex: 'abc000', type: 'adsb_icao', flight: 'TEST1   ', r: '', t: 'A320', alt_baro: 35000, gs: 450, track: 90, baro_rate: 0, squawk: '1000', emergency: 'none', category: 'A3', lat: 45, lon: 10, seen_pos: 1.2, seen: 0.5, dbFlags: 0 }, a); }
const MIL = [
  { hex: 'ae1460', flight: 'RCH421  ', t: 'C17', r: '07-7183', lat: 50.1, lon: 8.3, track: 110, alt_baro: 31000, dbFlags: 1 },
  { hex: 'ae5420', flight: 'FORTE12 ', t: 'RQ4', r: '11-2046', lat: 44.0, lon: 33.0, track: 60, alt_baro: 52000, gs: 320, dbFlags: 1 },
  { hex: 'ae01c5', flight: 'JAKE11  ', t: 'R135', r: '62-4134', lat: 56.4, lon: 20.2, track: 20, alt_baro: 33000, dbFlags: 1 },
  { hex: '4d03c1', flight: 'NATO01  ', t: 'E3TF', r: 'LX-N90442', lat: 52.4, lon: 19.6, track: 300, alt_baro: 29000, dbFlags: 1 },
  { hex: 'ae0412', flight: 'VIPER21 ', t: 'F16', r: '89-2031', lat: 49.5, lon: 7.7, track: 200, alt_baro: 24000, gs: 480, dbFlags: 1 },
  { hex: 'ae0413', flight: 'VIPER22 ', t: 'F16', r: '89-2032', lat: 49.6, lon: 7.8, track: 202, alt_baro: 24200, gs: 482, dbFlags: 1 },
  { hex: 'ae2c3f', flight: 'GOLD51  ', t: 'K35R', r: '58-0100', lat: 47.0, lon: 15.0, track: 270, alt_baro: 26000, dbFlags: 1 },
  { hex: 'ae1188', flight: 'SAM44   ', t: 'C32', r: '98-0002', lat: 41.8, lon: 12.2, track: 330, alt_baro: 38000, dbFlags: 1 },
  { hex: 'ae6a20', flight: 'PAT63   ', t: 'H60', r: '20-21000', lat: 49.4, lon: 7.6, track: 10, alt_baro: 2500, gs: 130, category: 'A7', dbFlags: 1 },
  { hex: '33ff01', flight: 'IAM1452 ', t: 'C30J', r: 'MM62187', lat: 37.4, lon: 14.9, track: 180, alt_baro: 21000, dbFlags: 1 },
  { hex: 'ae4f11', flight: 'HOMER22 ', t: 'P8', r: '169001', lat: 36.0, lon: 25.0, track: 95, alt_baro: 25000, dbFlags: 1 },
  { hex: '738a01', flight: 'IAF701  ', t: 'K35R', r: '4X-', lat: 31.9, lon: 34.9, track: 30, alt_baro: 22000, dbFlags: 1 }
].concat(Array.from({ length: 30 }, (_, i) => ({ hex: 'ae9' + String(100 + i), flight: `RCH${700 + i}  `, t: 'C17', lat: R(25, 60), lon: R(-100, 40), track: R(0, 360), alt_baro: Math.round(R(20000, 36000)), dbFlags: 1 })));
function adsbArea(lat, lon, r) {
  const ac = MIL.map(readsb).filter(a => Math.hypot(a.lat - lat, a.lon - lon) < r / 50);
  for (let i = 0; i < 260; i++) ac.push(readsb({ hex: (0x400000 + i).toString(16), flight: ['ITY', 'RYR', 'DLH', 'AFR', 'EZY', 'BAW'][i % 6] + (100 + i), t: ['A320', 'B738', 'A21N', 'B77W', 'E190'][i % 5], r: 'EI-' + i,
    lat: lat + R(-r / 70, r / 70), lon: lon + R(-r / 50, r / 50), track: R(0, 360), alt_baro: Math.round(R(3000, 39000)), gs: R(200, 520) }));
  ac.push(readsb({ hex: '3c6dd1', flight: 'DLH9EM  ', t: 'A321', r: 'D-AISE', lat: lat + 0.3, lon: lon - 0.4, squawk: '7700', emergency: 'general', alt_baro: 18000, baro_rate: -2400, track: 140 }));
  return { ac, msg: 'No error', now: Date.now(), total: ac.length, ctime: Date.now(), ptime: 5 };
}
function opensky() {
  const states = [];
  for (let i = 0; i < 2500; i++) states.push([(0x500000 + i).toString(16), 'OSK' + i + ' ', ['Italy', 'Germany', 'United States', 'China', 'Brazil'][i % 5], Math.floor(Date.now() / 1000) - 5, Math.floor(Date.now() / 1000),
    R(-160, 170), R(-45, 65), R(3000, 12000), false, R(150, 260), R(0, 360), R(-5, 5), null, R(3000, 12000), i === 7 ? '7600' : String(1000 + (i % 7000)), false, 0]);
  return { time: Math.floor(Date.now() / 1000), states };
}

/* ── notizie ── */
const NOW = () => Date.now();
const ago = m => new Date(NOW() - m * 60000).toUTCString();
const TITLES = [
  ['Russian missile strike hits Kharkiv, several killed', 8], ['Israel strikes Gaza as ceasefire talks stall', 25], ['Houthi drones target cargo ship in the Red Sea', 40],
  ['Iran says nuclear talks with IAEA will resume next week', 12], ['Taiwan reports Chinese warships near the Taiwan Strait', 55], ['Earthquake of magnitude 6.4 strikes off northern Japan', 30],
  ['Sudan: RSF attack on El Fasher displaces thousands', 90], ['NATO jets scrambled over the Baltic after airspace violation near Kaliningrad', 70], ['Markets rally as oil prices fall', 15],
  ['Hezbollah and Israel exchange fire across the Lebanon border', 120], ['North Korea fires ballistic missile into the sea, says Seoul', 18], ['Cyber attack disrupts ports in Germany', 200],
  ['Wildfires force evacuations in Australia', 300], ['UN Security Council meets on Yemen crisis', 160], ['Explosion reported at Odesa port after drone attack', 5]
];
const IT = [['Ucraina, attacco con droni su Odessa: tre morti', 9], ['Meloni a Bruxelles per il vertice Ue sulla difesa', 60], ['Terremoto in Turchia, scossa di magnitudo 5.1', 45], ['Gaza, nuovi raid israeliani nella notte', 33], ['Roma, vertice sulla sicurezza al Viminale', 100]];
function rss(feedUrl) {
  const it = /ansa|rainews/.test(feedUrl) ? IT : TITLES;
  const shift = feedUrl.length % 5;
  const items = it.map(([t, m], i) => `<item><title><![CDATA[${t}${i % 3 === shift % 3 ? '' : ' — ' + (feedUrl.match(/\/\/([^/]+)/) || [])[1]}]]></title><link>https://example.org/news/${i}</link><pubDate>${ago(m + shift)}</pubDate><description>Dettagli: ${t}</description></item>`).join('');
  return `<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Feed</title>${items}</channel></rss>`;
}
function gdelt() {
  const pad = n => String(n).padStart(2, '0');
  const d = new Date(NOW() - 20 * 60000), sd = `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}00Z`;
  return { articles: [{ url: 'https://example.org/g1', title: 'Shelling reported near Pokrovsk as troops regroup', seendate: sd, domain: 'kyivpost.com', language: 'English', sourcecountry: 'Ukraine' },
    { url: 'https://example.org/g2', title: 'Navy destroyer intercepts missile over Red Sea', seendate: sd, domain: 'navytimes.com', language: 'English', sourcecountry: 'United States' }] };
}

/* ── mercati ── */
function spark(syms) {
  const out = {};
  for (const s of syms) { const base = s.includes('VIX') ? 18 : s.includes('=F') ? 80 : 400 + s.length * 50; const close = Array.from({ length: 14 }, (_, i) => +(base * (1 + Math.sin(i / 3 + s.length) * 0.01)).toFixed(2));
    out[s] = { symbol: s, timestamp: close.map((_, i) => Math.floor(NOW() / 1000) - (14 - i) * 1800), close, chartPreviousClose: base * 0.995, previousClose: null, dataGranularity: 1800 }; }
  return out;
}
function coingecko(ids) {
  return ids.split(',').map((id, i) => ({ id, symbol: id.slice(0, 3), current_price: [68000, 3400, 160, 0.6, 590, 0.15][i] || 1, price_change_percentage_24h: [1.8, -0.7, 3.2, -1.1, 0.4, 5.5][i] || 0, market_cap: 1e9,
    sparkline_in_7d: { price: Array.from({ length: 168 }, (_, k) => 100 + Math.sin(k / 10 + i) * 5) } }));
}
function frankfurter() {
  const rates = {}; for (let i = 8; i >= 0; i--) { const d = new Date(NOW() - i * 86400e3).toISOString().slice(0, 10); rates[d] = { EUR: 0.92 + i * 0.001, GBP: 0.78, JPY: 151 + i * 0.2, CHF: 0.88, CNY: 7.2, TRY: 34.5, ILS: 3.7 }; }
  return { amount: 1, base: 'USD', start_date: Object.keys(rates)[0], end_date: Object.keys(rates).at(-1), rates };
}

/* ── terremoti, eventi, spazio ── */
function usgs() {
  const f = (id, mag, place, mins, lat, lon, depth, extra = {}) => ({ type: 'Feature', id, properties: Object.assign({ mag, place, time: NOW() - mins * 60000, url: 'https://earthquake.usgs.gov/earthquakes/eventpage/' + id, tsunami: 0, type: 'earthquake', sig: Math.round(mag * 80), felt: null, alert: null }, extra), geometry: { type: 'Point', coordinates: [lon, lat, depth] } });
  const list = [f('us7000aaa1', 6.4, 'off the east coast of Honshu, Japan', 30, 39.9, 143.1, 25, { tsunami: 1, alert: 'yellow' }), f('us7000aaa2', 5.1, 'central Turkey', 45, 38.4, 37.8, 10),
    f('us7000aaa3', 4.6, 'Tonga region', 200, -20.1, -174.3, 100), f('ci40000001', 2.9, '10 km NW of Ridgecrest, CA', 15, 35.7, -117.7, 7)];
  for (let i = 0; i < 120; i++) list.push(f('xx' + i, +(R(1, 4.4)).toFixed(1), `Region ${i}`, R(1, 1400), R(-60, 70), R(-180, 180), R(1, 300)));
  return { type: 'FeatureCollection', metadata: { count: list.length }, features: list };
}
function eonet() {
  const e = (id, cat, title, lat, lon, mins, mag) => ({ id, title, categories: [{ id: cat, title: cat }], sources: [{ id: 'X', url: 'https://example.org/' + id }], geometry: [{ magnitudeValue: mag || null, magnitudeUnit: mag ? 'kts' : null, date: new Date(NOW() - mins * 60000).toISOString(), type: 'Point', coordinates: [lon, lat] }] });
  return { events: [e('EONET_1', 'wildfires', 'Wildfire - New South Wales, Australia', -33.5, 150.2, 600), e('EONET_2', 'volcanoes', 'Etna Volcano, Italy', 37.75, 14.99, 1200), e('EONET_3', 'severeStorms', 'Typhoon Kong-rey', 22.0, 125.0, 180, 95),
    e('EONET_4', 'seaLakeIce', 'Iceberg A23A', -60.0, -45.0, 5000), e('EONET_5', 'wildfires', 'Wildfire - California, United States', 36.5, -120.4, 300), e('EONET_6', 'floods', 'Floods - Valencia, Spain', 39.4, -0.4, 900)] };
}
function swpc(path) {
  const t = i => new Date(NOW() - i * 60000).toISOString().replace('T', ' ').slice(0, 19);
  if (path.includes('planetary_k_index_1m')) return Array.from({ length: 10 }, (_, i) => ({ time_tag: t(10 - i), kp_index: 3, estimated_kp: 3.33, kp: '3P' }));
  if (path.includes('noaa-planetary-k-index')) return [['time_tag', 'Kp', 'a_running', 'station_count'], ...Array.from({ length: 24 }, (_, i) => [t((24 - i) * 180), (2 + Math.sin(i / 3) * 1.5).toFixed(2), '9', '8'])];
  if (path.includes('plasma-5-minute')) return [['time_tag', 'density', 'speed', 'temperature'], [t(10), '4.10', '455.2', '98000'], [t(5), '4.31', '461.7', '101000']];
  if (path.includes('mag-5-minute')) return [['time_tag', 'bx_gsm', 'by_gsm', 'bz_gsm', 'lon_gsm', 'lat_gsm', 'bt'], [t(5), '2.1', '-3.0', '-4.2', '300', '-30', '5.6']];
  if (path.includes('noaa-scales')) return { 0: { DateStamp: '2026-11-03', R: { Scale: '0' }, S: { Scale: '0' }, G: { Scale: '1' } } };
  if (path.includes('xrays-6-hour')) return [{ time_tag: t(2), satellite: 19, flux: 3.2e-6, energy: '0.1-0.8nm' }, { time_tag: t(2), satellite: 19, flux: 2e-7, energy: '0.05-0.4nm' }];
  if (path.includes('ovation_aurora_latest')) {
    const c = []; for (let lon = 0; lon < 360; lon += 2) for (let lat = -90; lat <= 90; lat += 2) { const d = Math.min(Math.abs(lat - 67), Math.abs(lat + 67)); c.push([lon, lat, d < 6 ? Math.round(40 - d * 6) : 0]); }
    return { 'Observation Time': new Date().toISOString(), 'Forecast Time': new Date().toISOString(), 'Data Format': '[Longitude, Latitude, Aurora]', coordinates: c };
  }
  return null;
}

/* ── meteo / geo / ip ── */
function forecast() {
  return { latitude: 41.9, longitude: 12.5, timezone: 'Europe/Rome', utc_offset_seconds: 3600,
    current: { time: new Date().toISOString().slice(0, 16), temperature_2m: 17.4, relative_humidity_2m: 66, apparent_temperature: 16.8, precipitation: 0, weather_code: 2, cloud_cover: 40, pressure_msl: 1016.2, wind_speed_10m: 12.4, wind_direction_10m: 230, wind_gusts_10m: 25.2, is_day: 1 },
    hourly: { time: Array.from({ length: 24 }, (_, i) => i), temperature_2m: Array.from({ length: 24 }, (_, i) => +(14 + Math.sin(i / 4) * 4).toFixed(1)), precipitation_probability: Array.from({ length: 24 }, (_, i) => (i * 7) % 60) } };
}

/* ── router ── */
const J = d => ({ status: 200, contentType: 'application/json', body: JSON.stringify(d) });
const T = (d, ct = 'text/plain') => ({ status: 200, contentType: ct, body: d });
export function respond(url) {
  const u = new URL(url), host = u.host, p = u.pathname, q = u.searchParams;
  if (/arcgisonline|cartocdn|openstreetmap|gibs\.earthdata|tilecache\.rainviewer/.test(host)) {
    const m = p.match(/(\d+)\/(\d+)\/(\d+)/), [z, a, b] = m ? m.slice(1).map(Number) : [0, 0, 0];
    const kind = /rainviewer/.test(host) ? 'radar' : /only_labels|World_Boundaries_and_Places/.test(p) ? 'label' : /CityLights|Black_Marble/.test(p) ? 'night' : /gibs/.test(host) ? 'gibs' : /dark_all|Dark_Gray/.test(p) ? 'dark' : 'sat';
    return { status: 200, contentType: 'image/png', body: imageryTile(kind, z, a, b) };
  }
  if (host === 's3.amazonaws.com' && p.includes('terrarium')) { const [z, x, y] = p.match(/(\d+)\/(\d+)\/(\d+)\.png/).slice(1).map(Number); return { status: 200, contentType: 'image/png', body: terrariumTile(z, x, y) }; }
  if (host === 'api.adsb.lol' || host === 'api.airplanes.live' || host === 'opendata.adsb.fi') {
    if (p.endsWith('/mil')) return J({ ac: MIL.map(readsb), now: Date.now(), total: MIL.length });
    const m = p.match(/(-?[\d.]+)\/(?:lon\/)?(-?[\d.]+)\/(?:dist\/)?(\d+)$/);
    if (m) return J(adsbArea(+m[1], +m[2], +m[3]));
  }
  if (host === 'opensky-network.org') return J(opensky());
  if (host === 'celestrak.org') return T(tleGroup(q.get('GROUP')));
  if (host === 'api.wheretheiss.at') return J({ name: 'iss', id: 25544, latitude: 42.1, longitude: 12.9, altitude: 418.2, velocity: 27580.4, visibility: 'daylight', timestamp: Math.floor(NOW() / 1000) });
  if (host === 'earthquake.usgs.gov') return J(usgs());
  if (host === 'eonet.gsfc.nasa.gov') return J(eonet());
  if (host === 'services.swpc.noaa.gov') { const d = swpc(p); return d ? J(d) : { status: 404, contentType: 'text/plain', body: 'nf' }; }
  if (host === 'api.rainviewer.com') return J({ version: '2.0', generated: Math.floor(NOW() / 1000), host: 'https://tilecache.rainviewer.com', radar: { past: [{ time: Math.floor(NOW() / 1000) - 600, path: '/v2/radar/abc123' }], nowcast: [] } });
  if (/bbci|aljazeera|ansa\.it|rainews|dw\.com|theguardian|france24|nytimes|npr\.org|skynews|defensenews|timesofisrael/.test(host)) return T(rss(url), 'application/rss+xml');
  if (host === 'api.gdeltproject.org') return J(gdelt());
  if (host === 'query1.finance.yahoo.com') return J(spark((q.get('symbols') || '').split(',')));
  if (host === 'api.coingecko.com') return J(coingecko(q.get('ids') || 'bitcoin'));
  if (/frankfurter/.test(host)) return J(frankfurter());
  if (host === 'api.adsbdb.com') return p.includes('callsign') ? J({ response: { flightroute: { callsign: 'X', airline: { name: 'Lufthansa' }, origin: { iata_code: 'FRA', icao_code: 'EDDF', municipality: 'Frankfurt', name: 'Frankfurt am Main' }, destination: { iata_code: 'FCO', icao_code: 'LIRF', municipality: 'Roma', name: 'Fiumicino' } } } })
    : J({ response: { aircraft: { type: 'A321-131', icao_type: 'A321', manufacturer: 'Airbus', registration: 'D-AISE', registered_owner: 'Lufthansa', registered_owner_country_name: 'Germany', url_photo_thumbnail: null } } });
  if (host === 'api.planespotters.net') return J({ photos: [] });
  if (host === 'api.open-meteo.com' && p.includes('elevation')) return J({ elevation: [37] });
  if (host === 'api.open-meteo.com') return J(forecast());
  if (host === 'geocoding-api.open-meteo.com') return J({ results: [{ name: q.get('name')?.includes('Roma') ? 'Roma' : q.get('name'), latitude: 41.89, longitude: 12.48, country_code: 'IT', country: 'Italia', admin1: 'Lazio', population: 2800000 }] });
  if (host === 'air-quality-api.open-meteo.com') return J({ current: { european_aqi: 34, pm2_5: 9.1, pm10: 15.2 } });
  if (host === 'api.bigdatacloud.net') return J({ city: 'Roma', locality: 'Roma', principalSubdivision: 'Lazio', countryName: 'Italia', countryCode: 'IT' });
  if (host === 'ipwho.is') return J(p.length > 1 ? { success: true, ip: decodeURIComponent(p.slice(1)), type: 'IPv4', city: 'Mountain View', region: 'California', country: 'United States', country_code: 'US', latitude: 37.39, longitude: -122.08, connection: { asn: 15169, org: 'Google LLC', isp: 'Google LLC' }, timezone: { id: 'America/Los_Angeles' } }
    : { success: true, ip: '93.40.1.2', type: 'IPv4', city: 'Roma', region: 'Lazio', country: 'Italy', country_code: 'IT', latitude: 41.9, longitude: 12.5, connection: { asn: 3269, org: 'Telecom Italia', isp: 'TIM' }, timezone: { id: 'Europe/Rome' } });
  if (host === 'dns.google') return J({ Status: 0, Answer: [{ name: q.get('name') + '.', type: 1, TTL: 300, data: '151.101.1.1' }] });
  if (host === 'noembed.com') return J(/kfWVnQiUJ_4/.test(decodeURIComponent(u.search)) ? { error: '404 Not Found', url: q.get('url') } : { title: 'Live webcam', provider_name: 'YouTube', type: 'video' });
  if (/youtube|windy/.test(host)) return T(`<!doctype html><body style="background:#111;color:#0f0;font:14px monospace">EMBED ${host}${p}</body>`, 'text/html');
  if (host === 'fonts.googleapis.com') return T('', 'text/css');
  return null;
}

/* hosts che NON mandano CORS (simulato): il fetch diretto fallisce e deve passare dal proxy */
export const NO_CORS = /bbci|aljazeera|ansa\.it|rainews|dw\.com|theguardian|france24|nytimes|npr\.org|skynews|defensenews|timesofisrael|query1\.finance\.yahoo|stooq|api\.adsb\.lol/;
export const PROXY = /api\.allorigins\.win|corsproxy\.io|api\.codetabs\.com|api\.cors\.lol/;

/* file statici delle librerie (npm) al posto della CDN */
export function cdnLocal(url, libs) {
  const m = url.match(/cdn\.jsdelivr\.net\/npm\/(cesium@[\d.]+|satellite\.js@[\d.]+|leaflet@[\d.]+)\/(.*)$/); if (!m) return null;
  const pkg = m[1].split('@')[0], rest = m[2].split('?')[0];
  const f = join(libs, 'node_modules', pkg, rest);
  if (!existsSync(f)) return { status: 404, contentType: 'text/plain', body: 'missing ' + f };
  const ct = { '.js': 'application/javascript', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.wasm': 'application/wasm', '.glb': 'model/gltf-binary', '.ktx2': 'image/ktx2', '.svg': 'image/svg+xml' }[extname(f)] || 'application/octet-stream';
  return { status: 200, contentType: ct, body: readFileSync(f) };
}
