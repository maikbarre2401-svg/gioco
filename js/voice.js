window.GL = window.GL || {};

(() => {
  'use strict';

  const { $, $$, toast, log, haptic, setPressed, fitCanvas, COLORS } = GL.ui;
  let ctx = null, stream = null, source = null, analyser = null, raf = 0;
  let effectNode = null, recorder = null, chunks = [], recURL = null;
  let mode = 'robot';
  let dataArr = null;

  // Each effect builds a small Web Audio graph from the mic to the speakers.
  const EFFECTS = {
    robot: 'Robot', grave: 'Grave', acuto: 'Acuto', eco: 'Eco', radio: 'Radio', alieno: 'Alieno',
  };

  function buildGraph() {
    // disconnect old
    if (effectNode) { try { source.disconnect(); } catch {} }
    const dest = ctx.createGain();
    dest.gain.value = 1;
    dest.connect(analyser);
    analyser.connect(ctx.destination);
    recDest && dest.connect(recDest);

    if (mode === 'robot') {
      // ring modulation with a 50 Hz carrier
      const osc = ctx.createOscillator(); osc.frequency.value = 50; osc.type = 'square';
      const ring = ctx.createGain(); ring.gain.value = 0;
      osc.connect(ring.gain); osc.start();
      source.connect(ring); ring.connect(dest);
    } else if (mode === 'grave' || mode === 'acuto' || mode === 'alieno') {
      // pitch shift via granular delay modulation
      const shift = mode === 'grave' ? -5 : mode === 'acuto' ? 6 : 9;
      pitchShift(source, dest, shift);
    } else if (mode === 'eco') {
      const delay = ctx.createDelay(1.0); delay.delayTime.value = 0.22;
      const fb = ctx.createGain(); fb.gain.value = 0.45;
      delay.connect(fb); fb.connect(delay);
      source.connect(dest); source.connect(delay); delay.connect(dest);
    } else if (mode === 'radio') {
      const bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = 1600; bp.Q.value = 4;
      const dist = ctx.createWaveShaper(); dist.curve = distortionCurve(30);
      source.connect(bp); bp.connect(dist); dist.connect(dest);
    } else {
      source.connect(dest);
    }
  }

  // Simple two-delay pitch shifter (overlap-add), semitones in.
  function pitchShift(input, output, semitones) {
    const rate = Math.pow(2, semitones / 12);
    const bufSize = 1024;
    const node = ctx.createScriptProcessor ? ctx.createScriptProcessor(bufSize, 1, 1) : null;
    if (!node) { input.connect(output); return; }
    let readA = 0, readB = bufSize / 2;
    const ring = new Float32Array(bufSize * 4);
    let writePos = 0;
    node.onaudioprocess = e => {
      const inp = e.inputBuffer.getChannelData(0);
      const out = e.outputBuffer.getChannelData(0);
      for (let i = 0; i < inp.length; i++) { ring[writePos] = inp[i]; writePos = (writePos + 1) % ring.length; }
      for (let i = 0; i < out.length; i++) {
        const ia = Math.floor(readA) % ring.length;
        const ib = Math.floor(readB) % ring.length;
        const fade = Math.abs(((readA % bufSize) / bufSize) - 0.5) * 2;
        out[i] = ring[ia] * (1 - fade) + ring[ib] * fade;
        readA = (readA + rate); readB = (readB + rate);
        if (readA >= ring.length) readA -= ring.length;
        if (readB >= ring.length) readB -= ring.length;
      }
    };
    input.connect(node); node.connect(output);
    effectNode = node;
  }

  function distortionCurve(amount) {
    const n = 44100, curve = new Float32Array(n), deg = Math.PI / 180;
    for (let i = 0; i < n; i++) { const x = (i * 2) / n - 1; curve[i] = ((3 + amount) * x * 20 * deg) / (Math.PI + amount * Math.abs(x)); }
    return curve;
  }

  let recDest = null;

  async function start() {
    if (stream) { stop(); return; }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false } });
    } catch { toast('Microfono non disponibile'); return; }
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    source = ctx.createMediaStreamSource(stream);
    analyser = ctx.createAnalyser(); analyser.fftSize = 1024;
    dataArr = new Uint8Array(analyser.fftSize);
    recDest = ctx.createMediaStreamDestination();
    buildGraph();
    $('#voice-start').textContent = 'Spegni';
    $('#voice-rec').disabled = false;
    GL.sfx.play('nav');
    log('Cambia voce attivo', 'ok');
    GL.app?.xp(4, 'voce');
    cancelAnimationFrame(raf); drawWave();
  }

  function stop() {
    cancelAnimationFrame(raf);
    if (recorder && recorder.state === 'recording') recorder.stop();
    stream?.getTracks().forEach(t => t.stop());
    ctx?.close();
    stream = null; ctx = null; source = null; effectNode = null;
    $('#voice-start').textContent = 'Accendi microfono';
    $('#voice-rec').disabled = true;
    $('#voice-rec').textContent = 'Registra';
  }

  function drawWave() {
    const { ctx: g, w, h } = fitCanvas($('#voice-wave'));
    g.clearRect(0, 0, w, h);
    if (analyser) {
      analyser.getByteTimeDomainData(dataArr);
      g.strokeStyle = COLORS.cyan; g.lineWidth = 2; g.beginPath();
      for (let i = 0; i < dataArr.length; i++) {
        const x = (i / dataArr.length) * w;
        const y = (dataArr[i] / 255) * h;
        i ? g.lineTo(x, y) : g.moveTo(x, y);
      }
      g.stroke();
    }
    raf = requestAnimationFrame(drawWave);
  }

  function record() {
    if (!recDest) return;
    if (recorder && recorder.state === 'recording') { recorder.stop(); return; }
    chunks = [];
    try { recorder = new MediaRecorder(recDest.stream); } catch { toast('Registrazione non supportata'); return; }
    recorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
    recorder.onstop = () => {
      const blob = new Blob(chunks, { type: chunks[0]?.type || 'audio/webm' });
      if (recURL) URL.revokeObjectURL(recURL);
      recURL = URL.createObjectURL(blob);
      const audio = $('#voice-playback');
      audio.src = recURL; audio.hidden = false;
      $('#voice-rec').textContent = 'Registra';
      GL.sfx.play('ok'); haptic(15);
      log('Registrazione con voce modificata pronta', 'ok');
    };
    recorder.start();
    $('#voice-rec').textContent = '■ Ferma';
    GL.sfx.play('blip');
  }

  function init() {
    $('#voice-start').addEventListener('click', start);
    $('#voice-rec').addEventListener('click', record);
    const box = $('#voice-modes');
    box.replaceChildren(...Object.entries(EFFECTS).map(([k, label]) => {
      const b = document.createElement('button');
      b.type = 'button'; b.textContent = label; b.className = 'chip-btn'; b.dataset.m = k;
      b.setAttribute('aria-pressed', String(k === mode));
      b.addEventListener('click', () => {
        mode = k; setPressed($$('#voice-modes button'), b); GL.sfx.play('tap');
        if (ctx && source) { try { source.disconnect(); } catch {} if (effectNode) { try { effectNode.disconnect(); } catch {} effectNode = null; } buildGraph(); }
      });
      return b;
    }));
  }

  function leave() { stop(); }

  GL.voice = { init, leave };
})();
