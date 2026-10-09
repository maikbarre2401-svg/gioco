window.GL = window.GL || {};

(() => {
  'use strict';

  const { $, toast, log, haptic, fitCanvas, fmt, COLORS } = GL.ui;

  // Rough offset from dBFS to dB SPL for a typical phone mic. Uncalibrated: good for comparisons only.
  const SPL_OFFSET = 95;
  const SCALE = [
    [30, 'Silenzio quasi assoluto'],
    [45, 'Stanza tranquilla'],
    [60, 'Conversazione normale'],
    [75, 'Ristorante affollato'],
    [90, 'Traffico intenso'],
    [105, 'Concerto o discoteca'],
    [Infinity, 'Soglia del dolore'],
  ];

  let ctx = null, stream = null, analyser = null, raf = 0;
  let timeBuf, freqBuf;
  let peak = 0, sum = 0, count = 0, shown = 0, lastText = 0;

  function levelLabel(db) { return SCALE.find(([max]) => db < max)[1]; }

  function frame(t) {
    analyser.getFloatTimeDomainData(timeBuf);
    let sq = 0;
    for (let i = 0; i < timeBuf.length; i++) sq += timeBuf[i] * timeBuf[i];
    const rms = Math.sqrt(sq / timeBuf.length);
    const db = Math.max(20, Math.min(130, 20 * Math.log10(rms || 1e-7) + SPL_OFFSET));
    shown += (db - shown) * 0.25;
    peak = Math.max(peak, db);
    sum += db; count++;

    $('#aud-bar').style.width = `${Math.min(100, ((shown - 20) / 100) * 100)}%`;
    const dominant = drawSpectrum();
    if (t - lastText > 150) {
      lastText = t;
      $('#aud-db').textContent = Math.round(shown);
      $('#aud-label').textContent = levelLabel(shown);
      $('#aud-peak').textContent = `${Math.round(peak)} dB`;
      $('#aud-avg').textContent = `${Math.round(sum / count)} dB`;
      $('#aud-freq').textContent = dominant ? `${fmt.num(dominant, 0)} Hz` : '—';
    }
    raf = requestAnimationFrame(frame);
  }

  function drawSpectrum() {
    analyser.getByteFrequencyData(freqBuf);
    const { ctx: g, w, h } = fitCanvas($('#spectrum'));
    g.clearRect(0, 0, w, h);
    g.strokeStyle = COLORS.line;
    g.lineWidth = 1;
    for (let i = 1; i < 4; i++) { g.beginPath(); g.moveTo(0, (h * i) / 4); g.lineTo(w, (h * i) / 4); g.stroke(); }

    const bars = 48;
    const nyquist = ctx.sampleRate / 2;
    const minF = 40, maxF = Math.min(16000, nyquist);
    const gap = 2;
    const bw = (w - gap * (bars - 1)) / bars;
    const grad = g.createLinearGradient(0, h, 0, 0);
    grad.addColorStop(0, COLORS.cyan);
    grad.addColorStop(0.7, COLORS.amber);
    grad.addColorStop(1, COLORS.magenta);
    g.fillStyle = grad;

    let maxVal = 0, maxBin = 0;
    for (let i = 0; i < freqBuf.length; i++) if (freqBuf[i] > maxVal) { maxVal = freqBuf[i]; maxBin = i; }

    for (let b = 0; b < bars; b++) {
      // logarithmic frequency bands, like a real analyzer
      const f0 = minF * (maxF / minF) ** (b / bars);
      const f1 = minF * (maxF / minF) ** ((b + 1) / bars);
      const i0 = Math.floor((f0 / nyquist) * freqBuf.length);
      const i1 = Math.max(i0 + 1, Math.floor((f1 / nyquist) * freqBuf.length));
      let v = 0;
      for (let i = i0; i < i1; i++) v = Math.max(v, freqBuf[i]);
      const bh = (v / 255) * (h - 4);
      g.fillRect(b * (bw + gap), h - bh, bw, bh);
    }
    return maxVal > 120 ? (maxBin * nyquist) / freqBuf.length : null;
  }

  async function start() {
    if (!navigator.mediaDevices?.getUserMedia) { toast('Microfono non disponibile su questo browser'); return; }
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      });
    } catch {
      toast('Permesso microfono negato: abilitalo nelle impostazioni del browser', 3500);
      log('Accesso al microfono negato', 'hot');
      return;
    }
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    analyser = ctx.createAnalyser();
    analyser.fftSize = 4096;
    analyser.smoothingTimeConstant = 0.6;
    ctx.createMediaStreamSource(stream).connect(analyser);
    timeBuf = new Float32Array(analyser.fftSize);
    freqBuf = new Uint8Array(analyser.frequencyBinCount);
    peak = 0; sum = 0; count = 0; shown = 40;
    const btn = $('#aud-start');
    btn.textContent = 'Spegni microfono';
    btn.classList.add('danger');
    log('Microfono in ascolto', 'warn');
    haptic(15);
    raf = requestAnimationFrame(frame);
  }

  function stop() {
    cancelAnimationFrame(raf);
    stream?.getTracks().forEach(t => t.stop());
    ctx?.close();
    if (stream) log('Microfono spento');
    stream = null; ctx = null; analyser = null;
    const btn = $('#aud-start');
    btn.textContent = 'Accendi microfono';
    btn.classList.remove('danger');
    $('#aud-label').textContent = 'In attesa';
  }

  function init() {
    $('#aud-start').addEventListener('click', () => (stream ? stop() : start()));
  }

  function leave() { stop(); }

  GL.audio = { init, leave };
})();
