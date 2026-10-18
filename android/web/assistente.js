/* L'assistente vocale: tieni premuto il tasto Home (o tocca «Assistente»),
   il tuo avatar compare sopra un pannello di vetro, ti ascolta, fa la cosa
   sul telefono e te la dice. Il microfono e la voce sono dell'app
   (AssistActivity); il cervello è lo stesso del compagno (zeph-core.js + telefono.js). */
(function () {
'use strict';

const A = window.ZephAndroid || null;
const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
let info = { mic: true, recog: true, source: params.get('src') || 'app' };
try { if (A && A.info) info = Object.assign(info, JSON.parse(A.info())); } catch (e) {}

// la chiave del cervello AI sta nell'app, mai nella pagina
if (A && A.aiKey) ZephCore.ai.useStore({ get: () => A.aiKey(), set: k => A.setAiKey(k) });
try { const n = A && A.petName ? A.petName() : null; if (n && n !== ZephCore.memory.petName()) ZephCore.memory.setPetName(n); } catch (e) {}
const memSync = ZephTelefono.syncMemory(A);
const botCtx = {};
try { botCtx.name = localStorage.getItem('zephName') || null; } catch (e) {}
const pet = () => ZephCore.memory.petName();
$('name').textContent = pet();

// ---------- la scena: il tuo avatar a mezzo busto ----------
const canvas = $('three');
const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2.5));
renderer.setClearColor(0x000000, 0);
renderer.outputEncoding = THREE.sRGBEncoding;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.95;
const scene = new THREE.Scene();
scene.environment = ZephCore.studioEnvironment(THREE, renderer);
const camera = new THREE.PerspectiveCamera(24, 1, 0.05, 30);
scene.add(new THREE.HemisphereLight(0xe8f1ff, 0x4a5568, 0.42));
const key = new THREE.DirectionalLight(0xfff1e0, 0.95); key.position.set(1.6, 3.2, 4); scene.add(key);
const rimL = new THREE.DirectionalLight(0x5eead4, 0.75); rimL.position.set(-3, 2.2, -2.5); scene.add(rimL);
const rimR = new THREE.DirectionalLight(0xa78bfa, 0.6); rimR.position.set(3, 2, -2.5); scene.add(rimR);

const zeph = ZephCore.build(THREE);
Object.values(zeph.mats || {}).forEach(m => { if (m && m.isMeshStandardMaterial) m.envMapIntensity = 0.35; });
scene.add(zeph.root);
const anim = new ZephCore.Animator(zeph);
const actor = { obj: zeph.root };
let driver = null;
const holo = ZephCore.createHologram(THREE);
const styles = ZephCore.createStyles(THREE, holo);
const sparkles = ZephCore.createSparkles(THREE, scene, 50);
const roots = () => [zeph.root, actor.obj];

function useDriver(d) {
  if (driver) scene.remove(driver.root);
  driver = d;
  if (d) {
    zeph.root.visible = false;
    d.root.traverse(o => { if (o.material && o.material.isMeshStandardMaterial) o.material.envMapIntensity = 0.85; });
    scene.add(d.root);
    anim.avatar = d;
    actor.obj = d.root;
  }
  let st = 'normale';
  try { st = (A && A.style ? A.style() : '') || 'normale'; } catch (e) {}
  styles.set(st, roots());
}
function loadAvatar() {
  const zephLook = () => fetch('look.json?v=' + Date.now()).then(r => (r.ok ? r.json() : null)).catch(() => null)
    .then(look => ZephCore.applyLook(THREE, zeph, look)).then(() => useDriver(null));
  if (typeof THREE.GLTFLoader !== 'function') { zephLook(); return; }
  new THREE.GLTFLoader().load('avatar.glb?v=' + Date.now(), g => {
    try {
      useDriver(ZephCore.createAvatarDriver(THREE, g.scene, { height: 1.75, animations: g.animations, anisotropy: renderer.capabilities.getMaxAnisotropy() }));
    } catch (e) { zephLook(); }
  }, undefined, zephLook);
}

