// Pannelli: unità in onda, livelli dei canali, statistiche, impostazioni dal vivo.

import { $, el, api, colore, eta, mhz, memoria } from './util.js';

// ───────── unità in onda
let inOndaOra = new Set();
export function impostaInOnda(set) { inOndaOra = set; }

export function disegnaUnita(units, seguita, onScegli) {
  const box = $('#lista-unita');
  box.textContent = '';
  const vive = (units || []).filter(u => u.lat != null);
  if (!vive.length) { box.append(el('p', 'vuoto', 'nessuna unità')); return; }
  for (const u of vive) {
    const r = el('div', 'riga-unita' + (seguita === u.unit ? ' seguita' : '')
      + (inOndaOra.has(u.unit) ? ' onda' : ''));
    const p = el('span', 'punto'); p.style.background = colore(u.unit);
    r.append(p, el('span', 'sigla', u.unit), el('span', 'luogo', u.place || ''),
      el('span', 'eta', eta(u.age)));
    r.onclick = () => onScegli(seguita === u.unit ? null : u.unit);
    box.append(r);
  }
}

// ───────── livelli dei canali (il "cruscotto" della radio)
const DB_MIN = -100;
const perc = db => Math.max(0, Math.min(100, ((db - DB_MIN) / -DB_MIN) * 100));

export function disegnaLivelli(dati) {
  const box = $('#lista-livelli');
  if (!dati || !dati.canali || !dati.canali.length) {
    if (!box.dataset.chiavi) {
      box.textContent = '';
      box.append(el('p', 'vuoto', window.GUARDIA && window.GUARDIA.mode === 'demo'
        ? 'modo demo: nessuna radio in ascolto' : 'in attesa della radio…'));
    }
    return;
  }
  const canali = dati.canali;
  if (box.childElementCount !== canali.length || box.dataset.chiavi !== canali.map(c => c.unit + c.freq).join()) {
    box.textContent = '';
    box.dataset.chiavi = canali.map(c => c.unit + c.freq).join();
    for (const c of canali) box.append(rigaCanale(c));
  }
  canali.forEach((c, i) => aggiornaRiga(box.children[i], c));
  $('#nota-livelli').textContent = dati.centro
    ? 'gruppo sintonizzato su ' + (dati.centro / 1e6).toFixed(3) + ' MHz'
    : '';
}

function rigaCanale(c) {
  const r = el('div', 'canale');
  const t = el('div', 'intestazione');
  const p = el('span', 'punto'); p.style.background = colore(c.unit);
  t.append(p, el('span', 'sigla', c.unit), el('span', 'mhz', mhz(c.freq)),
    el('span', 'stato-canale', ''), el('span', 'db', ''));
  const barra = el('div', 'barra-livello');
  barra.append(el('div', 'pieno'), el('div', 'soglia'));
  r.append(t, barra);
  return r;
}

function aggiornaRiga(r, c) {
  if (!r) return;
  r.classList.toggle('aperta', !!c.open);
  const t = r.firstChild;
  t.children[3].textContent = c.cal ? 'CALIBRA' : (c.open ? 'IN ONDA' : '');
  t.children[4].textContent = (c.rssi > -119 ? c.rssi.toFixed(0) : '–') + ' dBFS'
    + (c.floor != null ? '  (fondo ' + c.floor.toFixed(0) + ')' : '');
  r.lastChild.firstChild.style.width = perc(c.rssi) + '%';
  r.lastChild.lastChild.style.left = perc(c.thr) + '%';
}

