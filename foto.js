/* Avatar dalla foto: scatti un selfie (o scegli una foto), si prendono i
   colori veri di pelle, capelli e vestiti, e la tua faccia va sulla testa
   di Zeph. Funziona nel telefono (app Android) e nel browser.
   Tutto resta sul dispositivo: la foto non viene mandata a nessuno. */
(function () {
'use strict';

const P = window.ZephPhoto || null; // ponte dell'app Android (assente nel browser)
const $ = id => document.getElementById(id);
const video = $('video'), still = $('still'), cam = $('cam');
const OVAL = { cx: 0.5, cy: 0.46, rx: 0.31, ry: 0.31 * 1.3226 }; // come l'ovale disegnato (viewBox 300×400)
const OUT_W = 600, OUT_H = 800;

// ---------- 1. Fotocamera frontale ----------
let stream = null, photo = null;
const view = { zoom: 1, ox: 0, oy: 0 };

function showError(msg) { $('err').textContent = msg; }
function startCamera() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showError('Qui la fotocamera non è disponibile: scegli una foto dalla galleria.');
    return;
  }
  navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 960 } }, audio: false })
    .then(s => {
      stream = s;
      video.srcObject = s;
      return video.play();
    })
    .catch(() => showError('Non riesco ad aprire la fotocamera (permesso negato?). Puoi scegliere una foto dalla galleria.'));
}
function stopCamera() {
  if (stream) stream.getTracks().forEach(t => t.stop());
  stream = null;
}

// disegna la sorgente «a riempimento» come si vede nel riquadro (senza specchio)
function drawCover(g, src, sw, sh, W, H, zoom, ox, oy) {
  const scale = Math.max(W / sw, H / sh) * zoom;
  const dw = sw * scale, dh = sh * scale;
  g.drawImage(src, (W - dw) / 2 + ox * W, (H - dh) / 2 + oy * H, dw, dh);
}
function capture() {
  const c = document.createElement('canvas');
  c.width = OUT_W; c.height = OUT_H;
  const g = c.getContext('2d');
  if (photo) drawCover(g, photo, photo.naturalWidth, photo.naturalHeight, OUT_W, OUT_H, view.zoom, view.ox, view.oy);
  else if (video.videoWidth) drawCover(g, video, video.videoWidth, video.videoHeight, OUT_W, OUT_H, 1, 0, 0);
  else return null;
  return c;
}

// ---------- foto dalla galleria: si sposta e si ingrandisce col dito ----------
function drawStill() {
  const r = cam.getBoundingClientRect();
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  still.width = Math.round(r.width * dpr); still.height = Math.round(r.height * dpr);
  const g = still.getContext('2d');
  g.fillStyle = '#000'; g.fillRect(0, 0, still.width, still.height);
  drawCover(g, photo, photo.naturalWidth, photo.naturalHeight, still.width, still.height, view.zoom, view.ox, view.oy);
}
$('file').addEventListener('change', e => {
  const f = e.target.files && e.target.files[0];
  if (!f) return;
  const img = new Image();
  img.onload = () => {
    photo = img;
    view.zoom = 1; view.ox = 0; view.oy = 0;
    $('zoom').value = 1;
    stopCamera();
    video.style.display = 'none';
    still.style.display = 'block';
    $('zoomrow').style.display = 'flex';
    $('shoot').textContent = '✅ Fatto, è nell’ovale';
    showError('');
    drawStill();
  };
  img.onerror = () => showError('Questa immagine non riesco ad aprirla.');
  img.src = URL.createObjectURL(f);
});
$('zoom').addEventListener('input', e => { view.zoom = parseFloat(e.target.value); if (photo) drawStill(); });
let drag = null;
cam.addEventListener('pointerdown', e => { if (!photo) return; drag = { x: e.clientX, y: e.clientY, ox: view.ox, oy: view.oy }; cam.setPointerCapture(e.pointerId); });
cam.addEventListener('pointermove', e => {
  if (!drag) return;
  const r = cam.getBoundingClientRect();
  view.ox = drag.ox + (e.clientX - drag.x) / r.width;
  view.oy = drag.oy + (e.clientY - drag.y) / r.height;
  drawStill();
});
cam.addEventListener('pointerup', () => { drag = null; });
cam.addEventListener('pointercancel', () => { drag = null; });

// ---------- scatto con il conto alla rovescia ----------
let look = null;
$('shoot').addEventListener('click', () => {
  if (photo) { finishShot(); return; }
  if (!video.videoWidth) { showError('La fotocamera non è pronta: aspetta un attimo, oppure scegli una foto.'); return; }
  $('shoot').disabled = true;
  let n = 3;
  const tick = () => {
    $('count').textContent = n || '';
    if (n === 0) {
      $('flash').style.opacity = 1;
      setTimeout(() => { $('flash').style.opacity = 0; }, 120);
      finishShot();
      $('shoot').disabled = false;
      return;
    }
    n--;
    setTimeout(tick, 800);
  };
  tick();
});
function finishShot() {
  const c = capture();
  if (!c) return;
  look = ZephCore.lookFromPhoto(c, { cx: OVAL.cx * OUT_W, cy: OVAL.cy * OUT_H, rx: OVAL.rx * OUT_W, ry: OVAL.ry * OUT_W });
  look.eyes = look.eyes || EYES[0];
  stopCamera();
  showStep2();
}

