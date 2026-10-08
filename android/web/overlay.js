/* Zeph per Android — il personaggio dentro la finestrella trasparente che
   galleggia sopra le altre app. La finestra è grande quanto il personaggio:
   per farlo camminare, saltare o volare si sposta la FINESTRA (tramite il
   ponte ZephAndroid), mentre qui dentro lui resta inquadrato.
   Il modello e le animazioni vengono da zeph-core.js. */
(function () {
'use strict';

const A = window.ZephAndroid || null; // ponte nativo (assente nei test nel browser)
const DEFAULT_HOST = { screenW: 1080, screenH: 2340, density: 3, winW: 540, winH: 780, x: 270 };
let host = DEFAULT_HOST;
try { if (A) host = JSON.parse(A.info()); } catch (e) { host = DEFAULT_HOST; }

// il nome e la chiave del cervello AI stanno nelle impostazioni dell'app
// (le cambi da lì o dalla chat): la chiave non viene mai salvata nella pagina
if (A && A.aiKey) ZephCore.ai.useStore({ get: () => A.aiKey(), set: k => A.setAiKey(k) });
function syncPrefs() {
  try {
    const n = A && A.petName ? A.petName() : null;
    if (n && n !== ZephCore.memory.petName()) ZephCore.memory.setPetName(n);
  } catch (e) { /* app vecchia senza questi metodi */ }
}
syncPrefs();

// ---------- Scena ----------
const VIS_H = 2.25;                 // metri visibili in altezza nella finestra
const pxPerM = () => host.winH / VIS_H; // pixel dello schermo per metro

const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 3));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setClearColor(0x000000, 0);
renderer.outputEncoding = THREE.sRGBEncoding;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
function frustum() {
  const aspect = window.innerWidth / Math.max(1, window.innerHeight);
  const halfW = (VIS_H * aspect) / 2;
  return { l: -halfW, r: halfW, t: VIS_H - 0.07, b: -0.07 };
}
const f0 = frustum();
const camera = new THREE.OrthographicCamera(f0.l, f0.r, f0.t, f0.b, 0.1, 50);
camera.position.set(0, 0, 12);
camera.lookAt(0, 0, 0);

scene.add(new THREE.HemisphereLight(0xe8f1ff, 0x8a8f96, 0.75));
const key = new THREE.DirectionalLight(0xfff2dd, 0.85);
key.position.set(3, 6, 8);
scene.add(key);
const rim = new THREE.DirectionalLight(0xbcd7ff, 0.5);
rim.position.set(-4, 5, -6);
scene.add(rim);

// ombra morbida sotto i piedi (si restringe quando si stacca da terra)
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
  new THREE.PlaneGeometry(1.0, 0.26),
  new THREE.MeshBasicMaterial({ map: shadowTexture(), transparent: true, depthWrite: false })
);
blob.position.y = 0.02;
scene.add(blob);

// ---------- Zeph o il tuo avatar ----------
const zeph = ZephCore.build(THREE);
scene.add(zeph.root);
const anim = new ZephCore.Animator(zeph);
const actor = { obj: zeph.root };
let avatarDriver = null;
const sparkles = ZephCore.createSparkles(THREE, scene);

function setAvatarScene(avScene, animations) {
  try {
    const driver = ZephCore.createAvatarDriver(THREE, avScene, {
      height: 1.75, animations,
      anisotropy: renderer.capabilities.getMaxAnisotropy(),
    });
    if (avatarDriver) scene.remove(avatarDriver.root);
    avatarDriver = driver;
    zeph.root.visible = false;
    scene.add(driver.root);
    anim.avatar = driver;
    actor.obj = driver.root;
  } catch (e) { console.error('Avatar non utilizzabile:', e); }
}
function backToZeph() {
  if (!avatarDriver) return;
  scene.remove(avatarDriver.root);
  avatarDriver = null;
  zeph.root.visible = true;
  anim.avatar = zeph;
  actor.obj = zeph.root;
}
// il look fatto con la foto (colori + la tua faccia), se c'è
function loadLook() {
  fetch('look.json?v=' + Date.now())
    .then(r => (r.ok ? r.json() : null))
    .catch(() => null)
    .then(look => ZephCore.applyLook(THREE, zeph, look));
}
// l'app serve il tuo avatar a questo indirizzo (404 se non c'è: resta Zeph, col tuo look)
function loadAvatar() {
  if (typeof THREE.GLTFLoader !== 'function') { loadLook(); return; }
  new THREE.GLTFLoader().load('avatar.glb?v=' + Date.now(),
    g => setAvatarScene(g.scene, g.animations),
    undefined,
    () => { backToZeph(); loadLook(); });
}

