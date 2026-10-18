window.GL = window.GL || {};

(() => {
  'use strict';

  const { native, $, toast, log, haptic, sha256 } = GL.ui;

  // Face unlock. The face match itself is done by the phone's own secure unlock
  // (Android BiometricPrompt in the APK, WebAuthn platform authenticator in the browser), so the
  // face template never reaches this app and a photo cannot pass. The selfie taken during
  // enrolment is only the lock-screen avatar.
  //
  // State lives in prefs: lockSetup (enrolment finished), lockBio (face/fingerprint registered),
  // lockKind, faceCred (WebAuthn id), pinHash/pinSalt (backup code). Both ways can coexist and
  // the lock screen always offers whichever ones exist, plus a way to add the missing one.
  let resolveGate = null;
  let pendingNative = null;
  let stream = null;
  let scanRaf = 0;

  const b64 = buf => btoa(String.fromCharCode(...new Uint8Array(buf)));
  const unb64 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));

  /* ---------------- platform ---------------- */
  function platform() {
    if (native && native.bioAvailable) return native.bioAvailable();   // face | biometric | credential | none
    if (window.PublicKeyCredential) return 'webauthn';
    return 'none';
  }
  const bioPossible = () => platform() !== 'none';

  function nativeAuth(title, subtitle) {
    return new Promise(res => {
      pendingNative = res;
      try { native.bioAuth(title, subtitle); } catch { pendingNative = null; res({ ok: false, msg: 'non disponibile' }); }
      setTimeout(() => { if (pendingNative) { pendingNative = null; res({ ok: false, msg: 'tempo scaduto' }); } }, 60000);
    });
  }
  function _native(ok, msg) {
    const r = pendingNative; pendingNative = null;
    if (r) r({ ok: !!ok, msg: msg || '' });
  }

  async function webauthnEnroll() {
    const challenge = crypto.getRandomValues(new Uint8Array(32));
    const userId = crypto.getRandomValues(new Uint8Array(16));
    const name = GL.prefs.get().codename || 'agente';
    const cred = await navigator.credentials.create({
      publicKey: {
        challenge, rp: { name: 'Ghostlink' },
        user: { id: userId, name, displayName: name },
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

  /* ---------------- camera preview ---------------- */
  async function camera(on) {
    if (!on) {
      cancelAnimationFrame(scanRaf);
      stream?.getTracks().forEach(t => t.stop());
      stream = null;
      const v = $('#lock-video');
      v.srcObject = null; v.hidden = true;
      return;
    }
    const res = await GL.ui.getCamera({ video: { facingMode: 'user' }, audio: false });
    if (!res.stream) { drawScan(); return; }   // the oval still animates; the code still works
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
    if (!canvas) return;
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
    ctx.strokeStyle = 'rgba(255,45,117,0.9)';
    const m = 12, L = 22;
    [[cx - rx - m, cy - ry - m, 1, 1], [cx + rx + m, cy - ry - m, -1, 1], [cx - rx - m, cy + ry + m, 1, -1], [cx + rx + m, cy + ry + m, -1, -1]]
      .forEach(([x, y, dx, dy]) => { ctx.beginPath(); ctx.moveTo(x, y + dy * L); ctx.lineTo(x, y); ctx.lineTo(x + dx * L, y); ctx.stroke(); });
  }

  function snapAvatar() {
    const v = $('#lock-video');
    if (!v || !v.videoWidth) return null;
    const c = document.createElement('canvas');
    c.width = c.height = 160;
    const s = Math.min(v.videoWidth, v.videoHeight);
    const g = c.getContext('2d');
    g.translate(160, 0); g.scale(-1, 1);
    g.drawImage(v, (v.videoWidth - s) / 2, (v.videoHeight - s) / 2, s, s, 0, 0, 160, 160);
    return c.toDataURL('image/jpeg', 0.7);
  }

  /* ---------------- panels ---------------- */
  const PANELS = { enroll: '#lock-enroll', setpin: '#lock-setpin', unlock: '#lock-unlock', pin: '#lock-pinview' };
  function show(view) {
    Object.entries(PANELS).forEach(([v, sel]) => { const el = $(sel); if (el) el.hidden = v !== view; });
  }

  const KIND_LABEL = {
    face: 'volto', biometric: 'impronta o volto', credential: 'codice del telefono',
    webauthn: 'volto o impronta', none: 'non disponibile',
  };

  /* ---------------- enrolment ---------------- */
  async function registerFace() {
    const btn = $('#lock-enroll-go');
    btn.disabled = true;
    btn.textContent = 'Verifica in corso…';
    const avatar = snapAvatar();
    const kind = platform();
    let ok = false, credId = null, msg = '';
    try {
      if (kind === 'webauthn') { credId = await webauthnEnroll(); ok = true; }
      else if (kind !== 'none') {
        const r = await nativeAuth('Registra il tuo volto', 'Usa il volto o l\'impronta per collegare questo accesso');
        ok = r.ok; msg = r.msg;
      } else msg = 'nessun sensore disponibile';
    } catch (e) { msg = e.name === 'NotAllowedError' ? 'annullato' : 'non riuscita'; }
    btn.disabled = false;
    btn.textContent = 'Registra il mio volto';

    if (ok) {
      GL.prefs.set({ lockBio: true, lockKind: kind, faceCred: credId, avatar });
      GL.sfx?.play('ok'); haptic([20, 50, 20]);
      log('Volto registrato', 'ok');
      toast('Volto registrato. Ora imposta un codice di riserva.');
      goSetPin(true);
    } else {
      GL.sfx?.play('err');
      toast(`Volto non registrato: ${msg}. Imposta un codice per entrare.`, 5000);
      GL.prefs.set({ avatar });
      goSetPin(false);
    }
  }

  function goSetPin(faceOk) {
    $('#lock-setpin-why').textContent = faceOk
      ? 'Serve se un giorno il volto non venisse riconosciuto. Almeno 4 cifre.'
      : 'Il volto non è disponibile su questo telefono, quindi il codice è necessario. Almeno 4 cifre.';
    $('#lock-setpin-skip').hidden = !faceOk;   // a code is mandatory only when the face failed
    $('#lock-newpin').value = ''; $('#lock-newpin2').value = ''; $('#lock-setpin-msg').textContent = '';
    show('setpin');
  }

  async function savePin() {
    const a = $('#lock-newpin').value.trim(), b = $('#lock-newpin2').value.trim();
    if (a.length < 4) { $('#lock-setpin-msg').textContent = 'Il codice deve avere almeno 4 cifre'; return; }
    if (a !== b) { $('#lock-setpin-msg').textContent = 'I due codici non coincidono'; return; }
    const salt = b64(crypto.getRandomValues(new Uint8Array(8)));
    GL.prefs.set({ pinHash: await sha256(salt + a), pinSalt: salt, lockSetup: true });
    GL.sfx?.play('ok');
    toast('Codice salvato');
    log('Codice di accesso impostato', 'ok');
    finish();
  }

  /* ---------------- unlocking ---------------- */
  async function tryFace(auto) {
    const p = GL.prefs.get();
    const btn = $('#lock-face-go');
    btn.disabled = true;
    btn.textContent = 'Verifica…';
    $('#lock-unlock-msg').textContent = '';
    let ok = false, msg = '';
    try {
      if (p.lockKind === 'webauthn') ok = await webauthnAuth(p.faceCred);
      else { const r = await nativeAuth('Sblocca Ghostlink', 'Guarda la fotocamera'); ok = r.ok; msg = r.msg; }
    } catch (e) { msg = e.name === 'NotAllowedError' ? 'annullato' : 'non riuscito'; }
    btn.disabled = false;
    btn.textContent = 'Sblocca con il volto';
    if (ok) {
      GL.sfx?.play('ok'); haptic([15, 40, 15]);
      log('Accesso con il volto riuscito', 'ok');
      finish();
    } else {
      GL.sfx?.play('err');
      if (!auto) haptic([60, 40, 60]);
      $('#lock-unlock-msg').textContent = msg ? `Volto non riconosciuto: ${msg}` : 'Volto non riconosciuto';
    }
  }

  async function checkPin() {
    const input = $('#lock-pin');
    const val = input.value.trim();
    const p = GL.prefs.get();
    if (!p.pinHash) { $('#lock-pin-msg').textContent = 'Nessun codice impostato su questo telefono'; return; }
    if (await sha256((p.pinSalt || '') + val) === p.pinHash) {
      GL.sfx?.play('ok'); haptic(15);
      log('Accesso con il codice riuscito', 'ok');
      finish();
    } else {
      input.value = '';
      GL.sfx?.play('err'); haptic([60, 40, 60]);
      $('#lock-pin-msg').textContent = 'Codice sbagliato';
    }
  }

  function finish() {
    GL.prefs.set({ lockSetup: true });
    camera(false);
    const el = $('#lock');
    if (!el) { const r = resolveGate; resolveGate = null; if (r) r(); return; }
    el.classList.add('done');
    setTimeout(() => el.remove(), 350);
    const r = resolveGate; resolveGate = null;
    if (r) r();
  }

  // Adds face unlock later, from the lock screen or from Settings.
  async function addFace() {
    const kind = platform();
    if (kind === 'none') { toast('Questo telefono non offre sblocco biometrico alle app', 4500); return false; }
    let ok = false, msg = '';
    try {
      if (kind === 'webauthn') { const id = await webauthnEnroll(); GL.prefs.set({ faceCred: id }); ok = true; }
      else { const r = await nativeAuth('Attiva lo sblocco', 'Conferma con volto o impronta'); ok = r.ok; msg = r.msg; }
    } catch (e) { msg = e.name === 'NotAllowedError' ? 'annullato' : 'non riuscito'; }
    if (ok) {
      GL.prefs.set({ lockBio: true, lockKind: kind });
      GL.sfx?.play('ok'); haptic([20, 50, 20]);
      toast('Sblocco con il volto attivato');
      log('Sblocco con il volto attivato', 'ok');
    } else {
      GL.sfx?.play('err');
      toast(`Non attivato: ${msg}`, 4000);
    }
    return ok;
  }

  /* ---------------- gate ---------------- */
  function renderUnlock() {
    const p = GL.prefs.get();
    const canBio = p.lockBio && bioPossible();
    $('#lock-unlock-who').textContent = p.codename || 'Agente';
    if (p.avatar) { $('#lock-avatar').src = p.avatar; $('#lock-avatar').hidden = false; }
    $('#lock-face-go').hidden = !canBio;
    $('#lock-pin-go2').hidden = !p.pinHash;
    // never leave the user with no way in: offer to add whichever is missing
    $('#lock-addface').hidden = canBio || !bioPossible();
    show('unlock');
    return canBio;
  }

  function gate() {
    return new Promise(res => {
      const el = $('#lock');
      if (!el) { res(); return; }
      resolveGate = res;
      const p = GL.prefs.get();

      $('#lock-enroll-go').addEventListener('click', registerFace);
      $('#lock-enroll-skip').addEventListener('click', () => goSetPin(false));
      $('#lock-setpin-go').addEventListener('click', savePin);
      $('#lock-setpin-skip').addEventListener('click', finish);
      $('#lock-newpin2').addEventListener('keydown', e => { if (e.key === 'Enter') savePin(); });

      $('#lock-face-go').addEventListener('click', () => tryFace(false));
      $('#lock-pin-go2').addEventListener('click', () => {
        $('#lock-pin').value = ''; $('#lock-pin-msg').textContent = '';
        $('#lock-back-face').hidden = !bioPossible();   // back to the chooser / "activate face"
        show('pin');
        setTimeout(() => $('#lock-pin').focus(), 100);
      });
      $('#lock-addface').addEventListener('click', async () => { if (await addFace()) renderUnlock(); });
      $('#lock-pin-enter').addEventListener('click', checkPin);
      $('#lock-pin').addEventListener('keydown', e => { if (e.key === 'Enter') checkPin(); });
      $('#lock-back-face').addEventListener('click', () => { renderUnlock(); });

      const setupDone = p.lockSetup || p.faceEnrolled;   // faceEnrolled: older installs
      if (!setupDone) {
        $('#lock-kind').textContent = KIND_LABEL[platform()] || 'volto';
        $('#lock-enroll-go').hidden = !bioPossible();
        show('enroll');
        camera(true);
        return;
      }

      // Migrate installs made before both options existed.
      if (p.lockBio === undefined || p.lockBio === null) {
        GL.prefs.set({ lockBio: p.faceKind === 'face' || p.faceKind === 'biometric' || p.faceKind === 'webauthn', lockKind: p.faceKind || 'none' });
      }

      const canBio = renderUnlock();
      if (!canBio && !GL.prefs.get().pinHash) {
        // nothing registered at all (e.g. a skipped setup): let them straight in and say so
        toast('Sblocco non impostato: attivalo dalle Impostazioni', 4000);
        finish();
        return;
      }
      if (canBio) {
        tryFace(true);                 // ask for the face right away, like the phone's lock screen
      } else if (!bioPossible()) {
        $('#lock-pin-go2').click();    // this phone offers nothing else: go straight to the code
      }
      // otherwise stay on the chooser, which shows the code button plus "activate face" 
    });
  }

  async function reEnroll() {
    GL.prefs.set({ lockSetup: false, lockBio: false, lockKind: 'none', faceCred: null, faceEnrolled: false });
    toast('Riavvio per registrare di nuovo…');
    setTimeout(() => location.reload(), 900);
  }

  GL.face = { gate, reEnroll, addFace, platform, bioPossible, _native };
})();
