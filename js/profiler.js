window.GL = window.GL || {};

(() => {
  'use strict';

  const { $, toast, log, haptic, fitCanvas, COLORS } = GL.ui;

  // Everything here is invented on the spot, like the game's profiler: no real data about anyone.
  const NOMI = ['Giulia', 'Marco', 'Sara', 'Luca', 'Chiara', 'Davide', 'Elena', 'Matteo', 'Francesca', 'Alessio', 'Martina', 'Simone', 'Valentina', 'Paolo', 'Irene', 'Andrea', 'Federica', 'Stefano', 'Noemi', 'Riccardo'];
  const COGNOMI = ['Ferri', 'Conti', 'Gallo', 'Rinaldi', 'Moretti', 'Bruno', 'Marini', 'Greco', 'Lombardi', 'Barbieri', 'Fontana', 'Serra', 'Villa', 'Caruso', 'Testa', 'Pellegrini', 'Fabbri', 'Riva', 'Sala', 'Neri'];
  const LAVORI = [['Barista', 1.1], ['Infermiere', 1.6], ['Programmatore', 2.4], ['Architetto', 2.2], ['Studente', 0.3], ['Rider', 0.9], ['Insegnante', 1.5],
    ['Elettricista', 1.7], ['Grafico', 1.4], ['Cuoco', 1.4], ['Pensionato', 1.2], ['Commesso', 1.1], ['Ingegnere', 2.6], ['Fotografo', 1.3],
    ['Meccanico', 1.5], ['Youtuber', 0.8], ['Panettiere', 1.3], ['Avvocato', 2.8], ['Tatuatore', 1.6], ['DJ', 1.0], ['Veterinario', 2.1]];
  const CURIOSITA = ['Mette l\'ananas sulla pizza', 'Colleziona calamite da frigo', 'Ha un gatto di nome Biscotto', 'Canta sotto la doccia',
    'Ha corso una mezza maratona', 'Coltiva basilico sul balcone', 'Risolve il cubo di Rubik in 2 minuti', 'Ha 412 foto di tramonti nel telefono',
    'Ascolta solo musica anni \'80', 'Ha paura dei piccioni', 'Scrive la lista della spesa in ordine alfabetico', 'Fa il pane in casa ogni domenica',
    'Gioca a scacchi online ogni sera', 'Beve 4 caffè al giorno', 'Ha un canale di ricette con 37 iscritti', 'Conosce a memoria tutte le battute di un film',
    'Ha visto una serie intera in un weekend', 'Non ha mai perso un treno', 'Parla con le piante', 'Ha vinto una gara di torte nel 2019'];

  let stream = null, raf = 0, lockT = 0, locked = false, scanning = false;
  const pick = arr => arr[Math.floor(Math.random() * arr.length)];

  function profile() {
    const [job, k] = pick(LAVORI);
    const eta = job === 'Studente' ? 18 + Math.floor(Math.random() * 8) : job === 'Pensionato' ? 66 + Math.floor(Math.random() * 15) : 22 + Math.floor(Math.random() * 40);
    const income = Math.round((k * (18000 + Math.random() * 9000)) / 100) * 100;
    const facts = new Set();
    while (facts.size < 2) facts.add(pick(CURIOSITA));
    return { nome: `${pick(NOMI)} ${pick(COGNOMI)}`, eta, job, income, facts: [...facts], id: Math.floor(Math.random() * 1e8).toString(16).toUpperCase() };
  }

  function renderCard(p) {
    const card = $('#prf-card');
    card.replaceChildren();
    const add = (cls, text) => { const d = document.createElement('div'); d.className = cls; d.textContent = text; card.append(d); return d; };
    add('prf-tag', 'PROFILO FITTIZIO');
    add('prf-name', p.nome);
    add('prf-row', `${p.eta} anni · ${p.job}`);
    add('prf-row', `Reddito stimato: ${p.income.toLocaleString('it-IT')} €`);
    p.facts.forEach(f => add('prf-fact', `▸ ${f}`));
    add('prf-id', `ID ${p.id}`);
    card.hidden = false;
  }

  function draw(t) {
    const canvas = $('#prf-overlay');
    const { ctx, w, h } = fitCanvas(canvas);
    ctx.clearRect(0, 0, w, h);
    if (!stream) {
      // no camera: animated static so the HUD still has something to sit on
      for (let i = 0; i < 260; i++) {
        ctx.fillStyle = `rgba(46,242,255,${Math.random() * 0.12})`;
        ctx.fillRect(Math.random() * w, Math.random() * h, 2, 2);
      }
    }
    const cx = w / 2, cy = h / 2;
    // frame brackets
    ctx.strokeStyle = COLORS.cyan;
    ctx.lineWidth = 2;
    const m = 14, L = 26;
    [[m, m, 1, 1], [w - m, m, -1, 1], [m, h - m, 1, -1], [w - m, h - m, -1, -1]].forEach(([x, y, dx, dy]) => {
      ctx.beginPath(); ctx.moveTo(x, y + dy * L); ctx.lineTo(x, y); ctx.lineTo(x + dx * L, y); ctx.stroke();
    });
    // scan line
    const sy = ((t / 12) % h);
    const grad = ctx.createLinearGradient(0, sy - 30, 0, sy);
    grad.addColorStop(0, 'rgba(46,242,255,0)');
    grad.addColorStop(1, 'rgba(46,242,255,0.25)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, sy - 30, w, 30);
    // reticle: shrinks while locking, turns magenta when locked
    const k = scanning ? Math.min(1, (t - lockT) / 1200) : 0;
    const r = Math.min(w, h) * (0.28 - 0.12 * k);
    ctx.strokeStyle = locked ? COLORS.magenta : COLORS.cyan;
    ctx.lineWidth = 2;
    for (let i = 0; i < 4; i++) {
      const a0 = t / 900 + (i * Math.PI) / 2;
      ctx.beginPath(); ctx.arc(cx, cy, r, a0, a0 + Math.PI / 3.2); ctx.stroke();
    }
    ctx.beginPath(); ctx.arc(cx, cy, 3, 0, Math.PI * 2); ctx.fillStyle = ctx.strokeStyle; ctx.fill();
    ctx.font = '600 11px "JetBrains Mono", monospace';
    ctx.fillStyle = COLORS.cyan;
    ctx.fillText(locked ? 'BERSAGLIO AGGANCIATO' : scanning ? `ANALISI ${Math.round(k * 100)}%` : 'PROFILER PRONTO', 22, h - 22);
    ctx.textAlign = 'right';
    ctx.fillText(new Date().toLocaleTimeString('it-IT'), w - 22, h - 22);
    ctx.textAlign = 'left';
    raf = requestAnimationFrame(draw);
  }

  async function camera() {
    if (stream) { stopCamera(); return; }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
      const v = $('#prf-video');
      v.srcObject = stream;
      await v.play();
      $('#prf-cam').textContent = 'Spegni fotocamera';
      GL.sfx.play('nav');
      log('Profiler: fotocamera attiva', 'ok');
    } catch {
      stream = null;
      toast('Fotocamera non disponibile: il profiler funziona lo stesso', 3000);
    }
  }

  function stopCamera() {
    stream?.getTracks().forEach(t => t.stop());
    stream = null;
    $('#prf-video').srcObject = null;
    $('#prf-cam').textContent = 'Accendi fotocamera';
  }

  function scan() {
    if (scanning) return;
    scanning = true;
    locked = false;
    lockT = performance.now();
    $('#prf-card').hidden = true;
    $('#prf-scan').disabled = true;
    GL.sfx.play('lock');
    haptic(10);
    const beeps = setInterval(() => GL.sfx.play('blip'), 200);
    setTimeout(() => {
      clearInterval(beeps);
      locked = true;
      const p = profile();
      renderCard(p);
      GL.sfx.play('ok');
      haptic([15, 30, 15]);
      log(`Profilo generato: ${p.nome} (fittizio)`, 'warn');
      GL.app?.xp(5, 'profili');
      setTimeout(() => { scanning = false; $('#prf-scan').disabled = false; }, 400);
    }, 1300);
  }

  function init() {
    $('#prf-cam').addEventListener('click', camera);
    $('#prf-scan').addEventListener('click', scan);
  }

  function enter() { cancelAnimationFrame(raf); raf = requestAnimationFrame(draw); }
  function leave() { cancelAnimationFrame(raf); stopCamera(); scanning = false; locked = false; }

  GL.profiler = { init, enter, leave };
})();
