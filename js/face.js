window.GL = window.GL || {};

(() => {
  'use strict';

  const { native, $, toast, log, haptic, sha256 } = GL.ui;

  // Face unlock. The actual face match is done by the phone's own secure unlock
  // (Android BiometricPrompt in the APK, WebAuthn platform authenticator in the browser):
  // the face template never reaches this app, and a photo of you cannot fool it.
  // The selfie captured during enrolment is only the agent avatar shown on the lock screen.
  let resolveGate = null;
  let pendingNative = null;
  let stream = null;
  let scanRaf = 0;

  const b64 = buf => btoa(String.fromCharCode(...new Uint8Array(buf)));
  const unb64 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));

  /* ---------------- platform capability ---------------- */
  function platform() {
    if (native && native.bioAvailable) return native.bioAvailable();     // 'face' | 'biometric' | 'none'
    if (window.PublicKeyCredential) return 'webauthn';
    return 'none';
  }

  function nativeAuth(title, subtitle) {
    return new Promise(res => {
      pendingNative = res;
      try { native.bioAuth(title, subtitle); } catch { pendingNative = null; res({ ok: false, msg: 'non disponibile' }); }
      setTimeout(() => { if (pendingNative) { pendingNative = null; res({ ok: false, msg: 'tempo scaduto' }); } }, 60000);
    });
  }
  // Called back from MainActivity once the system prompt closes.
  function _native(ok, msg) {
    const r = pendingNative; pendingNative = null;
    if (r) r({ ok: !!ok, msg: msg || '' });
  }

  async function webauthnEnroll() {
    const challenge = crypto.getRandomValues(new Uint8Array(32));
    const userId = crypto.getRandomValues(new Uint8Array(16));
    const cred = await navigator.credentials.create({
      publicKey: {
        challenge, rp: { name: 'Ghostlink' },
        user: { id: userId, name: GL.prefs.get().codename || 'agente', displayName: GL.prefs.get().codename || 'Agente' },
        pubKeyCredParams: [{ type: 'public-key', alg: -7 }, { type: 'public-key', alg: -257 }],
        authenticatorSelection: { authenticatorAttachment: 'platform', userVerification: 'required' },
        timeout: 60000, attestation: 'none',
      },
    });
    if (!cred) throw new Error('no-cred');
    return b64(cred.rawId);
  }

  async function webauthnAuth(credId) {
    const challenge = crypto.getRandomValues(new Uint8Array(32));
    const assertion = await navigator.credentials.get({
      publicKey: {
        challenge,
        allowCredentials: credId ? [{ type: 'public-key', id: unb64(credId) }] : [],
        userVerification: 'required', timeout: 60000,
      },
    });
    return !!assertion;
  }

  /* ---------------- camera preview + scan animation ---------------- */
  async function camera(on) {
    if (!on) {
      cancelAnimationFrame(scanRaf);
      stream?.getTracks().forEach(t => t.stop());
      stream = null;
      $('#lock-video').srcObject = null;
      return;
    }
    const res = await GL.ui.getCamera({ video: { facingMode: 'user' }, audio: false });
    if (!res.stream) { drawScan(); return; }   // the oval still animates; the PIN stays available
    stream = res.stream;
    const v = $('#lock-video');
    v.srcObject = stream;
    try { await v.play(); } catch { /* autoplay guard */ }
    v.hidden = false;
    drawScan();
  }

  let scanLast = 0;
  function drawScan(t) {
    scanRaf = requestAnimationFrame(drawScan);
    if (document.hidden || (t && t - scanLast < 50)) return;
    scanLast = t || 0;
    const canvas = $('#lock-overlay');
    const { ctx, w, h } = GL.ui.fitCanvas(canvas);
    ctx.clearRect(0, 0, w, h);
    const cx = w / 2, cy = h / 2, rx = w * 0.30, ry = h * 0.36;
    ctx.strokeStyle = 'rgba(46,242,255,0.8)';
    ctx.lineWidth = 2;
    ctx.setLineDash([10, 8]);
    ctx.beginPath(); ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2); ctx.stroke();
    ctx.setLineDash([]);
    const sy = cy - ry + (((t || 0) / 14) % (ry * 2));
    const g = ctx.createLinearGradient(0, sy - 26, 0, sy);
    g.addColorStop(0, 'rgba(46,242,255,0)');
    g.addColorStop(1, 'rgba(46,242,255,0.35)');
    ctx.save();
    ctx.beginPath(); ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2); ctx.clip();
    ctx.fillStyle = g; ctx.fillRect(cx - rx, sy - 26, rx * 2, 26);
    ctx.restore();
    // corner brackets
    ctx.strokeStyle = 'rgba(255,45,117,0.9)';
    const m = 12, L = 22;
    [[cx - rx - m, cy - ry - m, 1, 1], [cx + rx + m, cy - ry - m, -1, 1], [cx - rx - m, cy + ry + m, 1, -1], [cx + rx + m, cy + ry + m, -1, -1]]
      .forEach(([x, y, dx, dy]) => { ctx.beginPath(); ctx.moveTo(x, y + dy * L); ctx.lineTo(x, y); ctx.lineTo(x + dx * L, y); ctx.stroke(); });
  }

  // Grab a small square avatar from the preview (cosmetic only).
  function snapAvatar() {
    const v = $('#lock-video');
    if (!v.videoWidth) return null;
    const c = document.createElement('canvas');
    c.width = c.height = 160;
    const s = Math.min(v.videoWidth, v.videoHeight);
    const g = c.getContext('2d');
    g.translate(160, 0); g.scale(-1, 1);   // mirror, like a selfie
    g.drawImage(v, (v.videoWidth - s) / 2, (v.videoHeight - s) / 2, s, s, 0, 0, 160, 160);
    return c.toDataURL('image/jpeg', 0.7);
  }

  /* ---------------- flows ---------------- */
  const PANELS = { enroll: '#lock-enroll', unlock: '#lock-unlock', pin: '#lock-pinview' };
  function show(view) {
    Object.entries(PANELS).forEach(([v, sel]) => { $(sel).hidden = v !== view; });
  }

  async function enroll() {
    const btn = $('#lock-enroll-go');
    btn.disabled = true;
    btn.textContent = 'Registrazione…';
    const avatar = snapAvatar();
    const kind = platform();
    let ok = false, credId = null, msg = '';
    try {
      if (kind === 'webauthn') { credId = await webauthnEnroll(); ok = true; }
      else if (kind === 'face' || kind === 'biometric') {
        const r = await nativeAuth('Registra il tuo volto', 'Guarda la fotocamera per collegare il tuo volto a Ghostlink');
        ok = r.ok; msg = r.msg;
      } else msg = 'nessun sensore biometrico';
    } catch (e) { msg = e.name === 'NotAllowedError' ? 'registrazione annullata' : 'non riuscita'; }

    btn.disabled = false;
    btn.textContent = 'Registra il mio volto';
    if (!ok) {
      toast(`Registrazione non riuscita: ${msg}. Imposta un PIN di accesso.`, 4500);
      GL.sfx?.play('err');
      $('#lock-pin-title').textContent = 'Imposta un PIN di accesso';
      $('#lock-pin-go').textContent = 'Salva PIN';
      $('#lock-pin').dataset.mode = 'set';
      show('pin');
      return;
    }
    GL.prefs.set({ faceEnrolled: true, faceKind: kind, faceCred: credId, avatar });
    GL.sfx?.play('ok');
    haptic([20, 50, 20]);
    log('Volto registrato: accesso biometrico attivo', 'ok');
    toast('Volto registrato. Da ora entri con la tua faccia.');
    finish();
  }

  async function unlock() {
    const btn = $('#lock-unlock-go');
    btn.disabled = true;
    btn.textContent = 'Verifica…';
    const p = GL.prefs.get();
    let ok = false, msg = '';
    try {
      if (p.faceKind === 'webauthn') ok = await webauthnAuth(p.faceCred);
      else { const r = await nativeAuth('Sblocca Ghostlink', 'Guarda la fotocamera'); ok = r.ok; msg = r.msg; }
    } catch (e) { msg = e.name === 'NotAllowedError' ? 'annullato' : 'non riuscito'; }
    btn.disabled = false;
    btn.textContent = 'Sblocca con il volto';
    if (ok) {
      GL.sfx?.play('ok'); haptic([15, 40, 15]);
      log('Accesso biometrico riuscito', 'ok');
      finish();
    } else {
      GL.sfx?.play('err'); haptic([60, 40, 60]);
      $('#lock-unlock-msg').textContent = msg ? `Accesso negato: ${msg}` : 'Accesso negato';
    }
  }

  async function pinSubmit() {
    const input = $('#lock-pin');
    const val = input.value.trim();
    if (val.length < 4) { toast('Il PIN deve avere almeno 4 cifre'); return; }
    const p = GL.prefs.get();
    if (input.dataset.mode === 'set') {
      const salt = b64(crypto.getRandomValues(new Uint8Array(8)));
      GL.prefs.set({ pinHash: await sha256(salt + val), pinSalt: salt, faceEnrolled: true, faceKind: 'pin', avatar: snapAvatar() });
      GL.sfx?.play('ok');
      toast('PIN impostato');
      finish();
      return;
    }
    if (await sha256((p.pinSalt || '') + val) === p.pinHash) { GL.sfx?.play('ok'); finish(); }
    else { input.value = ''; GL.sfx?.play('err'); haptic([60, 40, 60]); $('#lock-pin-msg').textContent = 'PIN sbagliato'; }
  }

  function finish() {
    camera(false);
    const el = $('#lock');
    el.classList.add('done');
    setTimeout(() => el.remove(), 350);
    const r = resolveGate; resolveGate = null;
    if (r) r();
  }

  // Resolves when the user is through the lock; called by app start-up before the intro.
  function gate() {
    return new Promise(res => {
      const el = $('#lock');
      if (!el) { res(); return; }
      const p = GL.prefs.get();
      resolveGate = res;

      $('#lock-enroll-go').addEventListener('click', enroll);
      $('#lock-unlock-go').addEventListener('click', unlock);
      $('#lock-pin-go').addEventListener('click', pinSubmit);
      $('#lock-pin').addEventListener('keydown', e => { if (e.key === 'Enter') pinSubmit(); });
      const usePin = () => {
        $('#lock-pin-title').textContent = GL.prefs.get().pinHash ? 'Inserisci il PIN' : 'Imposta un PIN di accesso';
        $('#lock-pin').dataset.mode = GL.prefs.get().pinHash ? 'check' : 'set';
        $('#lock-pin-go').textContent = GL.prefs.get().pinHash ? 'Entra' : 'Salva PIN';
        show('pin');
      };
      $('#lock-use-pin').addEventListener('click', usePin);
      $('#lock-use-pin2').addEventListener('click', usePin);
      $('#lock-skip').addEventListener('click', () => {
        GL.prefs.set({ faceEnrolled: false, faceKind: 'none' });
        toast('Puoi attivare lo sblocco col volto dalle Impostazioni');
        finish();
      });

      if (!p.faceEnrolled) {
        show('enroll');
        $('#lock-kind').textContent = { face: 'volto', biometric: 'volto o impronta', webauthn: 'volto o impronta', none: 'non disponibile' }[platform()] || 'volto';
        camera(true);
      } else if (p.faceKind === 'pin') {
        $('#lock-pin-title').textContent = 'Inserisci il PIN';
        $('#lock-pin').dataset.mode = 'check';
        $('#lock-pin-go').textContent = 'Entra';
        show('pin');
      } else {
        show('unlock');
        if (p.avatar) { $('#lock-avatar').src = p.avatar; $('#lock-avatar').hidden = false; }
        $('#lock-unlock-who').textContent = p.codename || 'Agente';
        unlock();   // ask straight away, like the phone's own lock screen
      }
    });
  }

  // Re-run enrolment from Settings.
  async function reEnroll() {
    GL.prefs.set({ faceEnrolled: false, faceKind: 'none', faceCred: null });
    toast('Riavvio per registrare di nuovo il volto…');
    setTimeout(() => location.reload(), 900);
  }

  GL.face = { gate, reEnroll, platform, _native };
})();