// ---------- Stato ----------
const state = {
  x: host.x != null ? host.x : (host.screenW - host.winW) / 2,  // bordo sinistro della finestra (px)
  heading: 0, speed: 0, targetX: null,
  wander: true, running: false, flying: false, flyLerp: 0,
  muted: false, visible: true, grabbed: false,
  nextWanderAt: 4, nextChatterAt: 30, nextStretchAt: 45,
  lastTouch: 0, nextZzzAt: 0, taps: [],
};
const WALK = 1.0, RUN = 2.1; // metri al secondo (in scala personaggio)
const botCtx = {};
try { botCtx.name = localStorage.getItem('zephName') || null; } catch (e) {}

function maxX() { return Math.max(0, host.screenW - host.winW); }
function clampX(v) { return Math.max(0, Math.min(maxX(), v)); }
function lerpAngle(a, b, k) {
  let d = (b - a) % (Math.PI * 2);
  if (d > Math.PI) d -= Math.PI * 2;
  if (d < -Math.PI) d += Math.PI * 2;
  return a + d * k;
}

// ---------- Movimento: la finestra scorre lungo il fondo dello schermo ----------
let sentX = null, sentLift = null;
function updateMovement(dt) {
  let dir = 0;
  if (state.targetX !== null && !state.grabbed) {
    const d = state.targetX - state.x;
    if (Math.abs(d) < 3) state.targetX = null;
    else dir = Math.sign(d);
  }
  const act = anim.state.action;
  const blocked = (act && act.name !== 'wave') || state.grabbed;
  const target = dir !== 0 && !blocked ? (state.flying ? RUN * 1.4 : state.running ? RUN : WALK) : 0;
  state.speed += (target - state.speed) * Math.min(1, dt * 6);
  if (state.speed < 0.01) state.speed = 0;

  // di profilo mentre cammina, di fronte (verso di te) quando è fermo
  const th = dir !== 0 && !blocked ? dir * Math.PI / 2 * 0.92 : 0;
  state.heading = lerpAngle(state.heading, th, Math.min(1, dt * 6));

  if (state.speed > 0.01 && dir !== 0) {
    state.x = clampX(state.x + dir * state.speed * pxPerM() * dt);
    const stride = 0.7 + 0.3 * Math.min(1, Math.max(0, state.speed / WALK - 1));
    anim.state.phase += state.speed * dt * (Math.PI / stride);
  }
  state.flyLerp += ((state.flying ? 1 : 0) - state.flyLerp) * Math.min(1, dt * 2);
  anim.state.speedRatio = (state.speed / WALK) * (1 - state.flyLerp);
  anim.state.flying = state.flying;

  // lo sguardo va verso di te, cioè verso lo schermo
  anim.state.gazeYaw = -state.heading;
  anim.state.gazePitch = 0.05;
  anim.state.gazeW = (blocked ? 0 : 1) * (1 - 0.6 * Math.min(1, state.speed / WALK));
}

