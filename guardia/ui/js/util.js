// Utilità condivise: nessuna dipendenza, tutto il resto parte da qui.

export const CFG = window.GUARDIA || {};
export const QS = CFG.token ? '?t=' + encodeURIComponent(CFG.token) : '';

export const COLORI = { CC: '#2563eb', PS: '#dc2626', PL: '#16a34a', VVF: '#d97706' };
export const colore = u => COLORI[u] || '#6ea8ff';
export const colore3 = u => parseInt(colore(u).slice(1), 16);

export const $ = (sel, r = document) => r.querySelector(sel);
export const $$ = (sel, r = document) => [...r.querySelectorAll(sel)];

export function el(tag, cls, testo) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (testo != null) n.textContent = testo;          // mai innerHTML: il testo è trascritto
  return n;
}

export const eta = s => s < 60 ? (s | 0) + 's' : s < 3600 ? ((s / 60) | 0) + 'm' : ((s / 3600) | 0) + 'h';
export const orario = ts => new Date(ts * 1000).toLocaleTimeString('it-IT');
export const mhz = f => ((f || 0) / 1e6).toFixed(4);

/** fetch con token, timeout e errori come eccezioni leggibili. */
export async function api(percorso, opz = {}) {
  const sep = percorso.includes('?') ? '&' : '?';
  const url = percorso + (CFG.token ? sep + 't=' + encodeURIComponent(CFG.token) : '');
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), opz.timeout || 12000);
  try {
    const r = await fetch(url, { cache: 'no-store', signal: ctrl.signal, ...opz });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.headers.get('content-type')?.includes('json') ? r.json() : r.text();
  } finally {
    clearTimeout(timer);
  }
}

/** Minimo indispensabile per disaccoppiare chi produce dati da chi li disegna. */
export class Emettitore {
  constructor() { this._a = new Map(); }
  on(tipo, fn) {
    if (!this._a.has(tipo)) this._a.set(tipo, []);
    this._a.get(tipo).push(fn);
    return this;
  }
  emit(tipo, dati) {
    for (const fn of this._a.get(tipo) || []) {
      try { fn(dati); } catch (e) { console.error('[' + tipo + ']', e); }
    }
  }
}

/** localStorage può lanciare (modalità privata): mai far cadere la pagina per una preferenza. */
export const memoria = {
  get(k, d) { try { const v = localStorage.getItem('guardia.' + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('guardia.' + k, JSON.stringify(v)); } catch { } },
};
