window.GL = window.GL || {};

(() => {
  'use strict';

  const { $, $$, toast, copyText, sha256 } = GL.ui;
  const enc = new TextEncoder();
  const dec = new TextDecoder();

  /* ---------------- compact MD5 (RFC 1321) for the classic hacker hash ---------------- */
  function md5(str) {
    const bytes = enc.encode(str);
    function rl(x, c) { return (x << c) | (x >>> (32 - c)); }
    function add(a, b) { return (a + b) & 0xffffffff; }
    const K = [], S = [7, 12, 17, 22, 5, 9, 14, 20, 4, 11, 16, 23, 6, 10, 15, 21];
    for (let i = 0; i < 64; i++) K[i] = Math.floor(Math.abs(Math.sin(i + 1)) * 4294967296);
    const len = bytes.length;
    const withOne = len + 1;
    const padded = new Uint8Array((((withOne + 8) + 63) & ~63));
    padded.set(bytes); padded[len] = 0x80;
    const bits = len * 8;
    const dv = new DataView(padded.buffer);
    dv.setUint32(padded.length - 8, bits & 0xffffffff, true);
    dv.setUint32(padded.length - 4, Math.floor(bits / 4294967296), true);
    let a0 = 0x67452301, b0 = 0xefcdab89, c0 = 0x98badcfe, d0 = 0x10325476;
    for (let off = 0; off < padded.length; off += 64) {
      const M = [];
      for (let i = 0; i < 16; i++) M[i] = dv.getUint32(off + i * 4, true);
      let A = a0, B = b0, C = c0, D = d0;
      for (let i = 0; i < 64; i++) {
        let F, g;
        if (i < 16) { F = (B & C) | (~B & D); g = i; }
        else if (i < 32) { F = (D & B) | (~D & C); g = (5 * i + 1) % 16; }
        else if (i < 48) { F = B ^ C ^ D; g = (3 * i + 5) % 16; }
        else { F = C ^ (B | ~D); g = (7 * i) % 16; }
        F = add(add(add(F, A), K[i]), M[g]);
        A = D; D = C; C = B;
        B = add(B, rl(F, S[(Math.floor(i / 16) * 4) + (i % 4)]));
      }
      a0 = add(a0, A); b0 = add(b0, B); c0 = add(c0, C); d0 = add(d0, D);
    }
    const hex = n => [0, 8, 16, 24].map(s => ((n >>> s) & 0xff).toString(16).padStart(2, '0')).join('');
    return hex(a0) + hex(b0) + hex(c0) + hex(d0);
  }

  const b64 = s => btoa(unescape(encodeURIComponent(s)));
  const unb64 = s => decodeURIComponent(escape(atob(s.replace(/-/g, '+').replace(/_/g, '/'))));
  const toHex = s => [...enc.encode(s)].map(b => b.toString(16).padStart(2, '0')).join(' ');
  const fromHex = s => dec.decode(Uint8Array.from(s.trim().split(/[\s:]+/).filter(Boolean).map(h => parseInt(h, 16))));
  const toBin = s => [...enc.encode(s)].map(b => b.toString(2).padStart(8, '0')).join(' ');
  const fromBin = s => dec.decode(Uint8Array.from(s.trim().split(/\s+/).filter(Boolean).map(b => parseInt(b, 2))));
  const rot13 = s => s.replace(/[a-z]/gi, c => { const b = c <= 'Z' ? 65 : 97; return String.fromCharCode((c.charCodeAt(0) - b + 13) % 26 + b); });
  const MORSE = { A: '.-', B: '-...', C: '-.-.', D: '-..', E: '.', F: '..-.', G: '--.', H: '....', I: '..', J: '.---', K: '-.-', L: '.-..', M: '--', N: '-.', O: '---', P: '.--.', Q: '--.-', R: '.-.', S: '...', T: '-', U: '..-', V: '...-', W: '.--', X: '-..-', Y: '-.--', Z: '--..', 0: '-----', 1: '.----', 2: '..---', 3: '...--', 4: '....-', 5: '.....', 6: '-....', 7: '--...', 8: '---..', 9: '----.' };
  const RMORSE = Object.fromEntries(Object.entries(MORSE).map(([k, v]) => [v, k]));
  const toMorse = s => s.toUpperCase().split('').map(c => c === ' ' ? '/' : (MORSE[c] || '')).join(' ').trim();
  const fromMorse = s => s.trim().split(' ').map(c => c === '/' ? ' ' : (RMORSE[c] || '')).join('');

  function jwt(token) {
    const parts = token.trim().split('.');
    if (parts.length < 2) throw new Error('jwt');
    const pretty = o => JSON.stringify(JSON.parse(o), null, 2);
    let out = `— HEADER —\n${pretty(unb64(parts[0]))}\n\n— PAYLOAD —\n${pretty(unb64(parts[1]))}`;
    try {
      const p = JSON.parse(unb64(parts[1]));
      if (p.exp) out += `\n\nScadenza: ${new Date(p.exp * 1000).toLocaleString('it-IT')}${p.exp * 1000 < Date.now() ? ' (SCADUTO)' : ''}`;
    } catch { /* no exp */ }
    return out;
  }

  const OPS = {
    'base64 →': { fn: async t => b64(t), out: 'Base64' },
    '→ base64': { fn: async t => unb64(t), out: 'Testo' },
    'hex →': { fn: async t => toHex(t), out: 'Esadecimale' },
    '→ hex': { fn: async t => fromHex(t), out: 'Testo' },
    'binario →': { fn: async t => toBin(t), out: 'Binario' },
    '→ binario': { fn: async t => fromBin(t), out: 'Testo' },
    'URL →': { fn: async t => encodeURIComponent(t), out: 'URL' },
    '→ URL': { fn: async t => decodeURIComponent(t), out: 'Testo' },
    'ROT13': { fn: async t => rot13(t), out: 'ROT13' },
    'Morse →': { fn: async t => toMorse(t), out: 'Morse' },
    '→ Morse': { fn: async t => fromMorse(t), out: 'Testo' },
    'inverti': { fn: async t => [...t].reverse().join(''), out: 'Invertito' },
    'MD5': { fn: async t => md5(t), out: 'MD5' },
    'SHA-1': { fn: async t => hashHex(t, 'SHA-1'), out: 'SHA-1' },
    'SHA-256': { fn: async t => sha256(t), out: 'SHA-256' },
    'SHA-512': { fn: async t => hashHex(t, 'SHA-512'), out: 'SHA-512' },
    'JWT decode': { fn: async t => jwt(t), out: 'JWT' },
    'conta': { fn: async t => `${t.length} caratteri · ${t.trim() ? t.trim().split(/\s+/).length : 0} parole · ${enc.encode(t).length} byte`, out: 'Statistiche' },
  };

  async function hashHex(t, algo) {
    const buf = await crypto.subtle.digest(algo, enc.encode(t));
    return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
  }

  let currentOp = 'base64 →';

  async function runOp() {
    const input = $('#dec-in').value;
    if (!input) { toast('Scrivi qualcosa da trasformare'); return; }
    const out = $('#dec-out');
    try {
      out.value = await OPS[currentOp].fn(input);
      GL.sfx.play('blip');
      GL.app?.xp(2, 'decoder');
    } catch {
      out.value = '';
      toast(`"${currentOp}" non riesce a leggere questo testo`);
      GL.sfx.play('err');
    }
  }

  function init() {
    const box = $('#dec-ops');
    box.replaceChildren(...Object.keys(OPS).map(name => {
      const b = document.createElement('button');
      b.type = 'button'; b.textContent = name; b.className = 'chip-btn';
      b.setAttribute('aria-pressed', String(name === currentOp));
      b.addEventListener('click', () => {
        currentOp = name;
        $$('#dec-ops button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
        runOp();
      });
      return b;
    }));
    $('#dec-in').addEventListener('input', runOp);
    $('#dec-copy').addEventListener('click', () => copyText($('#dec-out').value));
    $('#dec-swap').addEventListener('click', () => { const v = $('#dec-out').value; if (v) { $('#dec-in').value = v; runOp(); } });
  }

  GL.decoder = { init };
})();
