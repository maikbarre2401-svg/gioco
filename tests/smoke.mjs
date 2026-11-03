// Test end-to-end di OJO DE DEUS in Chromium headless (WebGL SwiftShader) con API simulate.
// Uso:  cd tests && npm install && node smoke.mjs [--2d] [--mobile] [--shots DIR]
import { createServer } from 'node:http';
import { readFileSync, existsSync, mkdirSync } from 'node:fs';
import { join, dirname, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { respond, NO_CORS, PROXY, cdnLocal } from './mocks.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const HERE = dirname(fileURLToPath(import.meta.url)), ROOT = join(HERE, '..');
const LIBS = process.env.OJO_LIBS || HERE;
const args = process.argv.slice(2), MODE2D = args.includes('--2d'), MOBILE = args.includes('--mobile');
const FILE = args.includes('--file'), LOCALPROXY = args.includes('--local-proxy');   // pagina aperta da disco / avviatore con proxy
const SHOTS = args.includes('--shots') ? args[args.indexOf('--shots') + 1] : join(HERE, 'shots');
mkdirSync(SHOTS, { recursive: true });

const localHits = new Set();
const srv = createServer((req, res) => {
  if (LOCALPROXY && req.url.startsWith('/ojo-ping')) { res.writeHead(200, { 'content-type': 'application/json' }); return res.end('{"ojo":"local-proxy","v":1}'); }
  if (LOCALPROXY && req.url.startsWith('/ojo-proxy')) {      // come AVVIA-OJO / ojo-server.py
    const target = new URL(req.url, 'http://x').searchParams.get('url'); localHits.add(new URL(target).host);
    const r = respond(target); res.writeHead(r ? r.status : 502, { 'content-type': r ? r.contentType : 'text/plain', 'access-control-allow-origin': '*' }); return res.end(r ? r.body : 'bad');
  }
  const f = join(ROOT, decodeURIComponent(req.url.split('?')[0]).replace(/^\/+/, '') || 'index.html');
  if (!existsSync(f)) { res.writeHead(404); return res.end('nf'); }
  res.writeHead(200, { 'content-type': { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript', '.css': 'text/css' }[extname(f)] || 'application/octet-stream' });
  res.end(readFileSync(f));
}).listen(0);
const PORT = srv.address().port;

const errors = [], unknown = new Set(), proxied = new Set(), log = [];
let pass = 0, fail = 0;
const ok = (c, m) => { if (c) { pass++; console.log('  ✓', m); } else { fail++; console.log('  ✗', m); } };

const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const ctx = await browser.newContext(MOBILE ? { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true } : { viewport: { width: 1600, height: 1000 } });
await ctx.route('**/*', async route => {
  const url = route.request().url();
  if (url.startsWith(`http://localhost:${PORT}`) || url.startsWith('data:') || url.startsWith('blob:')) return route.continue();
  const local = cdnLocal(url, LIBS); if (local) return route.fulfill({ status: local.status, body: local.body, headers: { 'content-type': local.contentType, 'access-control-allow-origin': '*' } });
  const u = new URL(url);
  if (PROXY.test(u.host)) {
    const target = u.searchParams.get('url') || u.searchParams.get('quest');
    proxied.add(new URL(target).host);
    const r = target && respond(target);
    return r ? route.fulfill({ status: r.status, body: r.body, headers: { 'content-type': r.contentType, 'access-control-allow-origin': '*' } }) : route.fulfill({ status: 502, body: 'bad gateway' });
  }
  if (NO_CORS.test(u.host)) return route.abort('failed');
  const r = respond(url);
  if (r) return route.fulfill({ status: r.status, body: r.body, headers: { 'content-type': r.contentType, 'access-control-allow-origin': '*' } });
  unknown.add(u.host + u.pathname.slice(0, 40)); return route.abort('failed');
});
const page = await ctx.newPage();
ctx.on('page', p => { if (p !== page) setTimeout(() => p.close().catch(() => {}), 4000); });
page.on('console', m => { const t = m.text(); log.push(`[${m.type()}] ${t}`); if (m.type() === 'error' && !/Failed to load resource|ERR_FAILED|net::/.test(t)) errors.push(t); });
page.on('pageerror', e => errors.push('PAGEERROR ' + e.message + '\n' + (e.stack || '').split('\n').slice(0, 4).join('\n')));
if (MODE2D) await page.addInitScript(() => localStorage.setItem('ojo.force2d', 'true'));

const wait = ms => page.waitForTimeout(ms);
const txt = sel => page.$eval(sel, e => e.textContent.trim()).catch(() => '');
const shot = async n => { await page.screenshot({ path: join(SHOTS, `${MOBILE ? 'm-' : MODE2D ? '2d-' : ''}${n}.png`), timeout: 150000 }).catch(e => console.log('    (screenshot ' + n + ' saltato: ' + e.message.split('\n')[0] + ')')); };

console.log(`\n▶ OJO DE DEUS smoke test (${MODE2D ? '2D' : '3D'}${MOBILE ? ', mobile' : ''})`);
await page.goto(FILE ? 'file://' + join(ROOT, 'index.html') : `http://localhost:${PORT}/index.html`);
if (FILE) ok(await page.isVisible('#boot-file'), 'avviso "aperto da file" con istruzioni per l\'avviatore');
await wait(600);
ok(await page.isVisible('#boot-start'), 'schermata di avvio visibile, nessun avvio automatico senza consenso');
await shot('00-boot');
await page.click('#boot-start');
await page.waitForSelector('#boot', { state: 'detached', timeout: 90000 }).catch(() => {});
ok(!(await page.$('#boot')), 'boot completato');
const engine = await txt('#sb-engine');
ok(MODE2D ? /2D/.test(engine) : /3D/.test(engine), 'motore: ' + engine);
await wait(16000);
await shot('01-overview');

console.log('— feed');
const health = await page.evaluate(() => Health.all().map(f => [f.id, f.status, f.via || '', f.msg || '']));
health.forEach(([id, s, via, msg]) => console.log(`    ${s.padEnd(5)} ${id.padEnd(8)} ${via} ${msg ? '· ' + msg : ''}`));
const H = Object.fromEntries(health.map(([id, s]) => [id, s]));
for (const id of ['engine', 'adsb', 'sats', 'iss', 'quakes', 'eonet', 'space', 'aurora', 'news', 'markets', 'crypto', 'fx']) ok(H[id] === 'live', `feed ${id} LIVE`);
if (!MODE2D) ok(H.terrain === 'live', 'terreno 3D (terrarium) decodificato');
ok(H.firms === 'key', 'FIRMS senza chiave segnalato come KEY (non finto)');
const n = async s => parseInt((await txt(s)).replace(/\D/g, '')) || 0;
ok(await n('#ac-tot') > 100, 'aerei tracciati: ' + await txt('#ac-tot'));
ok(await n('#ac-mil') >= 10, 'militari: ' + await txt('#ac-mil'));
ok(await n('#ac-emg') >= 1, 'emergenze squawk rilevate: ' + await txt('#ac-emg'));
ok(await n('#sat-tot') > 100, 'satelliti propagati: ' + await txt('#sat-tot'));
ok(await n('#eq-tot') > 50, 'terremoti: ' + await txt('#eq-tot'));
ok((await page.$$('#news-list .ni')).length > 10, 'notizie in elenco: ' + (await page.$$('#news-list .ni')).length);
ok(/\d/.test(await txt('#kp-v')), 'Kp: ' + await txt('#kp-v'));
ok(/\$/.test(await txt('#sb-btc')), 'BTC: ' + await txt('#sb-btc'));
ok(/\d/.test(await page.$eval('#mkt-idx .mk-p', e => e.textContent)), 'S&P 500: ' + await page.$eval('#mkt-idx .mk-p', e => e.textContent));
ok(/ALLERTA [1-5]/.test(await txt('#threat-badge')), 'indice: ' + await txt('#threat-badge'));
ok((await page.$$('#hot-list .ci-item')).length === 10, 'zone calde valutate');
ok((await page.$$('#alert-list .al-row')).length >= 2, 'allerte automatiche: ' + (await page.$$eval('#alert-list .al-x', es => es.slice(0, 4).map(e => e.firstChild.textContent).join(' | '))));
ok((await txt('#brief-text')).length > 60, 'briefing generato');
ok(/[A-Z]/.test(await txt('#ticker-track')), 'ticker notizie');
if (LOCALPROXY) {
  ok(/locale/.test((await page.evaluate(() => Health.all().find(f => f.id === 'proxy').msg)) || ''), 'proxy locale dell\'avviatore rilevato');
  ok([...localHits].some(h => /bbci|nytimes/.test(h)) && ![...proxied].some(h => /bbci/.test(h)), 'RSS senza CORS passati dal proxy LOCALE: ' + [...localHits].join(', '));
} else ok([...proxied].some(h => /bbci|nytimes/.test(h)), 'RSS senza CORS recuperati via proxy: ' + [...proxied].join(', '));

console.log('— interazione');
await page.click('#ac-list .row');
await wait(800);
ok(await page.isVisible('#trkp') && /AEREO/.test(await txt('#trkp .trk-h')), 'pannello bersaglio aereo');
await wait(1500);
ok(/Frankfurt|Roma|rotta|Nessun/.test(await txt('#ac-extra')), 'rotta adsbdb: ' + (await txt('#ac-extra')).slice(0, 60));
await page.click('#trk-btns .abtn'); await wait(1200);
ok(/SEGUI/.test(await txt('#sb-engine')), 'modalità segui');
if (!MODE2D) {
  await page.click('#trk-btns .abtn:nth-child(2)'); await wait(1500);
  ok(/COCKPIT/.test(await txt('#sb-engine')), 'vista cockpit');
  await shot('02-cockpit');
  await page.keyboard.press('Escape'); await wait(800);
  ok(!/COCKPIT|SEGUI/.test(await txt('#sb-engine')), 'Esc esce dal cockpit');
}
await page.keyboard.press('Escape');
await page.fill('#sat-q', 'ISS'); await wait(4500);
await page.click('#sat-list .row'); await wait(1500);
ok(/SATELLITE/.test(await txt('#trkp .trk-h')) && /ISS/.test(await txt('#trkp .trk-name')), 'pannello satellite ISS');
await wait(600); await shot('03-sat');
await page.click('#eq-list .row'); await wait(900);
ok(/TERREMOTO/.test(await txt('#trkp .trk-h')), 'pannello terremoto');
await page.click('#news-list .ni'); await wait(500);
ok(/NOTIZIA/.test(await txt('#trkp .trk-h')), 'pannello notizia');
await page.click('#nuke-list .row'); await wait(500);
ok(/NUCLEARE/.test(await txt('#trkp .trk-h')), 'pannello sito nucleare');
await page.click('#eo-list .row'); await wait(500);
ok(/EONET/.test(await txt('#trkp .trk-h')), 'pannello EONET');
await wait(1500);
// clic sul globo: picking reale
await page.keyboard.press('Escape');
await page.evaluate(() => window.scrollTo(0, 0)); await wait(400);
const box = await page.$eval('#map-section', e => { const r = e.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; });
await page.evaluate(() => MapCtl.flyTo(20, 0, 9e6, { duration: 0 })); await wait(2500);
await page.mouse.click(box.x + box.w / 2 + 40, box.y + box.h / 2 + 30); await wait(2500);
ok(/ANALISI PUNTO|TERREMOTO|NOTIZIA|AEREO|SATELLITE/.test(await txt('#trkp .trk-h')), 'clic sulla mappa → ' + await txt('#trkp .trk-h'));
if (/ANALISI/.test(await txt('#trkp .trk-h'))) ok(/Roma|Italia|°C/.test(await txt('#pt-geo')), 'analisi punto: ' + (await txt('#pt-geo')).slice(0, 70));
if (!MODE2D) {
  await page.keyboard.press('Escape'); await wait(300);
  const pickedAc = await page.evaluate(async () => {
    const C = Globe3D.C, v = Globe3D.viewer, a = S.acList.find(x => x.cls === 'civil');
    v.camera.setView({ destination: C.Cartesian3.fromDegrees(a.plon ?? a.lon, (a.plat ?? a.lat) - 0.02, 160000) });
    await new Promise(r => setTimeout(r, 2500));
    const e = [...S.ac.values()].find(x => x.hex === a.hex);
    const p = C.SceneTransforms.worldToWindowCoordinates(v.scene, C.Cartesian3.fromDegrees(e.plon ?? e.lon, e.plat ?? e.lat, e.altM));
    return p ? { x: p.x, y: p.y, hex: a.hex } : null;
  });
  let hit = null;
  if (pickedAc) {
    await page.evaluate(() => window.scrollTo(0, 0)); await wait(300);
    const r = await page.$eval('#globe3d canvas', c => c.getBoundingClientRect().toJSON());
    hit = await page.evaluate(([x, y]) => { const el = document.elementFromPoint(x, y); return el ? (el.id || el.className || el.tagName) : null; }, [r.x + pickedAc.x, r.y + pickedAc.y]);
    await page.mouse.click(r.x + pickedAc.x, r.y + pickedAc.y); await wait(900);
  }
  ok(/AEREO/.test(await txt('#trkp .trk-h')), `picking 3D di un aereo cliccandolo sul globo (${JSON.stringify(pickedAc)} → elemento ${hit} → ${await txt('#trkp .trk-h')})`);
  await page.keyboard.press('Escape');
}

console.log('— controlli mappa');
for (const v of ['nvg', 'flir', 'crt', 'nrm']) { await page.click(`[data-vis="${v}"]`); await wait(900); if (v !== 'nrm') await shot('04-vis-' + v); }
ok(true, 'visori NVG / FLIR / CRT');
if (!MODE2D) {
  await page.evaluate(() => MapCtl.flyTo(46.5, 10.5, 60000, { pitch: -25, duration: 0 })); await wait(5000); await shot('05-terrain-alps');
  for (const s of ['cv', '2d', '3d']) { await page.click(`[data-scene="${s}"]`); await wait(2200); }
  ok(true, 'modalità 2.5D / 2D / 3D');
  await page.selectOption('#base-sel', 'dark'); await wait(1200); await page.selectOption('#base-sel', 'sat');
  await page.$eval('#exag', e => { e.value = 3; e.dispatchEvent(new Event('input')); }); ok((await txt('#exag-v')) === '3×', 'esagerazione rilievo');
}
await page.click('#btn-layers'); await wait(400);
const layers = await page.$$eval('#layer-list .layer-item:not(.disabled)', es => es.map(e => e.dataset.layer));
for (const k of layers) { await page.click(`#layer-list [data-layer="${k}"]`); await wait(250); await page.click(`#layer-list [data-layer="${k}"]`); await wait(150); }
ok(layers.length >= 13, `toggle di ${layers.length} layer senza errori`);
await page.click(`#layer-list [data-layer="radar"]`); await wait(1500);
ok((await page.evaluate(() => Health.status('radar'))) === 'live', 'radar RainViewer attivato');
await page.click('[data-close="layer-panel"]');
await page.click('#btn-health'); await wait(300); ok((await page.$$('#health-list .hp-item')).length >= 15, 'pannello stato feed'); await shot('06-health'); await page.click('[data-close="health-panel"]');

console.log('— strumenti');
await page.fill('#omni', 'Roma'); await wait(300);
ok((await page.$$('#omni-sug .sug')).length > 0, 'suggerimenti ricerca: ' + (await page.$$eval('#omni-sug .sug', es => es.map(e => e.textContent).slice(0, 3).join(' | '))));
await page.keyboard.press('Enter'); await wait(600);
await page.fill('#omni', 'RCH4'); await wait(300);
ok(/RCH421/.test(await txt('#omni-sug')), 'ricerca volo per callsign');
await page.keyboard.press('Escape');
for (const c of ['help', 'status', 'layers', 'find SAM44', 'sat ISS', 'base dark', 'base sat', 'vis nvg', 'vis nrm', 'exag 2', 'alerts', 'layer bases on', 'news gaza', 'tv 0', 'cam 1', 'flyto 41.9 12.5 50', 'goto Milano', 'pippo']) { await page.fill('#hk-inp', c); await page.keyboard.press('Enter'); await wait(350); }
const term = await txt('#hk-out');
ok(/comandi:/.test(term) && /motore/.test(term) && /trovato SAM44/.test(term) && /satellite ISS/.test(term) && /comando sconosciuto/.test(term), 'terminale: comandi eseguiti');
if (FILE) {
  const pop = page.waitForEvent('popup', { timeout: 8000 }).catch(() => null);
  await page.click('#tv-grid-news .tv-btn'); const pw = await pop; if (pw) await pw.waitForLoadState('domcontentloaded').catch(() => {});
  ok(pw && /youtube\.com\/channel\/.+\/live/.test(pw.url()), 'da file: la TV si apre in una finestra YouTube funzionante (' + (pw ? pw.url() : 'nessun popup') + ')');
  ok(/Errore 153/.test(await txt('#tv-ph')), 'da file: spiegazione Errore 153 nel riquadro TV');
  if (pw) await pw.close();
} else {
  ok(/live_stream\?channel=/.test(await page.$eval('#tv-iframe', e => e.src)), 'TV: diretta da canale ufficiale');
  ok(/youtube\.com\/embed\//.test(await page.$eval('#wc-iframe', e => e.src)), 'webcam caricata');
}
await page.fill('#news-q', ''); await page.dispatchEvent('#news-q', 'input');
await page.fill('#wx-inp', 'Roma'); await page.click('#wx-btn'); await wait(1500);
ok(/Roma/.test(await txt('#wx-result')) && /°C/.test(await txt('#wx-result')), 'meteo città');
await page.fill('#ip-inp', 'rai.it'); await page.click('#ip-btn'); await wait(1800);
ok(/DNS/.test(await txt('#geo-result')) && /Mountain View/.test(await txt('#geo-result')), 'GeoTrace DNS + IP');
await page.click('[data-windy="rain"]'); await wait(300); ok(/overlay=rain/.test(await page.$eval('#windy-frame', e => e.src)), 'Windy pioggia centrato sulla vista');
await page.click('#iss-pass-btn'); await wait(4000); ok((await page.$$('#iss-pass .row, #iss-pass .empty')).length > 0, 'passaggi ISS calcolati: ' + (await txt('#iss-pass')).slice(0, 80));
await page.click('#hot-list .ci-item'); await wait(700); ok(/DOSSIER/.test(await txt('#modal-title')), 'dossier zona calda'); await shot('07-dossier'); await page.click('[data-close-modal]');
await page.click('#threat-badge'); await wait(400); ok(/BRIEFING/.test(await txt('#modal-title')), 'briefing completo'); await page.click('[data-close-modal]');
await page.click('#btn-settings'); await wait(300); await page.fill('#st-proxy', 'https://example.workers.dev/?url={url}'); await page.click('#modal-foot .btn:last-child'); await wait(300);
ok((await page.evaluate(() => Settings.get('proxy'))).includes('{url}'), 'impostazioni salvate');
await page.evaluate(() => Settings.set('proxy', ''));
await page.click('#btn-help'); await wait(200); ok(/AIUTO/.test(await txt('#modal-title')), 'aiuto'); await page.keyboard.press('Escape');
await page.click('#tv-expand'); await wait(500);
if (FILE) { ok(/AVVIATORE/.test(await txt('#modal-title')), 'da file: TV grande → istruzioni'); await page.click('[data-close-modal]'); }
else { ok(await page.isVisible('#media-modal'), 'modale TV grande'); await page.click('#media-close'); }
await page.click('#btn-reset'); await wait(1200); ok(/ripristinata/.test(await txt('#alert-pop')), 'pulsante 🛠 ripristina mappa');
await page.click('#tv-edit'); await wait(200); ok(/CANALI/.test(await txt('#modal-title')), 'editor canali TV'); await page.click('[data-close-modal]');
await page.click('#btn-full'); await wait(800); await shot('08-fullmap'); await page.click('#btn-full'); await wait(400);
await page.keyboard.press('?'); await wait(200); await page.keyboard.press('Escape');
await wait(2500);
await shot('09-final');

console.log('— errori');
const fps = await txt('#sb-fps');
console.log('    fps (SwiftShader software):', fps);
ok(errors.length === 0, `nessun errore JavaScript (${errors.length})`);
errors.slice(0, 12).forEach(e => console.log('    ⚠', e.slice(0, 400)));
if (unknown.size) console.log('    host non simulati:', [...unknown].slice(0, 20).join(', '));
console.log(`\n${fail ? '✗' : '✓'} ${pass} superati, ${fail} falliti\n`);
await browser.close(); srv.close();
process.exit(fail ? 1 : 0);