function resize() {
  const w = canvas.clientWidth || window.innerWidth, h = Math.max(1, canvas.clientHeight);
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  // testa e spalle, qualunque sia la forma del riquadro
  const dist = 2.55 / Math.min(1, camera.aspect * 1.15);
  camera.position.set(0, 1.62, dist);
  camera.lookAt(0, 1.52, 0);
  camera.updateProjectionMatrix();
  layoutStage();
}
// il riquadro dell'avatar poggia sul pannello
function layoutStage() {
  document.documentElement.style.setProperty('--panel-h', $('panel').offsetHeight + 'px');
}
window.addEventListener('resize', resize);

// ---------- l'onda della voce ----------
const wave = $('wave');
const wg = wave.getContext('2d');
let level = 0, levelT = 0;
function drawWave(t) {
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  const W = wave.clientWidth, H = wave.clientHeight;
  if (wave.width !== Math.round(W * dpr)) { wave.width = Math.round(W * dpr); wave.height = Math.round(H * dpr); }
  wg.setTransform(dpr, 0, 0, dpr, 0, 0);
  wg.clearRect(0, 0, W, H);
  const talking = anim.state.talking;
  const base = mode === 'listening' ? 0.12 + level * 0.88 : mode === 'thinking' ? 0.22 : talking ? 0.3 + (anim.state.mouthSmooth || 0) * 0.7 : 0.05;
  const cols = mode === 'thinking' ? ['#a78bfa', '#818cf8', '#f472b6'] : ['#5eead4', '#38bdf8', '#a78bfa'];
  for (let k = 0; k < 3; k++) {
    wg.beginPath();
    for (let x = 0; x <= W; x += 3) {
      const u = x / W;
      const env = Math.sin(Math.PI * u) ** 2;
      const y = H / 2 + Math.sin(u * (9 + k * 3) + t * (3.2 + k * 1.3) + k) * env * (H * 0.42) * base * (1 - k * 0.22);
      if (x === 0) wg.moveTo(x, y); else wg.lineTo(x, y);
    }
    wg.strokeStyle = cols[k];
    wg.globalAlpha = 0.85 - k * 0.22;
    wg.lineWidth = 2.2 - k * 0.5;
    wg.shadowColor = cols[k];
    wg.shadowBlur = 10;
    wg.stroke();
  }
  wg.globalAlpha = 1;
}

// ---------- stato: ascolto, penso, parlo ----------
let mode = 'idle';
let conversation = false;
let closeTimer = null, waitTimer = null, closeAfterSpeech = false, pendingSpeaks = 0, spoke = false;
const STATUS = { idle: 'Tocca il microfono per parlare', listening: 'Ti ascolto…', thinking: 'Ci penso…', speaking: 'Sto parlando…' };
function setMode(m, text) {
  mode = m;
  document.body.classList.toggle('listening', m === 'listening');
  document.body.classList.toggle('thinking', m === 'thinking');
  $('statusText').textContent = text || STATUS[m] || '';
  const accent = m === 'thinking' ? '#a78bfa' : m === 'speaking' ? '#38bdf8' : m === 'listening' ? '#5eead4' : '#64748b';
  document.documentElement.style.setProperty('--accent', accent);
  if (m !== 'idle') clearTimeout(closeTimer);
}
function scheduleClose(ms) {
  clearTimeout(closeTimer);
  if (conversation) return;
  closeTimer = setTimeout(close, ms);
}
let closed = false;
function close() {
  if (closed) return;
  closed = true;
  memSync.flush(); // la memoria nel file dell'app, subito
  document.body.classList.add('closing');
  if (A && A.stopListen) A.stopListen();
  setTimeout(() => { if (A && A.close) A.close(); }, 200);
}
function listen() {
  clearTimeout(closeTimer);
  if (!A || !A.listen || !info.mic || !info.recog) { setMode('idle', info.recog ? 'Scrivimi pure qui sotto' : 'Il riconoscimento vocale non c’è: scrivimi'); openTyping(); return; }
  if (A.stopSpeak && anim.state.talking) A.stopSpeak();
  A.listen();
}

