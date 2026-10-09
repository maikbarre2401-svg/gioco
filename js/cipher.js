window.GL = window.GL || {};

(() => {
  'use strict';

  const { native, $, toast, log, haptic, copyText, setPressed } = GL.ui;

  // Message format: "GL1." + base64url( salt[16] | iv[12] | AES-GCM ciphertext+tag )
  const PREFIX = 'GL1.';
  const ITERATIONS = 250000;
  const enc = new TextEncoder();
  const dec = new TextDecoder();
  let mode = 'enc';

  const b64url = bytes => {
    let s = '';
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  };
  const unb64url = str => {
    const s = str.replace(/-/g, '+').replace(/_/g, '/');
    const bin = atob(s + '='.repeat((4 - (s.length % 4)) % 4));
    return Uint8Array.from(bin, ch => ch.charCodeAt(0));
  };

  async function deriveKey(pass, salt) {
    const base = await crypto.subtle.importKey('raw', enc.encode(pass), 'PBKDF2', false, ['deriveKey']);
    return crypto.subtle.deriveKey(
      { name: 'PBKDF2', salt, iterations: ITERATIONS, hash: 'SHA-256' },
      base,
      { name: 'AES-GCM', length: 256 },
      false,
      ['encrypt', 'decrypt'],
    );
  }

  async function encrypt(text, pass) {
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const key = await deriveKey(pass, salt);
    const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, enc.encode(text)));
    const packed = new Uint8Array(salt.length + iv.length + ct.length);
    packed.set(salt, 0);
    packed.set(iv, 16);
    packed.set(ct, 28);
    return PREFIX + b64url(packed);
  }

  async function decrypt(token, pass) {
    const match = token.replace(/\s+/g, '').match(/GL1\.([A-Za-z0-9_-]+)/);
    if (!match) throw new Error('format');
    const packed = unb64url(match[1]);
    if (packed.length < 29) throw new Error('format');
    const key = await deriveKey(pass, packed.slice(0, 16));
    const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: packed.slice(16, 28) }, key, packed.slice(28));
    return dec.decode(pt);
  }

  function setMode(next) {
    mode = next;
    setPressed([$('#cry-mode-enc'), $('#cry-mode-dec')], next === 'enc' ? $('#cry-mode-enc') : $('#cry-mode-dec'));
    $('#cry-in-label').textContent = next === 'enc' ? 'Messaggio' : 'Messaggio cifrato';
    $('#cry-in').placeholder = next === 'enc' ? 'Ci vediamo alle 22 al solito posto' : 'Incolla qui il testo che inizia con GL1.';
    $('#cry-run').textContent = next === 'enc' ? 'Cifra messaggio' : 'Decifra messaggio';
    $('#cry-out').value = '';
  }

  async function run() {
    const input = $('#cry-in').value;
    const pass = $('#cry-key').value;
    const out = $('#cry-out');
    const btn = $('#cry-run');
    if (!crypto.subtle) { toast('Il cifratore richiede una connessione sicura (https)'); return; }
    if (!input.trim()) { toast(mode === 'enc' ? 'Scrivi prima un messaggio' : 'Incolla prima il messaggio cifrato'); return; }
    if (pass.length < 4) { toast('La chiave deve avere almeno 4 caratteri'); return; }

    btn.disabled = true;
    const label = btn.textContent;
    btn.textContent = mode === 'enc' ? 'Cifratura…' : 'Decifratura…';
    try {
      if (mode === 'enc') {
        out.value = await encrypt(input, pass);
        log(`Messaggio cifrato (${input.length} caratteri)`, 'ok');
      GL.sfx?.play('ok'); GL.app?.xp(8, 'messaggi');
        if (pass.length < 8) toast('Cifrato. Consiglio: usa una chiave di almeno 8 caratteri');
      } else {
        out.value = await decrypt(input, pass);
        log('Messaggio decifrato', 'ok');
      GL.sfx?.play('ok');
      }
      haptic([10, 30, 10]);
    } catch (err) {
      out.value = '';
      const msg = err.message === 'format'
        ? 'Questo non sembra un messaggio Ghostlink: deve contenere GL1.'
        : 'Chiave sbagliata o messaggio incompleto';
      toast(msg, 3200);
      log('Decifratura fallita', 'hot');
    GL.sfx?.play('err');
      haptic([60, 40, 60]);
    } finally {
      btn.disabled = false;
      btn.textContent = label;
    }
  }

  async function share() {
    const text = $('#cry-out').value;
    if (!text) { toast('Prima genera un risultato'); return; }
    if (native) { native.share(text); return; }
    if (navigator.share) {
      try { await navigator.share({ text }); return; } catch (err) { if (err.name === 'AbortError') return; }
    }
    copyText(text, 'Copiato: incollalo nella chat');
  }

  async function paste() {
    try {
      const text = native ? native.paste() : await navigator.clipboard.readText();
      if (!text) { toast('Gli appunti sono vuoti'); return; }
      $('#cry-in').value = text;
      if (text.includes(PREFIX) && mode === 'enc') setMode('dec');
      toast('Incollato');
    } catch {
      toast('Tieni premuto nel riquadro e scegli Incolla');
      $('#cry-in').focus();
    }
  }

  function init() {
    $('#cry-mode-enc').addEventListener('click', () => setMode('enc'));
    $('#cry-mode-dec').addEventListener('click', () => setMode('dec'));
    $('#cry-run').addEventListener('click', run);
    $('#cry-copy').addEventListener('click', () => copyText($('#cry-out').value));
    $('#cry-share').addEventListener('click', share);
    $('#cry-paste').addEventListener('click', paste);
    $('#cry-in').addEventListener('input', e => {
      if (mode === 'enc' && e.target.value.trim().startsWith(PREFIX)) { setMode('dec'); toast('Messaggio cifrato riconosciuto'); }
    });
    const show = $('#cry-key-show');
    show.addEventListener('click', () => {
      const on = show.getAttribute('aria-pressed') !== 'true';
      show.setAttribute('aria-pressed', String(on));
      show.textContent = on ? 'Nascondi' : 'Mostra';
      $('#cry-key').type = on ? 'text' : 'password';
    });
  }

  GL.cipher = { encrypt, decrypt, init };
})();