// dopo l'animazione: salti e volo spostano la finestra, non il personaggio
function placeWindow(t) {
  const rootY = anim.state.lastRootY || 0;
  const up = Math.max(0, rootY);
  const hover = state.flyLerp * (0.9 + Math.sin(t * 2.1) * 0.08);
  actor.obj.position.y = -up;
  actor.obj.rotation.y = state.heading;
  actor.obj.rotation.z = state.grabbed ? Math.sin(t * 9) * 0.16 : 0;
  const sh = 1 / (1 + (up + hover) * 1.6);
  blob.scale.set(sh, sh, 1);
  blob.material.opacity = state.grabbed ? 0 : sh;

  const lift = Math.round((up + hover) * pxPerM());
  const nx = Math.round(state.x);
  if (A && !state.grabbed && (nx !== sentX || lift !== sentLift)) {
    sentX = nx; sentLift = lift;
    A.setPos(nx, lift);
  }
}

function updateWander(t) {
  if (!state.wander || state.grabbed || anim.state.sleeping) return;
  if (state.targetX !== null || state.speed > 0.1 || anim.state.talking || anim.state.action) return;
  if (t > state.nextWanderAt) {
    state.targetX = Math.random() * maxX();
    state.nextWanderAt = t + 6 + Math.random() * 9;
  }
}

const FRASI_TELEFONO = [
  'Ehi, quante app hai aperto oggi?',
  'Io intanto mi faccio due passi sul tuo schermo.',
  'Se ti serve qualcosa, tienimi premuto e parliamo!',
  'Che bello stare nella tua tasca!',
  'Hai bevuto un po’ d’acqua oggi?',
  'Attento, sto passando!',
  'Toccami, che ti faccio vedere una cosa!',
];
function updateChatter(t) {
  if (anim.state.sleeping) return;
  if (t > state.nextChatterAt) {
    state.nextChatterAt = t + 60 + Math.random() * 90;
    if (anim.state.talking || anim.state.action || state.grabbed) return;
    // una domanda per conoscerti, un ricordo, o due chiacchiere
    const c = Math.random() < 0.6 ? ZephCore.memory.chatter(botCtx) : null;
    speak(c ? c.say : ZephCore.pick(FRASI_TELEFONO));
  }
}

// ---------- Voce (sintesi vocale del telefono) e fumetto ----------
let speakSeq = 0, fakeTimer = null, watchdog = null, hideTimer = null;
function showBubble(text) {
  clearTimeout(hideTimer);
  if (A) A.bubble(text);
}
function hideBubble(delay) {
  clearTimeout(hideTimer);
  hideTimer = setTimeout(() => { if (A) A.bubbleHide(); }, delay || 300);
}
function stopTalk() {
  anim.state.talking = false;
  hideBubble(900);
}
function fallbackTalk(text) {
  anim.state.talking = true;
  clearTimeout(fakeTimer);
  fakeTimer = setTimeout(stopTalk, Math.min(8000, Math.max(1600, 900 + text.length * 62)));
}
function speak(text, bubbleText) {
  ++speakSeq;
  anim.state.gestureLead = Math.random() < 0.5 ? -1 : 1;
  showBubble(bubbleText || text);
  clearTimeout(fakeTimer); clearTimeout(watchdog);
  const ok = A && !state.muted && A.speak(text);
  if (!ok) { fallbackTalk(text); return; }
  const id = speakSeq;
  // se la voce non parte entro un secondo e mezzo, anima comunque
  watchdog = setTimeout(() => { if (id === speakSeq && !anim.state.talking) fallbackTalk(text); }, 1500);
}
// chiamata dal telefono durante la sintesi vocale
window.zephTts = function (ev) {
  if (ev === 'start') { clearTimeout(watchdog); clearTimeout(fakeTimer); anim.state.talking = true; }
  else if (ev === 'word') anim.state.mouthPulse = 1;
  else if (ev === 'end') stopTalk();
};