// il telefono ci dice cosa succede al microfono
window.assistState = function (s, msg) {
  if (s === 'listening') { setMode('listening'); if (!spoke) showHeard('', 'hint', 'Ti ascolto…'); }
  else if (s === 'idle') {
    level = 0;
    if (mode === 'listening') setMode('idle', msg);
    if (!conversation) scheduleClose(9000);
  } else if (s === 'nomatch') {
    level = 0;
    setMode('idle', msg || 'Non ho sentito… tocca il microfono');
    if (conversation && (window.__silences = (window.__silences || 0) + 1) < 3) setTimeout(listen, 400);
    else scheduleClose(8000);
  } else if (s === 'error') {
    level = 0;
    setMode('idle', msg || 'Il microfono non va: scrivimi');
    openTyping();
  }
};
window.assistLevel = function (v) { level = Math.max(0, Math.min(1, v)); levelT = performance.now(); };
window.assistHeard = function (text, final) {
  text = String(text || '').trim();
  if (!final) { if (text) showHeard(text + '…', 'partial'); return; }
  window.__silences = 0;
  handle(text);
};
window.assistAgain = function () { closed = false; document.body.classList.remove('closing'); listen(); };

function showHeard(text, cls, hint) {
  const el = $('heard');
  el.className = cls || '';
  el.textContent = text || hint || '';
}

// ---------- quello che dici ----------
const STOP_RE = /^(?:basta|stop|niente|annulla|lascia stare|chiudi|esci|fine|grazie(?: mille)?(?:,? basta| così)?|ok grazie|a posto così|va bene così|ciao ciao|no grazie)[.!]*$/i;
function handle(text) {
  clearTimeout(closeTimer);
  if (!text) { setMode('idle', 'Non ho sentito… tocca il microfono'); scheduleClose(8000); return; }
  showHeard(text, '');
  $('reply').textContent = '';
  if (STOP_RE.test(text)) {
    conversation = false;
    paintLoop();
    say(ZephCore.pick(['A dopo!', 'Ci sono quando vuoi!', 'Ok, a dopo!']));
    closeAfterSpeech = true;
    return;
  }
  setMode('thinking');
  spoke = false;
  closeAfterSpeech = false;
  const out = ZephCore.botReply(text, botCtx);
  if (!out) { setMode('idle'); return; }
  // quante frasi arriveranno: «guardo il meteo…» e poi il meteo
  const aiChat = out.aiQuery && ZephCore.ai.enabled();
  pendingSpeaks = (out.weatherQuery || out.wikiQuery) ? 2 : 1;
  if (aiChat || out.briefing) pendingSpeaks = 1;
  tel.respondWith(out, false);
  clearTimeout(waitTimer);
  // se non dice niente (o la risposta tarda troppo) si torna ad ascoltare o si chiude
  waitTimer = setTimeout(() => { if (!spoke) afterSpeech(); }, aiChat || out.weatherQuery || out.wikiQuery || out.briefing ? 16000 : 1500);
}

// ---------- parlare ----------
let speakSeq = 0, fallback = null;
function say(text, bubble) {
  spoke = true;
  pendingSpeaks = Math.max(0, pendingSpeaks - 1);
  clearTimeout(waitTimer);
  const t = String(text || '');
  $('reply').textContent = bubble || t;
  layoutStage();
  setMode('speaking');
  anim.state.gestureLead = Math.random() < 0.5 ? -1 : 1;
  const id = ++speakSeq;
  const ok = A && A.speak && A.speak(t);
  clearTimeout(fallback);
  if (!ok) {
    // senza voce: muove la bocca il tempo di leggere
    anim.state.talking = true;
    fallback = setTimeout(() => { if (id === speakSeq) { anim.state.talking = false; speechEnded(); } }, Math.min(9000, 1400 + t.length * 55));
  } else {
    // se la voce non parte, non resta bloccato
    fallback = setTimeout(() => { if (id === speakSeq && !anim.state.talking) speechEnded(); }, 4000 + t.length * 80);
  }
}
window.zephTts = function (ev) {
  if (ev === 'start') { clearTimeout(fallback); anim.state.talking = true; }
  else if (ev === 'word') anim.state.mouthPulse = 1;
  else if (ev === 'end') { anim.state.talking = false; speechEnded(); }
};
function speechEnded() {
  if (pendingSpeaks > 0) { setMode('thinking'); return; } // arriva un'altra frase (meteo, Wikipedia…)
  afterSpeech();
}
// finito di parlare: si chiude, aspetta, o ti ascolta di nuovo
function afterSpeech() {
  if (closed) return;
  if (closeAfterSpeech) { close(); return; }
  const last = $('reply').textContent;
  const asks = /\?\s*(?:\(sì \/ no\))?\s*$/.test(last) || !!botCtx.pending;
  if (conversation || asks) { setTimeout(listen, 350); return; }
  setMode('idle', 'Tocca il microfono se ti serve altro');
  scheduleClose(6500);
}

