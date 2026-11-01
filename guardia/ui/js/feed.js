// Il registro delle chiamate: righe, filtri, ricerca, riproduzione dell'audio.

import { $, el, api, colore, orario, mhz } from './util.js';

const righe = new Map();          // id → elemento
let onApri = () => { };
const filtro = { unita: null, soloAvvisi: false, cerca: '' };
let inRicerca = false;
let piuVecchio = null;        // ts della riga più vecchia caricata
let staCaricando = false;
let esaurito = false;
const MAX_RIGHE = 400;
const PAGINA = 60;

export function init(apri) {
  onApri = apri || onApri;
  const campo = $('#cerca');
  let timer = null;
  campo.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => cerca(campo.value.trim()), 300);
  });
  $('#t-avvisi').onclick = () => {
    filtro.soloAvvisi = !filtro.soloAvvisi;
    $('#t-avvisi').classList.toggle('attivo', filtro.soloAvvisi);
    applica();
  };
  // registro lungo: si carica scorrendo, invece di tenere tutto in memoria dall'inizio
  $('#righe').addEventListener('scroll', ev => {
    const b = ev.target;
    if (b.scrollTop + b.clientHeight > b.scrollHeight - 120) piuVecchie();
  }, { passive: true });
}

async function piuVecchie() {
  if (staCaricando || esaurito || inRicerca || piuVecchio == null) return;
  staCaricando = true;
  try {
    const r = await api('/api/events?limit=' + PAGINA + '&before=' + piuVecchio);
    const ev = r.events || [];
    if (!ev.length) { esaurito = true; return; }
    for (const e of ev) {
      if (righe.has(e.id)) continue;
      const nodo = disegna(e, false);
      righe.set(e.id, nodo);
      $('#righe').append(nodo);
      applicaUna(nodo, e);
      piuVecchio = Math.min(piuVecchio, e.ts);
    }
  } catch (e) { /* si riprova al prossimo scorrimento */ }
  finally { staCaricando = false; }
}

/** Le pillole di filtro nascono dalle unità che hanno davvero parlato. */
export function pillole(unita) {
  const box = $('#pillole-unita');
  const presenti = new Set([...box.children].map(b => b.dataset.u));
  for (const u of unita) {
    if (presenti.has(u)) continue;
    const b = el('button', 'pillola', u);
    b.dataset.u = u;
    b.style.borderColor = colore(u);
    b.onclick = () => {
      filtro.unita = filtro.unita === u ? null : u;
      [...box.children].forEach(x => {
        const att = x.dataset.u === filtro.unita;
        x.classList.toggle('attiva', att);
        x.style.background = att ? colore(x.dataset.u) : '';
      });
      applica();
    };
    box.append(b);
  }
}

export async function carica() {
  try {
    const r = await api('/api/events?limit=80');
    sostituisciTutto(r.events || []);
  } catch (e) {
    $('#righe').append(el('p', 'vuoto', 'registro non raggiungibile: ' + e.message));
  }
}

async function cerca(q) {
  filtro.cerca = q;
  if (!q) { inRicerca = false; await carica(); applica(); return; }
  inRicerca = true;
  try {
    const r = await api('/api/events?limit=200&q=' + encodeURIComponent(q));
    sostituisciTutto(r.events || []);
  } catch (e) { /* si tiene quel che c'è */ }
}

function sostituisciTutto(eventi) {
  const box = $('#righe');
  box.textContent = '';
  righe.clear();
  esaurito = false;
  piuVecchio = eventi.length ? Math.min(...eventi.map(e => e.ts)) : null;
  for (const e of eventi.slice().reverse()) aggiungi(e, false);
  applica();
}

/** Una tratta appena registrata: compare subito, il testo arriva dopo. */
export function attesa(cap) {
  if (righe.has(cap.id)) return;
  aggiungi({ id: cap.id, ts: Date.now() / 1000, unit: cap.unit, freq: cap.freq, dur: cap.dur,
    rssi: cap.rssi, text: '', place: null, lat: null, lon: null, conf: 0, alert: null,
    has_audio: 1, _attesa: true }, true);
}

export function aggiungi(e, animata = true) {
  const box = $('#righe');
  const vecchia = righe.get(e.id);
  const nodo = disegna(e, animata && !vecchia);
  righe.set(e.id, nodo);
  if (vecchia) vecchia.replaceWith(nodo);
  else box.prepend(nodo);
  while (box.children.length > MAX_RIGHE) {
    const ultimo = box.lastChild;
    righe.delete(Number(ultimo.dataset.id));
    ultimo.remove();
    esaurito = false;               // ne è stata buttata una: si può ricaricare scorrendo
  }
  applicaUna(nodo, e);
}

function disegna(e, animata) {
  const r = el('div', 'riga' + (animata ? ' nuova' : '') + (e.alert ? ' allarme' : '') + (e._attesa ? ' attesa' : ''));
  r.dataset.id = e.id;
  r.dataset.unita = e.unit || '';
  r.dataset.allarme = e.alert ? '1' : '';
  const sig = el('span', 'sig', e.unit);
  sig.style.color = colore(e.unit);
  const corpo = el('div');
  const meta = el('div', 'meta');
  meta.append(el('span', null, orario(e.ts)), el('span', null, mhz(e.freq)));
  if (e.dur) meta.append(el('span', null, e.dur + 's'));
  if (e.rssi) meta.append(el('span', null, e.rssi + ' dBFS'));
  if (e.has_audio) meta.append(el('span', null, '♪'));
  if (e.conf) meta.append(onde(e.conf));
  if (e.alert) meta.append(el('span', 'marchio-allarme', e.alert.toUpperCase()));
  const testo = el('div', 'testo' + (e.text ? '' : ' muto'),
    e.text || (e._attesa ? 'trascrizione in corso…' : '— solo audio —'));
  corpo.append(meta, testo);
  if (e.place) corpo.append(el('div', 'posto', '▸ ' + e.place));
  r.append(sig, corpo);
  r.onclick = () => onApri(e);
  return r;
}

function onde(conf) {
  const s = el('span', 'onde');
  const n = Math.max(1, Math.min(4, Math.round((conf || 0) * 4)));
  for (let i = 1; i <= 4; i++) {
    const b = el('i');
    b.style.height = (3 + i * 1.6) + 'px';
    if (i <= n) b.className = 'on';
    s.append(b);
  }
  return s;
}

function applicaUna(nodo, e) {
  const unitaOk = !filtro.unita || nodo.dataset.unita === filtro.unita;
  const avvisoOk = !filtro.soloAvvisi || nodo.dataset.allarme === '1';
  nodo.style.display = unitaOk && avvisoOk ? '' : 'none';
}

function applica() {
  for (const nodo of $('#righe').children) {
    applicaUna(nodo, null);
  }
}

export const inCerca = () => inRicerca;

/** Unità che stanno trasmettendo in questo momento (dai livelli della radio). */
export function segnaInOnda(unita) {
  for (const b of $('#pillole-unita').children) b.classList.toggle('onda', unita.has(b.dataset.u));
}

/** Evidenzia la riga il cui audio sta suonando. */
export function segnaInAscolto(id) {
  for (const n of $('#righe').children) n.classList.toggle('suona', Number(n.dataset.id) === id);
}