// ───────── statistiche
export async function caricaStatistiche() {
  const box = $('#corpo-stat');
  try {
    const s = await api('/api/stats?ore=24');
    box.textContent = '';
    const g = el('div', 'griglia');
    g.append(cifra(s.totale, 'TRATTE TOTALI'), cifra(s.avvisi, 'AVVISI'),
      cifra((s.disco && s.disco.audio_mb) + ' MB', 'AUDIO SU DISCO'),
      cifra((s.stati && s.stati.pending) || 0, 'IN CODA'));
    box.append(g, el('h2', null, 'CHIAMATE PER ORA'), istogramma(s.per_ora));
    const t = el('table', 'tab');
    for (const u of s.per_unita) {
      const tr = el('tr');
      const td = el('td');
      const p = el('span', 'punto'); p.style.background = colore(u.unit);
      p.style.display = 'inline-block'; p.style.marginRight = '6px';
      td.append(p, document.createTextNode(u.unit));
      tr.append(td, el('td', null, u.n + ' · ' + (u.dur_media || 0) + 's medi'));
      t.append(tr);
    }
    if (s.per_unita.length) box.append(el('h2', null, 'PER UNITÀ'), t);
  } catch (e) {
    box.textContent = '';
    box.append(el('p', 'vuoto', 'statistiche non disponibili: ' + e.message));
  }
}

function cifra(valore, etichetta) {
  const d = el('div', 'cifra');
  d.append(el('b', null, String(valore)), el('span', null, etichetta));
  return d;
}

function istogramma(perOra) {
  const h = el('div', 'istogramma');
  const mappa = new Map((perOra || []).map(r => [r.fa, r.n]));
  const max = Math.max(1, ...mappa.values());
  for (let fa = 23; fa >= 0; fa--) {
    const n = mappa.get(fa) || 0;
    const b = el('i', fa === 0 ? 'adesso' : null);
    b.style.height = Math.max(2, (n / max) * 100) + '%';
    b.title = n + ' chiamate, ' + (fa ? fa + ' ore fa' : 'ultima ora');
    h.append(b);
  }
  return h;
}

// ───────── impostazioni dal vivo
const CAMPI = [
  { k: 'squelch_mode', t: 'scelta', opzioni: ['auto', 'manual'], e: 'Squelch' },
  { k: 'squelch_margin', t: 'cursore', min: 1, max: 20, passo: .5, e: 'Margine sul rumore (dB)' },
  { k: 'squelch', t: 'cursore', min: -90, max: 0, passo: 1, e: 'Soglia fissa (dBFS)' },
  { k: 'hang', t: 'cursore', min: .1, max: 3, passo: .1, e: 'Coda di chiusura (s)' },
  { k: 'min_voice', t: 'cursore', min: .2, max: 5, passo: .1, e: 'Durata minima (s)' },
  { k: 'max_seg', t: 'cursore', min: 2, max: 60, passo: 1, e: 'Durata massima (s)' },
  { k: 'dwell', t: 'cursore', min: .5, max: 20, passo: .5, e: 'Turno per gruppo (s)' },
  { k: 'retention_hours', t: 'numero', e: 'Conserva (ore)' },
  { k: 'max_audio_mb', t: 'numero', e: 'Tetto audio (MB)' },
  { k: 'alerts', t: 'testo', e: "Parole d'allarme" },
];

let impostazioni = {};
let timerInvio = null;

export async function caricaImpostazioni() {
  try {
    impostazioni = await api('/api/settings');
  } catch (e) { return; }
  const f = $('#modulo-imp');
  f.textContent = '';
  for (const c of CAMPI) {
    if (!(c.k in impostazioni)) continue;
    const riga = el('div', 'campo');
    const lab = el('label', null, c.e);
    lab.htmlFor = 'imp-' + c.k;
    riga.append(lab);
    let input;
    if (c.t === 'scelta') {
      input = el('select');
      for (const o of c.opzioni) {
        const op = el('option', null, o); op.value = o; input.append(op);
      }
    } else if (c.t === 'cursore') {
      input = el('input'); input.type = 'range';
      input.min = c.min; input.max = c.max; input.step = c.passo;
    } else if (c.t === 'numero') {
      input = el('input'); input.type = 'number'; input.min = 1;
    } else {
      input = el('input'); input.type = 'text';
    }
    input.id = 'imp-' + c.k;
    input.value = c.k === 'alerts' ? (impostazioni[c.k] || []).join(', ') : impostazioni[c.k];
    riga.append(input);
    if (c.t === 'cursore') {
      const v = el('span', 'val', String(impostazioni[c.k]));
      riga.append(v);
      input.oninput = () => { v.textContent = input.value; };
    }
    input.onchange = () => invia(c, input);
    f.append(riga);
  }
  if (_notifiche) { f.append(_notifiche.riga); _notifiche.aggiorna(); }
}

