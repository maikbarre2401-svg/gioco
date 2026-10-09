window.GL = window.GL || {};

(() => {
  'use strict';

  const { $, toast, haptic, sha256, copyText } = GL.ui;
  let history = [];
  let histIdx = -1;
  let matrixRaf = 0;
  const enc = new TextEncoder();

  function out(text, cls = '') {
    const box = $('#term-out');
    const line = document.createElement('div');
    if (cls) line.className = cls;
    line.textContent = text;
    box.append(line);
    box.scrollTop = box.scrollHeight;
    return line;
  }

  function echo(cmd) {
    const line = document.createElement('div');
    line.className = 'term-echo';
    const p = document.createElement('span'); p.className = 'term-prompt'; p.textContent = promptText();
    const c = document.createElement('span'); c.textContent = ' ' + cmd;
    line.append(p, c);
    $('#term-out').append(line);
  }

  function promptText() {
    const name = (GL.prefs.get().codename || 'ghost').toLowerCase();
    return `${name}@nodo:~$`;
  }

  async function typeOut(lines, delay = 24) {
    for (const l of lines) { out(l, 'term-type'); GL.sfx.play('type'); await new Promise(r => setTimeout(r, delay)); }
  }

  const b64 = s => btoa(unescape(encodeURIComponent(s)));
  const unb64 = s => decodeURIComponent(escape(atob(s)));

  const COMMANDS = {
    help() {
      out('Comandi disponibili:', 'ok');
      out('  help, clear, whoami, date, ip, ping <host>, speed');
      out('  hash <testo>, base64 <testo>, debase64 <testo>');
      out('  bin <testo>, morse <testo>, leet <testo>, rev <testo>');
      out('  roll [facce], coin, color, matrix, hack, sudo, exit');
    },
    clear() { $('#term-out').replaceChildren(); },
    whoami() {
      const p = GL.prefs.get(); const l = GL.prefs.level();
      out(`${p.codename || 'ospite'} · ${l.rank} (livello ${l.lvl})`, 'ok');
    },
    date() { out(new Date().toLocaleString('it-IT')); },
    async ip() {
      out('risoluzione IP pubblico…');
      try {
        const d = await (await fetch('https://ipapi.co/json/', { cache: 'no-store' })).json();
        out(`IP:        ${d.ip}`, 'ok');
        out(`posizione: ${[d.city, d.region, d.country_name].filter(Boolean).join(', ')}`);
        out(`operatore: ${d.org || '?'}`);
      } catch { out('impossibile raggiungere il servizio', 'err'); }
    },
    async ping(host) {
      if (!host) return out('uso: ping <host>  (es. ping cloudflare.com)', 'err');
      const url = /^https?:\/\//.test(host) ? host : `https://${host}`;
      out(`PING ${host}`);
      for (let i = 0; i < 4; i++) {
        const t0 = performance.now();
        try {
          await fetch(url, { mode: 'no-cors', cache: 'no-store' });
          out(`risposta da ${host}: tempo=${Math.round(performance.now() - t0)} ms`);
        } catch { out(`${host}: nessuna risposta`, 'err'); }
        GL.sfx.play('blip');
        await new Promise(r => setTimeout(r, 300));
      }
    },
    speed() { out('apro il test di velocità…', 'ok'); location.hash = 'velocita'; },
    async hash(...a) {
      const t = a.join(' '); if (!t) return out('uso: hash <testo>', 'err');
      out(`SHA-256: ${await sha256(t)}`, 'ok');
    },
    base64(...a) { const t = a.join(' '); if (!t) return out('uso: base64 <testo>', 'err'); out(b64(t), 'ok'); },
    debase64(...a) { try { out(unb64(a.join(' ')), 'ok'); } catch { out('non è base64 valido', 'err'); } },
    bin(...a) { const t = a.join(' '); if (!t) return out('uso: bin <testo>', 'err'); out([...enc.encode(t)].map(b => b.toString(2).padStart(8, '0')).join(' '), 'ok'); },
    morse(...a) {
      const M = { A: '.-', B: '-...', C: '-.-.', D: '-..', E: '.', F: '..-.', G: '--.', H: '....', I: '..', J: '.---', K: '-.-', L: '.-..', M: '--', N: '-.', O: '---', P: '.--.', Q: '--.-', R: '.-.', S: '...', T: '-', U: '..-', V: '...-', W: '.--', X: '-..-', Y: '-.--', Z: '--..', 0: '-----', 1: '.----', 2: '..---', 3: '...--', 4: '....-', 5: '.....', 6: '-....', 7: '--...', 8: '---..', 9: '----.' };
      out(a.join(' ').toUpperCase().split('').map(c => c === ' ' ? '/' : (M[c] || '')).join(' ').trim() || '—', 'ok');
    },
    leet(...a) { const m = { a: '4', e: '3', i: '1', o: '0', s: '5', t: '7', b: '8', g: '9' }; out(a.join(' ').toLowerCase().replace(/[aeiostbg]/g, c => m[c]), 'ok'); },
    rev(...a) { out([...a.join(' ')].reverse().join(''), 'ok'); },
    roll(f) { const faces = Math.max(2, parseInt(f) || 6); out(`🎲 ${1 + Math.floor(Math.random() * faces)} (d${faces})`, 'ok'); GL.sfx.play('ok'); },
    coin() { out(Math.random() < 0.5 ? '🪙 Testa' : '🪙 Croce', 'ok'); GL.sfx.play('ok'); },
    color() { const h = '#' + Array.from(crypto.getRandomValues(new Uint8Array(3))).map(b => b.toString(16).padStart(2, '0')).join(''); const l = out(`${h.toUpperCase()}  ████`, 'ok'); l.style.color = h; },
    matrix() { startMatrix(); },
    async hack() {
      const steps = ['bypass firewall perimetrale', 'brute force credenziali admin', 'escalation privilegi root', 'esfiltrazione dati', 'pulizia dei log'];
      GL.sfx.play('hack');
      for (const s of steps) { await typeOut([`[*] ${s}…`], 90); out('    [OK]', 'ok'); haptic(8); }
      out('ACCESSO OTTENUTO — scherzo, è tutto finto 😎', 'hot');
      GL.sfx.play('ok');
    },
    sudo(...a) { out(`${GL.prefs.get().codename || 'utente'} non è nel file sudoers. Questo episodio verrà segnalato. 👀`, 'err'); GL.sfx.play('err'); },
    exit() { out('disconnessione…'); setTimeout(() => { location.hash = 'home'; }, 400); },
  };
  const ALIASES = { cls: 'clear', ls: 'help', man: 'help', '?': 'help', b64: 'base64' };

  async function exec(raw) {
    const cmd = raw.trim();
    if (!cmd) return;
    echo(cmd);
    history.unshift(cmd); if (history.length > 40) history.pop();
    histIdx = -1;
    const [nameRaw, ...args] = cmd.split(/\s+/);
    const name = ALIASES[nameRaw.toLowerCase()] || nameRaw.toLowerCase();
    const fn = COMMANDS[name];
    if (!fn) { out(`comando non trovato: ${nameRaw}. Scrivi "help".`, 'err'); GL.sfx.play('err'); return; }
    try { await fn(...args); } catch { out('errore durante l\'esecuzione', 'err'); }
    GL.app?.xp(2, 'comandi');
  }

  function startMatrix() {
    const box = $('#term-out');
    box.replaceChildren();
    const pre = document.createElement('pre');
    pre.className = 'matrix';
    box.append(pre);
    const cols = 34, rows = 16;
    const glyphs = '01ｱｲｳｴｵｶｷｸ日ﾊﾋﾎ<>/#$@';
    const drops = Array.from({ length: cols }, () => Math.floor(Math.random() * rows));
    let ticks = 0;
    cancelAnimationFrame(matrixRaf);
    const grid = Array.from({ length: rows }, () => Array(cols).fill(' '));
    const loop = () => {
      for (let c = 0; c < cols; c++) {
        const r = drops[c];
        if (r < rows) grid[r][c] = glyphs[Math.floor(Math.random() * glyphs.length)];
        drops[c] = r + 1 > rows + Math.random() * 6 ? 0 : r + 1;
      }
      // fade older rows by shifting up occasionally
      pre.textContent = grid.map(row => row.join('')).join('\n');
      for (let c = 0; c < cols; c++) if (Math.random() < 0.3) grid[(drops[c] - 2 + rows) % rows][c] = ' ';
      if (ticks++ < 90) matrixRaf = requestAnimationFrame(loop);
      else { out('', ''); out('…fine della simulazione. Scrivi "help".', 'ok'); }
    };
    matrixRaf = requestAnimationFrame(loop);
  }

  const QUICK = ['help', 'ip', 'hack', 'matrix', 'coin', 'color', 'clear'];

  function init() {
    $('#term-prompt').textContent = promptText();
    $('#term-form').addEventListener('submit', e => {
      e.preventDefault();
      const input = $('#term-in');
      exec(input.value);
      input.value = '';
    });
    $('#term-in').addEventListener('keydown', e => {
      if (e.key === 'ArrowUp') { e.preventDefault(); if (histIdx < history.length - 1) $('#term-in').value = history[++histIdx]; }
      else if (e.key === 'ArrowDown') { e.preventDefault(); histIdx = Math.max(-1, histIdx - 1); $('#term-in').value = histIdx < 0 ? '' : history[histIdx]; }
      else GL.sfx.play('type');
    });
    $('#term-keys').replaceChildren(...QUICK.map(c => {
      const b = document.createElement('button');
      b.type = 'button'; b.textContent = c;
      b.addEventListener('click', () => { cancelAnimationFrame(matrixRaf); exec(c); $('#term-in').focus(); });
      return b;
    }));
  }

  let greeted = false;
  function enter() {
    $('#term-prompt').textContent = promptText();
    if (!greeted) {
      greeted = true;
      out('GHOSTLINK SHELL 2.0 — accesso riuscito.', 'ok');
      out('Scrivi "help" per i comandi, o tocca i pulsanti qui sotto.');
    }
    setTimeout(() => $('#term-in').focus(), 120);
  }
  function leave() { cancelAnimationFrame(matrixRaf); }

  GL.terminal = { init, enter, leave };
})();
