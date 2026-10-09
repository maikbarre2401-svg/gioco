window.GL = window.GL || {};

(() => {
  'use strict';

  const { $ } = GL.ui;
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const wait = ms => new Promise(r => setTimeout(r, ms));

  /* ---------------- data rain ---------------- */
  function rain(canvas) {
    const g = canvas.getContext('2d');
    const glyphs = '01ABCDEF0123456789アイウエオカキクケコ<>/$#';
    let cols = [], raf = 0, last = 0, w = 0, h = 0;
    const size = 14;
    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = canvas.clientWidth; h = canvas.clientHeight;
      canvas.width = w * dpr; canvas.height = h * dpr;
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      cols = Array.from({ length: Math.ceil(w / size) }, () => Math.random() * -h / size);
    }
    function frame(t) {
      raf = requestAnimationFrame(frame);
      if (t - last < 45) return;
      last = t;
      g.fillStyle = 'rgba(5,7,13,0.18)';
      g.fillRect(0, 0, w, h);
      g.font = `${size}px "JetBrains Mono", monospace`;
      cols.forEach((y, i) => {
        const ch = glyphs[Math.floor(Math.random() * glyphs.length)];
        g.fillStyle = Math.random() < 0.04 ? '#ff2d75' : (Math.random() < 0.15 ? '#c8fbff' : 'rgba(46,242,255,0.55)');
        g.fillText(ch, i * size, y * size);
        cols[i] = y * size > h && Math.random() > 0.975 ? 0 : y + 1;
      });
    }
    resize();
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }

  /* ---------------- sequence ---------------- */
  async function typeLines(pre, lines, skipped) {
    for (const [text, tail, cls] of lines) {
      if (skipped()) return;
      const line = document.createElement('div');
      pre.append(line);
      for (let i = 0; i < text.length; i += 2) {
        if (skipped()) return;
        line.textContent = text.slice(0, i + 2);
        if (i % 6 === 0) GL.sfx.play('type');
        await wait(14);
      }
      if (tail) {
        const s = document.createElement('span');
        s.className = cls || 'ok';
        s.textContent = tail;
        line.append(s);
        GL.sfx.play('blip');
      }
      await wait(110);
    }
  }

  function run(nodeId) {
    return new Promise(resolve => {
      const el = $('#intro');
      el.classList.add('js-on');
      const prefs = GL.prefs.get();
      let skipped = false;
      let finished = false;
      const stopRain = reduceMotion ? () => {} : rain($('#intro-rain'));
      const ghost = GL.hacker.mount($('#intro-hacker'));

      const finish = () => {
        if (finished) return;
        finished = true;
        el.classList.add('done');
        setTimeout(() => { stopRain(); ghost.stop(); el.remove(); resolve(); }, 500);
      };
      $('#intro-skip').addEventListener('click', () => { skipped = true; GL.sfx.unlock(); finish(); });

      async function sequence(firstTime) {
        $('#intro-login').hidden = true;
        $('#intro-tap').hidden = true;
        const name = GL.prefs.get().codename;
        GL.sfx.play('boot');
        ghost.glitch();
        const lines = GL.prefs.get().intro === 'short' ? [] : [
          ['GHOSTLINK OS 2.0 // kernel mobile', '', ''],
          ['> aggancio al nodo ', nodeId, 'hot'],
          ['> rete instradata su 3 proxy ...... ', 'OK'],
          ['> firewall locale ................. ', 'AGGIRATO'],
          ['> cifratura AES-256 ............... ', 'ATTIVA'],
          [`> identità ${name} `, 'VERIFICATA'],
        ];
        await typeLines($('#intro-lines'), lines, () => skipped);
        if (skipped) return;
        $('#intro-granted').hidden = false;
        GL.sfx.play('ok');
        ghost.glitch();
        GL.sfx.say(firstTime ? `Benvenuto, ${spoken(name)}. Accesso consentito.` : `Bentornato, ${spoken(name)}. Sistema online.`, v => ghost.setMouth(v));
        await wait(2200);
        finish();
      }

      if (reduceMotion && prefs.codename) { finish(); return; }

      if (!prefs.codename) {
        const form = $('#intro-login');
        const input = $('#intro-name');
        input.value = GL.prefs.randomCodename();
        form.hidden = false;
        $('#intro-dice').addEventListener('click', () => { input.value = GL.prefs.randomCodename(); GL.sfx.unlock().then(() => GL.sfx.play('glitch')); });
        form.addEventListener('submit', async e => {
          e.preventDefault();
          const codename = input.value.trim().toUpperCase().replace(/[^A-Z0-9À-Ù_-]/g, '').slice(0, 16) || GL.prefs.randomCodename();
          GL.prefs.set({ codename });
          await GL.sfx.unlock();
          sequence(true);
        });
        return;
      }

      GL.sfx.unlock().then(ok => {
        if (ok || !prefs.sound) { sequence(false); return; }
        const tap = $('#intro-tap');
        tap.hidden = false;
        tap.addEventListener('click', async () => { await GL.sfx.unlock(); sequence(false); }, { once: true });
      });
    });
  }

  // "SPETTRO-47" reads better aloud as "Spettro 47".
  function spoken(name) { return name.replace(/[-_]/g, ' ').toLowerCase().replace(/^\w/, c => c.toUpperCase()); }

  GL.intro = { run, spoken };
})();
