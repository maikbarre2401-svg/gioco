/* Zeph Desktop — la scena trasparente in cui Zeph vive sullo schermo.
   Passeggia lungo il bordo inferiore, parla, balla, segue il mouse.
   Il modello e le animazioni vengono da ../zeph-core.js. */
(function () {
'use strict';

const bridge = window.zephBridge || null; // assente se aperto in un browser normale
const botCtx = {}; // stato giochi + nome (riempito dopo)
try { botCtx.name = localStorage.getItem('zephName') || null; } catch (e) {}

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
// luci da discoteca (si accendono con la musica)
const disco1 = new THREE.PointLight(0xff4fd8, 0, 8);
const disco2 = new THREE.PointLight(0x4fd8ff, 0, 8);
scene.add(disco1, disco2);
let musicOn = false;
function startMusic() { if (musicOn) return; musicOn = true; ZephCore.music.start(); anim.state.danceFreq = 6.6; }
function stopMusic() { musicOn = false; ZephCore.music.stop(); anim.state.danceFreq = 6.0; }

// guardaroba
const OUTFITS = [
  { jacket: 0x3c5a64, jeans: 0x46618c, shoe: 0xe9eaec, hair: 0x3a2d21 },
  { jacket: 0x8a3d4e, jeans: 0x2e3a52, shoe: 0xf2f2f2, hair: 0x201a14 },
  { jacket: 0xc7842e, jeans: 0x3f4f46, shoe: 0x2f3338, hair: 0x5a4632 },
  { jacket: 0x4a7a4f, jeans: 0x54514e, shoe: 0xe8e4d8, hair: 0x77502e },
  { jacket: 0x5a4f8a, jeans: 0x333a47, shoe: 0xd9d4e8, hair: 0x14100d },
  { jacket: 0x2d6a8f, jeans: 0x6b4f3a, shoe: 0xf5efe0, hair: 0x8a7048 },
];
function applyOutfit(i) {
  const o = OUTFITS[((i % OUTFITS.length) + OUTFITS.length) % OUTFITS.length];
  zeph.mats.jacket.color.set(o.jacket);
  zeph.mats.jacketDark.color.set(o.jacket).multiplyScalar(0.62);
  zeph.mats.jeans.color.set(o.jeans);
  zeph.mats.shoe.color.set(o.shoe);
  zeph.mats.hair.color.set(o.hair);
  try { localStorage.setItem('zephOutfit', String(i)); } catch (e) {}
}
function randomOutfit() {
  let cur = 0;
  try { cur = parseInt(localStorage.getItem('zephOutfit') || '0', 10) || 0; } catch (e) {}
  let i = cur;
  while (i === cur) i = (Math.random() * OUTFITS.length) | 0;
  applyOutfit(i);
}
try {
  const saved = parseInt(localStorage.getItem('zephOutfit') || '0', 10);
  if (saved) applyOutfit(saved);
} catch (e) {}

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

// ---------- Avatar personalizzato (avatar.glb) ----------
const anim = new ZephCore.Animator(zeph);
const actor = { obj: zeph.root };
let avatarDriver = null;

function setAvatarScene(avScene) {
  try {
    const driver = ZephCore.createAvatarDriver(THREE, avScene, { height: 1.75 });
    if (avatarDriver) scene.remove(avatarDriver.root);
    avatarDriver = driver;
    zeph.root.visible = false;
    driver.root.position.x = state.x;
    scene.add(driver.root);
    anim.avatar = driver;
    actor.obj = driver.root;
  } catch (e) { console.error('Avatar non utilizzabile:', e); }
}
function tryLoadAvatar() {
  if (typeof THREE.GLTFLoader !== 'function') return;
  if (bridge && bridge.loadAvatar) {
    const ab = bridge.loadAvatar();
    if (ab && ab.byteLength) {
      new THREE.GLTFLoader().parse(ab, '', g => setAvatarScene(g.scene),
        err => console.error('avatar.glb non leggibile:', err));
    }
  }
}

// ---------- Stato e movimento (solo lungo x) ----------
const state = {
  x: 0, heading: 0, speed: 0,
  targetX: null,
  wander: true, follow: false, muted: false,
  nextWanderAt: 3, nextChatterAt: 20,
  mouseX: null,
};
const WALK_SPEED = 1.7;
const RUN_SPEED = 3.4;
state.running = false;
state.flying = false;
state.flyLerp = 0;
// afferrato col mouse e lasciato cadere, come un'ochetta
const grab = { pending: false, on: false, y: 0, vy: 0, falling: false, sx: 0, sy: 0, said: false };

function margin() { return 0.8; }
function maxX() { return worldHalfWidth() - margin(); }

function updateMovement(dt) {
  if (grab.on || grab.falling) {
    if (grab.falling) {
      grab.vy -= 22 * dt;
      grab.y += grab.vy * dt;
      if (grab.y <= 0) {
        grab.y = 0; grab.falling = false;
        sparkles.burst(state.x, 0.15, 0, 10);
        if (Math.random() < 0.6) speak(ZephCore.pick(['Ahia! Però che volo!', 'Uff! Avvisami la prossima volta!', 'Wiii! Di nuovo!']));
      }
    }
    state.speed = 0;
    anim.state.speedRatio = 0;
    actor.obj.position.x = state.x;
    actor.obj.position.y = grab.y;
    actor.obj.rotation.y = 0;
    actor.obj.rotation.z = grab.on ? Math.sin(Date.now() * 0.004) * 0.14 : 0;
    blob.position.x = state.x;
    const sh2 = 1 / (1 + grab.y * 1.2);
    blob.scale.set(sh2, sh2, 1);
    blob.material.opacity = sh2 * 0.9;
    return;
  }
  state.flyLerp += ((state.flying ? 1 : 0) - state.flyLerp) * Math.min(1, dt * 2);
  actor.obj.position.y = (1.15 + Math.sin(Date.now() * 0.0021) * 0.14) * state.flyLerp;
  actor.obj.rotation.z = 0;
  anim.state.flying = state.flying;

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
  const targetSpeed = (dir !== 0 && !blocked) ? (state.running ? RUN_SPEED : WALK_SPEED) : 0;
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
    const stride = 0.7 + 0.3 * Math.min(1, Math.max(0, state.speed / WALK_SPEED - 1));
    anim.state.phase += state.speed * dt * (Math.PI / stride);
  }
  anim.state.speedRatio = (state.speed / WALK_SPEED) * (1 - state.flyLerp);

  actor.obj.position.x = state.x;
  actor.obj.rotation.y = state.heading;

  // ombra finta: segue Zeph e si restringe quando salta o vola
  const air = (anim.state.jumpAir || 0) + state.flyLerp * 0.9;
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

// ---------- Rocky il cane ----------
const dog = { on: false, built: null, x: 2.5, heading: 0, speed: 0, phase: 0, nextBarkAt: 20, blob: null };
function setDogStrip(on) {
  dog.on = on;
  if (on && !dog.built) {
    dog.built = ZephCore.buildDog(THREE);
    scene.add(dog.built.root);
    dog.x = state.x + 1.5;
    dog.blob = blob.clone();
    dog.blob.scale.set(0.5, 0.5, 1);
    scene.add(dog.blob);
  }
  if (dog.built) { dog.built.root.visible = on; dog.blob.visible = on; }
}
function updateDogStrip(t, dt) {
  if (!dog.on || !dog.built) return;
  const tx = state.x + (dog.x <= state.x ? -0.85 : 0.85);
  const dx = tx - dog.x;
  const dist = Math.abs(dx);
  const targetSpeed = dist > 3 ? 4.4 : dist > 0.2 ? Math.min(2.9, dist * 2.6) : 0;
  dog.speed += (targetSpeed - dog.speed) * Math.min(1, dt * 5);
  if (dog.speed > 0.02) {
    dog.x += Math.sign(dx) * dog.speed * dt;
    dog.phase += dog.speed * dt * (Math.PI / 0.3);
  }
  const targetHeading = dog.speed > 0.15 ? Math.sign(dx) * Math.PI / 2 * 0.9 : 0;
  dog.heading += (targetHeading - dog.heading) * Math.min(1, dt * 6);
  dog.built.root.position.x = dog.x;
  dog.built.root.rotation.y = dog.heading;
  ZephCore.updateDog(dog.built, t, dt, {
    speedRatio: dog.speed / 2.9, phase: dog.phase,
    excited: anim.state.talking || !!anim.state.action,
  });
  dog.blob.position.x = dog.x;
  if (t > dog.nextBarkAt) {
    dog.nextBarkAt = t + 10 + Math.random() * 18;
    if (!state.muted) ZephCore.bark();
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
  const p = new THREE.Vector3(state.x, 1.95 + anim.state.lastRootY, 0);
  p.project(camera);
  let bx = (p.x * 0.5 + 0.5) * W();
  bx = Math.max(130, Math.min(W() - 130, bx));
  bubble.style.left = bx + 'px';
  bubble.style.top = ((-p.y * 0.5 + 0.5) * H() - 6) + 'px';
}

// ---------- Comandi (tray e chat) ----------
function batteryReport() {
  if (!navigator.getBattery) { speak('Non riesco a leggere la batteria su questo PC!'); return; }
  navigator.getBattery().then(b => {
    const perc = Math.round(b.level * 100);
    speak('La batteria è al ' + perc + ' per cento' +
      (b.charging ? ' e si sta caricando!' : perc < 20 ? '… mettila in carica!' : '!'));
  }).catch(() => speak('Non riesco a leggere la batteria su questo PC!'));
}

function botRespond(text) {
  const out = ZephCore.botReply(text, botCtx);
  if (!out) return;
  if (out.stop) { state.wander = false; state.follow = false; state.targetX = null; }
  if (out.wander) { state.wander = true; state.follow = false; }
  if (out.follow) { state.follow = true; }
  if (out.come && state.mouseX !== null) {
    state.targetX = Math.max(-maxX(), Math.min(maxX(), (state.mouseX / W() * 2 - 1) * worldHalfWidth()));
  }
  if (out.appUrl && bridge) {
    // protocollo di sistema: apre la VERA app installata (WhatsApp, Impostazioni…)
    bridge.doAction({ type: 'url', url: out.appUrl });
  } else if (out.open) {
    if (bridge) bridge.doAction({ type: 'url', url: out.open });
    else window.open(out.open, '_blank');
  }
  if (out.app && bridge) bridge.doAction({ type: 'app', id: out.app });
  if (out.volume && bridge) bridge.doAction({ type: 'volume', dir: out.volume });
  if (out.battery) { batteryReport(); return; }
  if (out.setName) { localStorage.setItem('zephName', out.setName); botCtx.name = out.setName; }
  if (out.whoami) {
    const n = localStorage.getItem('zephName');
    out.say = n ? ('Ti chiami ' + n + '! Come potrei dimenticarlo?')
      : 'Non me l\u2019hai ancora detto! Scrivimi \u00abmi chiamo\u2026\u00bb e me lo ricorder\u00f2.';
  }
  if (out.run !== undefined) state.running = out.run;
  if (out.dog) setDogStrip(out.dog === 'on');
  if (out.sky || out.weather || out.autoSky !== undefined) {
    out.say = 'Il cielo e il meteo li comando solo nel mio mondo nel browser! Qui sul desktop ci pensa Windows.';
  }
  if (out.photo) out.say = 'Le foto ricordo le scatto solo nel mio mondo nel browser!';
  if (out.ball) out.say = 'La palla la lancio solo nel prato del browser! Qui Rocky mi segue e basta.';
  if (out.music === 'on') startMusic();
  if (out.music === 'off') stopMusic();
  if (out.fly !== undefined) state.flying = out.fly;
  if (out.camMode) out.say = 'La camera si muove solo nel mio mondo nel browser!';
  if (out.stars) out.say = 'Le stelle da raccogliere sono nel mio mondo nel browser! Qui mi accontento della taskbar.';
  if (out.outfit) {
    if (avatarDriver) out.say = 'Il look lo cambio solo quando sono Zeph, non con il tuo avatar!';
    else randomOutfit();
  }
  if (out.remind) {
    const r = out.remind;
    setTimeout(() => {
      anim.startAction('jump');
      speak('Ehi! Promemoria: ' + r.text);
      try { new Notification('Zeph ⏰', { body: r.text }); } catch (e) { /* niente notifiche */ }
    }, r.seconds * 1000);
  }
  if (out.action) anim.startAction(out.action);
  speak(out.say);
}

if (bridge) {
  bridge.onCommand(cmd => {
    if (cmd === 'saluta') botRespond('ciao');
    else if (cmd === 'balla') botRespond('balla');
    else if (cmd === 'salta') botRespond('salta');
    else if (cmd === 'flip') botRespond('salto mortale');
    else if (cmd === 'spin') botRespond('piroetta');
    else if (cmd === 'barzelletta') botRespond('barzelletta');
    else if (cmd === 'dog:on') { setDogStrip(true); speak('Rocky! Vieni qui bello!'); }
    else if (cmd === 'dog:off') { setDogStrip(false); speak('Rocky, a cuccia!'); }
    else if (cmd === 'music:on') { startMusic(); speak('DJ Zeph in consolle! Si ballaaa!'); anim.startAction('dance'); }
    else if (cmd === 'music:off') { stopMusic(); speak('Musica spenta!'); }
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
const dock = document.getElementById('dock');

function cursorOverZeph(mx, my) {
  const v = new THREE.Vector2((mx / W()) * 2 - 1, -(my / H()) * 2 + 1);
  raycaster.setFromCamera(v, camera);
  return raycaster.intersectObject(actor.obj, true).length > 0;
}
function cursorOverDock(mx, my) {
  const r = dock.getBoundingClientRect();
  return mx >= r.left - 8 && mx <= r.right + 8 && my >= r.top - 8 && my <= r.bottom + 8;
}

window.addEventListener('mousemove', e => {
  state.mouseX = e.clientX;
  // presa: se trascini dopo aver premuto su Zeph, lo sollevi
  if (grab.pending && !grab.on && Math.abs(e.clientX - grab.sx) + Math.abs(e.clientY - grab.sy) > 12) {
    grab.on = true; grab.falling = false;
    state.targetX = null;
    anim.state.action = null;
    if (!grab.said) { grab.said = true; speak('Ehiii! Mettimi giù!'); }
  }
  if (grab.on) {
    const wx = (e.clientX / W() * 2 - 1) * worldHalfWidth();
    state.x = Math.max(-maxX(), Math.min(maxX(), wx));
    grab.y = Math.max(0, (H() - e.clientY) / PX_PER_WORLD - 0.9);
  }
  const over = grab.on || grab.pending ||
    cursorOverZeph(e.clientX, e.clientY) || cursorOverDock(e.clientX, e.clientY);
  if (over !== interactive) {
    interactive = over;
    document.body.style.cursor = over ? 'pointer' : 'default';
    if (bridge) bridge.setInteractive(over);
  }
});

// ---------- Pulsanti sullo schermo: chat e microfono ----------
document.getElementById('chatbtn').addEventListener('click', () => {
  if (bridge && bridge.openChat) bridge.openChat();
  else speak('La chat si apre solo nella versione desktop completa!');
});

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const micBtn = document.getElementById('micbtn');
let rec = null, listening = false;

function stopListeningUI() {
  listening = false;
  micBtn.classList.remove('listening');
}
micBtn.addEventListener('click', () => {
  if (listening) { try { rec.stop(); } catch (e) {} stopListeningUI(); return; }
  if (!SR) { micNotAvailable(); return; }
  try {
    rec = new SR();
    rec.lang = 'it-IT';
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    let got = false;
    rec.onresult = ev => {
      got = true;
      const t = ev.results[0][0].transcript;
      botRespond(t);
    };
    rec.onerror = ev => {
      stopListeningUI();
      if (ev.error === 'network' || ev.error === 'service-not-allowed' || ev.error === 'language-not-supported') micNotAvailable();
      else if (ev.error === 'not-allowed') speak('Mi serve il permesso del microfono per sentirti!');
      else if (!got) speak('Non ti ho sentito bene… riprova!');
    };
    rec.onend = stopListeningUI;
    rec.start();
    listening = true;
    micBtn.classList.add('listening');
  } catch (e) { stopListeningUI(); micNotAvailable(); }
});
function micNotAvailable() {
  speak('Qui sul desktop non riesco ancora a sentirti dal microfono… ma scrivimi dalla chat qui accanto e ti rispondo a voce! Nella versione browser invece posso sentirti davvero.');
  if (bridge && bridge.openChat) bridge.openChat();
}

const CLICK_REPLIES = [
  { say: 'Ehi! Mi hai cliccato!', action: 'wave' },
  { say: 'Serve qualcosa? Sono tutto orecchie!', action: null },
  { say: 'Guarda cosa so fare!', action: 'dance' },
  { say: 'Op!', action: 'jump' },
  { say: 'Dimmi pure! Premi il fumetto 💬 qui in basso a destra per scrivermi!', action: 'wave' },
];
window.addEventListener('mousedown', e => {
  if (e.button !== 0) return;
  if (cursorOverDock(e.clientX, e.clientY)) return;
  if (!cursorOverZeph(e.clientX, e.clientY)) return;
  grab.pending = true; grab.sx = e.clientX; grab.sy = e.clientY;
});
window.addEventListener('mouseup', e => {
  if (e.button !== 0) return;
  if (grab.on) {
    // lasciato a mezz'aria: cade
    grab.on = false; grab.pending = false;
    grab.falling = true; grab.vy = 0; grab.said = false;
    return;
  }
  if (grab.pending) {
    grab.pending = false;
    const r = ZephCore.pick(CLICK_REPLIES);
    if (r.action) anim.startAction(r.action);
    speak(r.say);
  }
});
// clic destro su Zeph → apre la chat
window.addEventListener('contextmenu', e => {
  if (cursorOverZeph(e.clientX, e.clientY)) {
    e.preventDefault();
    if (bridge && bridge.openChat) bridge.openChat();
  }
});

window.addEventListener('resize', () => {
  renderer.setSize(W(), H());
  camera.left = -worldHalfWidth();
  camera.right = worldHalfWidth();
  camera.top = H() / PX_PER_WORLD - 0.05;
  camera.updateProjectionMatrix();
});

// ---------- Loop ----------
const sparkles = ZephCore.createSparkles(THREE, scene);
let prevActionName = null;
let nextStretchAt = 40;

const clock = new THREE.Clock();
function tick() {
  requestAnimationFrame(tick);
  const dt = Math.min(0.05, clock.getDelta());
  const t = clock.elapsedTime;

  updateMovement(dt);
  updateWander(t);
  updateChatter(t);
  anim.update(t, dt);
  updateDogStrip(t, dt);
  updateBubblePosition();

  // scintille su balli, piroette e atterraggi
  const act = anim.state.action;
  if (act && (act.name === 'dance' || act.name === 'spin') && Math.random() < dt * 7) {
    sparkles.burst(state.x + (Math.random() - 0.5) * 0.9, 0.9 + Math.random() * 0.7, (Math.random() - 0.5) * 0.4, 2);
  }
  const actName = act ? act.name : null;
  if (!actName && (prevActionName === 'jump' || prevActionName === 'flip')) {
    sparkles.burst(state.x, 0.12, 0, 12);
  }
  prevActionName = actName;
  sparkles.update(dt, camera);

  // ogni tanto, da fermo, si stiracchia
  if (t > nextStretchAt) {
    nextStretchAt = t + 30 + Math.random() * 30;
    if (!act && !anim.state.talking && state.speed < 0.1 && !state.follow && !musicOn) anim.startAction('stretch');
  }

  // scia del jetpack
  if (state.flyLerp > 0.3 && Math.random() < dt * 20) {
    sparkles.burst(state.x + (Math.random() - 0.5) * 0.2, actor.obj.position.y + 0.2, 0, 1);
  }

  // luci disco e ballo continuo finché c'è musica
  if (musicOn) {
    if (!anim.state.action && !anim.state.talking && state.speed < 0.1 && !grab.on && !grab.falling) anim.startAction('dance');
    const beat = 1.1 + Math.sin(t * 13.2) * 0.55;
    disco1.intensity = beat; disco2.intensity = 1.65 - beat * 0.5;
    const da = t * 1.7;
    disco1.position.set(state.x + Math.sin(da) * 1.8, 2.2, 2 + Math.cos(da) * 1.4);
    disco2.position.set(state.x - Math.sin(da) * 1.8, 2.2, 2 - Math.cos(da) * 1.4);
  } else {
    disco1.intensity = 0; disco2.intensity = 0;
  }

  renderer.render(scene, camera);
}
tick();

// avatar personalizzato, se presente
tryLoadAvatar();

// saluto di benvenuto
setTimeout(() => {
  anim.startAction('wave');
  const h = new Date().getHours();
  const salve = h < 12 ? 'Buongiorno' : h < 18 ? 'Ciao' : 'Buonasera';
  speak(botCtx.name
    ? (salve + ', ' + botCtx.name + '! Eccomi di nuovo sul tuo schermo! Prova a dirmi «vola»!')
    : salve + '! Sono Zeph, da adesso abito qui sul tuo schermo!');
}, 1200);

// gancio per test
window.zephDesktop = {
  state, anim, speak, botRespond, setAvatarScene,
  loadAvatarUrl: url => { if (typeof THREE.GLTFLoader === 'function') new THREE.GLTFLoader().load(url, g => setAvatarScene(g.scene)); },
};
})();