// ---------- 2. Anteprima 3D e ritocchi ----------
const EYES = ['#5b3b22', '#7a5a2e', '#3f6f9e', '#4f7a4a', '#6c7a86', '#2a1d14'];
let three = null;
function setupPreview() {
  const box = $('preview');
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  renderer.outputEncoding = THREE.sRGBEncoding;
  box.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.05, 50);
  scene.add(new THREE.HemisphereLight(0xeaf2ff, 0x5a6270, 0.8));
  const key = new THREE.DirectionalLight(0xfff1e0, 0.9); key.position.set(1.5, 3, 4); scene.add(key);
  const rim = new THREE.DirectionalLight(0xbcd7ff, 0.45); rim.position.set(-3, 2, -3); scene.add(rim);
  const zeph = ZephCore.build(THREE);
  scene.add(zeph.root);
  const anim = new ZephCore.Animator(zeph);
  three = { renderer, scene, camera, zeph, anim, full: false, clock: new THREE.Clock(), nextTalk: 1.2 };
  function resize() {
    const w = box.clientWidth, h = box.clientHeight;
    renderer.setSize(w, h);
    camera.aspect = w / Math.max(1, h);
    camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize);
  resize();
  (function loop() {
    requestAnimationFrame(loop);
    const dt = Math.min(0.05, three.clock.getDelta()), t = three.clock.elapsedTime;
    // parla ogni tanto, così vedi la tua faccia che muove la bocca
    if (t > three.nextTalk) {
      anim.state.talking = !anim.state.talking;
      three.nextTalk = t + (anim.state.talking ? 2.2 : 2.8);
      if (!anim.state.talking && Math.random() < 0.4) anim.startAction(Math.random() < 0.5 ? 'wave' : 'dance');
    }
    anim.state.gazeYaw = -zeph.root.rotation.y;
    anim.state.gazeW = 1;
    anim.update(t, dt);
    zeph.root.rotation.y = Math.sin(t * 0.45) * 0.45;
    const tgt = three.full ? { y: 0.95, d: 4.4 } : { y: 1.58, d: 1.15 };
    camera.position.set(0, tgt.y + (three.full ? 0.25 : 0.04), tgt.d);
    camera.lookAt(0, tgt.y, 0);
    renderer.render(scene, camera);
  })();
}
$('viewbtn').addEventListener('click', () => {
  three.full = !three.full;
  $('viewbtn').textContent = three.full ? '👤 Solo la faccia' : '🧍 Tutto il corpo';
});
function currentLook() {
  return {
    v: 1, skin: $('cSkin').value, hair: $('bald').checked ? 'none' : $('cHair').value, top: $('cTop').value,
    eyes: look.eyes, face: look.face, useFace: $('useFace').checked,
  };
}
function refresh() { ZephCore.applyLook(THREE, three.zeph, currentLook()); }
function showStep2() {
  $('step1').hidden = true;
  $('step2').hidden = false;
  if (!three) setupPreview();
  $('cSkin').value = look.skin;
  $('cHair').value = look.hair || '#3a2d21';
  $('cTop').value = look.top || '#3c5a64';
  $('bald').checked = false;
  const eyes = $('eyes');
  eyes.innerHTML = '';
  EYES.forEach(c => {
    const d = document.createElement('div');
    d.className = 'chip' + (c === look.eyes ? ' on' : '');
    d.style.background = c;
    d.addEventListener('click', () => {
      look.eyes = c;
      [...eyes.children].forEach(x => x.classList.toggle('on', x === d));
      refresh();
    });
    eyes.appendChild(d);
  });
  refresh();
  window.scrollTo(0, 0);
}
['cSkin', 'cHair', 'cTop', 'bald', 'useFace'].forEach(id => $(id).addEventListener('input', refresh));
$('redo').addEventListener('click', () => {
  $('step2').hidden = true;
  $('step1').hidden = false;
  if (!photo) startCamera();
});

// ---------- salva ----------
function petName() {
  try { return P ? P.petName() : ZephCore.memory.petName(); } catch (e) { return 'Zeph'; }
}
$('pet').value = petName() === 'Zeph' ? '' : petName();
$('save').addEventListener('click', () => {
  const out = currentLook();
  const pet = $('pet').value.replace(/[^A-Za-zÀ-ÿ' -]/g, '').trim().slice(0, 16);
  if (pet) out.petName = pet.charAt(0).toUpperCase() + pet.slice(1);
  $('save').disabled = true;
  if (P) { P.save(JSON.stringify(out)); return; } // l'app salva e chiude questa pagina
  try {
    localStorage.setItem('zephLook', JSON.stringify(out));
    localStorage.setItem('zephPreferZeph', '1'); // nel browser: Zeph con il tuo look al posto del .glb
    if (out.petName) ZephCore.memory.setPetName(out.petName);
  } catch (e) {
    $('save').disabled = false;
    showError('Non riesco a salvare (memoria del browser piena o bloccata).');
    return;
  }
  location.href = 'index.html';
});
$('avaturn').addEventListener('click', () => {
  if (P) P.openUrl('https://avaturn.me');
  else window.open('https://avaturn.me', '_blank', 'noopener');
});

// gancio per i test
window.zephFoto = { get look() { return look; }, finishShot, currentLook, get three() { return three; } };
startCamera();
})();
