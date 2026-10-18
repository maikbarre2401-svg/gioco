window.GL = window.GL || {};

(() => {
  'use strict';

  const { $, $$, toast, haptic, setPressed } = GL.ui;

  const STAT_LABELS = {
    mappa: 'Zone scansionate', analisi: 'Oggetti analizzati', profili: 'Profili generati',
    'test velocità': 'Test di velocità', comandi: 'Comandi eseguiti', messaggi: 'Messaggi cifrati',
    password: 'Password generate', morse: 'Messaggi in Morse',
    cassaforte: 'Accessi cassaforte', steganografia: 'Foto con segreti',
    'controllo breach': 'Password controllate', qr: 'QR usati', metadati: 'Foto analizzate',
    visione: 'Visione usata', decoder: 'Conversioni', voce: 'Voce modificata',
    sismografo: 'Sismografo', iss: 'Tracker ISS', cielo: 'Cielo AR',
  };

  function renderStats() {
    const p = GL.prefs.get();
    const l = GL.prefs.level();
    const box = $('#set-stats');
    const rows = [['Livello', `${l.lvl} · ${l.rank}`], ['Esperienza', `${p.xp} XP`], ['Al prossimo livello', `${l.next} XP`]];
    Object.entries(p.stats || {}).forEach(([k, v]) => rows.push([STAT_LABELS[k] || k, String(v)]));
    box.replaceChildren(...rows.map(([k, v]) => {
      const d = document.createElement('div'); d.className = 'kv';
      const s = document.createElement('span'); s.textContent = k;
      const b = document.createElement('b'); b.textContent = v;
      d.append(s, b); return d;
    }));
  }

  function bindSwitch(id, key) {
    const el = $(id);
    el.checked = !!GL.prefs.get()[key];
    el.addEventListener('change', () => {
      GL.prefs.set({ [key]: el.checked });
      if (key === 'sound' && el.checked) GL.sfx.unlock().then(() => GL.sfx.play('ok'));
      if (key === 'voice' && el.checked) GL.sfx.say('Voce attiva.');
      haptic(10);
    });
  }

  function init() {
    bindSwitch('#set-sound', 'sound');
    bindSwitch('#set-voice', 'voice');
    bindSwitch('#set-vibration', 'vibration');

    const name = $('#set-name');
    $('#set-name-save').addEventListener('click', () => {
      const v = name.value.trim().toUpperCase().replace(/[^A-Z0-9À-Ù_-]/g, '').slice(0, 16);
      if (!v) { toast('Scrivi un nome in codice'); return; }
      GL.prefs.set({ codename: v });
      toast(`Nome in codice: ${v}`);
      GL.sfx.play('ok');
      GL.app?.refreshAgent();
    });

    const setIntro = mode => {
      GL.prefs.set({ intro: mode });
      setPressed([$('#set-intro-full'), $('#set-intro-short')], mode === 'full' ? $('#set-intro-full') : $('#set-intro-short'));
      GL.sfx.play('tap');
    };
    $('#set-intro-full').addEventListener('click', () => setIntro('full'));
    $('#set-intro-short').addEventListener('click', () => setIntro('short'));

    $('#set-test').addEventListener('click', async () => {
      await GL.sfx.unlock();
      GL.sfx.play('boot');
      GL.sfx.say(`Test audio del nodo ${GL.intro.spoken(GL.prefs.get().codename || 'ospite')}.`);
    });

    $('#set-face-go').addEventListener('click', async () => { if (await GL.face.addFace()) enter(); });
    $('#set-face-reset').addEventListener('click', () => GL.face.reEnroll());
    $('#set-pin-go').addEventListener('click', () => {
      const box = $('#set-pin-box');
      box.hidden = !box.hidden;
      $('#set-pin-a').value = ''; $('#set-pin-b').value = ''; $('#set-pin-msg').textContent = '';
    });
    $('#set-pin-save').addEventListener('click', async () => {
      const a = $('#set-pin-a').value.trim(), b = $('#set-pin-b').value.trim();
      if (a.length < 4) { $('#set-pin-msg').textContent = 'Almeno 4 cifre'; return; }
      if (a !== b) { $('#set-pin-msg').textContent = 'I due codici non coincidono'; return; }
      const salt = btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(8))));
      GL.prefs.set({ pinSalt: salt, pinHash: await GL.ui.sha256(salt + a), lockSetup: true });
      $('#set-pin-box').hidden = true;
      toast('Codice salvato');
      GL.sfx?.play('ok');
      enter();
    });
    $('#set-reset').addEventListener('click', () => { $('#set-reset-confirm').hidden = false; });
    $('#set-reset-no').addEventListener('click', () => { $('#set-reset-confirm').hidden = true; });
    $('#set-reset-yes').addEventListener('click', () => {
      GL.prefs.reset();
      toast('Profilo azzerato. Riavvio…');
      GL.sfx.play('err');
      setTimeout(() => location.reload(), 900);
    });
  }

  function enter() {
    const p = GL.prefs.get();
    const KINDS = { face: 'attivo · volto', biometric: 'attivo · volto o impronta', credential: 'attivo · codice del telefono', webauthn: 'attivo · volto o impronta' };
    const st = $('#set-face-state');
    const bio = p.lockBio && GL.face.bioPossible();
    st.textContent = bio ? (KINDS[p.lockKind] || 'attivo') : 'non attivo';
    st.className = bio ? 'good' : 'warn';
    $('#set-face-go').textContent = bio ? 'Rinnova lo sblocco con il volto' : 'Attiva lo sblocco con il volto';
    const pin = $('#set-pin-state');
    pin.textContent = p.pinHash ? 'impostato' : 'non impostato';
    pin.className = p.pinHash ? 'good' : 'warn';
    const detail = GL.ui.native?.bioDetail ? GL.ui.native.bioDetail() : `supporto: ${GL.face.platform()}`;
    $('#set-bio-detail').textContent = detail;
    $('#set-name').value = p.codename || '';
    setPressed([$('#set-intro-full'), $('#set-intro-short')], p.intro === 'short' ? $('#set-intro-short') : $('#set-intro-full'));
    renderStats();
  }

  GL.settings = { init, enter };
})();