// ---------- Sonno: di notte, se lo lasci tranquillo, si addormenta ----------
const SLEEP_AFTER = 90; // secondi senza essere toccato
function isNight() {
  if (state.forceNight !== undefined) return state.forceNight;
  const h = new Date().getHours();
  return h >= 23 || h < 7;
}
function touched() { state.lastTouch = clock.elapsedTime; }
// svegliato da un tocco, un messaggio o un comando: risponde comunque al resto
function wake(quiet) {
  touched();
  if (!anim.state.sleeping) return false;
  anim.state.sleeping = false;
  if (A) A.bubbleHide();
  if (!quiet) speak(ZephCore.pick(['Uaaah… ero nel mondo dei sogni!', 'Mmh? Eccomi, eccomi!', 'Che sonno… dimmi tutto!']));
  return true;
}
function updateSleep(t) {
  const st = anim.state;
  if (!st.sleeping) {
    if (isNight() && t - state.lastTouch > SLEEP_AFTER && !st.talking && !st.action &&
        state.speed < 0.05 && !musicOn && !state.grabbed && !state.flying) {
      st.sleeping = true;
      state.targetX = null;
      state.nextZzzAt = t + 2;
    }
    return;
  }
  if (!isNight()) { wake(true); return; }
  if (t > state.nextZzzAt) {
    state.nextZzzAt = t + 7 + Math.random() * 5;
    showBubble(ZephCore.pick(['Zzz…', 'Zzz… zzz…', 'Ronf… zzz…']));
    hideBubble(2600);
  }
}

// ---------- Musica ----------
let musicOn = false;
function startMusic() { if (musicOn) return; musicOn = true; ZephCore.music.start(); anim.state.danceFreq = 6.6; }
function stopMusic() { musicOn = false; ZephCore.music.stop(); anim.state.danceFreq = 6.0; }

