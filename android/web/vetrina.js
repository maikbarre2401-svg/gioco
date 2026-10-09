/* La vetrina 3D in cima all'app: il tuo avatar (o Zeph col tuo look) su un
   piedistallo di luce, che gira piano. Trascinalo col dito per ruotarlo,
   toccalo due volte per farlo ballare. L'app cambia la modalità con
   vetrinaStyle('neon') e ricarica l'avatar con vetrinaReload(). */
(function () {
'use strict';

const params = new URLSearchParams(location.search);
const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2.5));
renderer.setClearColor(0x000000, 0);
renderer.outputEncoding = THREE.sRGBEncoding;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.95;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.environment = ZephCore.studioEnvironment(THREE, renderer);
const camera = new THREE.PerspectiveCamera(26, 1, 0.1, 50);
scene.add(new THREE.HemisphereLight(0xe8f1ff, 0x5a6270, 0.35));
const key = new THREE.DirectionalLight(0xfff1e0, 0.9); key.position.set(2, 4, 5); scene.add(key);
const rim = new THREE.DirectionalLight(0x8fd8ff, 0.7); rim.position.set(-3, 3, -4); scene.add(rim);

// il piedistallo: disco, anello che gira e anello tratteggiato
const podium = new THREE.Group();
const glowMat = (color, opacity) => new THREE.MeshBasicMaterial({ color, transparent: true, opacity, depthWrite: false, side: THREE.DoubleSide });
const disc = new THREE.Mesh(new THREE.CircleGeometry(0.62, 48), glowMat(0x0e7490, 0.35)); disc.rotation.x = -Math.PI / 2;
const ring = new THREE.Mesh(new THREE.RingGeometry(0.6, 0.66, 64), glowMat(0x5eead4, 0.95)); ring.rotation.x = -Math.PI / 2;
const dash = new THREE.Mesh(new THREE.RingGeometry(0.74, 0.76, 48, 1, 0, Math.PI * 1.6), glowMat(0xa78bfa, 0.8)); dash.rotation.x = -Math.PI / 2;
podium.add(disc, ring, dash);
podium.position.y = 0.005;
scene.add(podium);

const zeph = ZephCore.build(THREE);
Object.values(zeph.mats || {}).forEach(m => { if (m && m.isMeshStandardMaterial) m.envMapIntensity = 0.35; });
scene.add(zeph.root);
const anim = new ZephCore.Animator(zeph);
const actor = { obj: zeph.root };
let driver = null;
const holo = ZephCore.createHologram(THREE);
scene.add(holo.base);
const styles = ZephCore.createStyles(THREE, holo);
const sparkles = ZephCore.createSparkles(THREE, scene, 40);
let style = params.get('style') || 'normale';

function roots() { return [zeph.root, actor.obj]; }
function useDriver(d) {
  if (driver) scene.remove(driver.root);
  driver = d;
  if (d) {
    zeph.root.visible = false;
    d.root.traverse(o => { if (o.material && o.material.isMeshStandardMaterial) o.material.envMapIntensity = 0.85; });
    scene.add(d.root);
    anim.avatar = d;
    actor.obj = d.root;
  } else {
    zeph.root.visible = true;
    anim.avatar = zeph;
    actor.obj = zeph.root;
  }
  styles.set(style, roots());
}
function loadLook() {
  return fetch('look.json?v=' + Date.now()).then(r => (r.ok ? r.json() : null)).catch(() => null)
    .then(look => ZephCore.applyLook(THREE, zeph, look)).then(() => styles.refresh(roots()));
}
function load() {
  new THREE.GLTFLoader().load('avatar.glb?v=' + Date.now(), g => {
    try {
      useDriver(ZephCore.createAvatarDriver(THREE, g.scene, { height: 1.75, animations: g.animations, anisotropy: renderer.capabilities.getMaxAnisotropy() }));
    } catch (e) { useDriver(null); }
  }, undefined, () => { useDriver(null); loadLook(); });
}

// ---------- tocchi: trascina per ruotare, doppio tocco per ballare ----------
let yaw = 0, spin = 0.35, drag = null, lastTap = 0;
renderer.domElement.addEventListener('pointerdown', e => { drag = { x: e.clientX, yaw }; spin = 0; });
renderer.domElement.addEventListener('pointermove', e => { if (drag) yaw = drag.yaw + (e.clientX - drag.x) * 0.012; });
const up = () => {
  if (!drag) return;
  drag = null;
  setTimeout(() => { if (!drag) spin = 0.35; }, 2500);
  const now = performance.now();
  if (now - lastTap < 320) { anim.startAction(Math.random() < 0.5 ? 'dance' : 'spin'); sparkles.burst(0, 1.1, 0, 16); }
  lastTap = now;
};
renderer.domElement.addEventListener('pointerup', up);
renderer.domElement.addEventListener('pointercancel', up);

function resize() {
  const w = window.innerWidth, h = Math.max(1, window.innerHeight);
  renderer.setSize(w, h);
  camera.aspect = w / h;
  // tutta la figura, piedistallo compreso, qualunque sia la forma del riquadro
  const dist = 5.6 / Math.min(1, camera.aspect);
  camera.position.set(0, 1.15, dist);
  camera.lookAt(0, 0.98, 0);
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize();

const clock = new THREE.Clock();
let acc = 0, nextMove = 3;
(function loop() {
  requestAnimationFrame(loop);
  const dtRaw = Math.min(0.1, clock.getDelta());
  acc += dtRaw;
  if (acc < 1 / 31) return;
  const dt = Math.min(0.08, acc);
  acc = 0;
  const t = clock.elapsedTime;
  yaw += spin * dt;
  actor.obj.rotation.y = yaw;
  if (t > nextMove && !anim.state.action) {
    nextMove = t + 6 + Math.random() * 6;
    anim.startAction(['wave', 'stretch', 'spin', 'dance'][(Math.random() * 4) | 0]);
  }
  anim.state.gazeYaw = -Math.sin(yaw) * 0.6;
  anim.state.gazeW = 0.6;
  anim.update(t, dt);
  const lift = Math.max(0, anim.state.lastRootY || 0) + (styles.floats ? 0.18 + Math.sin(t * 1.7) * 0.05 : 0);
  actor.obj.position.y = lift;
  ring.rotation.z = t * 0.6;
  dash.rotation.z = -t * 0.9;
  ring.material.opacity = 0.75 + Math.sin(t * 2.4) * 0.2;
  holo.update(t);
  styles.update(t);
  sparkles.update(dt, camera);
  renderer.render(scene, camera);
})();

// ---------- comandi dall'app ----------
window.vetrinaStyle = function (name) {
  style = styles.set(name, roots());
  sparkles.burst(0, 1.0, 0, 22);
  anim.startAction('spin');
};
window.vetrinaReload = load;
window.zephVetrina = { styles, anim, get style() { return style; } };
load();
})();
