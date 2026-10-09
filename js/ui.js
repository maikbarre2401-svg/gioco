// Shared helpers used by every tool module.

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const pad = n => String(n).padStart(2, '0');
export const clock = (d = new Date()) => `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;

let toastTimer;
export function toast(msg, ms = 2200) {
  const el = $('#toast');
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, ms);
}

// Home "system log". kind: ok | warn | hot | (empty)
export function log(msg, kind = '') {
  const list = $('#log');
  if (!list) return;
  const li = document.createElement('li');
  const t = document.createElement('time');
  t.textContent = clock();
  const span = document.createElement('span');
  span.textContent = msg;
  if (kind) span.className = `t-${kind}`;
  li.append(t, span);
  list.prepend(li);
  while (list.children.length > 14) list.lastElementChild.remove();
}

export function haptic(pattern = 12) {
  try { navigator.vibrate?.(pattern); } catch { /* not supported */ }
}

export async function copyText(text, okMsg = 'Copiato negli appunti') {
  if (!text) { toast('Niente da copiare'); return false; }
  try {
    await navigator.clipboard.writeText(text);
    toast(okMsg);
    haptic();
    return true;
  } catch {
    // Fallback for browsers that refuse the async clipboard.
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.append(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch { ok = false; }
    ta.remove();
    toast(ok ? okMsg : 'Copia non riuscita: tieni premuto sul testo per copiarlo');
    return ok;
  }
}

export function setPressed(buttons, active) {
  buttons.forEach(b => b.setAttribute('aria-pressed', String(b === active)));
}

export const fmt = {
  num: (n, d = 0) => Number(n).toLocaleString('it-IT', { minimumFractionDigits: d, maximumFractionDigits: d }),
  bytes: gb => (gb >= 1 ? `${gb} GB` : `${gb * 1024} MB`),
};

// Pretty duration for "time to crack" style numbers (seconds in, Italian text out).
export function humanTime(sec) {
  if (!isFinite(sec) || sec > 1e30) return 'praticamente infinito';
  if (sec < 1) return 'istantaneo';
  const units = [
    ['secoli', 3.156e9], ['anni', 3.156e7], ['giorni', 86400], ['ore', 3600], ['minuti', 60], ['secondi', 1],
  ];
  for (const [name, s] of units) {
    if (sec >= s) {
      const v = sec / s;
      if (name === 'secoli' && v >= 1e6) return `${v.toExponential(1).replace('e+', ' × 10^')} secoli`;
      return `${fmt.num(v, v < 10 ? 1 : 0)} ${name}`;
    }
  }
  return 'istantaneo';
}

// SHA-256 hex of a string; falls back to a simple FNV hash when SubtleCrypto is unavailable.
export async function sha256(text) {
  try {
    const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
    return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
  } catch {
    let h = 0x811c9dc5;
    for (let i = 0; i < text.length; i++) { h ^= text.charCodeAt(i); h = Math.imul(h, 0x01000193); }
    return (h >>> 0).toString(16).padStart(8, '0').repeat(8);
  }
}

// Size a canvas backing store to its CSS box at device pixel ratio; returns the 2D context.
export function fitCanvas(canvas) {
  const dpr = Math.min(window.devicePixelRatio || 1, 3);
  const w = canvas.clientWidth || canvas.width;
  const h = canvas.clientHeight || canvas.height;
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
  }
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w, h };
}

export const COLORS = {
  cyan: '#2ef2ff', magenta: '#ff2d75', amber: '#ffb020', ok: '#4dffb0',
  line: '#1b2c45', dim: '#7489a6', fg: '#d9e6f7', bg: '#05070d',
};