// ---------- Il cervello: risposte e azioni sul telefono ----------
function phone(o) {
  if (!A) return true;
  try { return !!A.action(JSON.stringify(o)); } catch (e) { return false; }
}
function batteryReport() {
  try {
    const b = JSON.parse(A ? A.battery() : '{"level":-1}');
    if (b.level < 0) throw new Error('n/d');
    return 'La batteria è al ' + b.level + ' per cento' +
      (b.charging ? ' e si sta caricando!' : b.level < 20 ? '… mettila in carica!' : '!');
  } catch (e) { return 'Non riesco a leggere la batteria del telefono!'; }
}
function thinking() {
  showBubble('💭 …');
  anim.state.gestureLead = 1;
}
function botRespond(text) {
  const out = ZephCore.botReply(text, botCtx);
  if (!out) return;
  if (out.setPetName && A && A.setPetName) A.setPetName(out.setPetName);
  if (out.party) sparkles.burst(0, 1.2, 0, 24);
  if (out.stop) { state.wander = false; state.targetX = null; }
  if (out.wander) state.wander = true;
  if (out.follow) out.say = 'Sul telefono non c’è il mouse da seguire… ma posso passeggiare! Dimmi «cammina».';
  if (out.come) state.targetX = (host.screenW - host.winW) / 2;
  if (out.run !== undefined) state.running = out.run;
  if (out.fly !== undefined) state.flying = out.fly;
  if (out.setName) { try { localStorage.setItem('zephName', out.setName); } catch (e) {} botCtx.name = out.setName; }
  if (out.whoami) {
    out.say = botCtx.name ? 'Ti chiami ' + botCtx.name + '! Come potrei dimenticarlo?'
      : 'Non me l’hai ancora detto! Scrivimi «mi chiamo…» e me lo ricorderò.';
  }
  if (out.setPref) {
    try {
      const p = JSON.parse(localStorage.getItem('zephPrefs') || '{}');
      p[out.setPref.k] = out.setPref.v;
      localStorage.setItem('zephPrefs', JSON.stringify(p));
    } catch (e) {}
  }
  if (out.getPref) {
    let p = {};
    try { p = JSON.parse(localStorage.getItem('zephPrefs') || '{}'); } catch (e) {}
    out.say = p[out.getPref] ? 'Il tuo ' + out.getPref + ' preferito è ' + p[out.getPref] + '!'
      : 'Non me l’hai ancora detto! Scrivimi «il mio ' + out.getPref + ' preferito è …»';
  }
  // app vere del telefono: prima l'app, poi il sito come riserva
  if (out.appUrl || out.app || out.open) {
    let ok = false;
    if (out.appUrl) ok = phone({ type: 'appUrl', url: out.appUrl });
    if (!ok && out.app) ok = phone({ type: 'app', id: out.app });
    if (!ok && out.open) ok = phone({ type: 'url', url: out.open });
    if (!ok) out.say = 'Uffa, sul telefono questa non la trovo: forse l’app non è installata.';
  }
  if (out.volume) {
    phone({ type: 'volume', dir: out.volume });
    out.say = out.say.replace(/del PC/g, 'del telefono');
  }
  if (out.torch !== undefined && !phone({ type: 'torch', on: out.torch })) {
    out.say = 'Uffa, su questo telefono non riesco a usare la torcia.';
  }
  if (out.alarm && !phone({ type: 'alarm', h: out.alarm.h, m: out.alarm.m })) {
    out.say = 'Non riesco a puntare la sveglia: c’è l’app Orologio sul telefono?';
  }
  if (out.timer) {
    // il timer vero dell'Orologio suona anche se Zeph è chiuso: allora niente doppione
    if (phone({ type: 'timer', seconds: out.timer.seconds })) {
      delete out.remind;
      out.say += ' L’ho messo anche nell’Orologio del telefono.';
    }
  }
  if (out.dial !== undefined && !phone({ type: 'dial', number: out.dial })) {
    out.say = 'Non riesco ad aprire il telefono per chiamare.';
  }
  if (out.media) {
    if (out.media === 'pause' && musicOn) stopMusic();
    phone({ type: 'media', key: out.media });
  }
  if (out.weatherQuery) {
    speak(ZephCore.pick(['Un attimo che guardo fuori…', 'Controllo il cielo…', 'Vediamo cosa dicono le nuvole…']));
    ZephCore.weatherReport(out.weatherQuery).then(r => {
      if (r.kind === 'rain' || r.kind === 'snow') anim.startAction('stretch');
      else if (r.kind === 'clear') anim.startAction('wave');
      speak(r.say);
    });
  }
  if (out.battery) out.say = batteryReport();
  if (out.remind) {
    const r = out.remind;
    setTimeout(() => {
      anim.startAction('jump');
      speak('Ehi! Promemoria: ' + r.text);
      if (A) A.remind(r.text);
    }, r.seconds * 1000);
  }
  if (out.music === 'on') startMusic();
  if (out.music === 'off') stopMusic();
  if (out.dog) out.say = 'Rocky è rimasto a casa nel computer! Qui sul telefono c’è spazio solo per me.';
  if (out.photoAvatar && !(A && A.openPhoto && (A.openPhoto(), true))) out.say = 'Apri l’app e premi «Crea l’avatar con una foto»!';
  if (out.sky || out.weather || out.autoSky !== undefined || out.photo || out.stars ||
      out.missions || out.fireworks || out.camMode || out.quality || out.ball) {
    out.say = 'Questa la so fare nel mio mondo sul computer! Qui sul telefono cammino, ballo e ti apro le app.';
  }
  if (out.outfit) {
    out.say = avatarDriver ? 'Il look lo cambio solo quando sono Zeph, non con il tuo avatar!' : out.say;
    if (!avatarDriver) randomOutfit();
  }
  // chiacchiere: con il cervello AI risponde Claude (il cervello offline resta di riserva)
  if (out.aiQuery && ZephCore.ai.enabled()) {
    thinking();
    ZephCore.ai.ask(out.aiQuery, botCtx, out.say).then(r => {
      const act = r.action || out.action;
      if (act) anim.startAction(act);
      speak(r.say);
    });
    return;
  }
  if (out.action) anim.startAction(out.action);
  if (out.say) speak(out.say);
}