// ---------- il cervello del telefono ----------
const tel = ZephTelefono.create({
  A, ctx: botCtx, speak: say,
  act: name => anim.startAction(name),
  burst: n => sparkles.burst(0, 1.45, 0, Math.min(30, n)),
  thinking: () => setMode('thinking'),
  setStyle: name => { styles.set(name, roots()); if (A && A.setStyle) A.setStyle(styles.current); sparkles.burst(0, 1.45, 0, 20); },
  talk: () => { conversation = true; paintLoop(); },
  globalDelay: 450,
  // un'altra app si apre: la finestra si chiude quando ho finito di parlare (la voce continua)
  opened(kind) {
    if (kind === 'global') { closeAfterSpeech = true; close(); return; }
    closeAfterSpeech = true;
  },
  local(out) {
    if (out.music === 'on') { out.sys = { type: 'play', q: '', app: '' }; out.say = 'Metto un po’ di musica!'; }
    if (out.music === 'off') { out.media = 'pause'; out.say = 'Musica in pausa!'; }
    if (out.stop || out.wander || out.come || out.run !== undefined || out.fly !== undefined || out.follow) {
      out.say = 'Qui faccio l’assistente! Per vedermi camminare e volare sullo schermo scegli la modalità «Compagno» nell’app.';
    }
    if (out.outfit) out.say = 'Il look lo cambi nell’app: modalità, foto o il tuo avatar!';
    return false;
  },
});

// ---------- suggerimenti ----------
const IDEE = [
  ['☀️ Meteo', 'che tempo fa?'], ['📅 Agenda', 'che impegni ho oggi?'], ['📩 Messaggi', 'chi mi ha scritto?'],
  ['🧭 Portami a casa', 'portami a casa'], ['🎵 Musica', 'metti un po\' di musica'], ['🔦 Torcia', 'accendi la torcia'],
  ['⏰ Sveglia 7:00', 'svegliami alle 7'], ['⏱ Timer 10 min', 'timer di 10 minuti'], ['🔕 Non disturbare', 'non disturbare'],
  ['📸 Selfie', 'fai un selfie'], ['🔋 Batteria', 'quanta batteria ho?'], ['📝 Prendi nota', 'prendi nota: '],
  ['🌅 La mia giornata', 'com\'è la mia giornata?'], ['😂 Barzelletta', 'raccontami una barzelletta'],
];
function chips() {
  const box = $('chips');
  box.innerHTML = '';
  const h = new Date().getHours();
  const order = IDEE.slice();
  if (h < 11) order.unshift(order.splice(12, 1)[0]); // la mattina: la giornata per prima
  order.forEach(([label, cmd]) => {
    const c = document.createElement('div');
    c.className = 'chip';
    c.textContent = label;
    c.addEventListener('click', () => {
      if (/: $/.test(cmd)) { openTyping(cmd); return; }
      if (A && A.stopListen) A.stopListen();
      handle(cmd);
    });
    box.appendChild(c);
  });
}
function paintLoop() { $('loop').style.background = conversation ? 'linear-gradient(90deg,#14b8a6,#8b5cf6)' : ''; }

