// Punto di avvio: collega i dati che arrivano ai pezzi che li disegnano.

import { $, CFG, api, colore, memoria } from './util.js';
import { Live } from './live.js';
import { mappa, inquadra, anello, azzeraTocco } from './map.js';
import * as veicoli from './vehicles.js';
import * as pannelli from './panels.js';
import * as feed from './feed.js';

const live = new Live();
let seguita = null;
let auto = memoria.get('auto', true);
let centrata = false;
let ultimo = { units: [], air: [] };
let collegamento = 'avvio';

// ───────── telecamera
function segui(unita) {
  seguita = unita;
  pannelli.disegnaUnita(ultimo.units, seguita, segui);
  if (!unita) return;
  const p = veicoli.posizione(unita);
  if (p) mappa.easeTo({ center: p, zoom: Math.max(mappa.getZoom(), 16), duration: 900 });
}

function apri(e) {
  if (e.lat != null) {
    azzeraTocco();
    mappa.easeTo({ center: [e.lon, e.lat], zoom: 16.5, pitch: 60, duration: 1200 });
  }
  if (e.has_audio) riproduci(e.id);
}

let suono = null, inAscolto = null;
function riproduci(id) {
  try {
    if (suono) { suono.pause(); suono = null; }
    if (inAscolto === id) { inAscolto = null; feed.segnaInAscolto(null); return; }
    suono = new Audio('/api/audio/' + id + (CFG.token ? '?t=' + encodeURIComponent(CFG.token) : ''));
    inAscolto = id;
    feed.segnaInAscolto(id);
    const fine = () => { if (inAscolto === id) { inAscolto = null; feed.segnaInAscolto(null); } };
    suono.addEventListener('ended', fine);
    suono.addEventListener('error', fine);
    suono.play().catch(fine);
  } catch (e) { }
}

// ───────── dati in arrivo
live.on('state', d => {
  if (!d) return;
  ultimo = d;
  veicoli.aggiorna(d.units, d.air);
  pannelli.disegnaUnita(d.units, seguita, segui);
  feed.pillole([...new Set((d.units || []).map(u => u.unit))]);
  if (d.levels) pannelli.disegnaLivelli({ canali: d.levels.canali, centro: d.levels.centro });
  intestazione(d);
  if (seguita) {
    const p = veicoli.posizione(seguita);
    if (p) mappa.easeTo({ center: p, duration: 1400 });
  }
  const prima = (d.units || []).find(u => u.lat != null);
  if (!centrata && prima) {
    centrata = true;
    inquadra(prima.lon, prima.lat, 15.5);
  }
});

live.on('event', e => {
  if (!e || feed.inCerca()) return;
  feed.aggiungi(e, true);
  if (e.lat != null) {
    anello(e.lon, e.lat, colore(e.unit));
    if (auto && centrata) inquadra(e.lon, e.lat);
  }
  if (e.alert) avvisa(e);
});

live.on('capture', c => { if (c && !feed.inCerca()) feed.attesa(c); });
live.on('levels', d => pannelli.disegnaLivelli(d));
live.on('settings', s => pannelli.sincronizzaImpostazioni(s));
live.on('collegamento', s => { collegamento = s.modo; intestazione(ultimo); });
live.on('errore', () => { collegamento = 'giu'; intestazione(ultimo); });

function intestazione(d) {
  const n = (d && d.units || []).length, a = (d && d.air || []).length;
  const spia = $('#spia');
  const etichette = { ws: ['LIVE', 'onda'], poll: ['LENTO', ''], negato: ['TOKEN', 'giu'],
    giu: ['OFFLINE', 'giu'], avvio: ['…', ''] };
  const [testo, cls] = etichette[collegamento] || ['LIVE', ''];
  spia.textContent = testo;
  spia.className = 'spia ' + cls;
  $('#riga-stato').textContent =
    n + ' unità · ' + a + ' aeromobili · ' + (CFG.mode || '?') + (veicoli.c3d ? ' · 3D' : ' · 2D');
}

// ───────── avvisi
let permesso = memoria.get('notifiche', false);
function avvisa(e) {
  if (!permesso || !('Notification' in window) || Notification.permission !== 'granted') return;
  try {
    new Notification(e.unit + ' · ' + e.alert.toUpperCase(), {
      body: (e.text || '').slice(0, 120) + (e.place ? '\n▸ ' + e.place : ''),
      tag: 'guardia-' + e.id, icon: '/ui/icon.svg',
    });
  } catch (err) { }
}

// ───────── attrezzi
function attrezzi() {
  const bAuto = $('#t-auto');
  bAuto.classList.toggle('attivo', auto);
  bAuto.onclick = () => {
    auto = !auto;
    memoria.set('auto', auto);
    bAuto.classList.toggle('attivo', auto);
  };
  pannelli.interruttoreNotifiche(() => permesso, async acceso => {
    if (!acceso) { permesso = false; memoria.set('notifiche', false); return false; }
    if (!('Notification' in window)) return false;
    // il permesso si può chiedere solo da un gesto dell'utente: questo è il clic
    permesso = (await Notification.requestPermission()) === 'granted';
    memoria.set('notifiche', permesso);
    return permesso;
  });
  pannelli.collega('#t-livelli', '#p-livelli');
  pannelli.collega('#t-stat', '#p-stat', pannelli.caricaStatistiche);
  pannelli.collega('#t-imp', '#p-imp', pannelli.caricaImpostazioni);
  const csv = $('#t-csv');
  csv.href = '/api/export.csv?ore=168' + (CFG.token ? '&t=' + encodeURIComponent(CFG.token) : '');
  csv.setAttribute('download', '');
  scorciatoie();
}

/** Poche scorciatoie, quelle che servono davvero in una sala operativa. */
function scorciatoie() {
  document.addEventListener('keydown', ev => {
    const scrive = /^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName);
    if (ev.key === '/' && !scrive) { ev.preventDefault(); $('#cerca').focus(); }
    else if (ev.key === 'Escape') {
      if (scrive) { document.activeElement.blur(); return; }
      pannelli.chiudiTutti();
      if (seguita) segui(null);
    } else if (ev.key.toLowerCase() === 'l' && !scrive) $('#t-livelli').click();
    else if (ev.key.toLowerCase() === 'd' && !scrive) $('#t-stat').click();
    else if (ev.key === ' ' && !scrive && inAscolto == null) {
      const prima = $('#righe .riga');
      if (prima) { ev.preventDefault(); riproduci(Number(prima.dataset.id)); }
    }
  });
}

// ───────── avvio
veicoli.installa();
feed.init(apri);
attrezzi();
feed.carica();
intestazione(ultimo);
live.avvia();
setInterval(() => {                      // le età nel pannello invecchiano anche senza dati
  if (ultimo.units) {
    for (const u of ultimo.units) u.age = Math.round((Date.now() / 1000 - u.ts) * 10) / 10;
    pannelli.disegnaUnita(ultimo.units, seguita, segui);
  }
}, 5000);

window.GUARDIA_DEBUG = { live, mappa, veicoli, pannelli, feed, stato: () => ultimo };