const OUTFITS = [
  { jacket: 0x3c5a64, jeans: 0x46618c, shoe: 0xe9eaec, hair: 0x3a2d21 },
  { jacket: 0x8a3d4e, jeans: 0x2e3a52, shoe: 0xf2f2f2, hair: 0x201a14 },
  { jacket: 0xc7842e, jeans: 0x3f4f46, shoe: 0x2f3338, hair: 0x5a4632 },
  { jacket: 0x4a7a4f, jeans: 0x54514e, shoe: 0xe8e4d8, hair: 0x77502e },
  { jacket: 0x5a4f8a, jeans: 0x333a47, shoe: 0xd9d4e8, hair: 0x14100d },
];
function randomOutfit() {
  const o = ZephCore.pick(OUTFITS);
  zeph.mats.jacket.color.set(o.jacket);
  zeph.mats.jacketDark.color.set(o.jacket).multiplyScalar(0.62);
  zeph.mats.jeans.color.set(o.jeans);
  zeph.mats.shoe.color.set(o.shoe);
  zeph.mats.hair.color.set(o.hair);
}

// ---------- Chiamate dal telefono (notifica, tocchi, chat) ----------
const TAP_REPLIES = [
  { say: 'Ehi! Mi hai toccato!', action: 'wave' },
  { say: 'Serve qualcosa? Tienimi premuto e parliamo!', action: null },
  { say: 'Guarda cosa so fare!', action: 'dance' },
  { say: 'Op!', action: 'jump' },
  { say: 'Hop, salto mortale!', action: 'flip' },
];
window.zephTap = function () {
  if (wake()) return;
  const now = clock.elapsedTime;
  state.taps = state.taps.filter(x => now - x < 1.6);
  state.taps.push(now);
  if (state.taps.length >= 3) {
    // tre tocchi in fretta: solletico!
    state.taps = [];
    anim.startAction('spin');
    sparkles.burst(0, 1.1, 0, 14);
    speak(ZephCore.pick(['Ahahah! No, il solletico no!', 'Ihihih, basta, basta, soffro il solletico!', 'Ahah! Smettila, mi fai ridere troppo!']));
    return;
  }
  const r = ZephCore.pick(TAP_REPLIES);
  if (r.action) anim.startAction(r.action);
  speak(r.say);
};
const EVENTS = {
  charger: { say: ['Ahh, energia! Che bello, grazie!', 'Gnam, la corrente! Mi sento già più carico!'], action: 'dance' },
  unplug: { say: ['Staccato! Ora cerchiamo di risparmiare un po’.', 'Ok, si va a batteria!'], action: 'wave' },
  batteryLow: { say: ['Ehi, la batteria è quasi scarica! Mettimi in carica, per favore.', 'Mi sento debole… la batteria sta finendo!'], action: 'stretch' },
  headset: { say: ['Cuffie! Vuoi un po’ di musica? Dimmi «play».', 'Ooh, le cuffie! Si ascolta qualcosa?'], action: 'jump' },
};
window.zephEvent = function (ev) {
  const e = EVENTS[ev];
  if (!e) return;
  wake(true);
  if (e.action) anim.startAction(e.action);
  speak(ZephCore.pick(e.say));
};
// «Condividi → Zeph»: legge il testo ad alta voce
window.zephRead = function (text) {
  wake(true);
  text = String(text || '').trim();
  if (!text) return;
  const short = text.length > 150 ? text.slice(0, 147).trim() + '…' : text;
  anim.startAction('wave');
  speak(text, '📖 ' + short);
};
window.zephGrab = function () {
  wake(true);
  state.grabbed = true;
  state.targetX = null;
  anim.state.action = null;
  speak(ZephCore.pick(['Ehiii! Mettimi giù!', 'Wooo, che vista da quassù!', 'Non farmi cadere!']));
};
window.zephDrop = function (x) {
  state.grabbed = false;
  state.x = clampX(x);
  sentX = Math.round(state.x); sentLift = 0;
  sparkles.burst(0, 0.12, 0, 12);
  if (Math.random() < 0.7) speak(ZephCore.pick(['Ahia! Però che volo!', 'Uff! Avvisami la prossima volta!', 'Wiii! Di nuovo!']));
};
window.zephChat = function (text) { wake(true); botRespond(String(text || '')); };
window.zephCmd = function (cmd) {
  wake(true);
  const map = { saluta: 'ciao', balla: 'balla', salta: 'salta', flip: 'salto mortale', barzelletta: 'barzelletta', curiosita: 'dimmi una curiosità' };
  if (map[cmd]) botRespond(map[cmd]);
  else if (cmd === 'music:on') botRespond('metti la musica');
  else if (cmd === 'music:off') botRespond('basta musica');
  else if (cmd === 'mute:on') { state.muted = true; if (A) A.stopSpeak(); }
  else if (cmd === 'mute:off') state.muted = false;
};
window.zephVisible = function (v) {
  state.visible = !!v;
  if (!v) { stopMusic(); if (A) A.stopSpeak(); }
};
window.zephScreen = function (json) {
  try { host = Object.assign({}, host, JSON.parse(json)); } catch (e) { return; }
  state.x = clampX(state.x);
  onResize();
};
window.zephReloadAvatar = loadAvatar;
window.zephPrefsChanged = syncPrefs;