// ---------- tocchi ----------
function openTyping(prefill) {
  document.body.classList.add('typing');
  if (A && A.stopListen) A.stopListen();
  clearTimeout(closeTimer);
  const inp = $('typed');
  if (prefill) inp.value = prefill;
  setTimeout(() => { inp.focus(); layoutStage(); }, 60);
}
function sendTyped() {
  const v = $('typed').value.trim();
  if (!v) return;
  $('typed').value = '';
  handle(v);
}
$('send').addEventListener('click', sendTyped);
$('typed').addEventListener('keydown', e => { if (e.key === 'Enter') sendTyped(); });
$('typed').addEventListener('focus', () => clearTimeout(closeTimer));
$('kbd').addEventListener('click', () => (document.body.classList.contains('typing') ? document.body.classList.remove('typing') : openTyping()));
$('mic').addEventListener('click', () => {
  if (mode === 'listening') { if (A && A.stopListen) A.stopListen(); setMode('idle'); return; }
  document.body.classList.remove('typing');
  listen();
});
$('close').addEventListener('click', close);
$('shade').addEventListener('click', close);
$('app').addEventListener('click', () => { if (A && A.openApp) A.openApp(); });
$('loop').addEventListener('click', () => {
  conversation = !conversation;
  paintLoop();
  $('statusText').textContent = conversation ? 'Conversazione continua: ti riascolto dopo ogni risposta' : 'Conversazione normale';
  if (conversation && mode === 'idle') listen();
});
$('panel').addEventListener('pointerdown', () => { if (mode === 'idle') clearTimeout(closeTimer); });

// ---------- loop ----------
const clock = new THREE.Clock();
let acc = 0;
(function loop() {
  requestAnimationFrame(loop);
  const dtRaw = Math.min(0.1, clock.getDelta());
  acc += dtRaw;
  if (acc < 1 / 40) return;
  const dt = Math.min(0.08, acc);
  acc = 0;
  const t = clock.elapsedTime;
  if (performance.now() - levelT > 400) level *= 0.85;
  // ti guarda: un po' a destra e sinistra mentre ascolta, dritto mentre parla
  anim.state.gazeYaw = mode === 'listening' ? Math.sin(t * 0.7) * 0.08 : 0;
  anim.state.gazePitch = mode === 'thinking' ? 0.12 : 0.02;
  anim.state.gazeW = 1;
  anim.update(t, dt);
  actor.obj.rotation.y = Math.sin(t * 0.35) * 0.06 + (mode === 'thinking' ? Math.sin(t * 1.3) * 0.05 : 0);
  actor.obj.position.y = Math.max(0, anim.state.lastRootY || 0) * 0.3 + Math.sin(t * 1.1) * 0.008;
  const lv = mode === 'listening' ? level : anim.state.talking ? (anim.state.mouthSmooth || 0) * 0.6 : 0;
  document.documentElement.style.setProperty('--halo', (1 + lv * 0.22 + Math.sin(t * 2) * 0.015).toFixed(3));
  document.documentElement.style.setProperty('--spin', ((t * (mode === 'thinking' ? 160 : 40)) % 360).toFixed(1) + 'deg');
  document.documentElement.style.setProperty('--spin2', ((-t * 22) % 360).toFixed(1) + 'deg');
  $('mic').style.setProperty('--lvl', (mode === 'listening' ? level : 0).toFixed(2));
  holo.update(t);
  styles.update(t);
  sparkles.update(dt, camera);
  renderer.render(scene, camera);
  drawWave(t);
})();

// ---------- via! ----------
chips();
loadAvatar();
resize();
const h = new Date().getHours();
showHeard('', 'hint', (h < 12 ? 'Buongiorno' : h < 18 ? 'Ciao' : 'Buonasera') + (botCtx.name ? ', ' + botCtx.name : '') + '! Dimmi pure…');
anim.startAction('wave');
if (!info.mic || !info.recog || info.source === 'tastiera') listen();
else setMode('listening'); // il microfono l'ha già acceso l'app
requestAnimationFrame(layoutStage);

// gancio per i test
window.zephAssist = { handle, say, tel, anim, botCtx, get mode() { return mode; }, close, styles };
})();
