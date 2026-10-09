window.GL = window.GL || {};

(() => {
  'use strict';

  // Original synthesized sound design (no samples): sub drops, glitch bursts, data blips, voice.
  const native = window.GhostlinkNative || null;
  let ctx = null;
  let master = null;
  let echo = null;

  function prefs() { return GL.prefs ? GL.prefs.get() : { sound: true, voice: true }; }

  function ensure() {
    if (ctx) return ctx;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    ctx = new AC();
    master = ctx.createGain();
    master.gain.value = 0.55;
    // short feedback delay gives the "big room" feel of a HUD
    echo = ctx.createDelay(0.5);
    echo.delayTime.value = 0.13;
    const fb = ctx.createGain();
    fb.gain.value = 0.28;
    const wet = ctx.createGain();
    wet.gain.value = 0.35;
    echo.connect(fb).connect(echo);
    echo.connect(wet).connect(ctx.destination);
    master.connect(ctx.destination);
    master.connect(echo);
    return ctx;
  }

  // Resolves true when audio can actually play (after a tap in browsers; usually right away in the APK).
  async function unlock() {
    const c = ensure();
    if (!c) return false;
    try { if (c.state !== 'running') await c.resume(); } catch { /* blocked until a gesture */ }
    return c.state === 'running';
  }

  function ready() { return prefs().sound && ctx && ctx.state === 'running'; }

  function tone(type, f0, f1, start, dur, vol = 0.3, dest = master) {
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = type;
    o.frequency.setValueAtTime(f0, start);
    if (f1 !== f0) o.frequency.exponentialRampToValueAtTime(Math.max(f1, 1), start + dur);
    g.gain.setValueAtTime(0.0001, start);
    g.gain.exponentialRampToValueAtTime(vol, start + Math.min(0.012, dur / 4));
    g.gain.exponentialRampToValueAtTime(0.0001, start + dur);
    o.connect(g).connect(dest);
    o.start(start);
    o.stop(start + dur + 0.02);
  }

  let noiseBuf = null;
  function noise(start, dur, freq, q = 6, vol = 0.25, sweepTo = null) {
    if (!noiseBuf) {
      noiseBuf = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
      const d = noiseBuf.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    }
    const src = ctx.createBufferSource();
    src.buffer = noiseBuf;
    src.loop = true;
    const bp = ctx.createBiquadFilter();
    bp.type = 'bandpass';
    bp.Q.value = q;
    bp.frequency.setValueAtTime(freq, start);
    if (sweepTo) bp.frequency.exponentialRampToValueAtTime(sweepTo, start + dur);
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, start);
    g.gain.exponentialRampToValueAtTime(vol, start + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, start + dur);
    src.connect(bp).connect(g).connect(master);
    src.start(start, Math.random() * 0.5);
    src.stop(start + dur + 0.02);
  }

  const PENTA = [0, 3, 5, 7, 10, 12, 15, 17];
  const note = (base, i) => base * 2 ** (PENTA[i % PENTA.length] / 12);

  const sounds = {
    // Startup: sub drop, glitch bursts, data arpeggio, then a bright "access granted" chord.
    boot() {
      const t = ctx.currentTime + 0.05;
      tone('sine', 160, 38, t, 1.6, 0.6);
      tone('triangle', 80, 30, t, 1.4, 0.3);
      noise(t, 0.9, 200, 1.2, 0.18, 4000);
      for (let i = 0; i < 7; i++) noise(t + 0.35 + i * 0.09 + Math.random() * 0.04, 0.05, 800 + Math.random() * 5000, 9, 0.35);
      for (let i = 0; i < 18; i++) tone('square', note(440, (i * 5 + 3) % 8), note(440, (i * 5 + 3) % 8), t + 1.0 + i * 0.045, 0.04, 0.07);
      const end = t + 1.95;
      [220, 277.2, 329.6, 440].forEach((f, i) => tone('sawtooth', f, f * 1.003, end + i * 0.02, 1.4, 0.07));
      tone('sine', 1760, 1760, end, 1.6, 0.18);
      tone('sine', 2637, 2637, end + 0.08, 1.2, 0.08);
      noise(end, 0.5, 6000, 2, 0.08, 300);
    },
    tap() { const t = ctx.currentTime; tone('square', 1900, 1200, t, 0.03, 0.06); noise(t, 0.02, 5000, 4, 0.08); },
    nav() { const t = ctx.currentTime; noise(t, 0.22, 350, 3, 0.16, 3800); tone('sine', 300, 900, t, 0.16, 0.05); },
    type() { const t = ctx.currentTime; noise(t, 0.018, 2500 + Math.random() * 2500, 8, 0.12); },
    ok() { const t = ctx.currentTime; tone('square', 880, 880, t, 0.07, 0.07); tone('square', 1318, 1318, t + 0.08, 0.12, 0.07); tone('sine', 2637, 2637, t + 0.08, 0.3, 0.05); },
    err() { const t = ctx.currentTime; tone('sawtooth', 150, 120, t, 0.18, 0.16); tone('sawtooth', 150, 110, t + 0.2, 0.25, 0.16); },
    blip() { const t = ctx.currentTime; tone('sine', 1400 + Math.random() * 400, 1200, t, 0.06, 0.06); },
    glitch() {
      const t = ctx.currentTime;
      for (let i = 0; i < 5; i++) noise(t + i * 0.035, 0.03, 500 + Math.random() * 6000, 12, 0.25);
      tone('square', 90, 60, t, 0.15, 0.08);
    },
    // Map/network "hack" sequence: rising data stream that resolves on a high ping.
    hack() {
      const t = ctx.currentTime;
      for (let i = 0; i < 24; i++) tone('square', note(330, i), note(330, i), t + i * 0.035, 0.03, 0.05);
      noise(t, 0.9, 300, 2, 0.1, 7000);
      tone('sine', 1975, 1975, t + 0.9, 0.7, 0.16);
    },
    lock() { const t = ctx.currentTime; tone('triangle', 600, 1600, t, 0.25, 0.1); tone('sine', 3200, 3200, t + 0.25, 0.15, 0.06); },
    chirp() { const t = ctx.currentTime; tone('sine', 2400, 900, t, 0.08, 0.08); noise(t + 0.08, 0.12, 1800, 2, 0.06); },
  };

  function play(name) {
    try { if (ready() && sounds[name]) sounds[name](); } catch { /* audio graph failure: stay silent */ }
  }

  /* ---------------- voice ---------------- */
  let voice = null;
  function pickVoice() {
    if (!('speechSynthesis' in window)) return null;
    const list = speechSynthesis.getVoices();
    return list.find(v => /^it/i.test(v.lang) && /male|uomo|luca|cosimo|diego/i.test(v.name))
      || list.find(v => /^it/i.test(v.lang)) || null;
  }
  if ('speechSynthesis' in window) speechSynthesis.onvoiceschanged = () => { voice = pickVoice(); };

  // Calls onLevel(0..1) while speaking so the hacker's mouth can move.
  function say(text, onLevel) {
    if (!prefs().voice) return;
    play('chirp');
    let raf = 0;
    const start = performance.now();
    const animate = done => {
      if (!onLevel) return;
      const tick = () => {
        const t = (performance.now() - start) / 1000;
        onLevel(done() ? 0 : Math.abs(Math.sin(t * 17) * Math.sin(t * 5.3)) * 0.9 + 0.1);
        if (!done()) raf = requestAnimationFrame(tick); else onLevel(0);
      };
      raf = requestAnimationFrame(tick);
    };
    if (native?.speak) {
      native.speak(text);
      const ms = 450 + text.length * 70;
      animate(() => performance.now() - start > ms);
      return;
    }
    if (!('speechSynthesis' in window)) return;
    try {
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = 'it-IT';
      u.voice = voice || pickVoice();
      u.pitch = 0.45;
      u.rate = 0.95;
      let speaking = true;
      u.onend = u.onerror = () => { speaking = false; };
      setTimeout(() => speechSynthesis.speak(u), 120);
      animate(() => !speaking && performance.now() - start > 800);
    } catch { cancelAnimationFrame(raf); }
  }

  GL.sfx = { unlock, play, say, ready: () => !!ctx && ctx.state === 'running' };
})();
