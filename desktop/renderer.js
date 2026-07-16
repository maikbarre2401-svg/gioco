/* Zeph Desktop — la scena trasparente in cui Zeph vive sullo schermo.
   Passeggia lungo il bordo inferiore, parla, balla, segue il mouse.
   Il modello e le animazioni vengono da ../zeph-core.js. */
(function () {
'use strict';

const bridge = window.zephBridge || null; // assente se aperto in un browser normale

// ---------- Scena trasparente ----------
const W = () => window.innerWidth, H = () => window.innerHeight;
const PX_PER_WORLD = 150; // Zeph alto ~1.75 → ~260 px sullo schermo

const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(W(), H());
renderer.setClearColor(0x000000, 0);
renderer.outputEncoding = THREE.sRGBEncoding;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();

function worldHalfWidth() { return (W() / 2) / PX_PER_WORLD; }
const camera = new THREE.OrthographicCamera(
  -worldHalfWidth(), worldHalfWidth(),
  H() / PX_PER_WORLD - 0.05, -0.05, 0.1, 50
);
camera.position.set(0, 0, 12);
camera.lookAt(0, 0, 0);

const hemi = new THREE.HemisphereLight(0xe8f1ff, 0x8a8f96, 0.75);
scene.add(hemi);
const key = new THREE.DirectionalLight(0xfff2dd, 0.85);
key.position.set(3, 6, 8);
scene.add(key);
const rim = new THREE.DirectionalLight(0xbcd7ff, 0.5);
rim.position.set(-4, 5, -6);
scene.add(rim);

// ---------- Zeph e ombra finta ----------
const zeph = ZephCore.build(THREE);
scene.add(zeph.root);

function shadowTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d');
  const grad = g.createRadialGradient(64, 64, 6, 64, 64, 62);
  grad.addColorStop(0, 'rgba(0,0,0,0.34)');
  grad.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = grad; g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}
const blob = new THREE.Mesh(
  new THREE.PlaneGeometry(1.15, 0.3),
  new THREE.MeshBasicMaterial({ map: shadowTexture(), transparent: true, depthWrite: false })
);
blob.position.y = 0.02;
scene.add(blob);

// ---------- Stato e movimento (solo lungo x) ----------
const anim = new ZephCore.Animator(zeph);
const state = {
  x: 0, heading: 0, speed: 0,
  targetX: null,
  wander: true, follow: false, muted: false,
  nextWanderAt: 3, nextChatterAt: 20,
  mouseX: null,
};
const WALK_SPEED = 1.7;

function margin() { return 0.8; }
function maxX() { return worldHalfWidth() - margin(); }

function updateMovement(dt) {
  if (state.follow && state.mouseX !== null) {
    const wx = (state.mouseX / W() * 2 - 1) * worldHalfWidth();
    state.targetX = Math.max(-maxX(), Math.min(maxX(), wx));
  }

  let dir = 0;
  if (state.targetX !== null) {
    const d = state.targetX - state.x;
    if (Math.abs(d) < 0.12) { if (!state.follow) state.targetX = null; }
    else dir = Math.sign(d);
  }

  const act = anim.state.action;
  const blocked = act && act.name !== 'wave';
  const targetSpeed = (dir !== 0 && !blocked) ? WALK_SPEED : 0;
  state.speed += (targetSpeed - state.speed) * Math.min(1, dt * 6);
  if (state.speed < 0.01) state.speed = 0;

  // di profilo mentre cammina, di fronte quando è fermo o parla
  let targetHeading = state.heading;
  if (dir !== 0 && !blocked) targetHeading = dir * Math.PI / 2 * 0.92;
  else targetHeading = 0;
  state.heading = lerpAngle(state.heading, targetHeading, Math.min(1, dt * 6));

  if (state.speed > 0.01 && dir !== 0) {
    state.x += dir * state.speed * dt;
    state.x = Math.max(-maxX(), Math.min(maxX(), state.x));
    anim.state.phase += state.speed * dt * (Math.PI / 0.7);
  }
  anim.state.speedRatio = state.speed / WALK_SPEED;

  zeph.root.position.x = state.x;
  zeph.root.rotation.y = state.heading;

  // ombra finta: segue Zeph e si restringe quando salta
  const air = anim.state.jumpAir || 0;
  blob.position.x = state.x;
  const sh = 1 / (1 + air * 1.6);
  blob.scale.set(sh, sh, 1);
  blob.material.opacity = sh;
}

function lerpAngle(a, b, k) {
  let d = (b - a) % (Math.PI * 2);
  if (d > Math.PI) d -= Math.PI * 2;
  if (d < -Math.PI) d += Math.PI * 2;
  return a + d * k;
}

function updateWander(t) {
  if (!state.wander || state.follow) return;
  if (state.targetX !== null || state.speed > 0.1 || anim.state.talking || anim.state.action) return;
  if (t > state.nextWanderAt) {
    state.targetX = (Math.random() * 2 - 1) * maxX();
    state.nextWanderAt = t + 5 + Math.random() * 8;
  }
}

// ogni tanto un commento a voce
function updateChatter(t) {
  if (t > state.nextChatterAt) {
    state.nextChatterAt = t + 35 + Math.random() * 50;
    if (!anim.state.talking && !anim.state.action) {
      speak(ZephCore.pick(ZephCore.FRASI_DESKTOP));
    }
  }
}

// ---------- Voce e fumetto ----------
const bubble = document.getElementById('bubble');
let bubbleTimer = null, fakeTalkTimer = null, watchdog = null;
let voice = null;

function pickVoice() {
  if (!window.speechSynthesis) return;
  const vs = speechSynthesis.getVoices();
  voice =
    vs.find(v => /it[-_]IT/i.test(v.lang) && /google/i.test(v.name)) ||
    vs.find(v => /it[-_]IT/i.test(v.lang)) ||
    vs.find(v => /^it/i.test(v.lang)) || null;
}
if (window.speechSynthesis) {
  pickVoice();
  speechSynthesis.onvoiceschanged = pickVoice;
}

function showBubble(text) {
  bubble.textContent = text;
  bubble.classList.add('show');
  clearTimeout(bubbleTimer);
}
function hideBubble(delay) {
  clearTimeout(bubbleTimer);
  bubbleTimer = setTimeout(() => bubble.classList.remove('show'), delay || 250);
}
let speakSeq = 0;
function stopTalkVisuals() {
  anim.state.talking = false;
  hideBubble(350);
}
function fallbackTalk(text) {
  showBubble(text);
  anim.state.talking = true;
  clearTimeout(fakeTalkTimer);
  const dur = Math.min(8000, Math.max(1600, 900 + text.length * 62));
  fakeTalkTimer = setTimeout(stopTalkVisuals, dur);
}

function speak(text) {
  const id = ++speakSeq;
  anim.state.gestureLead = Math.random() < 0.5 ? -1 : 1;
  showBubble(text);
  clearTimeout(fakeTalkTimer);
  clearTimeout(watchdog);

  if (!window.speechSynthesis || state.muted) { fallbackTalk(text); return; }

  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = 'it-IT';
  if (voice) u.voice = voice;
  u.rate = 1.04; u.pitch = 1.05;
  let started = false;
  u.onstart = () => { if (id !== speakSeq) return; started = true; clearTimeout(watchdog); anim.state.talking = true; };
  u.onboundary = () => { if (id === speakSeq) anim.state.mouthPulse = 1; };
  u.onend = () => { if (id === speakSeq) stopTalkVisuals(); };
  // se il TTS fallisce senza essere mai partito (es. nessuna voce), anima comunque
  u.onerror = () => {
    if (id !== speakSeq) return;
    if (!started) fallbackTalk(text); else stopTalkVisuals();
  };
  speechSynthesis.speak(u);
  watchdog = setTimeout(() => { if (id === speakSeq && !started) fallbackTalk(text); }, 800);
}

function updateBubblePosition() {
  if (!bubble.classList.contains('show')) return;
  const p = new THREE.Vector3(state.x, 1.95 + (zeph.body.position.y - ZephCore.HIP_Y), 0);
  p.project(camera);
  let bx = (p.x * 0.5 + 0.5) * W();
  bx = Math.max(130, Math.min(W() - 130, bx));
  bubble.style.left = bx + 'px';
  bubble.style.top = ((-p.y * 0.5 + 0.5) * H() - 6) + 'px';
}

// ---------- Comandi (tray e chat) ----------
function botRespond(text) {
  const out = ZephCore.botReply(text);
  if (!out) return;
  if (out.stop) { state.wander = false; state.follow = false; state.targetX = null; }
  if (out.wander) { state.wander = true; state.follow = false; }
  if (out.follow) { state.follow = true; }
  if (out.come && state.mouseX !== null) {
    state.targetX = Math.max(-maxX(), Math.min(maxX(), (state.mouseX / W() * 2 - 1) * worldHalfWidth()));
  }
  if (out.action) anim.startAction(out.action);
  speak(out.say);
}

if (bridge) {
  bridge.onCommand(cmd => {
    if (cmd === 'saluta') botRespond('ciao');
    else if (cmd === 'balla') botRespond('balla');
    else if (cmd === 'salta') botRespond('salta');
    else if (cmd === 'barzelletta') botRespond('barzelletta');
    else if (cmd === 'wander:on') { state.wander = true; }
    else if (cmd === 'wander:off') { state.wander = false; state.targetX = null; }
    else if (cmd === 'follow:on') { state.follow = true; speak('Ti seguo! Muovi il mouse!'); }
    else if (cmd === 'follow:off') { state.follow = false; state.targetX = null; }
    else if (cmd === 'mute:on') { state.muted = true; if (window.speechSynthesis) speechSynthesis.cancel(); }
    else if (cmd === 'mute:off') { state.muted = false; }
  });
  bridge.onChat(text => botRespond(text));
}

// ---------- Mouse: hit-test per il click-through ----------
const raycaster = new THREE.Raycaster();
let interactive = false;

function cursorOverZeph(mx, my) {
  const v = new THREE.Vector2((mx / W()) * 2 - 1, -(my / H()) * 2 + 1);
  raycaster.setFromCamera(v, camera);
  return raycaster.intersectObject(zeph.root, true).length > 0;
}

window.addEventListener('mousemove', e => {
  state.mouseX = e.clientX;
  const over = cursorOverZeph(e.clientX, e.clientY);
  if (over !== interactive) {
    interactive = over;
    document.body.style.cursor = over ? 'pointer' : 'default';
    if (bridge) bridge.setInteractive(over);
  }
});

const CLICK_REPLIES = [
  { say: 'Ehi! Mi hai cliccato!', action: 'wave' },
  { say: 'Serve qualcosa? Sono tutto orecchie!', action: null },
  { say: 'Guarda cosa so fare!', action: 'dance' },
  { say: 'Op!', action: 'jump' },
  { say: 'Dimmi pure! Apri la chat dall’icona vicino all’orologio!', action: 'wave' },
];
window.addEventListener('mousedown', e => {
  if (!cursorOverZeph(e.clientX, e.clientY)) return;
  const r = ZephCore.pick(CLICK_REPLIES);
  if (r.action) anim.startAction(r.action);
  speak(r.say);
});

window.addEventListener('resize', () => {
  renderer.setSize(W(), H());
  camera.left = -worldHalfWidth();
  camera.right = worldHalfWidth();
  camera.top = H() / PX_PER_WORLD - 0.05;
  camera.updateProjectionMatrix();
});

// ---------- Loop ----------
const clock = new THREE.Clock();
function tick() {
  requestAnimationFrame(tick);
  const dt = Math.min(0.05, clock.getDelta());
  const t = clock.elapsedTime;

  updateMovement(dt);
  updateWander(t);
  updateChatter(t);
  anim.update(t, dt);
  updateBubblePosition();

  renderer.render(scene, camera);
}
tick();

// saluto di benvenuto
setTimeout(() => {
  anim.startAction('wave');
  speak('Ciao! Sono Zeph, da adesso abito qui sul tuo schermo!');
}, 1200);

// gancio per test
window.zephDesktop = { state, anim, speak, botRespond };
})();
