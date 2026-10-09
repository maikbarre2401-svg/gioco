window.GL = window.GL || {};

(() => {
  'use strict';

  // "GHOST": an original hooded hacker drawn on canvas. Visor scans, LED mouth follows the voice,
  // and the whole figure glitches with chromatic slices every few seconds.
  const C = { cyan: '#2ef2ff', magenta: '#ff2d75', bg: '#05070d', panel: '#0a111d', line: '#1b2c45' };

  function figure(g, w, h, t, s) {
    const cx = w / 2;
    // aura
    const aura = g.createRadialGradient(cx, h * 0.42, 0, cx, h * 0.42, w * 0.55);
    aura.addColorStop(0, 'rgba(46,242,255,0.20)');
    aura.addColorStop(1, 'rgba(46,242,255,0)');
    g.fillStyle = aura;
    g.fillRect(0, 0, w, h);

    // body + hood
    g.beginPath();
    g.moveTo(w * 0.02, h);
    g.bezierCurveTo(w * 0.05, h * 0.80, w * 0.18, h * 0.74, w * 0.26, h * 0.70);
    g.bezierCurveTo(w * 0.20, h * 0.52, w * 0.20, h * 0.10, cx, h * 0.07);
    g.bezierCurveTo(w * 0.80, h * 0.10, w * 0.80, h * 0.52, w * 0.74, h * 0.70);
    g.bezierCurveTo(w * 0.82, h * 0.74, w * 0.95, h * 0.80, w * 0.98, h);
    g.closePath();
    const cloth = g.createLinearGradient(0, 0, 0, h);
    cloth.addColorStop(0, '#111c2e');
    cloth.addColorStop(1, '#070b14');
    g.fillStyle = cloth;
    g.fill();
    g.lineWidth = Math.max(1.5, w * 0.008);
    g.strokeStyle = 'rgba(46,242,255,0.75)';
    g.save(); g.clip(); g.restore();
    g.stroke();

    // rim light on the right side in magenta
    g.beginPath();
    g.moveTo(cx + w * 0.02, h * 0.075);
    g.bezierCurveTo(w * 0.80, h * 0.10, w * 0.80, h * 0.52, w * 0.74, h * 0.70);
    g.strokeStyle = 'rgba(255,45,117,0.8)';
    g.stroke();

    // hood folds
    g.strokeStyle = 'rgba(0,0,0,0.55)';
    g.lineWidth = w * 0.012;
    g.beginPath();
    g.moveTo(w * 0.30, h * 0.66); g.quadraticCurveTo(w * 0.27, h * 0.40, w * 0.40, h * 0.17);
    g.moveTo(w * 0.70, h * 0.66); g.quadraticCurveTo(w * 0.73, h * 0.40, w * 0.60, h * 0.17);
    g.stroke();

    // face opening
    g.beginPath();
    g.ellipse(cx, h * 0.44, w * 0.165, h * 0.215, 0, 0, Math.PI * 2);
    g.fillStyle = '#000';
    g.fill();

    // faceplate
    g.beginPath();
    g.ellipse(cx, h * 0.47, w * 0.125, h * 0.17, 0, 0, Math.PI * 2);
    const plate = g.createLinearGradient(0, h * 0.3, 0, h * 0.64);
    plate.addColorStop(0, '#0d1626');
    plate.addColorStop(1, '#03050a');
    g.fillStyle = plate;
    g.fill();

    // visor with a scanning hot spot
    const vy = h * 0.405, vw = w * 0.21, vh = Math.max(4, h * 0.04);
    const vx = cx - vw / 2;
    g.shadowColor = C.cyan;
    g.shadowBlur = w * 0.06;
    g.fillStyle = 'rgba(46,242,255,0.85)';
    g.beginPath();
    g.moveTo(vx, vy); g.lineTo(vx + vw, vy); g.lineTo(vx + vw * 0.92, vy + vh); g.lineTo(vx + vw * 0.08, vy + vh); g.closePath();
    g.fill();
    g.shadowBlur = 0;
    const scan = vx + ((Math.sin(t / 650) + 1) / 2) * vw;
    const hot = g.createRadialGradient(scan, vy + vh / 2, 0, scan, vy + vh / 2, vw * 0.25);
    hot.addColorStop(0, 'rgba(255,255,255,0.95)');
    hot.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = hot;
    g.fillRect(vx, vy, vw, vh);
    // eye slits
    g.fillStyle = '#ffffff';
    const blink = (t % 4200) < 120 ? 0.2 : 1;
    [-1, 1].forEach(k => g.fillRect(cx + k * vw * 0.22 - vw * 0.09, vy + vh * 0.35, vw * 0.18, vh * 0.3 * blink));

    // LED mouth: 11×3 dot grid lit by the voice level
    const cols = 11, rows = 3, dot = Math.max(1.6, w * 0.011), gap = dot * 2.3;
    const mx = cx - ((cols - 1) * gap) / 2, my = h * 0.53;
    for (let c = 0; c < cols; c++) {
      const wave = s.mouth > 0.02 ? Math.abs(Math.sin(c * 0.9 + t / 60)) * s.mouth : 0;
      const lit = Math.round(wave * rows + (c === 5 ? 0.6 : 0.2));
      for (let r = 0; r < rows; r++) {
        const on = Math.abs(r - 1) < lit || (s.mouth <= 0.02 && r === 1);
        g.fillStyle = on ? (s.mouth > 0.02 ? C.magenta : 'rgba(255,45,117,0.55)') : 'rgba(255,255,255,0.06)';
        g.beginPath(); g.arc(mx + c * gap, my + (r - 1) * gap, dot, 0, Math.PI * 2); g.fill();
      }
    }

    // chest emblem: glitched G ring
    g.lineWidth = Math.max(1.5, w * 0.012);
    g.strokeStyle = C.cyan;
    g.beginPath(); g.arc(cx, h * 0.86, w * 0.05, Math.PI * 0.12, Math.PI * 1.78); g.stroke();
    g.beginPath(); g.moveTo(cx, h * 0.86); g.lineTo(cx + w * 0.05, h * 0.86); g.stroke();
  }

  function mount(canvas) {
    const off = document.createElement('canvas');
    const state = { mouth: 0, glitch: 0, running: true, raf: 0, nextGlitch: performance.now() + 2500 };
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

    function render(t) {
      const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
      const w = canvas.clientWidth || canvas.width, h = canvas.clientHeight || canvas.height;
      if (!w || !h) { state.raf = requestAnimationFrame(render); return; }
      const W = Math.round(w * dpr), H = Math.round(h * dpr);
      if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
      if (off.width !== W || off.height !== H) { off.width = W; off.height = H; }
      const og = off.getContext('2d');
      og.setTransform(dpr, 0, 0, dpr, 0, 0);
      og.clearRect(0, 0, w, h);
      figure(og, w, h, t, state);

      const g = canvas.getContext('2d');
      g.setTransform(1, 0, 0, 1, 0, 0);
      g.clearRect(0, 0, W, H);
      if (!reduce && t > state.nextGlitch) { state.glitch = 1; state.nextGlitch = t + 2500 + Math.random() * 4000; }
      if (state.glitch > 0.05) {
        const slices = 7;
        for (let i = 0; i < slices; i++) {
          const sy = Math.floor((H / slices) * i), sh = Math.ceil(H / slices);
          const dx = (Math.random() - 0.5) * W * 0.08 * state.glitch;
          g.drawImage(off, 0, sy, W, sh, dx, sy, W, sh);
        }
        g.globalCompositeOperation = 'lighter';
        g.globalAlpha = 0.35 * state.glitch;
        g.drawImage(off, -W * 0.015 * state.glitch, 0);
        g.globalAlpha = 1;
        g.globalCompositeOperation = 'source-over';
        state.glitch *= 0.82;
      } else {
        g.drawImage(off, 0, 0);
      }
      // scanlines
      g.fillStyle = 'rgba(0,0,0,0.22)';
      for (let y = 0; y < H; y += Math.round(3 * dpr)) g.fillRect(0, y, W, Math.max(1, Math.round(dpr)));
      if (state.running) state.raf = requestAnimationFrame(render);
    }
    state.raf = requestAnimationFrame(render);

    return {
      setMouth(v) { state.mouth = v; },
      glitch() { state.glitch = 1; },
      start() { if (!state.running) { state.running = true; state.raf = requestAnimationFrame(render); } },
      stop() { state.running = false; cancelAnimationFrame(state.raf); },
    };
  }

  GL.hacker = { mount };
})();
