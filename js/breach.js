window.GL = window.GL || {};

(() => {
  'use strict';

  const { $, toast, log, haptic, fmt } = GL.ui;
  const enc = new TextEncoder();

  async function sha1(text) {
    const buf = await crypto.subtle.digest('SHA-1', enc.encode(text));
    return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('').toUpperCase();
  }

  // k-anonymity: only the first 5 hex chars of the SHA-1 are sent; the API returns every
  // matching suffix and we compare locally. The password itself never leaves the device.
  async function check() {
    const pw = $('#breach-in').value;
    if (!pw) { toast('Scrivi una password da controllare'); return; }
    if (!navigator.onLine) { toast('Serve la connessione per questo controllo'); return; }
    const btn = $('#breach-run');
    btn.disabled = true;
    const res = $('#breach-result');
    res.hidden = false;
    res.className = 'card';
    res.innerHTML = '<div class="eyebrow">Controllo in corso…</div>';
    GL.sfx.play('hack');
    try {
      const hash = await sha1(pw);
      const prefix = hash.slice(0, 5), suffix = hash.slice(5);
      const r = await fetch(`https://api.pwnedpasswords.com/range/${prefix}`, { headers: { 'Add-Padding': 'true' }, cache: 'no-store' });
      if (!r.ok) throw new Error('api');
      const body = await r.text();
      let count = 0;
      for (const line of body.split('\n')) {
        const [suf, c] = line.trim().split(':');
        if (suf === suffix) { count = parseInt(c, 10); break; }
      }
      show(count);
      GL.app?.xp(5, 'controllo breach');
    } catch {
      res.innerHTML = '<div class="eyebrow" style="color:var(--amber)">Servizio non raggiungibile</div><p class="note">Riprova tra poco.</p>';
      GL.sfx.play('err');
    } finally { btn.disabled = false; }
  }

  function show(count) {
    const res = $('#breach-result');
    if (count > 0) {
      res.style.borderColor = 'var(--magenta)';
      res.innerHTML = `
        <div class="breach-big hot">⚠ COMPROMESSA</div>
        <p>Questa password è comparsa in <b>${fmt.num(count)}</b> fughe di dati note.</p>
        <p class="note">È in mano agli aggressori: non usarla da nessuna parte. Cambiala dove la usi e genera una password nuova nella sezione Password.</p>`;
      GL.sfx.play('err');
      haptic([60, 40, 60, 40, 80]);
      log('Password trovata nei data breach', 'hot');
    } else {
      res.style.borderColor = 'var(--ok)';
      res.innerHTML = `
        <div class="breach-big good">✔ NON TROVATA</div>
        <p>Questa password non compare nelle fughe di dati conosciute.</p>
        <p class="note">Buon segno, ma non è una garanzia: resta forte solo se è lunga e usata in un unico posto.</p>`;
      GL.sfx.play('ok');
      haptic([15, 30, 15]);
      log('Password non trovata nei breach', 'ok');
    }
  }

  function init() {
    $('#breach-run').addEventListener('click', check);
    $('#breach-in').addEventListener('keydown', e => { if (e.key === 'Enter') check(); });
    const show = $('#breach-show');
    show.addEventListener('click', () => {
      const on = show.getAttribute('aria-pressed') !== 'true';
      show.setAttribute('aria-pressed', String(on));
      show.textContent = on ? 'Nascondi' : 'Mostra';
      $('#breach-in').type = on ? 'text' : 'password';
    });
  }

  GL.breach = { init };
})();
