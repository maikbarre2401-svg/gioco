window.GL = window.GL || {};

(() => {
  'use strict';

  const { $, toast, log, haptic, copyText } = GL.ui;
  const KEY = 'ghostlink-vault';   // { salt, iv, data } all base64 — ciphertext of the JSON entry list
  const CHECK = 'ghostlink-vault-set';
  const enc = new TextEncoder();
  const dec = new TextDecoder();
  const ITER = 200000;

  let cryptoKey = null;   // derived AES key, held only while unlocked
  let entries = [];       // [{id, title, secret, type}]
  let unlocked = false;

  const b64 = buf => btoa(String.fromCharCode(...new Uint8Array(buf)));
  const unb64 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));

  async function deriveKey(pin, salt) {
    const base = await crypto.subtle.importKey('raw', enc.encode(pin), 'PBKDF2', false, ['deriveKey']);
    return crypto.subtle.deriveKey({ name: 'PBKDF2', salt, iterations: ITER, hash: 'SHA-256' }, base,
      { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
  }

  function load() { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch { return null; } }
  function exists() { try { return !!localStorage.getItem(KEY) || localStorage.getItem(CHECK) === '1'; } catch { return false; } }

  async function save() {
    const stored = load();
    if (!stored || !cryptoKey) return;   // keep the original salt so the PIN still works
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, cryptoKey, enc.encode(JSON.stringify(entries)));
    try {
      localStorage.setItem(KEY, JSON.stringify({ salt: stored.salt, iv: b64(iv), data: b64(ct) }));
      localStorage.setItem(CHECK, '1');
    } catch { toast('Spazio di archiviazione non disponibile'); }
  }

  async function createVault(pin) {
    const salt = crypto.getRandomValues(new Uint8Array(16));
    cryptoKey = await deriveKey(pin, salt);
    entries = [];
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, cryptoKey, enc.encode('[]'));
    try { localStorage.setItem(KEY, JSON.stringify({ salt: b64(salt), iv: b64(iv), data: b64(ct) })); localStorage.setItem(CHECK, '1'); } catch {}
    unlocked = true;
    render();
    GL.sfx.play('ok');
    log('Cassaforte creata', 'ok');
  }

  async function unlock(pin) {
    const stored = load();
    if (!stored) return createVault(pin);
    try {
      cryptoKey = await deriveKey(pin, unb64(stored.salt));
      const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: unb64(stored.iv) }, cryptoKey, unb64(stored.data));
      entries = JSON.parse(dec.decode(pt));
      unlocked = true;
      render();
      GL.sfx.play('lock');
      haptic([10, 30, 10]);
      log('Cassaforte sbloccata', 'ok');
      GL.app?.xp(3, 'cassaforte');
    } catch {
      cryptoKey = null;
      toast('PIN sbagliato');
      GL.sfx.play('err');
      haptic([60, 40, 60]);
      $('#vault-pin').value = '';
    }
  }

  function lock() {
    cryptoKey = null; entries = []; unlocked = false;
    render();
  }

  function addEntry() {
    const title = $('#vault-title').value.trim();
    const secret = $('#vault-secret').value;
    if (!title || !secret) { toast('Scrivi un nome e un contenuto'); return; }
    entries.push({ id: Date.now(), title, secret, type: $('#vault-secret').value.length < 64 && !/\s/.test(secret) ? 'password' : 'nota' });
    $('#vault-title').value = ''; $('#vault-secret').value = '';
    save();
    render();
    GL.sfx.play('ok');
    GL.app?.xp(3, 'cassaforte');
    toast('Salvato nella cassaforte');
  }

  function removeEntry(id) {
    entries = entries.filter(e => e.id !== id);
    save();
    render();
    GL.sfx.play('blip');
  }

  function render() {
    $('#vault-locked').hidden = unlocked;
    $('#vault-open').hidden = !unlocked;
    if (unlocked) {
      const list = $('#vault-list');
      if (!entries.length) {
        list.innerHTML = '<p class="note">La cassaforte è vuota. Aggiungi la prima voce qui sotto.</p>';
      } else {
        list.replaceChildren(...entries.slice().reverse().map(e => {
          const card = document.createElement('div');
          card.className = 'vault-item';
          const head = document.createElement('div'); head.className = 'vault-item-head';
          const t = document.createElement('b'); t.textContent = e.title;
          const tag = document.createElement('span'); tag.className = 'tag'; tag.textContent = e.type;
          head.append(t, tag);
          const body = document.createElement('div'); body.className = 'vault-secret'; body.textContent = '••••••••';
          let shown = false;
          const row = document.createElement('div'); row.className = 'row';
          const show = btn('Mostra', () => { shown = !shown; body.textContent = shown ? e.secret : '••••••••'; show.textContent = shown ? 'Nascondi' : 'Mostra'; });
          const cp = btn('Copia', () => copyText(e.secret, 'Copiato'));
          const del = btn('Elimina', () => removeEntry(e.id), 'danger');
          row.append(show, cp, del);
          card.append(head, body, row);
          return card;
        }));
      }
    }
    const first = $('#vault-first');
    if (first) first.hidden = exists();
  }

  function btn(label, fn, cls = '') {
    const b = document.createElement('button');
    b.type = 'button'; b.className = `btn ghost small ${cls}`; b.textContent = label;
    b.addEventListener('click', fn);
    return b;
  }

  function init() {
    $('#vault-unlock').addEventListener('click', () => {
      const pin = $('#vault-pin').value;
      if (pin.length < 4) { toast('Il PIN deve avere almeno 4 cifre'); return; }
      unlock(pin);
    });
    $('#vault-pin').addEventListener('keydown', e => { if (e.key === 'Enter') $('#vault-unlock').click(); });
    $('#vault-add').addEventListener('click', addEntry);
    $('#vault-lock').addEventListener('click', lock);
  }

  function enter() {
    $('#vault-pin').value = '';
    $('#vault-unlock').textContent = exists() ? 'Sblocca' : 'Crea cassaforte';
    render();
  }
  function leave() { lock(); }   // auto-lock when leaving the screen

  GL.vault = { init, enter, leave };
})();