function invia(campo, input) {
  let valore = input.value;
  if (campo.k === 'alerts') valore = valore.split(',').map(s => s.trim()).filter(Boolean);
  else if (campo.t !== 'scelta') valore = Number(valore);
  if (campo.t !== 'scelta' && campo.k !== 'alerts' && !Number.isFinite(valore)) return;
  clearTimeout(timerInvio);
  timerInvio = setTimeout(async () => {
    const nota = $('#nota-imp');
    try {
      const r = await api('/api/settings', {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ [campo.k]: valore }),
      });
      impostazioni = r.settings || impostazioni;
      nota.textContent = 'salvato';
      nota.className = 'nota salvato';
      setTimeout(() => {
        nota.textContent = 'Le modifiche hanno effetto subito e restano salvate.';
        nota.className = 'nota';
      }, 1800);
    } catch (e) {
      nota.textContent = 'non salvato: ' + e.message;
      nota.className = 'nota';
    }
  }, 250);
}

/** Interruttore delle notifiche di sistema, in fondo alle impostazioni. */
export function interruttoreNotifiche(leggi, scrivi) {
  const f = $('#modulo-imp');
  const riga = el('div', 'campo');
  const b = el('button', 'tasto piccolo');
  const aggiorna = () => {
    const on = leggi();
    b.textContent = on ? 'ATTIVE' : 'SPENTE';
    b.classList.toggle('attivo', !!on);
  };
  b.type = 'button';
  b.onclick = async () => { await scrivi(!leggi()); aggiorna(); };
  riga.append(el('label', null, 'Notifiche di sistema'), b);
  aggiorna();
  f.append(riga);
  _notifiche = { riga, aggiorna };
}
let _notifiche = null;

export function chiudiTutti() {
  for (const x of aperti) x.applica(false, true);
}

export function sincronizzaImpostazioni(nuove) {
  impostazioni = nuove || impostazioni;
  for (const c of CAMPI) {
    const i = document.getElementById('imp-' + c.k);
    if (!i || document.activeElement === i) continue;
    const v = c.k === 'alerts' ? (impostazioni[c.k] || []).join(', ') : impostazioni[c.k];
    if (String(i.value) !== String(v)) {
      i.value = v;
      const val = i.parentElement.querySelector('.val');
      if (val) val.textContent = i.value;
    }
  }
}

// ───────── apertura e chiusura
// I pannelli sovrapposti alla mappa sono esclusivi: due aperti insieme si coprono a
// vicenda sul telefono e nascondono la mappa.
const aperti = [];

export function collega(bottone, pannello, allApertura) {
  const b = $(bottone), p = $(pannello);
  const chiave = 'aperto' + pannello;
  const applica = (aperto, salva) => {
    if (aperto) for (const altro of aperti) if (altro.p !== p) altro.applica(false, true);
    p.classList.toggle('nascosto', !aperto);
    b.classList.toggle('attivo', aperto);
    if (salva) memoria.set(chiave, aperto);
    if (aperto && allApertura) allApertura();
  };
  aperti.push({ p, applica });
  b.onclick = () => applica(p.classList.contains('nascosto'), true);
  const x = p.querySelector('[data-chiudi]');
  if (x) x.onclick = () => applica(false, true);
  if (memoria.get(chiave, false)) applica(true, false);
}