// ---------- Loop (30 fotogrammi al secondo: risparmia batteria) ----------
function onResize() {
  renderer.setSize(window.innerWidth, window.innerHeight);
  const f = frustum();
  camera.left = f.l; camera.right = f.r; camera.top = f.t; camera.bottom = f.b;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', onResize);

const clock = new THREE.Clock();
let acc = 0, prevAction = null;
function tick() {
  requestAnimationFrame(tick);
  const dtRaw = Math.min(0.1, clock.getDelta());
  acc += dtRaw;
  if (acc < 1 / 31) return;
  const dt = Math.min(0.08, acc);
  acc = 0;
  if (!state.visible) return;
  const t = clock.elapsedTime;

  updateMovement(dt);
  updateWander(t);
  updateChatter(t);
  updateSleep(t);
  anim.update(t, dt);
  placeWindow(t);

  const act = anim.state.action;
  if (musicOn && !act && !anim.state.talking && state.speed < 0.1 && !state.grabbed && !anim.state.sleeping) anim.startAction('dance');
  if (act && (act.name === 'dance' || act.name === 'spin') && Math.random() < dt * 6) {
    sparkles.burst((Math.random() - 0.5) * 0.8, 0.9 + Math.random() * 0.6, 0, 2);
  }
  const an = act ? act.name : null;
  if (!an && (prevAction === 'jump' || prevAction === 'flip')) sparkles.burst(0, 0.12, 0, 10);
  prevAction = an;
  if (state.flyLerp > 0.3 && Math.random() < dt * 18) sparkles.burst((Math.random() - 0.5) * 0.2, 0.2, 0, 1);
  if (t > state.nextStretchAt) {
    state.nextStretchAt = t + 50 + Math.random() * 40;
    if (!act && !anim.state.talking && state.speed < 0.1 && !musicOn && !anim.state.sleeping) anim.startAction('stretch');
  }
  sparkles.update(dt, camera);
  renderer.render(scene, camera);
}

loadAvatar();
touched();
tick();
setTimeout(() => {
  // si ricorda di te: compleanno, giorni senza vedersi, com'è andata quella cosa…
  const g = ZephCore.memory.greeting(botCtx);
  if (g) {
    anim.startAction(g.action || 'wave');
    if (g.party) sparkles.burst(0, 1.2, 0, 30);
    speak(g.say);
    return;
  }
  anim.startAction('wave');
  const h = new Date().getHours();
  const salve = h < 12 ? 'Buongiorno' : h < 18 ? 'Ciao' : 'Buonasera';
  const pet = ZephCore.memory.petName();
  speak(botCtx.name ? salve + ', ' + botCtx.name + '! Eccomi sul tuo telefono!'
    : salve + '! Sono ' + pet + ': da adesso abito sul tuo telefono! Raccontami un po’ di te.');
}, 1200);

// gancio per i test
window.zephPhone = { state, anim, botRespond, wake, zeph, get host() { return host; } };
})();
