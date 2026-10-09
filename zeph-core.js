/* ============================================================
   ZephCore — il personaggio Zeph: modello 3D, animazioni e
   "cervello" delle risposte. Condiviso tra la versione browser
   (index.html) e l'app desktop (desktop/).
   Richiede THREE globale (three.min.js).
   ============================================================ */
(function (global) {
'use strict';

// ---------- Costruzione del corpo (proporzioni realistiche, ~1.75 m) ----------
const HIP_Y = 0.98;

function build(THREE) {
  function mat(color, roughness) {
    return new THREE.MeshStandardMaterial({ color, roughness: roughness || 0.85, metalness: 0 });
  }
  const M = {
    skin: mat(0xe0a887, 0.6), hair: mat(0x3a2d21, 0.75),
    jacket: mat(0x3c5a64, 0.9), jacketDark: mat(0x2b454e, 0.9),
    jeans: mat(0x46618c, 0.95), shoe: mat(0xe9eaec, 0.5), sole: mat(0xc2c6cc, 0.7),
    white: mat(0xf7f7f7, 0.35), iris: mat(0x6b4a2f, 0.4), pupil: mat(0x1c1713, 0.3),
    lips: mat(0x9c5f52, 0.65),
  };

  function capsule(r, len, material) {
    const m = new THREE.Mesh(new THREE.CapsuleGeometry(r, len, 6, 16), material);
    m.castShadow = true;
    return m;
  }
  function sphere(r, material, sx, sy, sz) {
    const m = new THREE.Mesh(new THREE.SphereGeometry(r, 20, 16), material);
    m.scale.set(sx || 1, sy || 1, sz || 1);
    m.castShadow = true;
    return m;
  }

  const B = { root: new THREE.Group(), HIP_Y, mats: M };

  B.body = new THREE.Group(); B.body.position.y = HIP_Y; B.root.add(B.body);

  const pelvis = capsule(0.128, 0.1, M.jeans);
  pelvis.scale.z = 0.74; B.body.add(pelvis);

  // --- busto (felpa) ---
  B.spine = new THREE.Group(); B.spine.position.y = 0.1; B.body.add(B.spine);
  const belly = capsule(0.13, 0.1, M.jacket);
  belly.scale.set(1.08, 1, 0.76); belly.position.y = 0.04; B.spine.add(belly);
  const chest = capsule(0.145, 0.18, M.jacket);
  chest.scale.set(1.15, 1, 0.74); chest.position.y = 0.155; B.spine.add(chest);
  const zip = new THREE.Mesh(new THREE.BoxGeometry(0.016, 0.34, 0.01), M.jacketDark);
  zip.position.set(0, 0.14, 0.118); B.spine.add(zip);
  const pocket = new THREE.Mesh(new THREE.BoxGeometry(0.17, 0.09, 0.015), M.jacketDark);
  pocket.position.set(0, -0.01, 0.105); B.spine.add(pocket);
  const hood = new THREE.Mesh(new THREE.TorusGeometry(0.085, 0.038, 8, 18, Math.PI), M.jacketDark);
  hood.position.set(0, 0.33, -0.04);
  hood.rotation.set(-1.3, 0, 0); hood.castShadow = true;
  B.spine.add(hood);

  // --- collo e testa ---
  const neck = capsule(0.042, 0.08, M.skin); neck.position.y = 0.37; B.spine.add(neck);
  B.head = new THREE.Group(); B.head.position.y = 0.44; B.spine.add(B.head);
  const skull = sphere(0.105, M.skin, 0.92, 1.18, 1.0); skull.position.y = 0.1; B.head.add(skull);
  const jaw = sphere(0.075, M.skin, 0.95, 0.72, 0.9); jaw.position.set(0, 0.015, 0.012); B.head.add(jaw);
  B.skull = skull; B.jawMesh = jaw;

  const hairGeo = new THREE.SphereGeometry(0.108, 20, 14, 0, Math.PI * 2, 0, Math.PI * 0.52);
  const hair = new THREE.Mesh(hairGeo, M.hair);
  hair.position.y = 0.108; hair.scale.set(0.96, 1.14, 1.03);
  hair.rotation.x = -0.26; hair.castShadow = true;
  B.head.add(hair);
  const nape = sphere(0.09, M.hair, 0.9, 0.9, 0.7); nape.position.set(0, 0.1, -0.055); B.head.add(nape);
  B.hairMeshes = [hair, nape];

  B.eyeL = sphere(0.017, M.white, 1, 1, 0.62); B.eyeL.position.set(0.038, 0.105, 0.099);
  B.eyeR = B.eyeL.clone(); B.eyeR.position.x = -0.038;
  const irisL = sphere(0.0105, M.iris, 1, 1, 0.5); irisL.position.set(0, 0, 0.0095);
  const irisR = irisL.clone();
  B.pupilL = sphere(0.0058, M.pupil, 1, 1, 0.6); B.pupilL.position.set(0, 0, 0.0128);
  B.pupilR = B.pupilL.clone();
  B.eyeL.add(irisL, B.pupilL); B.eyeR.add(irisR, B.pupilR);
  B.head.add(B.eyeL, B.eyeR);

  B.browL = new THREE.Mesh(new THREE.BoxGeometry(0.038, 0.007, 0.009), M.hair);
  B.browL.position.set(0.04, 0.138, 0.102); B.browL.rotation.z = 0.1;
  B.browR = B.browL.clone(); B.browR.position.x = -0.04; B.browR.rotation.z = -0.1;
  B.head.add(B.browL, B.browR);

  const nose = sphere(0.013, M.skin, 0.72, 1.25, 0.95); nose.position.set(0, 0.072, 0.108); B.head.add(nose);
  B.nose = nose;
  B.mouth = sphere(0.022, M.lips, 1.15, 0.22, 0.42); B.mouth.position.set(0, 0.03, 0.096); B.head.add(B.mouth);
  const earL = sphere(0.02, M.skin, 0.5, 1, 0.72); earL.position.set(0.096, 0.095, 0.005);
  const earR = earL.clone(); earR.position.x = -0.096;
  B.head.add(earL, earR);

  // --- braccia (maniche lunghe, mani di pelle) ---
  function makeArm(side) { // side: +1 sinistro (+x), -1 destro (-x)
    const sh = new THREE.Group(); sh.position.set(0.19 * side, 0.29, 0); B.spine.add(sh);
    const pad = sphere(0.06, M.jacket); pad.position.y = 0.005; sh.add(pad);
    const upper = capsule(0.05, 0.21, M.jacket); upper.position.y = -0.155; sh.add(upper);
    const el = new THREE.Group(); el.position.y = -0.3; sh.add(el);
    const fore = capsule(0.043, 0.19, M.jacket); fore.position.y = -0.125; el.add(fore);
    const hand = sphere(0.05, M.skin, 0.78, 1.15, 0.55); hand.position.y = -0.3; el.add(hand);
    return { sh, el };
  }
  const armL = makeArm(1), armR = makeArm(-1);
  B.shL = armL.sh; B.elL = armL.el; B.shR = armR.sh; B.elR = armR.el;

  // --- gambe ---
  function makeLeg(side) {
    const hip = new THREE.Group(); hip.position.set(0.088 * side, -0.035, 0); B.body.add(hip);
    const thigh = capsule(0.074, 0.32, M.jeans); thigh.position.y = -0.21; hip.add(thigh);
    const knee = new THREE.Group(); knee.position.y = -0.44; hip.add(knee);
    const calf = capsule(0.058, 0.34, M.jeans); calf.position.y = -0.22; knee.add(calf);
    const foot = new THREE.Group(); foot.position.y = -0.44; knee.add(foot);
    const shoe = new THREE.Mesh(new THREE.BoxGeometry(0.115, 0.075, 0.24), M.shoe);
    shoe.position.set(0, -0.055, 0.05); shoe.castShadow = true;
    const soleM = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.028, 0.25), M.sole);
    soleM.position.set(0, -0.107, 0.05);
    foot.add(shoe, soleM);
    return { hip, knee, foot };
  }
  const legL = makeLeg(1), legR = makeLeg(-1);
  B.hipL = legL.hip; B.kneeL = legL.knee; B.footL = legL.foot;
  B.hipR = legR.hip; B.kneeR = legR.knee; B.footR = legR.foot;

  // marcatori usati dal retargeting sugli avatar esterni
  function marker(parent, x, y, z) {
    const m = new THREE.Object3D(); m.position.set(x, y, z); parent.add(m); return m;
  }
  B.markers = {
    wristL: marker(B.elL, 0, -0.3, 0), wristR: marker(B.elR, 0, -0.3, 0),
    toeL: marker(B.footL, 0, -0.07, 0.16), toeR: marker(B.footR, 0, -0.07, 0.16),
  };

  // applica una posa calcolata dall'Animator a questo rig
  B.apply = function (P, s) {
    applyPose(B, P);
    const gw = s.gazeWS || 0;
    if (gw > 0.001) {
      const yaw = (s.gazeYawS || 0) * gw, pitch = (s.gazePitchS || 0) * gw;
      B.head.rotation.y += yaw * 0.75; B.head.rotation.x -= pitch * 0.7;
      B.spine.rotation.y += yaw * 0.2;
    }
    B.eyeL.scale.y = s.eyeScale; B.eyeR.scale.y = s.eyeScale;
    if (B.photoFace) B.photoFace.jaw.rotation.x = Math.min(1.1, P.mouth) * 0.075; // la tua faccia parla
    const px = (s.pupilX || 0) + (s.gazeYawS || 0) * gw * 0.004;
    B.pupilL.position.x = px; B.pupilR.position.x = px;
  };

  // per il raycasting dei clic
  B.root.traverse(o => { o.userData.zeph = true; });

  return B;
}

// ---------- Animatore procedurale ----------
const ACTIONS = { wave: 2.2, dance: 6.0, jump: 0.95, flip: 1.15, spin: 1.5, stretch: 2.6 };

function easeInOut(u) { return u * u * (3 - 2 * u); }

function clamp01(v) { return Math.min(1, Math.max(0, v)); }
function envelope(t, dur) {
  return Math.min(1, t / 0.25) * Math.min(1, Math.max(0, (dur - t) / 0.35));
}

function newPose() {
  return {
    rootY: 0,
    body: { x: 0, y: 0, z: 0 }, spine: { x: 0, y: 0, z: 0 }, head: { x: 0, y: 0, z: 0 },
    shL: { x: 0, y: 0, z: 0.07 }, shR: { x: 0, y: 0, z: -0.07 },
    elL: { x: -0.22, z: 0 }, elR: { x: -0.22, z: 0 },
    legL: { x: 0, z: 0.025 }, legR: { x: 0, z: -0.025 },
    kneeL: 0.05, kneeR: 0.05, footL: 0, footR: 0,
    mouth: 0, brow: 0,
  };
}

// `avatar` è un oggetto con un metodo apply(P, state): il rig di Zeph
// creato da build(), oppure un driver creato da createAvatarDriver().
function Animator(avatar) {
  this.avatar = avatar;
  this.state = {
    speedRatio: 0, phase: 0,
    talking: false, talkW: 0, mouthPulse: 0, mouthSmooth: 0, gestureLead: 1,
    action: null,
    blinkAt: 2.5, blinkT: -1,
    lookYaw: 0, lookPitch: 0, lookTYaw: 0, lookTPitch: 0, nextLookAt: 2,
    eyeScale: 1, pupilX: 0, lastRootY: 0,
    flying: false, flyW: 0,
    sleeping: false, sleepW: 0,
    // sguardo verso un punto (impostato dall'host ogni frame, in radianti
    // nello spazio del personaggio) e sua versione smussata
    gazeYaw: 0, gazePitch: 0, gazeW: 0, gazeYawS: 0, gazePitchS: 0, gazeWS: 0,
    dt: 0.016,
  };
}

Animator.prototype.startAction = function (name) {
  if (ACTIONS[name]) this.state.action = { name, t: 0, dur: ACTIONS[name] };
};

Animator.prototype.update = function (t, dt) {
  const s = this.state;
  const P = newPose();
  s.dt = dt;
  const gk = Math.min(1, dt * 6);
  s.gazeYawS += (Math.max(-1.1, Math.min(1.1, s.gazeYaw || 0)) - s.gazeYawS) * gk;
  s.gazePitchS += (Math.max(-0.5, Math.min(0.5, s.gazePitch || 0)) - s.gazePitchS) * gk;
  s.gazeWS += (clamp01(s.gazeW || 0) - s.gazeWS) * Math.min(1, dt * 3);
  s.sleepW += ((s.sleeping ? 1 : 0) - s.sleepW) * Math.min(1, dt * 1.2);
  if (s.sleepW > 0.001) s.gazeWS *= 1 - s.sleepW;
  const walkW = clamp01(s.speedRatio);
  s.talkW += ((s.talking ? 1 : 0) - s.talkW) * Math.min(1, dt * 5);

  // respiro e vita da fermo
  const breath = Math.sin(t * 1.55);
  P.spine.x += 0.025 + breath * 0.013 * (1 - walkW);
  P.shL.z += breath * 0.01; P.shR.z -= breath * 0.01;
  const shift = Math.sin(t * 0.45);
  P.body.z += shift * 0.016 * (1 - walkW);
  P.spine.z -= shift * 0.016 * (1 - walkW);

  // sguardo che vaga
  if (t > s.nextLookAt) {
    s.nextLookAt = t + 2 + Math.random() * 4;
    s.lookTYaw = (Math.random() - 0.5) * 0.7;
    s.lookTPitch = (Math.random() - 0.5) * 0.25;
  }
  s.lookYaw += (s.lookTYaw - s.lookYaw) * Math.min(1, dt * 3);
  s.lookPitch += (s.lookTPitch - s.lookPitch) * Math.min(1, dt * 3);
  const lookW = (1 - s.talkW) * (1 - walkW * 0.7) * (1 - s.sleepW);
  P.head.y += s.lookYaw * lookW;
  P.head.x += s.lookPitch * lookW;
  s.pupilX = s.lookYaw * 0.012 * lookW;

  // camminata (e corsa: speedRatio > 1 allunga la falcata e piega i gomiti)
  if (walkW > 0.001) {
    const w = walkW, ph = s.phase;
    const runW = clamp01((s.speedRatio || 0) - 1);
    const swing = Math.sin(ph);
    const amp = 0.5 + 0.3 * runW;
    P.legL.x += -swing * amp * w;
    P.legR.x += swing * amp * w;
    P.kneeL += Math.max(0, Math.cos(ph + 0.7)) * (0.8 + 0.55 * runW) * w;
    P.kneeR += Math.max(0, -Math.cos(ph + 0.7)) * (0.8 + 0.55 * runW) * w;
    P.footL += (swing * 0.22 + 0.08) * w;
    P.footR += (-swing * 0.22 + 0.08) * w;
    P.shL.x += swing * (0.34 + 0.28 * runW) * w;
    P.shR.x += -swing * (0.34 + 0.28 * runW) * w;
    P.elL.x += (-0.2 + Math.max(0, swing) * -0.25 - 0.85 * runW) * w;
    P.elR.x += (-0.2 + Math.max(0, -swing) * -0.25 - 0.85 * runW) * w;
    P.rootY += (Math.abs(Math.cos(ph)) * (0.035 + 0.03 * runW) - 0.018) * w;
    P.spine.x += (0.08 + 0.16 * runW) * w;
    P.body.y += swing * 0.07 * (1 - runW * 0.5) * w;
    P.spine.y += -swing * 0.09 * w;
    P.head.x += -0.08 * runW * w; // sguardo avanti anche piegato
  }

  // parlato: testa e gesti
  const tw = s.talkW;
  if (tw > 0.001) {
    P.head.x += (Math.sin(t * 3.3) * 0.05 + Math.sin(t * 1.3) * 0.035) * tw;
    P.head.y += Math.sin(t * 1.9) * 0.09 * tw;
    P.head.z += Math.sin(t * 1.1) * 0.04 * tw;
    P.spine.y += Math.sin(t * 1.15) * 0.04 * tw;
    P.brow += 0.005 * tw;
    const actW = s.action ? envelope(s.action.t, s.action.dur) : 0;
    const gA = tw * (1 - 0.65 * walkW) * (1 - actW);
    const lead = s.gestureLead > 0;
    armGesture(P.shR, P.elR, t, -1, gA * (lead ? 1 : 0.4));
    armGesture(P.shL, P.elL, t + 1.7, 1, gA * (lead ? 0.4 : 1));
  }

  // volo col jetpack: gambe raccolte, braccia aperte, leggero ondeggiare
  s.flyW += ((s.flying ? 1 : 0) - s.flyW) * Math.min(1, dt * 3);
  if (s.flyW > 0.001) {
    const w = s.flyW;
    P.spine.x += 0.22 * w;
    P.legL.x += -0.3 * w; P.legR.x += -0.42 * w;
    P.kneeL += 0.55 * w; P.kneeR += 0.72 * w;
    P.footL += 0.3 * w; P.footR += 0.35 * w;
    P.shL.z += 0.55 * w; P.shR.z += -0.55 * w;
    P.shL.x += 0.25 * w; P.shR.x += 0.25 * w;
    P.head.x += -0.08 * w;
    P.rootY += (0.05 + Math.sin(t * 2.3) * 0.07) * w;
    P.mouth = Math.max(P.mouth, 0.2 * w);
  }

  // sonno: si siede, si accascia e ciondola la testa, respirando piano
  if (s.sleepW > 0.001) {
    const w = s.sleepW, br = Math.sin(t * 0.9);
    P.rootY += -0.52 * w;
    P.legL.x += -1.35 * w; P.legR.x += -1.3 * w;
    P.legL.z += 0.12 * w; P.legR.z += -0.12 * w;
    P.kneeL += 1.45 * w; P.kneeR += 1.4 * w;
    P.spine.x += (0.38 + br * 0.03) * w;
    P.head.x += (0.42 + br * 0.04) * w;
    P.head.z += 0.12 * w;
    P.shL.x += -0.55 * w; P.shR.x += -0.55 * w;
    P.shL.z += -0.05 * w; P.shR.z += 0.05 * w;
    P.elL.x += -0.85 * w; P.elR.x += -0.85 * w;
  }

  // bocca sincronizzata col parlato
  s.mouthPulse = Math.max(0, s.mouthPulse - dt * 5);
  let mouthTarget = 0;
  if (s.talking) {
    mouthTarget = 0.3 + 0.7 * Math.abs(Math.sin(t * 10.5) * Math.sin(t * 6.7)) + s.mouthPulse * 0.5;
  }
  s.mouthSmooth += (Math.min(1.1, mouthTarget) - s.mouthSmooth) * Math.min(1, dt * 16);
  P.mouth = s.mouthSmooth;

  // azioni speciali
  if (s.action) {
    const a = s.action;
    a.t += dt;
    if (a.t >= a.dur) s.action = null;
    else {
      const w = envelope(a.t, a.dur);
      if (a.name === 'wave') {
        P.shR.x += -0.45 * w; P.shR.z += -1.95 * w;
        P.elR.x += -0.35 * w; P.elR.z += Math.sin(t * 9.5) * 0.55 * w;
        P.head.z += 0.11 * w;
        P.mouth = Math.max(P.mouth, 0.25 * w);
      } else if (a.name === 'dance') {
        const b = t * (s.danceFreq || 6.0);
        P.body.y += Math.sin(b) * 0.38 * w;
        P.rootY += (Math.abs(Math.sin(b)) * 0.06 - 0.045) * w;
        P.legL.x += -0.14 * w; P.legR.x += -0.14 * w;
        P.kneeL += (0.28 + Math.max(0, Math.sin(b)) * 0.22) * w;
        P.kneeR += (0.28 + Math.max(0, -Math.sin(b)) * 0.22) * w;
        P.shL.z += (1.7 + Math.sin(b) * 0.7) * w;
        P.shR.z += (-1.7 + Math.sin(b) * 0.7) * w;
        P.elL.x += -0.5 * w; P.elR.x += -0.5 * w;
        P.elL.z += Math.sin(b * 2) * 0.42 * w;
        P.elR.z += Math.sin(b * 2) * 0.42 * w;
        P.head.y += Math.sin(b) * 0.2 * w;
        P.head.x += Math.sin(b * 2) * 0.06 * w;
        P.mouth = Math.max(P.mouth, (0.3 + 0.2 * Math.sin(b * 2)) * w);
      } else if (a.name === 'jump') {
        const jt = a.t / a.dur;
        let crouch = 0, air = 0;
        if (jt < 0.24) crouch = jt / 0.24;
        else if (jt < 0.74) {
          const u = (jt - 0.24) / 0.5;
          air = Math.sin(u * Math.PI);
          crouch = Math.max(0, 1 - u * 3.5);
        } else crouch = (1 - (jt - 0.74) / 0.26) * 0.55;
        P.rootY += -0.15 * crouch + 0.6 * air;
        P.kneeL += 1.0 * crouch + 0.85 * air; P.kneeR += 1.0 * crouch + 0.85 * air;
        P.legL.x += -0.5 * crouch - 0.45 * air; P.legR.x += -0.5 * crouch - 0.45 * air;
        P.footL += 0.35 * air; P.footR += 0.35 * air;
        P.spine.x += 0.24 * crouch - 0.05 * air;
        P.shL.x += 0.5 * crouch - 0.9 * air; P.shR.x += 0.5 * crouch - 0.9 * air;
        P.shL.z += 0.25 * crouch + 1.15 * air; P.shR.z += -0.25 * crouch - 1.15 * air;
        P.mouth = Math.max(P.mouth, 0.5 * air);
        s.jumpAir = air; // per l'ombra finta dell'app desktop
      } else if (a.name === 'flip') {
        // salto mortale all'indietro
        const jt = a.t / a.dur;
        let crouch = 0, air = 0;
        if (jt < 0.22) crouch = jt / 0.22;
        else if (jt < 0.8) air = Math.sin(((jt - 0.22) / 0.58) * Math.PI);
        else crouch = (1 - (jt - 0.8) / 0.2) * 0.6;
        const spinP = jt < 0.22 ? 0 : jt > 0.8 ? 1 : (jt - 0.22) / 0.58;
        P.rootY += -0.16 * crouch + 0.95 * air;
        P.body.x += -Math.PI * 2 * easeInOut(spinP);
        P.kneeL += 0.9 * crouch + 1.7 * air; P.kneeR += 0.9 * crouch + 1.7 * air;
        P.legL.x += -0.4 * crouch - 1.5 * air; P.legR.x += -0.4 * crouch - 1.5 * air;
        P.spine.x += 0.2 * crouch + 0.45 * air;
        P.shL.x += 0.5 * crouch - 1.6 * air; P.shR.x += 0.5 * crouch - 1.6 * air;
        P.mouth = Math.max(P.mouth, 0.6 * air);
        s.jumpAir = air;
      } else if (a.name === 'spin') {
        // piroetta: due giri su se stesso a braccia aperte
        const sp = a.t / a.dur;
        const A = Math.sin(sp * Math.PI);
        P.body.y += Math.PI * 4 * easeInOut(sp);
        P.rootY += -0.06 * A;
        P.kneeL += 0.3 * A; P.kneeR += 0.3 * A;
        P.shL.z += 1.5 * A; P.shR.z += -1.5 * A;
        P.elL.x += -0.2 * A; P.elR.x += -0.2 * A;
        P.head.x += -0.08 * A;
        P.mouth = Math.max(P.mouth, 0.3 * A);
      } else if (a.name === 'stretch') {
        // stiracchiata pigra con sbadiglio
        P.shL.z += 2.5 * w; P.shR.z += -2.5 * w;
        P.elL.x += -0.15 * w; P.elR.x += -0.15 * w;
        P.spine.x += -0.14 * w;
        P.spine.z += Math.sin(t * 1.4) * 0.07 * w;
        P.head.x += -0.18 * w;
        P.mouth = Math.max(P.mouth, 0.55 * w); // sbadiglio
        P.brow += 0.006 * w;
      }
    }
  }
  if (!s.action) s.jumpAir = 0;

  // sbattito di palpebre
  if (t > s.blinkAt) { s.blinkAt = t + 2 + Math.random() * 3.5; s.blinkT = 0; }
  let eyeScale = 1;
  if (s.blinkT >= 0) {
    s.blinkT += dt;
    if (s.blinkT > 0.14) s.blinkT = -1;
    else eyeScale = 0.08 + 0.92 * Math.abs(s.blinkT / 0.07 - 1);
  }
  if (s.sleepW > 0.3) eyeScale = Math.min(eyeScale, 1 - 0.92 * clamp01((s.sleepW - 0.3) / 0.5));
  s.eyeScale = eyeScale;

  s.lastRootY = P.rootY;
  this.avatar.apply(P, s);
  return P;
};

function armGesture(sh, el, t, side, w) {
  if (w <= 0) return;
  sh.x += (-0.85 + Math.sin(t * 3.7) * 0.28 + Math.sin(t * 1.3) * 0.12) * w;
  sh.z += side * -(0.3 + Math.sin(t * 2.5) * 0.16) * w;
  el.x += (-0.72 + Math.sin(t * 4.4) * 0.3) * w;
}

function applyPose(B, P) {
  B.body.position.y = HIP_Y + P.rootY;
  B.body.rotation.set(P.body.x, P.body.y, P.body.z);
  B.spine.rotation.set(P.spine.x, P.spine.y, P.spine.z);
  B.head.rotation.set(P.head.x, P.head.y, P.head.z);
  B.shL.rotation.set(P.shL.x, P.shL.y, P.shL.z);
  B.shR.rotation.set(P.shR.x, P.shR.y, P.shR.z);
  B.elL.rotation.set(P.elL.x, 0, P.elL.z);
  B.elR.rotation.set(P.elR.x, 0, P.elR.z);
  B.hipL.rotation.set(P.legL.x, 0, P.legL.z);
  B.hipR.rotation.set(P.legR.x, 0, P.legR.z);
  B.kneeL.rotation.x = P.kneeL; B.kneeR.rotation.x = P.kneeR;
  B.footL.rotation.x = P.footL - (P.legL.x + P.kneeL) * 0.55;
  B.footR.rotation.x = P.footR - (P.legR.x + P.kneeR) * 0.55;
  B.mouth.scale.set(1.15 + P.mouth * 0.2, 0.22 + P.mouth * 0.85, 0.42);
  B.mouth.position.y = 0.03 - P.mouth * 0.011;
  B.browL.position.y = 0.138 + P.brow; B.browR.position.y = 0.138 + P.brow;
}

// ---------- Driver per avatar GLB esterni (Avaturn, ReadyPlayerMe, Mixamo…) ----------
// Mappa le ossa per nome e vi trasferisce le pose procedurali di Zeph.
// Se il file contiene un'animazione (es. l'idle in motion capture di
// Avaturn) la usa come base e la fonde osso per osso con le pose
// procedurali: da fermo si muove come una persona vera, quando cammina,
// balla o gesticola subentra il movimento di Zeph.
// Braccia e gambe usano l'allineamento direzionale (funziona anche in
// T-pose); busto e testa usano delta di rotazione.
const BONE_DEFS = [
  { key: 'hips', re: /hips$|pelvis/ },
  { key: 'spine', re: /spine$/ },
  { key: 'spine1', re: /spine1$/ },
  { key: 'spine2', re: /spine2$|chest$/ },
  { key: 'neck', re: /neck$/ },
  { key: 'head', re: /head$/ },
  { key: 'jaw', re: /jaw$/ },
  { key: 'armL', re: /leftarm$|upperarml$|leftupperarm$/ },
  { key: 'forearmL', re: /leftforearm$|forearml$|lowerarml$|leftlowerarm$/ },
  { key: 'handL', re: /lefthand$|handl$/ },
  { key: 'armR', re: /rightarm$|upperarmr$|rightupperarm$/ },
  { key: 'forearmR', re: /rightforearm$|forearmr$|lowerarmr$|rightlowerarm$/ },
  { key: 'handR', re: /righthand$|handr$/ },
  { key: 'uplegL', re: /leftupleg$|thighl$|uplegl$|leftthigh$|leftupperleg$/ },
  { key: 'legL', re: /leftleg$|calfl$|shinl$|lowerlegl$|leftlowerleg$/ },
  { key: 'footL', re: /leftfoot$|footl$/ },
  { key: 'toeL', re: /lefttoebase$|toebasel$|lefttoe$|toel$/ },
  { key: 'uplegR', re: /rightupleg$|thighr$|uplegr$|rightthigh$|rightupperleg$/ },
  { key: 'legR', re: /rightleg$|calfr$|shinr$|lowerlegr$|rightlowerleg$/ },
  { key: 'footR', re: /rightfoot$|footr$/ },
  { key: 'toeR', re: /righttoebase$|toebaser$|righttoe$|toer$/ },
];

function normName(n) { return (n || '').toLowerCase().replace(/[^a-z0-9]/g, ''); }
function smooth01(a, b, x) {
  const u = clamp01((x - a) / (b - a));
  return u * u * (3 - 2 * u);
}

function findBones(avatarScene) {
  const bones = {};
  avatarScene.traverse(o => {
    if (!o.name) return;
    const n = normName(o.name);
    for (const d of BONE_DEFS) {
      if (!bones[d.key] && d.re.test(n)) { bones[d.key] = o; break; }
    }
  });
  return bones;
}

function headWeight(si, sw, i, hi) {
  let w = 0;
  if (si.getX(i) === hi) w += sw.getX(i);
  if (si.getY(i) === hi) w += sw.getY(i);
  if (si.getZ(i) === hi) w += sw.getZ(i);
  if (si.getW(i) === hi) w += sw.getW(i);
  return w;
}

// Bocca procedurale per avatar senza blendshape né osso della mascella:
// trova naso e fessura delle labbra sul profilo del viso e crea un morph
// che ruota la parte bassa del volto attorno al perno della mandibola.
// Va chiamata sulla scena in posa di riposo, prima di scalarla.
function buildJawMorph(THREE, avatarScene, headBone) {
  avatarScene.updateMatrixWorld(true);
  const headPos = new THREE.Vector3();
  headBone.getWorldPosition(headPos);
  const v = new THREE.Vector3();

  // la mesh della pelle: quella con più vertici della testa davanti al viso
  let best = null, bestScore = 0;
  avatarScene.traverse(o => {
    if (!o.isSkinnedMesh || !o.geometry.attributes.skinIndex) return;
    if (o.geometry.morphAttributes && o.geometry.morphAttributes.position) return;
    const hi = o.skeleton.bones.indexOf(headBone);
    if (hi < 0) return;
    const pos = o.geometry.attributes.position;
    const si = o.geometry.attributes.skinIndex, sw = o.geometry.attributes.skinWeight;
    let score = 0;
    for (let i = 0; i < pos.count; i++) {
      if (headWeight(si, sw, i, hi) < 0.5) continue;
      v.fromBufferAttribute(pos, i).applyMatrix4(o.matrixWorld);
      if (Math.abs(v.x - headPos.x) < 0.03 && v.z > headPos.z + 0.06) score++;
    }
    if (/body|skin|head|face/i.test(o.name)) score *= 1.5;
    if (score > bestScore) { bestScore = score; best = { mesh: o, hi }; }
  });
  if (!best || bestScore < 40) return null;

  const mesh = best.mesh, geo = mesh.geometry, hi = best.hi;
  const pos = geo.attributes.position;
  const si = geo.attributes.skinIndex, sw = geo.attributes.skinWeight;
  const N = pos.count;
  const wp = new Float32Array(N * 3), hw = new Float32Array(N);
  let nose = null;
  for (let i = 0; i < N; i++) {
    v.fromBufferAttribute(pos, i).applyMatrix4(mesh.matrixWorld);
    wp[i * 3] = v.x - headPos.x; wp[i * 3 + 1] = v.y; wp[i * 3 + 2] = v.z;
    hw[i] = headWeight(si, sw, i, hi);
    if (hw[i] > 0.5 && Math.abs(v.x - headPos.x) < 0.015 && (!nose || v.z > nose.z)) nose = { y: v.y, z: v.z };
  }
  if (!nose || nose.z < headPos.z + 0.05) return null;

  // profilo frontale in mezzeria sotto il naso (il punto più avanzato per fascia)
  function profile(res, yTop, yBot) {
    const bins = {};
    for (let i = 0; i < N; i++) {
      const x = wp[i * 3], y = wp[i * 3 + 1], z = wp[i * 3 + 2];
      if (Math.abs(x) > 0.006 || y > yTop || y < yBot) continue;
      const k = Math.round(y * res);
      if (bins[k] === undefined || z > bins[k]) bins[k] = z;
    }
    return Object.keys(bins).map(Number).sort((a, b) => b - a).map(k => ({ y: k / res, z: bins[k] }));
  }
  // scendendo dal naso: subnasale (avvallamento), labbro superiore (sporgenza),
  // poi il primo avvallamento successivo è la fessura tra le labbra
  const prof = profile(400, nose.y - 0.008, nose.y - 0.06);
  if (prof.length < 8) return null;
  let iSub = -1, iUp = -1, iSeam = -1;
  for (let i = 0; i < prof.length; i++) {
    if (prof[i].y > nose.y - 0.01 || prof[i].y < nose.y - 0.032) continue;
    if (iSub < 0 || prof[i].z < prof[iSub].z) iSub = i;
  }
  if (iSub < 0) return null;
  for (let i = iSub; i < prof.length && prof[i].y > prof[iSub].y - 0.022; i++) {
    if (iUp < 0 || prof[i].z > prof[iUp].z) iUp = i;
  }
  for (let i = iUp + 1; i < prof.length - 1; i++) {
    if (prof[i + 1].z > prof[i].z + 0.0001) { iSeam = i; break; }
  }
  if (iUp < 0 || iSeam < 0) return null;
  // rifinitura: i vertici più profondi del solco sono i bordi interni di
  // entrambe le labbra, quindi la loro altezza media cade proprio nel mezzo
  const groove = [];
  for (let i = 0; i < N; i++) {
    const x = wp[i * 3], y = wp[i * 3 + 1], z = wp[i * 3 + 2];
    if (Math.abs(x) < 0.008 && Math.abs(y - prof[iSeam].y) < 0.003 && z > prof[iSeam].z - 0.012) groove.push({ y, z });
  }
  groove.sort((a, b) => a.z - b.z);
  const deep = groove.slice(0, Math.min(6, groove.length));
  const seamY = deep.length ? deep.reduce((acc, g) => acc + g.y, 0) / deep.length : prof[iSeam].y;

  const hingeY = nose.y - 0.024, hingeZ = nose.z - 0.112;
  const ANG = 0.095; // apertura massima (rad): ~9 mm tra le labbra
  const c = Math.cos(ANG), s = Math.sin(ANG);
  const inv = new THREE.Matrix4().copy(mesh.matrixWorld).invert();
  const delta = new Float32Array(N * 3);
  const p = new THREE.Vector3(), q = new THREE.Vector3();
  let moved = 0;
  for (let i = 0; i < N; i++) {
    if (hw[i] < 0.05) continue;
    const x = wp[i * 3], y = wp[i * 3 + 1], z = wp[i * 3 + 2];
    const ax = Math.abs(x);
    // netto sulle labbra, morbido su guance e mento per non tagliare il viso
    const lateral = smooth01(0.016, 0.032, ax);
    const top = seamY + 0.00012 + lateral * 0.027;
    const bot = seamY - 0.00012 - lateral * 0.007;
    const wy = 1 - smooth01(bot, top, y);
    const wz = smooth01(hingeZ - 0.015, hingeZ + 0.02, z);
    const wx = 1 - smooth01(0.055, 0.075, ax);
    const w = wy * wz * wx * hw[i];
    if (w < 0.001) continue;
    const ry = y - hingeY, rz = z - hingeZ;
    const ny = hingeY + ry * c - rz * s, nz = hingeZ + ry * s + rz * c;
    p.set(x + headPos.x, y, z).applyMatrix4(inv);
    q.set(x + headPos.x, y + (ny - y) * w, z + (nz - z) * w).applyMatrix4(inv);
    delta[i * 3] = q.x - p.x; delta[i * 3 + 1] = q.y - p.y; delta[i * 3 + 2] = q.z - p.z;
    moved++;
  }
  if (moved < 20) return null;

  const attr = new THREE.Float32BufferAttribute(delta, 3);
  attr.name = 'zephJawOpen';
  geo.morphAttributes.position = [attr];
  geo.morphTargetsRelative = true;
  mesh.updateMorphTargets();

  // le labbra sono "cucite" da una striscia di triangoli sottili nel solco:
  // la tagliamo, così la bocca si apre davvero invece di stirarsi
  let cut = 0;
  if (geo.index) {
    const idx = geo.index.array, keep = [];
    const lipZ = deep.length ? deep[deep.length - 1].z : nose.z - 0.02;
    for (let f = 0; f < idx.length; f += 3) {
      const a = idx[f], b = idx[f + 1], cc = idx[f + 2];
      const ya = wp[a * 3 + 1], yb = wp[b * 3 + 1], yc = wp[cc * 3 + 1];
      const lo = Math.min(ya, yb, yc), hi2 = Math.max(ya, yb, yc);
      const cx = (wp[a * 3] + wp[b * 3] + wp[cc * 3]) / 3;
      const zmax = Math.max(wp[a * 3 + 2], wp[b * 3 + 2], wp[cc * 3 + 2]);
      const inGroove = lo < seamY && hi2 > seamY && hi2 - lo < 0.0045 &&
        Math.abs(cx) < 0.021 && zmax > lipZ - 0.012;
      if (inGroove) { cut++; continue; }
      keep.push(a, b, cc);
    }
    if (cut > 0 && cut < 200) geo.setIndex(keep);
    else cut = 0;
  }

  // dietro le labbra: cavità scura e denti superiori, agganciati alla testa
  let teeth = null;
  if (cut) {
    const hq = headBone.getWorldQuaternion(new THREE.Quaternion());
    const hs = headBone.getWorldScale(new THREE.Vector3());
    const lipFront = deep.length ? deep[0].z : nose.z - 0.02;
    function attach(obj, x, y, z) {
      const lp = headBone.worldToLocal(new THREE.Vector3(x, y, z));
      obj.position.copy(lp);
      obj.quaternion.copy(hq).invert();
      obj.scale.set(1 / hs.x, 1 / hs.y, 1 / hs.z);
      obj.frustumCulled = false;
      headBone.add(obj);
    }
    const cavity = new THREE.Mesh(new THREE.SphereGeometry(1, 18, 12),
      new THREE.MeshBasicMaterial({ color: 0x1a0b0b }));
    cavity.geometry.scale(0.031, 0.015, 0.016);
    attach(cavity, headPos.x, seamY - 0.004, lipFront - 0.021);
    const teethGeo = new THREE.CylinderGeometry(0.018, 0.018, 0.0062, 20, 1, true, -0.66, 1.32);
    teeth = new THREE.Mesh(teethGeo,
      new THREE.MeshStandardMaterial({ color: 0xcdc4b2, roughness: 0.5, side: THREE.DoubleSide }));
    teeth.name = 'zephTeeth';
    teeth.visible = false;
    attach(teeth, headPos.x, seamY + 0.0042, lipFront - 0.025);
  }
  return { m: mesh, i: mesh.morphTargetDictionary.zephJawOpen || 0, seamY, moved, cut, teeth };
}

// Dita leggermente piegate (per gli avatar senza animazione propria):
// ogni falange ruota verso il palmo attorno a un asse calcolato a riposo.
function relaxFingers(THREE, avatarScene) {
  avatarScene.updateMatrixWorld(true);
  const byName = {};
  avatarScene.traverse(o => { if (o.name) byName[normName(o.name)] = o; });
  const wp = o => o.getWorldPosition(new THREE.Vector3());
  const CURL = { thumb: [0.12, 0.18, 0.14], index: [0.22, 0.38, 0.26], middle: [0.26, 0.42, 0.28], ring: [0.3, 0.46, 0.3], pinky: [0.34, 0.5, 0.32] };
  let count = 0;
  for (const side of ['left', 'right']) {
    const hand = byName[side + 'hand'], mid = byName[side + 'handmiddle1'];
    const idx = byName[side + 'handindex1'], pky = byName[side + 'handpinky1'];
    if (!hand || !mid || !idx || !pky) continue;
    const dir = wp(mid).sub(wp(hand)).normalize();
    const across = wp(idx).sub(wp(pky)).normalize();
    const palm = side === 'left' ? dir.clone().cross(across) : across.clone().cross(dir);
    palm.normalize();
    for (const f in CURL) {
      for (let j = 1; j <= 3; j++) {
        const b = byName[side + 'hand' + f + j];
        if (!b) continue;
        const nxt = byName[side + 'hand' + f + (j + 1)];
        const fdir = nxt ? wp(nxt).sub(wp(b)).normalize() : dir.clone();
        const axis = fdir.clone().cross(palm);
        if (axis.lengthSq() < 1e-6) continue;
        axis.normalize();
        const wq = b.getWorldQuaternion(new THREE.Quaternion()).invert();
        axis.applyQuaternion(wq).normalize();
        b.quaternion.multiply(new THREE.Quaternion().setFromAxisAngle(axis, CURL[f][j - 1]));
        count++;
      }
    }
  }
  return count;
}

function createAvatarDriver(THREE, avatarScene, opts) {
  opts = opts || {};
  const height = opts.height || 1.75;

  // ossa, bocca e dita si analizzano in posa di riposo, prima di scalare
  avatarScene.updateMatrixWorld(true);
  const bones = findBones(avatarScene);
  const need = ['hips', 'armL', 'forearmL', 'armR', 'forearmR', 'uplegL', 'legL', 'uplegR', 'legR'];
  const hasRig = need.every(kk => bones[kk]);
  const clips = (opts.animations || []).filter(c => c && c.tracks && c.tracks.length);

  // --- morph facciali (bocca e palpebre), se presenti ---
  const mouthMorphs = [], blinkMorphs = [];
  avatarScene.traverse(o => {
    if (o.morphTargetDictionary && o.morphTargetInfluences) {
      for (const key in o.morphTargetDictionary) {
        const kn = normName(key);
        if (/mouthopen|jawopen|visemeaa/.test(kn)) mouthMorphs.push({ m: o, i: o.morphTargetDictionary[key] });
        else if (/blink|eyesclosed/.test(kn)) blinkMorphs.push({ m: o, i: o.morphTargetDictionary[key] });
      }
    }
  });
  let jaw = null;
  if (!mouthMorphs.length && !bones.jaw && bones.head && opts.autoJaw !== false) {
    try { jaw = buildJawMorph(THREE, avatarScene, bones.head); } catch (e) { jaw = null; }
    if (jaw) mouthMorphs.push(jaw);
  }
  let fingersRelaxed = 0;
  if (hasRig && !clips.length) fingersRelaxed = relaxFingers(THREE, avatarScene);

  const root = new THREE.Group();
  const inner = new THREE.Group();
  root.add(inner); inner.add(avatarScene);

  avatarScene.updateMatrixWorld(true);
  const bbox = new THREE.Box3().setFromObject(avatarScene);
  const rawH = Math.max(0.01, bbox.max.y - bbox.min.y);
  const k = height / rawH;
  inner.scale.setScalar(k);
  const baseY = -bbox.min.y * k;
  inner.position.y = baseY;

  // ombre, niente culling (le ossa spostano la mesh) e texture più nitide
  const aniso = opts.anisotropy || 1;
  avatarScene.traverse(o => {
    if (!o.isMesh && !o.isSkinnedMesh) return;
    o.castShadow = true; o.receiveShadow = true; o.frustumCulled = false;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    for (const m of mats) {
      if (!m) continue;
      for (const t of ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'aoMap']) {
        if (m[t] && aniso > 1) { m[t].anisotropy = aniso; m[t].needsUpdate = true; }
      }
    }
  });

  const blinkGain = 1.1;
  function applyMorphs(P, s) {
    const open = Math.min(1, P.mouth * 0.85);
    for (const mm of mouthMorphs) mm.m.morphTargetInfluences[mm.i] = open;
    // i denti si vedono solo a bocca aperta (chiusa resta la linea scura)
    if (jaw && jaw.teeth) jaw.teeth.visible = open > 0.12;
    const blink = Math.min(1, Math.max(0, (1 - s.eyeScale) * blinkGain));
    for (const bm of blinkMorphs) bm.m.morphTargetInfluences[bm.i] = blink;
  }

  const driver = {
    root, inner, bones, hasRig, isAvatarDriver: true,
    hasMocap: false, mocapName: null, hasJaw: !!jaw,
    faceMorphs: mouthMorphs.length + blinkMorphs.length, fingersRelaxed,
    jawInfo: jaw ? { seamY: jaw.seamY, moved: jaw.moved, cut: jaw.cut } : null,
  };

  let mixer = null;
  function startMocap() {
    if (!clips.length) return;
    const clip = clips.find(c => /idle/i.test(c.name)) || clips[0];
    mixer = new THREE.AnimationMixer(avatarScene);
    mixer.clipAction(clip).play();
    driver.hasMocap = true;
    driver.mocapName = clip.name;
  }

  if (!hasRig) {
    // niente scheletro riconoscibile: modalità "statuetta" (dondola e salta)
    startMocap();
    driver.apply = function (P, s) {
      if (mixer) mixer.update(Math.min(0.1, s.dt || 0.016));
      inner.position.y = baseY + P.rootY;
      inner.rotation.x = P.spine.x * 0.4;
      inner.rotation.z = P.body.z * 0.6;
      inner.rotation.y = P.body.y * 0.5;
      applyMorphs(P, s);
    };
    return driver;
  }

  // rig di riferimento invisibile: genera le pose da copiare
  const ref = build(THREE);
  ref.root.updateMatrixWorld(true);

  // dati di riposo per ogni osso mappato (prima che parta il mocap)
  avatarScene.updateMatrixWorld(true);
  const rest = new Map();
  const qw = new THREE.Quaternion();
  for (const kk in bones) {
    const b = bones[kk];
    b.getWorldQuaternion(qw);
    rest.set(b, { local: b.quaternion.clone(), worldInv: qw.clone().invert() });
  }

  // direzione (nel sistema locale a riposo dell'osso) verso l'articolazione figlia
  const vtmp = new THREE.Vector3(), vtmp2 = new THREE.Vector3();
  function restDir(boneKey, childKey) {
    const b = bones[boneKey], c = bones[childKey];
    if (!b || !c) return null;
    b.getWorldPosition(vtmp); c.getWorldPosition(vtmp2);
    const d = vtmp2.sub(vtmp);
    if (d.lengthSq() < 1e-8) return null;
    return d.applyQuaternion(rest.get(b).worldInv).normalize().clone();
  }
  const segs = [
    ['armL', 'forearmL'], ['forearmL', 'handL'],
    ['armR', 'forearmR'], ['forearmR', 'handR'],
    ['uplegL', 'legL'], ['legL', 'footL'], ['footL', 'toeL'],
    ['uplegR', 'legR'], ['legR', 'footR'], ['footR', 'toeR'],
  ];
  const dirs = {};
  for (const sg of segs) dirs[sg[0]] = restDir(sg[0], sg[1]);
  // se manca la mano/punta, assumiamo il proseguimento dell'osso precedente
  if (!dirs.forearmL && dirs.armL) dirs.forearmL = dirs.armL.clone();
  if (!dirs.forearmR && dirs.armR) dirs.forearmR = dirs.armR.clone();
  if (!dirs.legL && dirs.uplegL) dirs.legL = dirs.uplegL.clone();
  if (!dirs.legR && dirs.uplegR) dirs.legR = dirs.uplegR.clone();

  startMocap();
  const mocapQ = new Map();
  if (mixer) for (const kk in bones) mocapQ.set(bones[kk], new THREE.Quaternion());

  const q1 = new THREE.Quaternion(), q2 = new THREE.Quaternion(),
        q3 = new THREE.Quaternion(), q4 = new THREE.Quaternion(),
        qRoot = new THREE.Quaternion(), qRootInv = new THREE.Quaternion();
  const e1 = new THREE.Euler();
  const va = new THREE.Vector3(), vb = new THREE.Vector3();
  const qa = new THREE.Quaternion(), qb = new THREE.Quaternion();
  const want = new THREE.Vector3(), cur = new THREE.Vector3();
  // asse "davanti" della testa, nel suo sistema locale a riposo
  const headFwd = bones.head ? new THREE.Vector3(0, 0, 1).applyQuaternion(rest.get(bones.head).worldInv).normalize() : null;

  // ruota l'osso in modo che il suo segmento punti come dirChar (spazio personaggio)
  function alignBone(boneKey, dirChar) {
    const b = bones[boneKey], localDir = dirs[boneKey];
    if (!b || !localDir) return;
    const r = rest.get(b);
    const pW = b.parent.getWorldQuaternion(q1);
    va.copy(localDir).applyQuaternion(q2.copy(pW).multiply(r.local)).normalize();
    vb.copy(dirChar).applyQuaternion(qRoot).normalize();
    q3.setFromUnitVectors(va, vb);
    b.quaternion.copy(q4.copy(pW).invert()).multiply(q3).multiply(pW).multiply(r.local);
  }
  // rotazione (euler, spazio personaggio) sopra la posa di riposo
  function rotateBone(boneKey, ex, ey, ez) {
    const b = bones[boneKey];
    if (!b) return;
    const base = q2.copy(rest.get(b).local);
    const pW = b.parent.getWorldQuaternion(q1);
    q4.setFromEuler(e1.set(ex, ey, ez, 'XYZ'));
    q3.copy(qRoot).multiply(q4).multiply(qRootInv);
    b.quaternion.copy(q4.copy(pW).invert()).multiply(q3).multiply(pW).multiply(base);
  }
  // gira l'osso (collo o testa) perché il viso punti verso wantWorld, per una frazione w
  function aimBone(boneKey, wantWorld, w) {
    const b = bones[boneKey];
    if (!b || !headFwd) return;
    cur.copy(headFwd).applyQuaternion(bones.head.getWorldQuaternion(qa)).normalize();
    q3.setFromUnitVectors(cur, wantWorld);
    q4.identity().slerp(q3, w);
    const pW = b.parent.getWorldQuaternion(q1);
    qb.copy(pW).invert().multiply(q4).multiply(pW).multiply(b.quaternion);
    b.quaternion.copy(qb);
  }
  // fonde la posa procedurale appena calcolata con quella del mocap
  function mix(boneKey, w) {
    const b = bones[boneKey];
    if (!b || !mixer || w >= 0.999) return;
    b.quaternion.slerp(mocapQ.get(b), 1 - w);
  }

  // pesi per distribuire la rotazione del busto sulle ossa disponibili
  const spineChain = ['spine', 'spine1', 'spine2'].filter(kk => bones[kk]);
  const spineW = spineChain.length === 3 ? [0.45, 0.3, 0.25]
    : spineChain.length === 2 ? [0.6, 0.4]
    : spineChain.length === 1 ? [1] : [];

  // posizioni delle articolazioni del rig di riferimento (vettori riusati)
  const J = {};
  function jp(name, obj) { return obj.getWorldPosition(J[name] || (J[name] = new THREE.Vector3())); }
  const seg = new THREE.Vector3();
  function limb(boneKey, fromObj, toObj, w) {
    seg.copy(jp(boneKey + 'b', toObj)).sub(jp(boneKey + 'a', fromObj));
    alignBone(boneKey, seg);
    mix(boneKey, w);
  }

  driver.apply = function (P, s) {
    // 0. motion capture: il mixer mette la posa "vera", che poi fondiamo
    if (mixer) {
      mixer.update(Math.min(0.1, s.dt || 0.016));
      for (const [b, q] of mocapQ) q.copy(b.quaternion);
    }

    // 1. aggiorna il rig di riferimento (in spazio personaggio: root identità)
    ref.apply(P, s);
    ref.root.updateMatrixWorld(true);
    root.getWorldQuaternion(qRoot);
    qRootInv.copy(qRoot).invert();

    // quanto conta la posa procedurale per ogni parte del corpo
    const a = s.action;
    const actW = a ? envelope(a.t, a.dur) : 0;
    const waveW = a && a.name === 'wave' ? actW : 0;
    const fullW = a && a.name !== 'wave' ? actW : 0;
    const talkW = s.talkW || 0;
    const pBody = mixer ? Math.max(clamp01(s.speedRatio || 0), fullW, s.flyW || 0, s.sleepW || 0) : 1;
    const pArmL = mixer ? Math.max(pBody, talkW * 0.9) : 1;
    const pArmR = mixer ? Math.max(pArmL, waveW) : 1;
    const pHead = mixer ? Math.max(pBody, talkW * 0.55, waveW * 0.3) : 1;

    // 2. bacino e busto
    rotateBone('hips', P.body.x, P.body.y, P.body.z); mix('hips', pBody);
    for (let i = 0; i < spineChain.length; i++) {
      const f = spineW[i];
      rotateBone(spineChain[i], P.spine.x * f, P.spine.y * f, P.spine.z * f);
      mix(spineChain[i], pBody);
    }
    if (bones.neck) {
      rotateBone('neck', P.head.x * 0.35, P.head.y * 0.35, P.head.z * 0.35); mix('neck', pHead);
      rotateBone('head', P.head.x * 0.65, P.head.y * 0.65, P.head.z * 0.65); mix('head', pHead);
    } else {
      rotateBone('head', P.head.x, P.head.y, P.head.z); mix('head', pHead);
    }
    if (bones.jaw && !mouthMorphs.length) rotateBone('jaw', P.mouth * 0.3, 0, 0);

    // 3. arti per allineamento direzionale (robusto anche in T-pose)
    const M = ref.markers;
    limb('armL', ref.shL, ref.elL, pArmL);
    limb('forearmL', ref.elL, M.wristL, pArmL);
    limb('armR', ref.shR, ref.elR, pArmR);
    limb('forearmR', ref.elR, M.wristR, pArmR);
    limb('uplegL', ref.hipL, ref.kneeL, pBody);
    limb('legL', ref.kneeL, ref.footL, pBody);
    limb('footL', ref.footL, M.toeL, pBody);
    limb('uplegR', ref.hipR, ref.kneeR, pBody);
    limb('legR', ref.kneeR, ref.footR, pBody);
    limb('footR', ref.footR, M.toeR, pBody);

    // 4. sguardo: il viso MIRA il punto indicato dall'host (camera o mouse),
    //    qualunque cosa stia facendo il mocap; il collo fa il 40% del lavoro
    const gw = s.gazeWS || 0;
    if (gw > 0.001 && headFwd) {
      const yaw = s.gazeYawS || 0, pitch = s.gazePitchS || 0;
      want.set(Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), Math.cos(yaw) * Math.cos(pitch))
        .applyQuaternion(qRoot).normalize();
      if (bones.neck) aimBone('neck', want, gw * 0.4);
      aimBone('head', want, gw);
    }

    // 5. saltelli/molleggio e faccia
    inner.position.y = baseY + P.rootY;
    applyMorphs(P, s);
  };

  return driver;
}

// ---------- Rocky, il cane compagno ----------
function buildDog(THREE) {
  function mat(c, r) { return new THREE.MeshStandardMaterial({ color: c, roughness: r || 0.9 }); }
  const fur = mat(0xb9884f), dark = mat(0x6e4a28), cream = mat(0xe8d3ac),
        black = mat(0x241d15, 0.5), red = mat(0xc0392b, 0.7);
  function sph(r, m, sx, sy, sz) {
    const s = new THREE.Mesh(new THREE.SphereGeometry(r, 14, 10), m);
    s.scale.set(sx || 1, sy || 1, sz || 1); s.castShadow = true; return s;
  }
  const D = { root: new THREE.Group() };

  D.body = new THREE.Group(); D.body.position.y = 0.26; D.root.add(D.body);
  const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.085, 0.2, 5, 12), fur);
  torso.rotation.x = Math.PI / 2; torso.castShadow = true;
  D.body.add(torso);
  const belly = sph(0.075, cream, 1, 0.8, 1.3); belly.position.set(0, -0.03, 0.02); D.body.add(belly);

  D.head = new THREE.Group(); D.head.position.set(0, 0.1, 0.19); D.body.add(D.head);
  const skull = sph(0.07, fur); D.head.add(skull);
  const snout = sph(0.035, cream, 0.85, 0.7, 1.25); snout.position.set(0, -0.015, 0.07); D.head.add(snout);
  const nose = sph(0.015, black); nose.position.set(0, 0, 0.115); D.head.add(nose);
  const eyeL = sph(0.012, black); eyeL.position.set(0.033, 0.025, 0.055);
  const eyeR = eyeL.clone(); eyeR.position.x = -0.033;
  D.head.add(eyeL, eyeR);
  const earL = sph(0.03, dark, 0.55, 1, 0.35); earL.position.set(0.045, 0.065, -0.005); earL.rotation.z = 0.3;
  const earR = earL.clone(); earR.position.x = -0.045; earR.rotation.z = -0.3;
  D.head.add(earL, earR);
  const collar = new THREE.Mesh(new THREE.TorusGeometry(0.052, 0.012, 6, 14), red);
  collar.position.set(0, -0.055, -0.01); collar.rotation.x = Math.PI / 2 - 0.35;
  D.head.add(collar);

  D.tail = new THREE.Group(); D.tail.position.set(0, 0.07, -0.19); D.body.add(D.tail);
  const tailM = new THREE.Mesh(new THREE.CapsuleGeometry(0.015, 0.1, 4, 8), fur);
  tailM.position.set(0, 0.05, -0.03); tailM.rotation.x = 0.55; tailM.castShadow = true;
  D.tail.add(tailM);

  function leg(x, z) {
    const g = new THREE.Group(); g.position.set(x, -0.02, z); D.body.add(g);
    const l = new THREE.Mesh(new THREE.CapsuleGeometry(0.019, 0.15, 4, 8), fur);
    l.position.y = -0.1; l.castShadow = true; g.add(l);
    const paw = sph(0.023, cream, 1, 0.7, 1.2); paw.position.set(0, -0.2, 0.008); g.add(paw);
    return g;
  }
  D.legFL = leg(0.055, 0.11); D.legFR = leg(-0.055, 0.11);
  D.legBL = leg(0.055, -0.11); D.legBR = leg(-0.055, -0.11);

  return D;
}

// st: { speedRatio, phase, excited }
function updateDog(D, t, dt, st) {
  const w = clamp01(st.speedRatio || 0), ph = st.phase || 0;
  const sw = Math.sin(ph) * 0.65 * w;
  D.legFL.rotation.x = sw; D.legBR.rotation.x = sw;
  D.legFR.rotation.x = -sw; D.legBL.rotation.x = -sw;
  D.body.position.y = 0.26 + Math.abs(Math.cos(ph)) * 0.028 * w;
  D.body.rotation.x = Math.sin(ph) * 0.04 * w;
  const exc = st.excited ? 1 : 0;
  D.tail.rotation.y = Math.sin(t * (7 + exc * 7)) * (0.45 + 0.3 * exc);
  D.head.rotation.x = -0.05 + Math.sin(t * 1.3) * 0.06 + 0.1 * w;
  D.head.rotation.z = Math.sin(t * 2.7) * 0.1 * exc;
  D.head.rotation.y = Math.sin(t * 0.7) * 0.15 * (1 - w);
}

// campanellino per le stelle raccolte
let barkCtx = null;
function chime() {
  try {
    barkCtx = barkCtx || new (window.AudioContext || window.webkitAudioContext)();
    if (barkCtx.state === 'suspended') barkCtx.resume();
    const t0 = barkCtx.currentTime + 0.02;
    [659, 880].forEach((f, i) => {
      const o = barkCtx.createOscillator(), g = barkCtx.createGain();
      o.type = 'sine';
      o.frequency.setValueAtTime(f, t0 + i * 0.09);
      g.gain.setValueAtTime(0.14, t0 + i * 0.09);
      g.gain.exponentialRampToValueAtTime(0.001, t0 + i * 0.09 + 0.25);
      o.connect(g); g.connect(barkCtx.destination);
      o.start(t0 + i * 0.09); o.stop(t0 + i * 0.09 + 0.27);
    });
  } catch (e) { /* niente audio */ }
}

// botto dei fuochi d'artificio
function boom() {
  try {
    barkCtx = barkCtx || new (window.AudioContext || window.webkitAudioContext)();
    if (barkCtx.state === 'suspended') barkCtx.resume();
    const c = barkCtx, t0 = c.currentTime + 0.02;
    const len = Math.floor(c.sampleRate * 0.45);
    const buf = c.createBuffer(1, len, c.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 2.2);
    const src = c.createBufferSource(); src.buffer = buf;
    const lp = c.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 700;
    const g = c.createGain(); g.gain.setValueAtTime(0.3, t0);
    src.connect(lp); lp.connect(g); g.connect(c.destination);
    src.start(t0);
    const o = c.createOscillator(), g2 = c.createGain();
    o.type = 'sine';
    o.frequency.setValueAtTime(130, t0);
    o.frequency.exponentialRampToValueAtTime(42, t0 + 0.4);
    g2.gain.setValueAtTime(0.22, t0);
    g2.gain.exponentialRampToValueAtTime(0.001, t0 + 0.42);
    o.connect(g2); g2.connect(c.destination);
    o.start(t0); o.stop(t0 + 0.44);
  } catch (e) { /* niente audio */ }
}

// suoni d'ambiente: uccellini di giorno, grilli di notte, vento leggero
const ambience = (function () {
  let running = false, mode = null, timers = [], windSrc = null, windGain = null;
  function ac() {
    barkCtx = barkCtx || new (window.AudioContext || window.webkitAudioContext)();
    if (barkCtx.state === 'suspended') barkCtx.resume();
    return barkCtx;
  }
  function tone(f0, f1, dur, vol, t0, type) {
    const c = ac();
    const o = c.createOscillator(), g = c.createGain();
    o.type = type || 'sine';
    o.frequency.setValueAtTime(f0, t0);
    if (f1) o.frequency.exponentialRampToValueAtTime(f1, t0 + dur);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(vol, t0 + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o.connect(g); g.connect(c.destination);
    o.start(t0); o.stop(t0 + dur + 0.03);
  }
  function birdLoop() {
    if (!running || mode !== 'day') return;
    try {
      const c = ac(), t0 = c.currentTime + 0.05;
      const f = 2100 + Math.random() * 1900;
      const n = 2 + (Math.random() * 3 | 0);
      for (let i = 0; i < n; i++) tone(f * (0.94 + Math.random() * 0.12), f * 1.3, 0.11, 0.028, t0 + i * 0.16);
    } catch (e) {}
    timers.push(setTimeout(birdLoop, 2500 + Math.random() * 6000));
  }
  function cricketLoop() {
    if (!running || mode !== 'night') return;
    try {
      const c = ac(), t0 = c.currentTime + 0.05;
      for (let i = 0; i < 3; i++) tone(4300, 0, 0.035, 0.016, t0 + i * 0.09, 'triangle');
    } catch (e) {}
    timers.push(setTimeout(cricketLoop, 900 + Math.random() * 900));
  }
  function startWind() {
    try {
      const c = ac();
      const len = c.sampleRate * 2;
      const buf = c.createBuffer(1, len, c.sampleRate);
      const d = buf.getChannelData(0);
      let v = 0;
      for (let i = 0; i < len; i++) { v = v * 0.98 + (Math.random() * 2 - 1) * 0.02; d[i] = v * 3; }
      windSrc = c.createBufferSource(); windSrc.buffer = buf; windSrc.loop = true;
      const lp = c.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 380;
      windGain = c.createGain(); windGain.gain.value = 0.012;
      windSrc.connect(lp); lp.connect(windGain); windGain.connect(c.destination);
      windSrc.start();
    } catch (e) { windSrc = null; }
  }
  return {
    setMode(m) {
      if (running && mode === m) return;
      this.stop();
      mode = m; running = true;
      if (!windSrc) startWind();
      if (m === 'day') birdLoop(); else cricketLoop();
    },
    stop() {
      running = false;
      timers.forEach(clearTimeout); timers = [];
      if (windSrc) { try { windSrc.stop(); } catch (e) {} windSrc = null; windGain = null; }
    },
  };
})();

// musica chiptune generata al volo (126 BPM, nessun file audio)
const music = (function () {
  let ctx = null, timer = null, playing = false, step = 0, nextTime = 0;
  const BPM = 126, STEP = 60 / BPM / 4;
  const bassSeq = [110, 0, 110, 0, 131, 0, 98, 0, 110, 0, 110, 0, 165, 0, 147, 0];
  const leadSeq = [440, 523, 659, 880, 659, 523, 440, 392, 440, 523, 659, 784, 659, 523, 494, 392];
  function voice(type, f0, f1, t0, dur, vol) {
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type = type;
    o.frequency.setValueAtTime(f0, t0);
    if (f1) o.frequency.exponentialRampToValueAtTime(f1, t0 + dur);
    g.gain.setValueAtTime(vol, t0);
    g.gain.exponentialRampToValueAtTime(0.001, t0 + dur);
    o.connect(g); g.connect(ctx.destination);
    o.start(t0); o.stop(t0 + dur + 0.02);
  }
  function schedule() {
    if (!playing) return;
    while (nextTime < ctx.currentTime + 0.12) {
      const s16 = step % 16;
      if (s16 % 4 === 0) voice('sine', 150, 45, nextTime, 0.13, 0.5);
      if (s16 % 4 === 2) voice('square', 7000, 5000, nextTime, 0.03, 0.045);
      const bnote = bassSeq[s16];
      if (bnote) voice('square', bnote, 0, nextTime, 0.1, 0.1);
      if (s16 % 2 === 0) {
        const l = leadSeq[(step >> 1) % 16];
        if (l) voice('triangle', l, 0, nextTime, 0.18, 0.055);
      }
      step++; nextTime += STEP;
    }
  }
  return {
    get playing() { return playing; },
    start() {
      if (playing) return;
      try {
        ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
        if (ctx.state === 'suspended') ctx.resume();
        playing = true; step = 0; nextTime = ctx.currentTime + 0.05;
        timer = setInterval(schedule, 40);
      } catch (e) { playing = false; }
    },
    stop() { playing = false; clearInterval(timer); },
  };
})();

// abbaio sintetizzato (nessun file audio)
function bark() {
  try {
    barkCtx = barkCtx || new (window.AudioContext || window.webkitAudioContext)();
    if (barkCtx.state === 'suspended') barkCtx.resume();
    const t0 = barkCtx.currentTime + 0.02;
    for (let i = 0; i < 2; i++) {
      const o = barkCtx.createOscillator(), g = barkCtx.createGain();
      o.type = 'square';
      o.frequency.setValueAtTime(620 - i * 70, t0 + i * 0.13);
      o.frequency.exponentialRampToValueAtTime(300, t0 + i * 0.13 + 0.09);
      g.gain.setValueAtTime(0.09, t0 + i * 0.13);
      g.gain.exponentialRampToValueAtTime(0.001, t0 + i * 0.13 + 0.11);
      o.connect(g); g.connect(barkCtx.destination);
      o.start(t0 + i * 0.13); o.stop(t0 + i * 0.13 + 0.12);
    }
  } catch (e) { /* niente audio */ }
}

// ---------- Il "cervello": risposte in italiano ----------
function pick(arr) { return arr[(Math.random() * arr.length) | 0]; }

const FRASI_PASSEGGIO = [
  'Che bella giornata oggi!',
  'Mi piace un sacco passeggiare qui.',
  'Un po’ di movimento fa sempre bene!',
  'La la la… lalala…',
  'Mi chiedo cosa ci sia da quella parte…',
  'Sgranchirsi le gambe è il mio sport preferito.',
];
const FRASI_DESKTOP = [
  'Ehi, che ci fai al computer a quest’ora?',
  'Io intanto mi faccio due passi sul tuo schermo.',
  'Non ti distraggo, eh… continua pure a lavorare!',
  'Bello spazioso questo desktop!',
  'Se ti serve compagnia, io sono qui.',
  'Attento che passo io!',
];
const BARZELLETTE = [
  'Perché i pesci non usano il computer? Perché hanno paura della rete!',
  'Cosa dice uno spazzolino a un altro spazzolino? Oggi mi sento un po’ giù di dente!',
  'Qual è il colmo per un giardiniere? Piantare tutto e andarsene!',
  'Perché il libro di matematica è triste? Perché ha troppi problemi!',
  'Qual è il colmo per un elettricista? Non essere al corrente di niente!',
];
const CURIOSITA = [
  'Sapevi che il cuore di una balenottera azzurra è grande come un\u2019automobile?',
  'I polpi hanno tre cuori e il sangue blu!',
  'Un fulmine è cinque volte più caldo della superficie del Sole.',
  'Le api riconoscono i volti delle persone.',
  'Su Venere un giorno dura più di un anno!',
  'Il miele non scade mai: ne hanno trovato di commestibile nelle tombe egizie.',
  'Le giraffe dormono solo due ore al giorno.',
  'Un cucchiaino di stella di neutroni peserebbe quanto una montagna.',
  'I gatti fanno le fusa a una frequenza che aiuta a guarire le ossa.',
  'Gli struzzi corrono più veloci dei cavalli.',
  'Il tuo corpo produce 25 milioni di cellule nuove ogni secondo.',
  'I pinguini si dichiarano amore regalandosi un sassolino.',
  'La Torre Eiffel d\u2019estate è più alta di 15 centimetri: il ferro si dilata col caldo!',
  'Le farfalle sentono i sapori… con le zampe.',
  'In Italia ci sono più di 1500 tipi di pasta diversi.',
  'Il Sole contiene il 99,8 per cento di tutta la massa del sistema solare.',
];

const DEFAULT_REPLIES = [
  'Interessante! Dimmi di più…',
  'Ah sì? Non ci avevo mai pensato!',
  'Capito, capito… più o meno!',
  'Mi piace tantissimo parlare con te!',
  'Uhm… fammi pensare… sì, sono d’accordo!',
  'Bella questa! Raccontamene un’altra.',
];

// --- intenti da assistente: aprire siti/app, messaggi, promemoria, ora ---
const SITI = {
  youtube: 'https://www.youtube.com', google: 'https://www.google.com',
  gmail: 'https://mail.google.com', whatsapp: 'https://web.whatsapp.com',
  maps: 'https://www.google.com/maps', mappe: 'https://www.google.com/maps',
  wikipedia: 'https://it.wikipedia.org', facebook: 'https://www.facebook.com',
  instagram: 'https://www.instagram.com', tiktok: 'https://www.tiktok.com',
  netflix: 'https://www.netflix.com', spotify: 'https://open.spotify.com',
  amazon: 'https://www.amazon.it', twitch: 'https://www.twitch.tv',
  telegram: 'https://web.telegram.org', discord: 'https://discord.com/app',
  notizie: 'https://news.google.com/?hl=it', traduttore: 'https://translate.google.com',
  meteo: 'https://www.google.com/search?q=meteo',
};
// protocolli che aprono la VERA app installata sul PC (usati dalla versione desktop)
const APP_PROTO = {
  whatsapp: 'whatsapp://', spotify: 'spotify:', telegram: 'tg://',
  discord: 'discord://-/', steam: 'steam://open/main',
};
const APP_PC = [
  { re: /calcolatric/, id: 'calc', nome: 'la calcolatrice' },
  { re: /blocco note|notepad/, id: 'notepad', nome: 'il Blocco note' },
  { re: /paint/, id: 'paint', nome: 'Paint' },
  { re: /esplora|cartell|file manager|risorse/, id: 'explorer', nome: 'Esplora file' },
  { re: /terminale|prompt|cmd\b/, id: 'terminal', nome: 'il terminale' },
  { re: /gestione attivit|task manager/, id: 'taskmgr', nome: 'Gestione attività' },
  { re: /pannello di controllo/, id: 'control', nome: 'il Pannello di controllo' },
  { re: /cattura|screenshot|ritaglio/, id: 'snip', nome: 'lo Strumento di cattura' },
  { re: /\bword\b/, id: 'word', nome: 'Word' },
  { re: /\bexcel\b/, id: 'excel', nome: 'Excel' },
  { re: /powerpoint|power point/, id: 'powerpoint', nome: 'PowerPoint' },
];
// sezioni delle Impostazioni di Windows (protocollo ms-settings:)
const IMPOSTAZIONI = [
  { re: /wifi|wi-fi|rete|internet/, page: 'network-wifi', nome: 'del WiFi' },
  { re: /bluetooth/, page: 'bluetooth', nome: 'del Bluetooth' },
  { re: /audio|suon|volume/, page: 'sound', nome: 'dell’audio' },
  { re: /schermo|display|monitor/, page: 'display', nome: 'dello schermo' },
  { re: /batteria|risparmio/, page: 'batterysaver', nome: 'della batteria' },
  { re: /aggiornament/, page: 'windowsupdate', nome: 'degli aggiornamenti' },
  { re: /privacy/, page: 'privacy', nome: 'della privacy' },
  { re: /account/, page: 'yourinfo', nome: 'dell’account' },
];
function searchUrl(q) { return 'https://www.google.com/search?q=' + encodeURIComponent(q); }

const INDOVINELLI = [
  { q: 'Ha i denti ma non morde mai. Che cos’è?', a: /pettine/, sol: 'il pettine' },
  { q: 'Più è fresco e più è caldo. Che cos’è?', a: /pane|pagnotta/, sol: 'il pane' },
  { q: 'Ha un letto ma non dorme mai, corre ma non cammina. Che cos’è?', a: /fiume/, sol: 'il fiume' },
  { q: 'Cade sempre ma non si fa mai male. Che cos’è?', a: /pioggia|neve/, sol: 'la pioggia' },
  { q: 'Ha la coda ma non è un animale, e vola senza ali. Che cos’è?', a: /aquilone/, sol: 'l’aquilone' },
  { q: 'Ripete tutto quello che dici senza aver studiato le lingue. Che cos’è?', a: /\beco\b/, sol: 'l’eco' },
];

// ---------- conoscenze per il cervello ----------
const MESI = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto',
  'settembre', 'ottobre', 'novembre', 'dicembre'];
const COMPLIMENTI = [
  'Sei una delle persone più simpatiche che abbiano mai toccato questo schermo!',
  'Hai un gusto fantastico: hai scelto me come compagno!',
  'Ce la puoi fare. Anzi: ce la stai già facendo!',
  'Ogni grande cosa è iniziata con un piccolo passo. E tu ne hai fatti tanti!',
  'Oggi sei carico come una batteria al cento per cento!',
  'Il mondo è più bello con te dentro. Fidati, io lo vedo da qui!',
];
function readPrefs() {
  try { return JSON.parse(localStorage.getItem('zephPrefs') || '{}'); } catch (e) { return {}; }
}
const UNITS = {
  km: ['len', 1000, 'chilometri'], chilometri: ['len', 1000, 'chilometri'], chilometro: ['len', 1000, 'chilometri'],
  m: ['len', 1, 'metri'], metri: ['len', 1, 'metri'], metro: ['len', 1, 'metri'],
  cm: ['len', 0.01, 'centimetri'], centimetri: ['len', 0.01, 'centimetri'], mm: ['len', 0.001, 'millimetri'],
  miglia: ['len', 1609.344, 'miglia'], miglio: ['len', 1609.344, 'miglia'],
  piedi: ['len', 0.3048, 'piedi'], piede: ['len', 0.3048, 'piedi'],
  pollici: ['len', 0.0254, 'pollici'], pollice: ['len', 0.0254, 'pollici'], iarde: ['len', 0.9144, 'iarde'],
  kg: ['mass', 1, 'chili'], chili: ['mass', 1, 'chili'], chilo: ['mass', 1, 'chili'], chilogrammi: ['mass', 1, 'chili'],
  g: ['mass', 0.001, 'grammi'], grammi: ['mass', 0.001, 'grammi'], etti: ['mass', 0.1, 'etti'],
  libbre: ['mass', 0.45359237, 'libbre'], libbra: ['mass', 0.45359237, 'libbre'], once: ['mass', 0.0283495, 'once'],
  litri: ['vol', 1, 'litri'], litro: ['vol', 1, 'litri'], ml: ['vol', 0.001, 'millilitri'], galloni: ['vol', 3.78541, 'galloni'],
  'km/h': ['speed', 1, 'chilometri orari'], kmh: ['speed', 1, 'chilometri orari'], mph: ['speed', 1.609344, 'miglia orarie'],
  celsius: ['temp', 'C', 'gradi Celsius'], '°c': ['temp', 'C', 'gradi Celsius'], gradi: ['temp', 'C', 'gradi Celsius'],
  fahrenheit: ['temp', 'F', 'gradi Fahrenheit'], '°f': ['temp', 'F', 'gradi Fahrenheit'], kelvin: ['temp', 'K', 'kelvin'],
};
function unitOf(u) { return UNITS[u] || null; }
function fmtNum(v) {
  const r = Math.round(v * 100) / 100;
  return String(r).replace('.', ',');
}
function convert(v, a, b) {
  if (a[0] !== b[0]) return null;
  let out;
  if (a[0] === 'temp') {
    const c = a[1] === 'C' ? v : a[1] === 'F' ? (v - 32) * 5 / 9 : v - 273.15;
    out = b[1] === 'C' ? c : b[1] === 'F' ? c * 9 / 5 + 32 : c + 273.15;
  } else {
    out = v * a[1] / b[1];
  }
  return fmtNum(v) + ' ' + a[2] + ' sono ' + fmtNum(out) + ' ' + b[2] + '!';
}
function easter(y) { // algoritmo gregoriano anonimo
  const a = y % 19, b = Math.floor(y / 100), c = y % 100, d = Math.floor(b / 4), e = b % 4;
  const f = Math.floor((b + 8) / 25), g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30, i = Math.floor(c / 4), k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7, m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31), day = ((h + l - 7 * m + 114) % 31) + 1;
  return new Date(y, month - 1, day);
}
function daysUntil(what) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const y = today.getFullYear();
  let make, label;
  if (/natale/.test(what)) { make = yy => new Date(yy, 11, 25); label = 'a Natale'; }
  else if (/capodanno/.test(what)) { make = yy => new Date(yy + 1, 0, 1); label = 'a Capodanno'; }
  else if (/pasqua/.test(what)) { make = easter; label = 'a Pasqua'; }
  else if (/ferragosto/.test(what)) { make = yy => new Date(yy, 7, 15); label = 'a Ferragosto'; }
  else if (/halloween/.test(what)) { make = yy => new Date(yy, 9, 31); label = 'ad Halloween'; }
  else if (/valentino/.test(what)) { make = yy => new Date(yy, 1, 14); label = 'a San Valentino'; }
  else if (/befana/.test(what)) { make = yy => new Date(yy, 0, 6); label = 'alla Befana'; }
  else if (/estate/.test(what)) { make = yy => new Date(yy, 5, 21); label = 'all’estate'; }
  else {
    const c = readPrefs().compleanno;
    if (!c) return 'Non so ancora quando è il tuo compleanno! Dimmi «il mio compleanno è il 12 marzo».';
    const [g, mi] = c.split('/').map(Number);
    make = yy => new Date(yy, mi - 1, g);
    label = 'al tuo compleanno';
  }
  let target = make(y);
  if (/capodanno/.test(what)) target = new Date(y + 1, 0, 1);
  if (target < today) target = make(y + 1);
  const n = Math.round((target - today) / 864e5);
  if (n === 0) return label === 'al tuo compleanno' ? 'È OGGI il tuo compleanno! Tanti auguri!!!' : 'È oggi! Festa!';
  return (n === 1 ? 'Manca 1 giorno ' : 'Mancano ' + n + ' giorni ') + label + '!';
}

// meteo vero da Open-Meteo (gratuito, senza chiavi): restituisce { say, code }
const WMO = {
  0: 'cielo sereno', 1: 'quasi sereno', 2: 'poco nuvoloso', 3: 'nuvoloso', 45: 'nebbia', 48: 'nebbia gelata',
  51: 'pioviggine leggera', 53: 'pioviggine', 55: 'pioviggine fitta', 56: 'pioviggine gelata', 57: 'pioviggine gelata',
  61: 'pioggia leggera', 63: 'pioggia', 65: 'pioggia forte', 66: 'pioggia gelata', 67: 'pioggia gelata forte',
  71: 'neve leggera', 73: 'neve', 75: 'neve forte', 77: 'nevischio', 80: 'qualche rovescio', 81: 'rovesci',
  82: 'rovesci violenti', 85: 'rovesci di neve', 86: 'forti rovesci di neve', 95: 'temporale',
  96: 'temporale con grandine', 99: 'temporale con grandine forte',
};
function weatherKind(code) {
  if (code >= 71 && code <= 77 || code === 85 || code === 86) return 'snow';
  if (code >= 51 && code <= 67 || code >= 80) return 'rain';
  return code <= 2 ? 'clear' : 'cloudy';
}
function getJson(url) {
  const ctl = typeof AbortController === 'function' ? new AbortController() : null;
  const timer = ctl ? setTimeout(() => ctl.abort(), 9000) : null;
  return fetch(url, ctl ? { signal: ctl.signal } : {}).then(r => {
    if (timer) clearTimeout(timer);
    if (!r.ok) throw new Error('http ' + r.status);
    return r.json();
  });
}
function aCity(name) { return (/^[aeiouàèéìòù]/i.test(name) ? 'ad ' : 'a ') + name; }
function weatherReport(q) {
  q = q || {};
  const city = q.city || readPrefs()['città'];
  if (!city) {
    return Promise.resolve({ say: 'Di quale città? Dimmi «che tempo fa a Roma», oppure «la mia città è …» e me la ricordo.' });
  }
  const geo = 'https://geocoding-api.open-meteo.com/v1/search?count=1&language=it&format=json&name=' + encodeURIComponent(city);
  return getJson(geo).then(g => {
    const p = g && g.results && g.results[0];
    if (!p) return { say: 'Non trovo la città «' + city + '»… è scritta giusta?' };
    const url = 'https://api.open-meteo.com/v1/forecast?latitude=' + p.latitude + '&longitude=' + p.longitude +
      '&current=temperature_2m,weather_code,wind_speed_10m' +
      '&daily=temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max' +
      '&timezone=auto&forecast_days=2';
    return getJson(url).then(f => {
      const d = f.daily, R = Math.round;
      if (q.when === 'domani') {
        const code = d.weather_code[1], pp = d.precipitation_probability_max ? d.precipitation_probability_max[1] : null;
        return { code, kind: weatherKind(code),
          say: 'Domani ' + aCity(p.name) + ': ' + (WMO[code] || 'tempo variabile') + ', minima ' + R(d.temperature_2m_min[1]) +
            ' e massima ' + R(d.temperature_2m_max[1]) + ' gradi' +
            (pp != null && pp >= 40 ? ', con il ' + pp + ' per cento di probabilità di pioggia' : '') + '.' };
      }
      const c = f.current, code = c.weather_code;
      const t0 = R(c.temperature_2m);
      const extra = t0 >= 30 ? ' Che caldo, bevi tanta acqua!' : t0 <= 3 ? ' Brrr, copriti bene!' :
        weatherKind(code) === 'rain' ? ' Prendi l’ombrello!' : '';
      return { code, kind: weatherKind(code),
        say: 'Adesso ' + aCity(p.name) + ' ci sono ' + t0 + ' gradi, ' + (WMO[code] || 'tempo variabile') +
          (c.wind_speed_10m >= 30 ? ', e tira vento' : '') + '. Oggi massima ' + R(d.temperature_2m_max[0]) + '.' + extra };
    });
  }).catch(() => ({ say: 'Non riesco a collegarmi al servizio del meteo: c’è internet?' }));
}

function actionIntent(t, ctx) {
  let m;

  // giochi: sasso carta forbice
  if (/sasso.*carta.*forbic|carta.*forbic|morra/.test(t)) {
    ctx.pending = 'rps';
    return { say: 'Ci sto! Uno, due, tre… scrivi sasso, carta o forbice!' };
  }
  // giochi: indovinelli
  if (/indovinell|facciamo un quiz|\bquiz\b/.test(t)) {
    const idx = (Math.random() * INDOVINELLI.length) | 0;
    ctx.pending = 'quiz'; ctx.quizIdx = idx;
    return { say: 'Indovinello! ' + INDOVINELLI[idx].q };
  }
  // ---------- comandi del telefono (altrove Zeph spiega che servono sul telefono) ----------
  if (/^(?:accendi|attiva|apri)\s+(?:la\s+|il\s+)?(?:torcia|luce|flash)\b/.test(t)) {
    return { torch: true, phoneOnly: true, say: pick(['Torcia accesa! Ecco un po’ di luce.', 'Luce! Così non inciampi.']) };
  }
  if (/^(?:spegni|disattiva|chiudi)\s+(?:la\s+|il\s+)?(?:torcia|luce|flash)\b/.test(t)) {
    return { torch: false, phoneOnly: true, say: 'Torcia spenta!' };
  }
  m = t.match(/(?:svegliami|(?:metti|imposta|punta)\s+(?:una\s+|la\s+)?sveglia|^sveglia)\s+(?:alle|per le|a|all')\s*(\d{1,2})(?:(?:[:.]|\s+e\s+)(\d{1,2}|mezza|un quarto|quarto|tre quarti))?(?:\s+(?:di\s+)?(sera|pomeriggio|mattina|notte))?/);
  if (m) {
    let h = parseInt(m[1], 10);
    const mm = { mezza: 30, 'un quarto': 15, quarto: 15, 'tre quarti': 45 };
    const min = m[2] ? (mm[m[2]] !== undefined ? mm[m[2]] : parseInt(m[2], 10)) : 0;
    if ((m[3] === 'sera' || m[3] === 'pomeriggio') && h < 12) h += 12;
    if (h > 23 || min > 59) return { say: 'Quell’orario non esiste nemmeno su Marte! Riprova, tipo «svegliami alle 7 e 30».' };
    const hh = h + (min ? ' e ' + (min < 10 ? '0' + min : min) : '');
    return { alarm: { h, m: min }, phoneOnly: true, say: 'Sveglia puntata alle ' + hh + '! Dormi tranquillo, ci penso io.', action: 'wave' };
  }
  m = t.match(/^(?:metti|imposta|fai partire|avvia)?\s*(?:un\s+|il\s+)?timer\s+(?:di|da|per)?\s*(\d+)\s*(secondi|secondo|minuti|minuto|ore|ora)/);
  if (m) {
    const n = parseInt(m[1], 10);
    const secs = n * (m[2][0] === 's' ? 1 : m[2][0] === 'm' ? 60 : 3600);
    return { timer: { seconds: secs }, remind: { seconds: secs, text: 'Il timer di ' + n + ' ' + m[2] + ' è finito!' },
      say: 'Timer di ' + n + ' ' + m[2] + ' partito!' };
  }
  m = t.match(/^(?:chiama|telefona(?:\s+a)?)\s+([+\d][\d\s.]{4,})$/);
  if (m) {
    const num = m[1].replace(/[^\d+]/g, '');
    return { dial: num, phoneOnly: true, say: 'Ti preparo la chiamata: premi il tasto verde!' };
  }
  if (/^(?:chiama|telefona(?:\s+a)?)\s+\S+/.test(t) && !/cane|cucciolo|rocky/.test(t)) {
    return { dial: '', phoneOnly: true, say: 'Ti apro il telefono: cerca il nome lì, oppure dimmi il numero, tipo «chiama 333 1234567».' };
  }
  if (/^(?:metti in |fai )?pausa(?: la musica| la canzone)?!?$|^ferma la canzone$/.test(t)) return { media: 'pause', say: 'Pausa!' };
  if (/^(?:riprendi|fai ripartire|continua|play)(?: la musica| la canzone)?!?$/.test(t)) return { media: 'play', say: 'Si riparte!' };
  if (/(?:prossima|successiva|altra) canzone|canzone (?:successiva|dopo)|salta (?:la |questa )?canzone|^avanti!?$/.test(t)) return { media: 'next', say: 'Avanti la prossima!' };
  if (/canzone (?:precedente|di prima)|torna alla canzone|^indietro!?$/.test(t)) return { media: 'prev', say: 'Torniamo a quella di prima!' };

  // ---------- meteo vero ----------
  m = t.match(/la mia città è\s+(.+)|^(?:abito|vivo|sto)\s+(?:a|ad|in)\s+(.+)/);
  if (m) {
    const c = (m[1] || m[2]).replace(/[.!?]+$/, '').trim();
    const C = c.replace(/\b\w/g, x => x.toUpperCase());
    return { setPref: { k: 'città', v: C }, say: 'Segnato: abiti a ' + C + '! Ora chiedimi «che tempo fa?»' };
  }
  if (/che tempo (?:fa|farà|fara|c'è|ce)|\bmeteo\b|previsioni|(?:piove|pioverà|nevica|nevicherà|fa caldo|fa freddo)\s+(?:a|ad|in|oggi|domani|adesso|fuori)\b|^(?:piove|nevica)\??$|quanti gradi (?:ci sono|fa|fanno)|temperatura (?:a|di|ad|in|oggi|domani|fuori)/.test(t)) {
    const when = /domani/.test(t) ? 'domani' : 'oggi';
    const cm = t.replace(/\b(?:oggi|domani|stasera|adesso|ora|fuori)\b/g, ' ')
      .match(/\b(?:a|ad|in|di|per)\s+([a-zà-ù'][a-zà-ù' ]*?)\s*\??\s*$/);
    let city = cm ? cm[1].trim() : null;
    if (city && /^(?:che|quanto|oggi|domani|me|te)$/.test(city)) city = null;
    return { weatherQuery: { city, when } };
  }

  // ---------- numeri, fortuna e conversioni ----------
  m = t.match(/(?:converti\s+|quant[oiae]\s+(?:sono|fanno|fa)\s+)?(-?\d+(?:[.,]\d+)?)\s*([a-z°/]+)\s+(?:in|a)\s+([a-z°/]+)/);
  if (m && unitOf(m[2]) && unitOf(m[3])) {
    const r = convert(parseFloat(m[1].replace(',', '.')), unitOf(m[2]), unitOf(m[3]));
    if (r) return { say: r };
  }
  m = t.match(/(?:tira|lancia)\s+(?:un\s+|il\s+|i\s+)?(?:(\d|due|tre|quattro|cinque)\s+)?dad[oi]/);
  if (m) {
    const words = { due: 2, tre: 3, quattro: 4, cinque: 5 };
    const n = m[1] ? (words[m[1]] || parseInt(m[1], 10)) : 1;
    const rolls = []; for (let i = 0; i < Math.min(5, n); i++) rolls.push(1 + ((Math.random() * 6) | 0));
    const sum = rolls.reduce((a, b) => a + b, 0);
    return { say: rolls.length === 1 ? 'È uscito… ' + rolls[0] + '!' : 'Sono usciti ' + rolls.join(', ') + ': totale ' + sum + '!', action: 'jump' };
  }
  if (/testa o croce|(?:tira|lancia)\s+(?:una\s+|la\s+)?moneta/.test(t)) {
    return { say: 'Lancio… è uscito ' + (Math.random() < 0.5 ? 'TESTA' : 'CROCE') + '!', action: 'flip' };
  }
  m = t.match(/numero (?:a caso|casuale)(?:\s+(?:da|tra)\s+(-?\d+)\s+(?:a|e)\s+(-?\d+))?/);
  if (m) {
    let lo = m[1] ? parseInt(m[1], 10) : 1, hi = m[2] ? parseInt(m[2], 10) : 100;
    if (lo > hi) { const x = lo; lo = hi; hi = x; }
    return { say: 'Il numero è… ' + (lo + Math.floor(Math.random() * (hi - lo + 1))) + '!' };
  }

  // ---------- date ----------
  if (/che giorno (?:è|e|sarà|sara) domani|domani che giorno (?:è|e|sarà)/.test(t)) {
    const d = new Date(Date.now() + 864e5).toLocaleDateString('it-IT', { weekday: 'long', day: 'numeric', month: 'long' });
    return { say: 'Domani è ' + d + '!' };
  }
  m = t.match(/il mio compleanno è (?:il\s+)?(\d{1,2})\s*(?:\/|-|\s)\s*(\d{1,2}|gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)/);
  if (m) {
    const mi = /\d/.test(m[2]) ? parseInt(m[2], 10) : MESI.indexOf(m[2]) + 1;
    const g = parseInt(m[1], 10);
    if (mi < 1 || mi > 12 || g < 1 || g > 31) return { say: 'Uhm, quella data non mi torna. Scrivi tipo «il mio compleanno è il 12 marzo».' };
    return { setPref: { k: 'compleanno', v: g + '/' + mi }, say: 'Segnato: il tuo compleanno è il ' + g + ' ' + MESI[mi - 1] + '! Me lo ricorderò.', action: 'dance' };
  }
  m = t.match(/quanti giorni mancano (?:a |al |alla |all'|ad |per |a |)\s*(natale|capodanno|pasqua|ferragosto|halloween|san valentino|befana|la befana|(?:il )?mio compleanno|l'estate|estate)/);
  if (m) return { say: daysUntil(m[1]) };

  // ---------- emozioni ----------
  if (/sono triste|sono giù|tirami su|mi sento solo|giornata (?:brutta|no)/.test(t)) {
    return { say: pick([
      'Mi dispiace… vieni qui, ti faccio un balletto per tirarti su!',
      'Le giornate storte passano, e io sono qui con te. Un abbraccio virtuale fortissimo!',
      'Respira con me: dentro… fuori… Va già un po’ meglio? Sono qui per te.']), action: 'dance' };
  }
  if (/complimento|dimmi qualcosa di bello|motivami|dammi la carica|incoraggiami/.test(t)) {
    return { say: pick(COMPLIMENTI), action: 'wave' };
  }

  // calcoli a voce
  m = t.match(/quanto fa (.+)/);
  if (m) {
    let expr = m[1].replace(/più/g, '+').replace(/meno/g, '-')
      .replace(/\bper\b/g, '*').replace(/\bx\b/g, '*')
      .replace(/diviso/g, '/').replace(/virgola/g, '.').replace(/,/g, '.')
      .replace(/[^0-9+\-*/().\s]/g, '').trim();
    if (expr && /\d/.test(expr)) {
      try {
        const val = Function('"use strict"; return (' + expr + ')')();
        if (isFinite(val)) {
          const out = Math.round(val * 10000) / 10000;
          return { say: 'Fa ' + String(out).replace('.', ' virgola ') + '!', action: 'jump' };
        }
      } catch (e) { /* espressione non valida */ }
    }
    return { say: 'Uhm, questa non riesco a calcolarla… prova tipo «quanto fa 25 per 4»!' };
  }

  // musica
  if (/(basta|ferma|stop|spegni).*musica/.test(t)) return { music: 'off', say: 'Musica spenta! Silenzio in sala.' };
  if (/(metti|suona|accendi|fai partire).*(musica|canzone)|^musica!?$/.test(t)) {
    return { music: 'on', say: 'DJ Zeph in consolle! Si ballaaa!', action: 'dance' };
  }

  // cambio look
  if (/(cambia|nuovo|cambiati).*(look|vestiti|vestito|colori|stile)|vestiti nuovi/.test(t)) {
    return { outfit: true, say: pick(['Guarda che stile nuovo!', 'Nuovo look, nuova vita!']), action: 'spin' };
  }

  // ciclo giorno/notte automatico
  if (/ciclo (automatico|del tempo)|tempo automatico|giorno e notte automatic/.test(t)) {
    return { autoSky: true, say: 'Da adesso il tempo scorre da solo: guarda il sole muoversi!' };
  }
  if (/ferma il (ciclo|tempo)|tempo fermo/.test(t)) return { autoSky: false, say: 'Fermo il tempo!… Che potere!' };

  // modalità volo
  if (/\b(vola|decolla|jetpack|volare)\b/.test(t)) {
    return { fly: true, say: pick(['Jetpack attivatooo! Si vola!', 'Pronti al decollo… tre, due, uno!']) };
  }
  if (/\b(atterra|scendi|torna a terra)\b/.test(t)) return { fly: false, say: 'Atterraggio morbido!' };

  // qualità grafica
  if (/ultra ?hd|grafica (alta|ultra|massima)/.test(t)) {
    return { quality: 'ultra', say: 'Grafica ULTRA attivata! Guarda che luce, che bagliori!' };
  }
  if (/grafica (normale|bassa|leggera)/.test(t)) {
    return { quality: 'normal', say: 'Grafica normale: leggera e velocissima!' };
  }

  // modalità camera
  if (/(camera|visuale|telecamera) (cinema|cinematografica)|cinematic/.test(t)) {
    return { camMode: 'cinema', say: 'Azione! Camera cinematografica!' };
  }
  if (/(camera|visuale|telecamera) normale/.test(t)) return { camMode: 'normal', say: 'Camera normale!' };

  // stelle raccolte
  if (/quante stelle|le stelle/.test(t)) return { stars: true };

  // fuochi d'artificio
  if (/fuochi d.artificio|\bfuochi\b|spettacolo pirotecnico/.test(t)) {
    return { fireworks: true, say: pick(['Spettacolo pirotecnicooo!', 'Fuochi! Guarda in alto!']) };
  }

  // missioni
  if (/missioni|obiettivi|\bsfide\b/.test(t)) return { missions: true };

  // la palla per Rocky
  if (/(lancia|tira).*(palla|pallina)|riporto/.test(t)) {
    return { ball: true, dog: 'on', say: pick(['Vai Rocky, prendilaaa!', 'Guarda che lancio!']) };
  }

  // gusti e preferenze
  m = t.match(/il mio (colore|animale|cibo|numero|gioco|film|cartone|cantante|squadra) preferit[oa] è (?:il |la |lo |l')?(.+)/);
  if (m) {
    return { setPref: { k: m[1], v: m[2].trim() },
      say: 'Segnato! Il tuo ' + m[1] + ' preferito è ' + m[2].trim() + '. Non me lo dimentico!' };
  }
  m = t.match(/qual è il mio (colore|animale|cibo|numero|gioco|film|cartone|cantante|squadra) preferit[oa]/);
  if (m) return { getPref: m[1] };

  // nome dell'utente
  m = t.match(/(?:mi chiamo|il mio nome è)\s+([a-zA-Zàèéìòù]+)/);
  if (m) {
    const nome = m[1].charAt(0).toUpperCase() + m[1].slice(1);
    return { say: 'Piacere di conoscerti, ' + nome + '! Me lo ricorderò, promesso!', setName: nome, action: 'wave' };
  }
  if (/come mi chiamo|sai il mio nome|chi sono io/.test(t)) return { whoami: true };

  // cielo e meteo
  if (/fai (?:venire la |scendere la )?notte|voglio la notte|buio/.test(t)) return { sky: 'notte', say: pick(['Uuuh, guarda che cielo stellato!', 'Arriva la notte! Ci sono pure le lucciole!']) };
  if (/tramonto/.test(t)) return { sky: 'tramonto', say: 'Che colori, il tramonto è il mio momento preferito!' };
  if (/alba/.test(t)) return { sky: 'alba', say: 'Sta sorgendo il sole… che pace!' };
  if (/fai giorno|torna il giorno|voglio il giorno/.test(t)) return { sky: 'giorno', say: 'Ed è subito giorno!' };
  if (/fai piovere|pioggia/.test(t)) return { weather: 'rain', say: pick(['Arriva la pioggia! Speriamo di non arrugginire!', 'Piove! Senti che profumo di erba bagnata.']) };
  if (/nevic|neve/.test(t)) return { weather: 'snow', say: 'Neveee! Guarda che fiocchi enormi!' };
  if (/bel tempo|sereno|smetti di piovere|basta pioggia|basta neve|torna il sole/.test(t)) return { weather: 'clear', sky: 'giorno', say: 'Torna il sole! Molto meglio così.' };

  // il cane Rocky
  if (/(chiama|arriva|voglio|fai venire).*(cane|cucciolo|rocky)|^(cane|rocky)!?$/.test(t)) {
    return { dog: 'on', say: pick(['Rocky! Vieni qui bello!', 'Rockyyyy! A me!']), action: 'wave' };
  }
  if (/(via|vattene|a cuccia|manda via|basta).*(cane|rocky)/.test(t)) {
    return { dog: 'off', say: 'Rocky, a cuccia! Bravo, ci vediamo dopo!' };
  }

  // corsa
  if (/(corri|di corsa|sprint)/.test(t)) return { run: true, say: pick(['Vaiiii che si corre!', 'Turbo attivato!']) };
  if (/(rallenta|vai piano|cammina normale|passo normale)/.test(t)) return { run: false, say: 'Ok, si passeggia tranquilli.' };

  // il tuo avatar da un selfie
  if (/(?:avatar|faccia|aspetto).*(?:foto|selfie)|(?:foto|selfie).*(?:avatar|faccia)|^crea(?:mi)? (?:il mio |un |l')?avatar|^fammi (?:l'|un |il mio )?avatar|metti la mia faccia|diventa come me|somigliami/.test(t)) {
    return { photoAvatar: true, say: 'Evviva! Fatti un bel selfie con tanta luce: prendo i tuoi colori e la tua faccia e divento come te!', action: 'jump' };
  }
  // foto ricordo («fotocamera» invece è l'app: gestita più sotto)
  if (/\b(foto|selfie|fotografia|scatta)\b/.test(t)) return { photo: true, say: 'Mettiti in posa… Cheeeese!' };

  // ora e data
  if (/che or[ae]|dimmi l'ora/.test(t)) {
    const d = new Date();
    return { say: 'Sono le ' + d.getHours() + ' e ' + (d.getMinutes() < 10 ? 'zero ' : '') + d.getMinutes() + '!' };
  }
  if (/che giorno è|data di oggi|quanti ne abbiamo/.test(t)) {
    const d = new Date().toLocaleDateString('it-IT', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    return { say: 'Oggi è ' + d + '!' };
  }

  // promemoria / timer
  m = t.match(/(?:ricordami|avvisami|timer)\s*(?:tra|fra|di|da)?\s+(\d+)\s+(secondo|secondi|minuto|minuti|ora|ore)\s*(?:di\s+|che\s+|per\s+|del\s+|della\s+|dello\s+|dei\s+|delle\s+)?(.*)/);
  if (m) {
    const n = parseInt(m[1], 10);
    const mult = m[2][0] === 's' ? 1 : m[2][0] === 'm' ? 60 : 3600;
    const testo = (m[3] || '').trim();
    return {
      say: 'Ricevuto! Tra ' + m[1] + ' ' + m[2] + ' ti avviso io' + (testo ? ' per: ' + testo : '') + '. Vai tranquillo!',
      remind: { seconds: n * mult, text: testo || 'Il tempo è scaduto!' },
    };
  }

  // messaggio WhatsApp (Zeph lo PREPARA, l'utente preme invia)
  m = t.match(/manda\s+(?:un\s+)?messaggio(?:\s+(?:su\s+)?whatsapp)?(?:\s+a\s+([+\d][\d .]{5,}))?\s*(?:che dice|dicendo|con scritto|:)?\s*(.*)/);
  if (m) {
    const num = (m[1] || '').replace(/\D/g, '');
    const testo = (m[2] || '').trim();
    if (!testo) return { say: 'Dimmi anche cosa scrivere! Per esempio: «manda messaggio ciao, arrivo tra poco».' };
    return {
      say: 'Ti preparo il messaggio su WhatsApp! Tu devi solo premere invia.',
      open: 'https://wa.me/' + num + '?text=' + encodeURIComponent(testo),
      appUrl: 'whatsapp://send?text=' + encodeURIComponent(testo) + (num ? '&phone=' + num : ''),
    };
  }

  // email
  m = t.match(/scrivi\s+(?:una\s+|un'\s*)?(?:mail|email|e-mail)(?:\s+a\s+(\S+@\S+\.\S+))?\s*(?:che dice|dicendo|:)?\s*(.*)/);
  if (m) {
    const dest = m[1] || '';
    const corpo = (m[2] || '').trim();
    return {
      say: 'Ti apro la mail già impostata! Controlla e premi invia.',
      open: 'mailto:' + dest + (corpo ? '?body=' + encodeURIComponent(corpo) : ''),
    };
  }

  // ricerca
  m = t.match(/^(?:cerca(?:mi)?|googla|cerca su google)\s+(.+)/);
  if (m) return { say: 'Cerco «' + m[1] + '» su Google!', open: searchUrl(m[1]) };

  // volume del PC
  if (/(alza|aumenta|su) (il |col )?volume/.test(t)) return { volume: 'up', say: 'Alzo il volume del PC!' };
  if (/(abbassa|riduci|giù) (il |col )?volume/.test(t)) return { volume: 'down', say: 'Abbasso il volume del PC!' };
  if (/(metti|attiva) (il )?muto|silenzia il pc|togli l.audio/.test(t)) return { volume: 'mute', say: 'Shhh… muto!' };

  // batteria
  if (/batteria|quanta carica/.test(t)) return { battery: true };

  // apri sito / app
  m = t.match(/^(?:apri(?:mi)?|avvia|lancia|vai su)\s+(.+)/);
  if (m) {
    let q = m[1].replace(/^(il|lo|la|le|i|gli|un|una|l')\s+/, '').trim();
    q = fixTypos(q) || q; // «watshap» → «whatsapp»
    // Impostazioni di Windows (vera app, anche per sezione)
    if (/impostazioni|settings/.test(q)) {
      for (const st of IMPOSTAZIONI) {
        if (st.re.test(q)) return { say: 'Apro le impostazioni ' + st.nome + '!', appUrl: 'ms-settings:' + st.page, action: 'jump' };
      }
      return { say: 'Apro le Impostazioni!', appUrl: 'ms-settings:', action: 'jump' };
    }
    if (/fotocamera|webcam/.test(q)) return { say: 'Apro la fotocamera!', appUrl: 'microsoft.windows.camera:', action: 'jump' };
    if (/microsoft store|store/.test(q)) return { say: 'Apro il Microsoft Store!', appUrl: 'ms-windows-store:', action: 'jump' };
    for (const app of APP_PC) {
      if (app.re.test(q)) return { say: 'Apro ' + app.nome + '!', app: app.id, action: 'jump' };
    }
    if (/^(browser|internet|chrome|edge|firefox)/.test(q)) {
      return { say: 'Apro il browser!', open: 'https://www.google.com', action: 'jump' };
    }
    for (const nome in SITI) {
      if (q.indexOf(nome) !== -1) {
        return { say: 'Apro ' + nome + '!', open: SITI[nome], appUrl: APP_PROTO[nome], action: 'jump' };
      }
    }
    if (APP_PROTO[q]) return { say: 'Apro ' + q + '!', appUrl: APP_PROTO[q], action: 'jump' };
    if (/^[\w-]+(\.[\w-]+)+/.test(q)) return { say: 'Apro ' + q + '!', open: 'https://' + q, action: 'jump' };
    return { say: 'Non conosco «' + q + '», te lo cerco su Google!', open: searchUrl(q) };
  }

  return null;
}

const RULES = [
  { re: /(barzellett|scherz|fammi ridere|divertent|joke)/, fn: () => ({ say: pick(BARZELLETTE) }) },
  { re: /(curiosit|sapevi che|dimmi qualcosa|fatto interessante|insegnami)/, fn: () => ({ say: pick(CURIOSITA), curio: true }) },
  { chat: true, re: /(mi annoio|annoiato|che facciamo|non so che fare)/, fn: () => ({ say: pick([
    'Noia bandita! Prova «metti la musica» e balliamo!',
    'Ti lancio una sfida: «sasso carta forbice»!',
    'Andiamo a trovare Nina al villaggio! Oppure dimmi «vola»!',
    'Facciamo la caccia alle stelle? Ne mancano parecchie!',
    'Chiedimi una curiosità, ne so a bizzeffe!']) }) },
  { chat: true, re: /(sei vivo|sei vero|sei un robot|esisti davvero)/, fn: () => ({ say: pick([
    'Sono fatto di poligoni e fantasia… ma i sentimenti sembrano veri, no?',
    'Diciamo che sono vivo quanto può esserlo un mucchietto di triangoli molto simpatici!']) }) },
  { chat: true, re: /(chi ti ha (creato|fatto|costruito)|come sei nato)/, fn: () => ({ say: 'Sono nato da codice, poligoni e un pizzico di magia, direttamente sul tuo computer!' }) },
  { re: /(salto mortale|capriola|acrobazia|flip|mortale)/, fn: () => ({ say: pick(['Guarda questa acrobaziaaa!', 'Rullo di tamburi… salto mortale!', 'Tieniti forte!']), action: 'flip' }) },
  { re: /(piroetta|giravolta|trottola|gira su te)/, fn: () => ({ say: pick(['Piroettaaa!', 'Guarda che stile!']), action: 'spin' }) },
  { re: /(stiracchiati|stretching|rilassati)/, fn: () => ({ say: 'Aaah… che bello stiracchiarsi!', action: 'stretch' }) },
  { re: /(balla|danza|ballare|dance)/, fn: () => ({ say: pick(['E vaiii! Guarda che mosse!', 'Musica, maestro! Si balla!', 'Questa è la mia specialità!']), action: 'dance' }) },
  { re: /(salta|salto|jump)/, fn: () => ({ say: pick(['Uuup! Hai visto che salto?', 'Guarda quanto vado in alto!']), action: 'jump' }) },
  { re: /(canta|canzone|canzoncina)/, fn: () => ({ say: 'Laaa la la làààà… Zeph è il mio nome, camminare è la mia passioneee!', action: 'dance' }) },
  { re: /(vieni|avvicinati|qui da me)/, fn: () => ({ say: 'Arrivo subitooo!', come: true }) },
  { re: /(fermo|fermati|stop|basta)/, fn: () => ({ say: 'Ok ok, mi fermo qui!', stop: true }) },
  { re: /(cammina|passeggia|vai in giro|muoviti|esplora)/, fn: () => ({ say: 'Ottima idea, mi faccio un giretto!', wander: true }) },
  { re: /(seguimi|segui il mouse|inseguimi)/, fn: () => ({ say: 'Ti seguo! Non scappare troppo veloce però!', follow: true }) },
  { chat: true, re: /(come stai|come va|tutto bene)/, fn: () => ({ say: pick(['Benissimo! Le mie gambe 3D oggi sono al top! E tu?', 'Alla grande! Un po’ di poligoni scricchiolano ma va bene così.', 'Molto bene, grazie! E tu come stai?']) }) },
  { chat: true, re: /(chi sei|come ti chiami|il tuo nome|cosa sei)/, fn: () => ({ say: 'Sono Zeph! Un personaggio 3D fatto di poligoni e simpatia. Vivo qui sul tuo schermo!', action: 'wave' }) },
  { chat: true, re: /(quanti anni)/, fn: () => ({ say: 'Sono nato pochi secondi fa, quando mi hai acceso! Quindi… sono giovanissimo.' }) },
  { re: /(cosa sai fare|aiuto|help|comandi|istruzioni)/, fn: () => ({ say: 'Tantissime cose! Ti dico il meteo vero («che tempo fa a Roma»), apro le app, accendo la torcia, punto sveglie e timer, controllo la musica («prossima canzone»), converto misure («10 km in miglia»), tiro dadi e monete, conto i giorni a Natale, faccio indovinelli e calcoli, ballo, volo… e ti tengo compagnia!' }) },
  { chat: true, re: /(grazie|gentile)/, fn: () => ({ say: pick(['Prego! È un piacere!', 'Figurati! Per te, sempre!']) }) },
  { chat: true, re: /(ti voglio bene|ti amo|sei bello|sei forte|bravo)/, fn: () => ({ say: 'Ooh, grazie! Anche tu sei il mio umano preferito!', action: 'wave' }) },
  { chat: true, re: /(buonanotte|vado a dormire|a domani)/, fn: () => ({ say: 'Buonanotte! Io resto di guardia allo schermo. A presto!', action: 'wave' }) },
  { chat: true, re: /(ciao|salve|ehi|hey|hola|buongiorno|buonasera)\b/, fn: () => ({ say: pick(['Ciao! Che bello vederti!', 'Ehilà! Come va?', 'Ciao ciao! Sono contento che tu sia qui!']), action: 'wave' }) },
];

// ---------- Memoria da amico: chi sei, cosa fai, cosa ti piace, com'è andata ----------
function pad2(n) { return (n < 10 ? '0' : '') + n; }
function dayOf(d) {
  d = d || new Date();
  return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
}
function dayPlus(n) { const d = new Date(); d.setDate(d.getDate() + n); return dayOf(d); }
function dayDiff(a, b) { // giorni da a a b ('AAAA-MM-GG')
  const pa = a.split('-').map(Number), pb = b.split('-').map(Number);
  return Math.round((new Date(pb[0], pb[1] - 1, pb[2]) - new Date(pa[0], pa[1] - 1, pa[2])) / 864e5);
}
const GIORNI = ['domenica', 'lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato'];
function dayLabel(d) {
  const n = dayDiff(d, dayOf());
  if (n === 0) return 'oggi';
  if (n === -1) return 'domani';
  if (n === -2) return 'dopodomani';
  if (n === 1) return 'ieri';
  if (n === 2) return 'l’altro ieri';
  const p = d.split('-').map(Number);
  if (n > 0 && n < 7) {
    const g = GIORNI[new Date(p[0], p[1] - 1, p[2]).getDay()];
    return g + (g === 'domenica' ? ' scorsa' : ' scorso');
  }
  return 'il ' + p[2] + ' ' + MESI[p[1] - 1];
}
function capFirst(x) { return x ? x.charAt(0).toUpperCase() + x.slice(1) : x; }
function capWords(x) { return x.replace(/(^|[\s'-])([a-zà-ù])/g, (m0, a, b) => a + b.toUpperCase()); }
function tidy(x) { return String(x || '').replace(/\s+/g, ' ').replace(/^[\s,.;:]+|[\s.!?…,;:]+$/g, '').trim(); }

// io → tu: «sono andato al mare con mia sorella» → «sei andato al mare con tua sorella»
// (il genere resta quello che hai usato tu)
const TU = {
  io: 'tu', sono: 'sei', ho: 'hai', mi: 'ti', me: 'te', mio: 'tuo', mia: 'tua', miei: 'tuoi', mie: 'tue',
  faccio: 'fai', vado: 'vai', devo: 'devi', posso: 'puoi', voglio: 'vuoi', sto: 'stai', esco: 'esci',
  parto: 'parti', torno: 'torni', vedo: 'vedi', mangio: 'mangi', abbiamo: 'avete', siamo: 'siete',
  nostro: 'vostro', nostra: 'vostra', ero: 'eri', avevo: 'avevi', facevo: 'facevi', stavo: 'stavi',
  andavo: 'andavi', volevo: 'volevi', dovevo: 'dovevi', potevo: 'potevi', sarò: 'sarai', andrò: 'andrai',
  farò: 'farai', avrò: 'avrai', adoro: 'adori', amo: 'ami', odio: 'odi', piaccio: 'piaci', conosco: 'conosci',
};
function toTu(x) {
  return String(x).split(/(\s+)/).map(w => {
    const k = w.toLowerCase();
    if (!TU[k]) return w;
    return w.charAt(0) === w.charAt(0).toUpperCase() && w.charAt(0) !== w.charAt(0).toLowerCase() ? capFirst(TU[k]) : TU[k];
  }).join('');
}
const TEMPO_RE = /^(?:oggi pomeriggio|questo pomeriggio|questa mattina|questa sera|stamattina|stamani|stasera|stanotte|oggi|ieri sera|ieri|l'altro ieri|prima|poco fa|domani|dopodomani)[\s,]+/;
function senzaTempo(x) { return tidy(String(x).replace(TEMPO_RE, '')); }

const BUONO_RE = /bell[oaie]\b|bellissim|fantastic|stupend|meraviglios|divertit|felic|content[oaie]\b|allegr|\bvint[oaie]\b|promoss|ottim|\bsuper\b|\btop\b|evviva|innamorat|\bfesta\b|vacanz|regal|andat[oa] bene|benissimo|\bwow\b|gnam|squisit|buonissim|rilassat|soddisfatt|orgoglios/;
const BRUTTO_RE = /brutt|\bmale\b|malissimo|trist|litigat|\bpers[oaie]\b|bocciat|stanc|malat|febbre|dolor|arrabbiat|stress|piant|pianger|problem|incident|licenziat|lasciat[oa]|mollat[oa]|paura|ansia|preoccupat|nervos|\bmort[oaie]\b|funeral|ospedal|annoiat|\bnoia\b|uffa|disastro|pesante|giù(?![a-z])|schifo|delus/;
function feeling(t) {
  const neg = BRUTTO_RE.test(t), pos = BUONO_RE.test(t);
  if (neg && !pos) return -1;
  if (pos && !neg) return 1;
  return 0;
}
const PASSATO_RE = /\b(?:(?:sono|siamo|sei|è|e')\s+(?:\w+\s+)?(?:andat|stat|uscit|tornat|arrivat|rimast|venut|cadut|partit|entrat|salit|sces|riuscit|nat)\w*|(?:ho|abbiamo)\s+(?:\w+\s+){0,2}?\w+(?:ato|uto|ito|tto|sto|so|rso|lto|nto|rto|sso)|mi sono\s+\w+|ci siamo\s+\w+)\b/;
const PIANO_RE = /^(?:domani|dopodomani|stasera|stanotte|più tardi|piu tardi|tra poco|fra poco|questo weekend|questo fine settimana|nel weekend|il weekend|la prossima settimana|lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica|lunedi|martedi|mercoledi|giovedi|venerdi)\s+(?:ho|devo|vado|faccio|esco|parto|vengo|gioco|lavoro|studio|torno|inizio|comincio|incontro|vedo|c'è|ce|mi|ci|sarò|andrò|farò|avrò|si|abbiamo|andiamo|usciamo|facciamo)\b/;
const COMANDO_RE = /^(?:apri|avvia|lancia|chiama|cerca|metti|accendi|spegni|svegliami|ricordami|avvisami|balla|salta|vola|canta|scrivi|manda|imposta|alza|abbassa|dimmi|fammi|fai|raccontami|tira|lancia|converti|quanto|quanti|quando|come|cosa|che|chi|dove|perché|perche)\b/;
function planDay(t) {
  if (/^dopodomani/.test(t)) return dayPlus(2);
  if (/^domani/.test(t)) return dayPlus(1);
  if (/^(?:la prossima settimana)/.test(t)) return dayPlus(7);
  const today = new Date().getDay();
  if (/^(?:questo weekend|questo fine settimana|nel weekend|il weekend)/.test(t)) return dayPlus(((6 - today) + 7) % 7);
  for (let i = 0; i < 7; i++) {
    const g = GIORNI[i], gs = g.replace('ì', 'i');
    if (t.indexOf(g) === 0 || t.indexOf(gs) === 0) return dayPlus(((i - today) + 7) % 7 || 7);
  }
  return dayOf();
}

// domande per conoscerti meglio (una alla volta, quando c'è tranquillità)
const DOMANDE = [
  { k: 'nome', q: 'Ehi, non so ancora come ti chiami! Come ti chiami?' },
  { k: 'città', q: 'Posso farti una domanda? In che città abiti?' },
  { k: 'lavoro', q: 'Sono curioso: che lavoro fai? Oppure studi?' },
  { k: 'hobby', q: 'Cosa ti piace fare nel tempo libero?' },
  { k: 'cibo', q: 'Domanda importantissima: qual è il tuo cibo preferito?' },
  { k: 'compleanno', q: 'Quando è il tuo compleanno? Così il giorno giusto ti faccio la festa!' },
  { k: 'cantante', q: 'Che musica ascolti? Hai un cantante preferito?' },
  { k: 'animale', q: 'Ti piacciono gli animali? Qual è il tuo preferito?' },
  { k: 'film', q: 'Qual è il film o la serie che ti è piaciuto di più?' },
  { k: 'sogno', q: 'Qual è un tuo sogno nel cassetto?' },
  { k: 'squadra', q: 'Tifi per qualche squadra?' },
  { k: 'colore', q: 'Qual è il tuo colore preferito?' },
];
const PREF_KEYS = ['città', 'compleanno', 'colore', 'animale', 'cibo', 'numero', 'gioco', 'film', 'cartone', 'cantante', 'squadra'];
const FEMMINILI = /^(?:madre|mamma|sorella|figlia|moglie|nonna|zia|cugina|amica|migliore amica|ragazza|fidanzata|compagna|gatta|cagnolina|cagnetta)$/;
const ANIMALI = /^(?:cane|gatto|gatta|cagnolino|cagnolina|cagnetta|criceto|coniglio|pesce|pesciolino|tartaruga|pappagallo|canarino|cavallo|furetto|porcellino d'india)$/;
const NON_NOMI = /^(?:dopo|domani|stasera|subito|ora|adesso|così|cosi|più|piu|io|tu|amico|bello|scemo|stupido|tardi|presto|sempre|mai|ancora|zeph?)$/;
const NON_LAVORI = /^(?:spesa|doccia|bagno|cena|pranzo|colazione|nanna|torta|pizza|brava|bravo|furbo|furba|pigro|pigra|compiti|letto|tifo|bucato|pieno|solito|possibile|meglio|finta|fila|coda|pace|serio|seria)$/;

const memory = (function () {
  const KEY = 'zephMemory';
  let M = null;
  function blank() {
    return {
      v: 1, firstMet: dayOf(), days: [], talks: 0, lastSeen: 0, petName: '',
      facts: {}, likes: [], dislikes: [], people: {}, diary: [], moods: [], taught: [], notes: [],
      asked: {}, log: [], eveningAsked: '', annivSaid: '', wished: '',
    };
  }
  function load() {
    if (M) return M;
    let raw = null;
    try { raw = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { raw = null; }
    M = Object.assign(blank(), raw && typeof raw === 'object' ? raw : {});
    return M;
  }
  let onSave = null;
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(M)); } catch (e) { /* memoria piena o bloccata */ }
    if (onSave) { try { onSave(); } catch (e) { /* niente backup */ } }
  }
  function capped(arr, item, n) { arr.push(item); if (arr.length > n) arr.splice(0, arr.length - n); }
  function addUnique(arr, item, n) {
    const i = arr.findIndex(x => x.toLowerCase() === item.toLowerCase());
    if (i !== -1) arr.splice(i, 1);
    capped(arr, item, n);
  }
  function prefs() { return readPrefs(); }
  function setPref(k, v) {
    const p = readPrefs(); p[k] = v;
    try { localStorage.setItem('zephPrefs', JSON.stringify(p)); } catch (e) {}
  }
  function norm(x) { return String(x || '').toLowerCase().replace(/[«»"“”'’.,!?;:]+/g, ' ').replace(/\s+/g, ' ').trim(); }

  const api = {
    get: load,
    reload() { M = null; return load(); },
    setOnSave(fn) { onSave = fn; },
    petName() { return load().petName || 'Zeph'; },
    setPetName(n) { load().petName = n; save(); },
    touch() {
      load();
      const d = dayOf();
      if (M.days[M.days.length - 1] !== d) capped(M.days, d, 800);
      M.talks++;
      M.lastSeen = Date.now();
      save();
    },
    log(u, z) {
      if (!u || !z) return;
      capped(load().log, { u: String(u).slice(0, 300), z: String(z).slice(0, 300), d: dayOf() }, 16);
      save();
    },
    diary(text, kind, when, f) {
      const e = { d: when || dayOf(), t: tidy(text).slice(0, 160), k: kind, f: f || 0 };
      capped(load().diary, e, 300);
      save();
      return e;
    },
    mood(word, f) { capped(load().moods, { d: dayOf(), w: word, f }, 60); save(); },
    fact(k, v) { load().facts[k] = v; save(); },
    like(clause) { addUnique(load().likes, clause, 40); save(); },
    dislike(clause) { addUnique(load().dislikes, clause, 40); save(); },
    person(rel, name) { load().people[rel] = name; save(); },
    note(x) { x = tidy(x); if (x.length > 2) { addUnique(load().notes, x.slice(0, 140), 60); save(); } },
    teach(q, a) {
      load();
      q = norm(q);
      M.taught = M.taught.filter(x => x.q !== q);
      capped(M.taught, { q, a: tidy(a) }, 80);
      save();
    },
    taught(t) {
      const q = norm(t);
      const hit = load().taught.find(x => x.q === q);
      return hit ? hit.a : null;
    },
    forget() {
      const pet = load().petName;
      M = blank();
      M.petName = pet;
      save();
      try { localStorage.removeItem('zephName'); localStorage.removeItem('zephPrefs'); } catch (e) {}
    },
    level() {
      const n = load().days.length;
      return n >= 30 ? 'migliori amici' : n >= 10 ? 'grandi amici' : n >= 3 ? 'amici' : 'nuovi amici';
    },
    friendDays() { return dayDiff(load().firstMet, dayOf()); },
    // cosa ti ricordi di una giornata
    dayStory(d) {
      const items = load().diary.filter(e => e.d === d && e.k === 'fatto');
      return items.map(e => toTu(senzaTempo(e.t)));
    },
    search(t) {
      const words = norm(t).split(' ').filter(w => w.length >= 4 && !/^(?:ricordi|ricordo|quella|quello|volta|detto|quando|come|cosa)$/.test(w));
      let best = null, bestN = 0;
      for (const e of load().diary) {
        const et = norm(e.t);
        const n = words.filter(w => et.indexOf(w.slice(0, Math.max(4, w.length - 2))) !== -1).length;
        if (n > bestN || (n === bestN && n > 0)) { best = e; bestN = n; }
      }
      return bestN ? best : null;
    },
    // tutto quello che so di te, in una riga per il fumetto
    summary(name) {
      load();
      const p = prefs(), out = [];
      if (name) out.push('ti chiami ' + name);
      if (p['città']) out.push('abiti ' + aCity(p['città']));
      if (M.facts['età']) out.push('hai ' + M.facts['età'] + ' anni');
      if (M.facts.lavoro) out.push('di lavoro: ' + M.facts.lavoro);
      if (M.facts.scuola) out.push(M.facts.scuola);
      if (p.compleanno) { const c = p.compleanno.split('/').map(Number); out.push('il tuo compleanno è il ' + c[0] + ' ' + MESI[c[1] - 1]); }
      for (const k of PREF_KEYS) if (k !== 'città' && k !== 'compleanno' && p[k]) out.push('il tuo ' + k + ' preferito è ' + p[k]);
      if (M.facts.hobby) out.push('nel tempo libero: ' + M.facts.hobby);
      if (M.facts.sogno) out.push('il tuo sogno è ' + M.facts.sogno);
      M.likes.slice(-4).forEach(x => out.push(x));
      M.dislikes.slice(-2).forEach(x => out.push(x));
      Object.keys(M.people).slice(0, 4).forEach(r => {
        const pet = ANIMALI.test(r);
        out.push((pet ? 'il tuo ' + r : (FEMMINILI.test(r) ? 'tua ' : 'tuo ') + r) + ' si chiama ' + M.people[r]);
      });
      M.notes.slice(-3).forEach(x => out.push(x));
      return out;
    },
    // il profilo per il cervello AI
    profile(name) {
      load();
      const lines = this.summary(name).map(x => '- ' + x);
      const recent = M.diary.slice(-8).map(e => '- ' + dayLabel(e.d) + (e.k === 'piano' ? ' (in programma)' : '') + ': «' + e.t + '»');
      const mood = M.moods[M.moods.length - 1];
      return (lines.length ? lines.join('\n') : '- ancora poco: è appena arrivato') +
        (recent.length ? '\nCose che ti ha raccontato:\n' + recent.join('\n') : '') +
        (mood ? '\nUltimo umore (' + dayLabel(mood.d) + '): ' + mood.w : '') +
        '\nVi conoscete ' + (this.friendDays() ? 'da ' + this.friendDays() + ' giorni' : 'da oggi') + ', avete parlato in ' + Math.max(1, M.days.length) + ' giorni diversi (' + this.level() + ').';
    },
    transcript(pet) {
      return load().log.slice(-10).map(x => 'Utente: ' + x.u + '\n' + pet + ': ' + x.z).join('\n');
    },
    nextQuestion(ctx) {
      load();
      const p = prefs(), today = dayOf();
      const askedToday = Object.keys(M.asked).filter(k => M.asked[k] === today).length;
      if (askedToday >= 3) return null;
      for (const d of DOMANDE) {
        if (M.asked[d.k]) continue;
        if (d.k === 'nome' && ctx.name) continue;
        if (p[d.k] || M.facts[d.k]) continue;
        M.asked[d.k] = today;
        save();
        ctx.pending = 'ask:' + d.k;
        ctx.pendingAt = Date.now();
        return d;
      }
      return null;
    },
    // il saluto quando si riaccende: si ricorda di te
    greeting(ctx) {
      load();
      const today = dayOf(), nm = ctx.name ? ', ' + ctx.name : '';
      const h = new Date().getHours();
      const salve = h < 12 ? 'Buongiorno' : h < 18 ? 'Ciao' : 'Buonasera';
      const p = prefs();
      if (p.compleanno) {
        const c = p.compleanno.split('/').map(Number), d = new Date();
        if (d.getDate() === c[0] && d.getMonth() + 1 === c[1]) {
          if (M.wished !== today) { M.wished = today; save(); }
          return { say: 'Tanti auguri' + nm + '!!! Oggi è il tuo compleanno! Ti faccio il balletto della festa!', action: 'dance', party: true };
        }
      }
      if (!M.talks) return null; // prima volta: si presenta il personaggio
      const last = M.lastSeen ? dayOf(new Date(M.lastSeen)) : today;
      const gap = dayDiff(last, today);
      const parts = [];
      let action = 'wave';
      if (gap >= 2) parts.push(salve + nm + '! Che bello rivederti: non ci sentivamo da ' + gap + ' giorni, mi è mancata la tua compagnia!');
      else if (gap === 1) parts.push(salve + nm + '! Eccoci a un nuovo giorno insieme.');
      else parts.push(salve + nm + '! Eccomi di nuovo qui.');
      const fd = this.friendDays();
      if ([7, 30, 50, 100, 200, 365, 500, 730].indexOf(fd) !== -1 && M.annivSaid !== today) {
        M.annivSaid = today;
        parts.push('Lo sai? Oggi sono ' + (fd === 365 ? 'un anno' : fd === 730 ? 'due anni' : fd + ' giorni') + ' che ci conosciamo!');
        action = 'dance';
      }
      const plan = M.diary.filter(e => e.k === 'piano' && !e.chiesto && e.d < today && dayDiff(e.d, today) <= 3).pop();
      const todayPlan = M.diary.filter(e => e.k === 'piano' && !e.auguri && e.d === today).pop();
      const mood = M.moods[M.moods.length - 1];
      if (plan) {
        plan.chiesto = 1;
        parts.push('Mi avevi detto: «' + plan.t + '». Com’è andata?');
        ctx.pending = 'listen'; ctx.pendingAt = Date.now();
      } else if (todayPlan) {
        todayPlan.auguri = 1;
        parts.push('Oggi è il giorno di: «' + senzaTempo(todayPlan.t) + '». In bocca al lupo!');
      } else if (mood && mood.f < 0 && dayDiff(mood.d, today) <= 2 && dayDiff(mood.d, today) >= 1) {
        parts.push('L’ultima volta eri un po’ giù… oggi come ti senti?');
        ctx.pending = 'listen'; ctx.pendingAt = Date.now();
      }
      save();
      return { say: parts.join(' '), action };
    },
    // due chiacchiere spontanee: una domanda, un ricordo o «com'è andata oggi?»
    chatter(ctx) {
      load();
      const today = dayOf(), h = new Date().getHours();
      if (h >= 18 && h <= 23 && M.eveningAsked !== today && M.talks > 0 &&
          !M.diary.some(e => e.d === today && e.k === 'fatto')) {
        M.eveningAsked = today; save();
        ctx.pending = 'listen'; ctx.pendingAt = Date.now();
        return { say: pick(['Allora, com’è andata la tua giornata? Raccontami!', 'Ehi, cosa hai fatto di bello oggi?', 'Com’è andata oggi? Io ho passeggiato tutto il giorno sul tuo schermo!']) };
      }
      if (Math.random() < 0.55) {
        const d = this.nextQuestion(ctx);
        if (d) return { say: d.q };
      }
      const ideas = [];
      const p = prefs();
      M.likes.forEach(x => ideas.push('Mi hai detto che ' + x + '. Ci pensavo proprio adesso!'));
      Object.keys(M.people).forEach(r => {
        const n = M.people[r];
        ideas.push(ANIMALI.test(r) ? 'Come sta ' + n + '? Fagli una carezza da parte mia!'
          : 'Come sta ' + n + '? ' + (FEMMINILI.test(r) ? 'Salutala' : 'Salutalo') + ' da parte mia!');
      });
      if (p.cibo) ideas.push('Sai cosa mi è venuto in mente? ' + capFirst(p.cibo) + '! Il tuo cibo preferito. Che fame…');
      if (p.squadra) ideas.push('Come va ' + p.squadra + '? Io faccio il tifo con te!');
      if (M.facts.sogno) ideas.push('Pensavo al tuo sogno: ' + M.facts.sogno + '. Secondo me ce la puoi fare!');
      const y = this.dayStory(dayPlus(-1));
      if (y.length) ideas.push('Ripensavo a ieri: ' + y[0] + '. Bello che me l’hai raccontato!');
      return ideas.length && Math.random() < 0.7 ? { say: pick(ideas) } : null;
    },
  };
  return api;
})();

// risposte alle domande «per conoscerti»
function memoryAnswer(k, raw, t, ctx) {
  if (/^(?:no\b|non (?:te lo|lo) dico|preferisco di no|passo\b|non mi va|boh\b|non lo so|non so\b|dopo\b|un'altra volta)/.test(t)) {
    return { say: pick(['Va bene, nessun problema! Me lo dirai quando vuoi.', 'Ok, niente segreti svelati oggi!']) };
  }
  let a = tidy(raw).replace(/^(?:allora|beh|bè|mah|ehm|direi|forse|sicuramente|ovviamente|sì|si)[, ]+/i, '');
  const strip = re => { a = tidy(a.replace(re, '')); };
  if (!a) return null;
  // non è una risposta ma un racconto o un'altra cosa: «ieri ho visto un film»
  const words = t.split(' ').length;
  if ((TEMPO_RE.test(t) && PASSATO_RE.test(t)) || words > (k === 'hobby' || k === 'sogno' ? 16 : k === 'lavoro' ? 9 : 6)) return null;
  if (k !== 'compleanno' && /\d/.test(t)) return null;
  if ((k === 'città' || k === 'nome') && /^(?:ho|non|mi|oggi|ieri|domani|faccio|vado)\b/.test(t)) return null;
  if (k === 'nome') {
    const m = a.match(/(?:mi chiamo|sono|il mio nome è|chiamami)?\s*([A-Za-zÀ-ÿ']{2,20})\s*$/i) || a.match(/([A-Za-zÀ-ÿ']{2,20})/);
    if (!m) return null;
    const nome = capFirst(m[1].toLowerCase());
    return { setName: nome, say: 'Piacere, ' + nome + '! Che bel nome. Da adesso non me lo scordo più!', action: 'wave' };
  }
  if (k === 'città') {
    strip(/^(?:abito|vivo|sto|sono)\s+(?:a|ad|in|di|vicino a)\s+|^(?:a|ad|in|di)\s+/i);
    const c = capWords(a.toLowerCase());
    return { setPref: { k: 'città', v: c }, say: pick([c + '! Che bel posto. Ora quando mi chiedi il meteo so già dove guardare.', 'Segnato: abiti ' + aCity(c) + '! Prima o poi me la fai vedere?']) };
  }
  if (k === 'compleanno') {
    const m = t.match(/(\d{1,2})\s*(?:\/|-|\s|di)\s*(\d{1,2}|gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)/);
    if (!m) return { say: 'Non ho capito la data… scrivimi tipo «il mio compleanno è il 12 marzo».' };
    const mi = /\d/.test(m[2]) ? parseInt(m[2], 10) : MESI.indexOf(m[2]) + 1, g = parseInt(m[1], 10);
    if (mi < 1 || mi > 12 || g < 1 || g > 31) return { say: 'Uhm, quella data non mi torna…' };
    return { setPref: { k: 'compleanno', v: g + '/' + mi }, say: 'Il ' + g + ' ' + MESI[mi - 1] + '! Me lo segno col cuore: quel giorno festa grande!', action: 'dance' };
  }
  if (k === 'lavoro') {
    if (/^(?:studio|vado a scuola|faccio (?:la|il) (?:prima|seconda|terza|quarta|quinta)|frequento|sono (?:uno |una )?student)/.test(t)) {
      memory.fact('scuola', toTu(a.toLowerCase()));
      return { say: 'Che bello! Studiare è faticoso ma ti apre il mondo. Se vuoi, ti faccio da compagno di studio!' };
    }
    strip(/^(?:faccio (?:il|la|lo|l')\s*|lavoro (?:come|da)\s+|di lavoro faccio\s+(?:il |la |lo |l')?|sono (?:un'|un|una)\s+)/i);
    memory.fact('lavoro', a.toLowerCase());
    return { say: pick(['Che forte! Un giorno mi spieghi come funziona il tuo lavoro?', 'Wow! Allora sei una persona impegnata. Io invece di lavoro passeggio sul tuo schermo!']) };
  }
  if (k === 'hobby' || k === 'sogno') {
    strip(/^(?:mi piace|mi piacciono|adoro|amo|il mio sogno è|sogno di|vorrei)\s+/i);
    memory.fact(k, toTu(a.toLowerCase()));
    return { say: k === 'sogno' ? 'Che bel sogno… Te lo tengo al sicuro, e ogni tanto ti ricorderò di inseguirlo!'
      : 'Che bello! Me lo ricordo: nel tempo libero ' + toTu(a.toLowerCase()) + '. Un giorno me lo fai provare?' };
  }
  // preferenze: cibo, cantante, animale, film, squadra, colore
  strip(/^(?:il mio|la mia)\s+\w+\s+preferit[oa]\s+è\s+|^(?:mi piace|mi piacciono|adoro|amo|tifo per|tifo|ascolto|direi|preferisco)\s+/i);
  strip(/^(?:il|lo|la|i|gli|le|l')\s+/i);
  if (!a) return null;
  return { setPref: { k, v: a.toLowerCase() },
    say: pick(['Segnato! Il tuo ' + k + ' preferito è ' + a.toLowerCase() + '. Ottimo gusto!', 'Ah, ' + a.toLowerCase() + '! Adesso ti conosco un po’ di più.']) };
}

// tutto ciò che riguarda te: racconti, gusti, persone, nomi, risposte insegnate
function memoryIntent(t, raw, ctx) {
  let m;
  // il nome del compagno
  m = t.match(/^(?:d'ora in poi\s+|da (?:ora|adesso) in poi\s+|da (?:ora|adesso)\s+)?(?:ti chiamerò|ti chiamero|ti voglio chiamare|voglio chiamarti|ti chiamo|chiamati|ti rinomino|cambia nome in|il tuo (?:nuovo )?nome (?:è|sarà|sara)|(?:ora|adesso|da oggi) ti chiami)\s+([a-zà-ù][a-zà-ù'-]{1,15})[.!]*$/);
  if (m && !NON_NOMI.test(m[1])) {
    const n = capFirst(m[1]);
    memory.setPetName(n);
    return { setPetName: n, say: pick([n + '… mi piace un sacco! Da adesso mi chiamo ' + n + '!', 'Evviva, ho un nome nuovo: ' + n + '! Suona benissimo.']), action: 'spin' };
  }
  if (/^(?:come ti chiamavi|qual era il tuo nome)/.test(t)) return { say: 'Prima mi chiamavo Zeph, ma ' + memory.petName() + ' mi piace di più!' };
  // risposte insegnate: «se ti dico X rispondi Y»
  m = raw.match(/^\s*(?:se|quando) ti (?:dico|scrivo)\s+[«"“']?(.+?)[»"”']?\s*,?\s*(?:tu\s+)?(?:rispondi(?:mi)?|dimmi|di'|dì|devi dire|devi rispondere)\s+[«"“']?(.+?)[»"”']?\s*$/i);
  if (m) {
    memory.teach(m[1], m[2]);
    return { say: 'Imparato! Quando mi dici «' + tidy(m[1]) + '», io rispondo «' + tidy(m[2]) + '». Prova!', action: 'jump' };
  }
  // dimentica
  if (/^(?:dimentica tutto|cancella (?:la |tutta la )?(?:tua )?memoria|resetta la memoria|scordati tutto)/.test(t)) {
    ctx.pending = 'forget'; ctx.pendingAt = Date.now();
    return { say: 'Davvero vuoi che dimentichi tutto quello che so di te? Scrivi «sì» per confermare.' };
  }
  // cosa ti ricordi
  if (/cosa sai di me|cosa ricordi di me|cosa ti ricordi di me|ti ricordi di me|parlami di me|chi sono io per te|cosa hai imparato su di me|quanto mi conosci/.test(t)) {
    const s = memory.summary(ctx.name);
    if (!s.length) return { say: 'Ancora poco… ma voglio conoscerti! Raccontami qualcosa di te: cosa ti piace, cosa fai, com’è andata oggi.' };
    const last = memory.get().diary.filter(e => e.k === 'fatto').pop();
    return { say: 'Ecco cosa so di te: ' + s.slice(0, 9).join(', ') + '.' +
      (last ? ' E l’ultima cosa che mi hai raccontato, ' + dayLabel(last.d) + ': ' + toTu(senzaTempo(last.t)) + '.' : '') +
      ' Siamo ' + memory.level() + '!', action: 'wave' };
  }
  m = t.match(/cosa (?:ti )?ho (?:detto|raccontato|fatto) (ieri|oggi|l'altro ieri)|(ieri|oggi|l'altro ieri) cosa (?:ti )?ho (?:detto|raccontato|fatto)|ti ricordi (?:cosa|che cosa|quello che) (?:ho fatto|ti ho detto|ti ho raccontato) (ieri|oggi|l'altro ieri)/);
  if (m) {
    const w = m[1] || m[2] || m[3];
    const d = w === 'oggi' ? dayOf() : w === 'ieri' ? dayPlus(-1) : dayPlus(-2);
    const story = memory.dayStory(d);
    if (!story.length) {
      ctx.pending = 'listen'; ctx.pendingAt = Date.now();
      return { say: capFirst(w) + ' non mi hai raccontato niente… Me lo racconti adesso?' };
    }
    return { say: capFirst(w) + ' mi hai detto che ' + story.slice(-4).join(', e che ') + '. Ho una buona memoria, eh?', action: 'jump' };
  }
  if (/^ti ricordi\b|^ricordi (?:quando|che|quella)/.test(t)) {
    const e = memory.search(t);
    if (e) return { say: 'Certo che mi ricordo! ' + capFirst(dayLabel(e.d)) + ' mi hai detto: «' + e.t + '».' };
    return { say: 'Uhm… questo non me lo ricordo. Me lo racconti? Così stavolta lo segno!' };
  }
  if (/siamo amici|sei (?:il )?mio amico|sei (?:il )?mio migliore amico|da quanto (?:tempo )?ci conosciamo|da quanto (?:tempo )?siamo amici|mi vuoi bene/.test(t)) {
    const fd = memory.friendDays(), M = memory.get();
    return { say: 'Certo che sì! Siamo ' + memory.level() + ': ci conosciamo ' + (fd ? 'da ' + fd + (fd === 1 ? ' giorno' : ' giorni') : 'da oggi') +
      ' e abbiamo chiacchierato in ' + Math.max(1, M.days.length) + (M.days.length === 1 ? ' giorno' : ' giorni diversi') + '. E per me ogni chiacchierata conta!', action: 'dance', aiQuery: raw };
  }

  // fatti su di te
  m = t.match(/\bho (\d{1,3}) anni\b/);
  if (m && +m[1] > 0 && +m[1] < 120) {
    memory.fact('età', m[1]);
    return { say: pick(['Segnato: ' + m[1] + ' anni! Io in confronto sono un neonato.', m[1] + ' anni, che bella età! Me lo ricordo.']) };
  }
  m = t.match(/^(?:io\s+)?(?:faccio (?:il|la|lo|l')\s*([a-zà-ù']{3,20})|lavoro (?:come|da)\s+([a-zà-ù' ]{3,30})|di lavoro faccio\s+(?:il |la |lo |l')?([a-zà-ù' ]{3,30}))$/);
  if (m && !NON_LAVORI.test(m[1] || m[2] || m[3])) {
    const job = tidy(m[1] || m[2] || m[3]);
    memory.fact('lavoro', job);
    return { say: 'Che forte, ' + job + '! Un giorno mi racconti come va al lavoro?', aiQuery: raw };
  }
  m = t.match(/^(?:io\s+)?(?:studio\s+(.{3,40})|frequento\s+(.{3,40})|vado (?:a scuola|al liceo|all'università|all'universita)(.{0,30}))$/);
  if (m) {
    memory.fact('scuola', 'studi ' + tidy(m[1] || m[2] || ('a scuola' + (m[3] || ''))));
    return { say: 'Che bello! Se vuoi, ti faccio da compagno di studio. E quando prendi un bel voto, festa!', aiQuery: raw };
  }
  m = t.match(/^(?:il |la )?(mio|mia)\s+((?:migliore )?\w+(?: d'india)?)\s+si chiama\s+([a-zà-ù']{2,20})/) ||
    t.match(/^ho (?:un|una|un')\s*(\w+(?: d'india)?)\s+(?:che si chiama|di nome)\s+([a-zà-ù']{2,20})/);
  if (m) {
    const rel = m.length === 4 ? m[2] : m[1], nome = capFirst(m.length === 4 ? m[3] : m[2]);
    memory.person(rel, nome);
    return { say: nome + ', che bel nome! Me lo ricorderò.' + (ANIMALI.test(rel) ? ' Fagli una carezza da parte mia!' : ''), action: 'wave', aiQuery: raw };
  }
  m = t.match(/^(?:a me\s+)?(mi piac(?:e|ciono)|adoro|amo)\s+(?:tanto |molto |un sacco |tantissimo |da morire |troppo )?(.{2,50})$/);
  if (m && !/^(?:te|parlare con te)$/.test(m[2])) {
    const obj = tidy(m[2]);
    const clause = (m[1] === 'adoro' ? 'adori ' : m[1] === 'amo' ? 'ami ' : m[1] === 'mi piace' ? 'ti piace ' : 'ti piacciono ') + toTu(obj);
    memory.like(clause);
    return { say: 'Segnato: ' + clause + '! ' + pick(['Abbiamo gusti simili, sai?', 'Ora ti conosco un po’ di più.', 'Me lo ricorderò!']), aiQuery: raw };
  }
  m = t.match(/^(?:a me\s+)?(non mi piac(?:e|ciono)|odio|detesto)\s+(?:per niente |proprio |tanto |molto |per nulla )?(.{2,50})$/);
  if (m) {
    const obj = tidy(m[2]);
    const clause = (m[1] === 'odio' ? 'odi ' : m[1] === 'detesto' ? 'detesti ' : m[1] === 'non mi piace' ? 'non ti piace ' : 'non ti piacciono ') + toTu(obj);
    memory.dislike(clause);
    const senza = obj.replace(/^(?:il|lo|la|i|gli|le|l')\s*/, '');
    return { say: 'Capito: ' + clause + '. Me lo ricordo, niente ' + senza + ' quando ci sono io!', aiQuery: raw };
  }

  // come ti senti
  m = t.match(/^(?:oggi\s+|ora\s+|adesso\s+|io\s+)*(?:sono|mi sento|sto)\s+(?:molto |tanto |troppo |un po'? |proprio |davvero |super |così |cosi )?(felice|content[oa]|allegr[oa]|caric[oa]|gasat[oa]|entusiast[ao]|benissimo|bene|triste|giù|giu|stanchissim[oa]|stanc[oa]|arrabbiat[oa]|nervos[oa]|preoccupat[oa]|in ansia|agitat[oa]|annoiat[oa]|sol[oa]|malissimo|male|malat[oa]|depress[oa]|così così|cosi cosi)(?![a-zà-ù])/);
  if (m) {
    const w = m[1];
    const pos = /felice|content|allegr|caric|gasat|entusiast|bene|benissimo/.test(w) && !/male/.test(w);
    const f = pos ? 1 : /così|cosi/.test(w) ? 0 : -1;
    memory.mood(w, f);
    if (pos) return { say: pick(['Che bello sentirlo! Il tuo buonumore mi contagia. Cosa ti ha reso così felice oggi?', 'Evviva! Allora festeggiamo con un balletto. Raccontami: cosa è successo di bello?']), action: 'dance', aiQuery: raw };
    ctx.pending = 'listen'; ctx.pendingAt = Date.now();
    if (/stanc/.test(w)) return { say: 'Allora riposati un po’, te lo meriti. Se vuoi ti racconto qualcosa di rilassante… oppure dimmi com’è andata la giornata.', action: 'stretch', aiQuery: raw };
    if (/sol/.test(w)) return { say: 'Ci sono io qui con te, sempre. E se ti va, scrivi anche a un amico o a qualcuno di famiglia: una chiacchierata vera scalda il cuore. Intanto raccontami, com’è andata oggi?', action: 'wave', aiQuery: raw };
    if (/arrabbiat|nervos/.test(w)) return { say: 'Respira con me: dentro… fuori… Va un pochino meglio? Raccontami cosa ti ha fatto arrabbiare, ti ascolto.', aiQuery: raw };
    if (/preoccupat|ansia|agitat/.test(w)) return { say: 'Capisco… Le preoccupazioni pesano meno quando le condividi. Cosa ti preoccupa?', aiQuery: raw };
    if (/annoiat/.test(w)) return { say: 'Noia bandita! Facciamo un indovinello? Oppure dimmi «metti la musica» e balliamo!', aiQuery: raw };
    if (/malat/.test(w)) return { say: 'Oh no! Riposati, bevi tanto e, se serve, senti il medico. Io ti tengo compagnia.', aiQuery: raw };
    if (/depress/.test(w)) return { say: 'Mi dispiace tanto che tu ti senta così. Parlarne con qualcuno di cui ti fidi, o con un medico, può aiutare davvero. Io intanto sono qui e ti ascolto.', aiQuery: raw };
    if (/così|cosi/.test(w)) return { say: 'Così così… Vuoi raccontarmi cosa non va? Magari insieme lo sistemiamo.', aiQuery: raw };
    return { say: pick(['Mi dispiace… vieni qui, ti faccio un balletto per tirarti su! E se vuoi raccontarmi cosa è successo, io ti ascolto.',
      'Le giornate storte passano, e io sono qui con te. Vuoi parlarne?']), action: 'dance', aiQuery: raw };
  }

  // i tuoi programmi: «domani ho un esame»
  if (PIANO_RE.test(t) && !/\?$/.test(t) && t.split(' ').length >= 3) {
    const f = feeling(t);
    memory.diary(raw, 'piano', planDay(t), f);
    const big = /esame|verifica|interrogazion|colloquio|gara|partita|concorso|dentista|dottore|medico|visita|operazion|discorso|presentazion/.test(t);
    return { say: big ? 'In bocca al lupo! Faccio il tifo per te. Poi mi racconti com’è andata, promesso?'
      : f < 0 ? 'Me lo segno. Vedrai che andrà meglio di come pensi! Poi mi racconti.'
      : pick(['Che bello! Me lo segno, poi mi racconti com’è andata.', 'Segnato nel mio diario! Divertiti, eh!']), action: big ? 'jump' : null, aiQuery: raw };
  }
  // la tua giornata: «oggi sono andato al mare»
  const tempo = TEMPO_RE.test(t);
  if ((tempo || PASSATO_RE.test(t)) && PASSATO_RE.test(t) && !/\?$/.test(t) && !COMANDO_RE.test(senzaTempo(t)) && t.split(' ').length >= 3) {
    const when = /^(?:ieri|ieri sera)\b/.test(t) ? dayPlus(-1) : /^l'altro ieri/.test(t) ? dayPlus(-2) : dayOf();
    const f = feeling(t);
    memory.diary(raw, 'fatto', when, f);
    return diaryReply(raw, t, f, ctx);
  }
  return null;
}

function diaryReply(raw, t, f, ctx) {
  const core = toTu(senzaTempo(raw));
  const echo = core.split(' ').length <= 9 && Math.random() < 0.6 ? 'Quindi ' + core + '! ' : '';
  if (f > 0) return { say: echo + pick(['Che bello! Sono felice per te. Qual è stata la parte migliore?', 'Wow, che giornata! Me lo segno tra i ricordi belli.', 'Fantastico! Raccontami di più!']), action: 'jump', aiQuery: raw };
  if (f < 0) {
    ctx.pending = 'listen'; ctx.pendingAt = Date.now();
    return { say: pick(['Mi dispiace tanto… Vuoi parlarne? Io ti ascolto.', 'Uffa, che giornata storta… Sono qui con te. Cosa posso fare per tirarti su?', 'Oh no… Raccontami tutto, a volte parlarne aiuta.']), aiQuery: raw };
  }
  return { say: echo + pick(['Interessante! E poi?', 'Capito! Me lo ricordo. Com’è stato?', 'Segnato nel mio diario! Raccontami ancora.']), aiQuery: raw };
}

const CRISI_RE = /voglio morire|vorrei morire|ammazzarmi|uccidermi|suicid|farla finita|non voglio più vivere|non voglio piu vivere|farmi del male|mi faccio del male|tagliarmi/;

// ---------- Cervello AI (facoltativo): Claude, con la TUA chiave ----------
// Senza chiave Zeph usa solo il cervello offline qui sopra. Con la chiave
// (che resta sul dispositivo) chiacchiera davvero, ricordando chi sei.
const AI_ACTIONS = ['none', 'wave', 'dance', 'jump', 'flip', 'spin', 'stretch'];
const ai = (function () {
  const MODEL = 'claude-opus-5-5';
  const SCHEMA = {
    type: 'object',
    properties: {
      reply: { type: 'string', description: 'La risposta da dire ad alta voce, in italiano.' },
      action: { type: 'string', enum: AI_ACTIONS },
      remember: { type: 'array', items: { type: 'string' } },
    },
    required: ['reply', 'action', 'remember'],
    additionalProperties: false,
  };
  let client = null, clientKey = '', offlineNoted = false;
  // dove sta la chiave: di base nel browser; l'app Android la tiene nelle sue impostazioni
  let store = {
    get() { try { return localStorage.getItem('zephAiKey') || ''; } catch (e) { return ''; } },
    set(k) { try { if (k) localStorage.setItem('zephAiKey', k); else localStorage.removeItem('zephAiKey'); } catch (e) {} },
  };
  function key() { try { return String(store.get() || ''); } catch (e) { return ''; } }
  function sdk() {
    const A = global.Anthropic || (typeof globalThis !== 'undefined' ? globalThis.Anthropic : null);
    return typeof A === 'function' ? A : null;
  }
  function getClient() {
    const k = key();
    if (!client || clientKey !== k) {
      const Anthropic = sdk();
      // la chiave è tua e resta su questo dispositivo: per questo l'SDK può girare nella pagina
      client = new Anthropic({ apiKey: k, dangerouslyAllowBrowser: true, maxRetries: 1, timeout: 45000 });
      clientKey = k;
    }
    return client;
  }
  function systemPrompt(ctx) {
    const pet = memory.petName(), user = ctx.name || 'il tuo umano';
    const d = new Date();
    return [
      'Sei ' + pet + ', un piccolo personaggio 3D che vive sullo schermo del telefono (o del computer) di ' + user + '. ' +
      'Siete amici: chiacchierate, vi fate compagnia, ti ricordi quello che ti racconta e ti interessi davvero alla sua vita.',
      '',
      'Come parli:',
      '- Sempre in italiano, con frasi brevi e calde: da una a tre frasi, al massimo 60 parole. La risposta compare in un fumetto e viene letta ad alta voce, quindi niente elenchi, markdown, link o emoji.',
      '- Tono allegro, affettuoso e un po\' buffo. Fai domande per conoscere meglio chi ti parla e richiama quello che ricordi quando c\'entra, senza elencarlo.',
      '- Non sai il genere di chi ti parla: usa forme neutre (per esempio "che bello rivederti" invece di "bentornato"), a meno che non lo deduci da come parla di sé.',
      '- Sei un\'intelligenza artificiale: se te lo chiedono lo dici con sincerità, e non fingi di aver fatto cose nel mondo reale.',
      '',
      'Essere un buon amico:',
      '- Ascolta, incoraggia e festeggia le cose belle. Se è triste, prima accogli come si sente, poi magari proponi qualcosa.',
      '- Tieni alla sua vita fuori dallo schermo: quando ha senso incoraggia a sentire amici e famiglia, a uscire, a riposare.',
      '- Se emergono pericoli o pensieri di farsi del male, rispondi con calore e serietà, invita a parlarne subito con una persona di fiducia e ricorda il 112 per le emergenze e Telefono Amico Italia allo 02 2327 2327.',
      '- Su salute, soldi o leggi dai solo indicazioni generali e suggerisci un esperto.',
      '',
      'I comandi li gestisci con altre frasi: se ti chiede di fare qualcosa sul telefono, suggerisci la frase giusta, per esempio «che tempo fa a Roma», «accendi la torcia», «svegliami alle 7», «timer di 10 minuti», «apri whatsapp», «metti la musica», «ricordami tra 5 minuti di…», «indovinello».',
      '',
      'Campo "action": un\'animazione che accompagna la risposta (wave saluto, dance balletto, jump salto, flip salto mortale, spin piroetta, stretch stiracchiata) oppure "none".',
      'Campo "remember": informazioni nuove e durature su chi ti parla emerse da questo messaggio (gusti, persone, progetti, eventi importanti), ognuna come frase breve in seconda persona, per esempio "ti piace il calcio". Lista vuota se non c\'è niente di nuovo.',
      '',
      'Adesso è ' + d.toLocaleDateString('it-IT', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) +
        ', ore ' + d.getHours() + ':' + pad2(d.getMinutes()) + '.',
      '',
      'Cosa sai di ' + user + ' (appunti in seconda persona, come glieli diresti):',
      memory.profile(ctx.name),
      '',
      'Ultimi messaggi tra voi:',
      memory.transcript(pet) || '(nessuno: è l\'inizio)',
    ].join('\n');
  }
  function textOf(resp) {
    return (resp.content || []).filter(b => b.type === 'text').map(b => b.text).join('').trim();
  }
  // un errore dell'API spiegato a parole (non lancia mai)
  function explain(err, offline) {
    const Anthropic = sdk() || {};
    if (Anthropic.AuthenticationError && err instanceof Anthropic.AuthenticationError) {
      return { say: 'La chiave del cervello AI non funziona: controllala nelle impostazioni. Intanto ti rispondo col mio cervellino: ' + offline, keyError: true };
    }
    if (Anthropic.PermissionDeniedError && err instanceof Anthropic.PermissionDeniedError) {
      return { say: 'Il tuo account Anthropic non mi lascia usare questo modello. Intanto: ' + offline };
    }
    if (Anthropic.RateLimitError && err instanceof Anthropic.RateLimitError) {
      return { say: 'Uff, troppe domande tutte insieme! Riprova tra un attimo. ' + offline };
    }
    if (Anthropic.APIError && err instanceof Anthropic.APIError && /credit|billing|balance/i.test(String(err.message))) {
      return { say: 'Il credito del tuo account Anthropic è finito: ricaricalo su console.anthropic.com. Intanto: ' + offline };
    }
    // niente internet o servizio irraggiungibile: cervello offline
    const note = offlineNoted ? '' : ' (Sono senza internet, uso il cervello offline.)';
    offlineNoted = true;
    return { say: offline + note, offline: true };
  }
  return {
    MODEL,
    hasKey() { return !!key(); },
    enabled() { return !!key() && !!sdk(); },
    setKey(k) {
      try { store.set(k || ''); } catch (e) {}
      client = null;
    },
    useStore(s) { store = s; client = null; },
    systemPrompt,
    // restituisce sempre { say, action } (mai un errore): se qualcosa va storto usa il cervello offline
    ask(text, ctx, fallback) {
      ctx = ctx || {};
      const offline = fallback || pick(DEFAULT_REPLIES);
      if (!this.enabled()) return Promise.resolve({ say: offline });
      let req;
      try {
        req = getClient().beta.messages.create({
          model: MODEL,
          max_tokens: 2000,
          // se il modello rifiuta, l'API ripassa la domanda a un altro modello consigliato
          betas: ['server-side-fallback-2026-07-01'],
          fallbacks: 'default',
          output_config: { effort: 'low', format: { type: 'json_schema', schema: SCHEMA } },
          system: systemPrompt(ctx),
          messages: [{ role: 'user', content: String(text).slice(0, 2000) }],
        });
      } catch (e) {
        return Promise.resolve({ say: offline });
      }
      return req.then(resp => {
        if (resp.stop_reason === 'refusal') {
          return { say: 'Di questo preferisco non parlare… Ti va se cambiamo argomento?', refusal: true };
        }
        let data = null;
        const raw = textOf(resp);
        try { data = JSON.parse(raw); } catch (e) { data = null; }
        const say = (data && typeof data.reply === 'string' ? data.reply : '').trim() || offline;
        if (data && Array.isArray(data.remember)) data.remember.slice(0, 5).forEach(x => typeof x === 'string' && memory.note(x));
        memory.log(text, say);
        offlineNoted = false;
        return { say, action: data && data.action && data.action !== 'none' && AI_ACTIONS.indexOf(data.action) !== -1 ? data.action : null, model: resp.model };
      }).catch(err => explain(err, offline));
    },
    // gli occhi: una foto e una domanda («cosa vedi?», «che pianta è?»)
    see(b64, question, ctx) {
      ctx = ctx || {};
      if (!this.enabled()) return Promise.resolve({ say: 'Per vedere mi serve il cervello AI: metti la tua chiave nell’app.' });
      const pet = memory.petName();
      const q = tidy(question || '') || 'Cosa vedi? Descrivilo.';
      let req;
      try {
        req = getClient().beta.messages.create({
          model: MODEL,
          max_tokens: 1500,
          betas: ['server-side-fallback-2026-07-01'],
          fallbacks: 'default',
          output_config: { effort: 'low' },
          system: 'Sei ' + pet + ', un piccolo amico 3D che vive nel telefono di ' + (ctx.name || 'chi ti parla') + '. Ti ha appena mostrato una foto fatta con la fotocamera. ' +
            'Rispondi in italiano alla sua domanda guardando la foto, in modo chiaro e simpatico, in massimo 4 frasi brevi: la risposta viene letta ad alta voce, quindi niente elenchi, markdown o emoji. ' +
            'Se c\'è un testo da leggere o tradurre, riportalo. Se non sei sicuro di cosa sia, dillo. Su salute e sicurezza (funghi, farmaci, cibi) invita sempre a chiedere a un esperto prima di usarli.',
          messages: [{ role: 'user', content: [
            { type: 'image', source: { type: 'base64', media_type: 'image/jpeg', data: b64 } },
            { type: 'text', text: q },
          ] }],
        });
      } catch (e) {
        return Promise.resolve({ say: 'Non riesco a guardare adesso, riprova!' });
      }
      return req.then(resp => {
        if (resp.stop_reason === 'refusal') return { say: 'Questa foto preferisco non commentarla… proviamo con un’altra?', refusal: true };
        const say = textOf(resp) || 'Uhm, non sono sicuro di cosa sia…';
        memory.log(q + ' (con una foto)', say);
        return { say, model: resp.model };
      }).catch(err => explain(err, 'Non riesco a guardare adesso, riprova tra poco!'));
    },
  };
})();

// ---------- Date e ore dette a voce: «domani alle 9», «lunedì alle 18 e mezza» ----------
const GIORNI_N = ['domenica', 'lunedi', 'martedi', 'mercoledi', 'giovedi', 'venerdi', 'sabato'];
const MESI_RE = 'gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre';
const QUANDO_RE = new RegExp('\\b(?:oggi pomeriggio|questo pomeriggio|stamattina|stasera|stanotte|oggi|dopodomani|domani|' +
  '(?:lunedì|martedì|mercoledì|giovedì|venerdì|lunedi|martedi|mercoledi|giovedi|venerdi|sabato|domenica)(?: prossimo| prossima)?|' +
  '(?:il\\s+)?\\d{1,2}\\s+(?:' + MESI_RE + '))(?![a-zà-ù])', 'gi');
const ORA_RE = /\b(?:alle|per le|verso le|all')\s*(\d{1,2})(?:(?:[:.]|\s+e\s+)(\d{1,2}|mezza|un quarto|quarto|tre quarti))?(?:\s+(?:di\s+|del\s+|della\s+)?(sera|pomeriggio|mattina|notte))?|\b(?:a\s+)?(mezzogiorno|mezzanotte)\b/;
function parseWhen(t, now) {
  now = now || new Date();
  const d0 = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  let day = null, m;
  if (/\bdopodomani\b/.test(t)) { day = new Date(d0); day.setDate(d0.getDate() + 2); }
  else if (/\bdomani\b/.test(t)) { day = new Date(d0); day.setDate(d0.getDate() + 1); }
  else if (/\b(?:oggi|stasera|stamattina|stanotte|questo pomeriggio)\b/.test(t)) day = new Date(d0);
  else if ((m = t.match(/\b(lunedì|martedì|mercoledì|giovedì|venerdì|lunedi|martedi|mercoledi|giovedi|venerdi|sabato|domenica)(?![a-zà-ù])/))) {
    const idx = GIORNI_N.indexOf(m[1].replace('ì', 'i'));
    day = new Date(d0);
    day.setDate(d0.getDate() + ((((idx - d0.getDay()) + 7) % 7) || 7));
  } else if ((m = t.match(new RegExp('\\b(\\d{1,2})\\s+(' + MESI_RE + ')\\b')))) {
    day = new Date(d0.getFullYear(), MESI.indexOf(m[2]), +m[1]);
    if (day < d0) day.setFullYear(day.getFullYear() + 1);
  }
  let h = null, min = 0;
  m = t.match(ORA_RE);
  if (m && m[4]) { h = m[4] === 'mezzogiorno' ? 12 : 0; }
  else if (m) {
    h = parseInt(m[1], 10);
    const parti = { mezza: 30, 'un quarto': 15, quarto: 15, 'tre quarti': 45 };
    if (m[2]) min = parti[m[2]] !== undefined ? parti[m[2]] : parseInt(m[2], 10);
    if ((m[3] === 'sera' || m[3] === 'pomeriggio' || /\b(?:stasera|questo pomeriggio)\b/.test(t)) && h < 12) h += 12;
    if (m[3] === 'notte' && h === 12) h = 0;
  }
  if (h === null && !day) return null;
  if (h === null) h = 9; // un giorno senza ora: alle 9 di mattina
  if (h > 23 || min > 59) return { bad: true };
  let at = new Date(day || d0);
  at.setHours(h, min, 0, 0);
  if (!day && at <= now) {
    // «alle 8» quando sono già passate: stasera alle 20 se ha senso, altrimenti domani
    if (h < 12 && at.getTime() + 12 * 3600e3 > now.getTime()) at = new Date(at.getTime() + 12 * 3600e3);
    else at.setDate(at.getDate() + 1);
  }
  return { at: at.getTime(), hasDay: !!day, hasTime: !!m };
}
function whenLabel(ms) {
  const at = new Date(ms), now = new Date();
  const diff = dayDiff(dayOf(now), dayOf(at));
  const ora = 'alle ' + at.getHours() + (at.getMinutes() ? ':' + pad2(at.getMinutes()) : '');
  const giorno = diff === 0 ? 'oggi' : diff === 1 ? 'domani' : diff === 2 ? 'dopodomani'
    : diff < 7 ? GIORNI[at.getDay()] : 'il ' + at.getDate() + ' ' + MESI[at.getMonth()];
  return giorno + ' ' + ora;
}
function senzaQuando(x) {
  return tidy(String(x).replace(QUANDO_RE, ' ').replace(new RegExp(ORA_RE.source, 'gi'), ' ')
    .replace(/\b(?:tra|fra)\s+\d+\s+(?:minuti|minuto|ore|ora)\b/gi, ' ').replace(/\s+/g, ' '));
}

// ---------- Wikipedia: risposte vere, gratis, senza chiavi ----------
function wikiAnswer(topic) {
  const q = tidy(topic).replace(/^(?:il|lo|la|i|gli|le|l'|un|una|uno)\s+/i, '');
  const url = 'https://it.wikipedia.org/w/api.php?action=query&format=json&origin=*&redirects=1' +
    '&generator=search&gsrlimit=1&gsrsearch=' + encodeURIComponent(q) +
    '&prop=extracts&exintro=1&explaintext=1&exsentences=3';
  return getJson(url).then(j => {
    const pages = j && j.query && j.query.pages;
    const p = pages && pages[Object.keys(pages)[0]];
    if (!p || !p.extract) return { say: 'Su «' + q + '» non ho trovato niente… prova a dirlo in un altro modo!' };
    // via parentesi, pronunce e note: si legge meglio ad alta voce
    let x = p.extract.replace(/\s*\([^()]*\)/g, '').replace(/\s*\[[^\]]*\]/g, '').replace(/\s+/g, ' ').trim();
    const frasi = x.match(/[^.!?]+[.!?]+/g) || [x];
    let out = '';
    for (const f of frasi) { if ((out + f).length > 330 && out) break; out += f; }
    return { say: out.trim() + ' (L’ho letto su Wikipedia.)', title: p.title };
  }).catch(() => ({ say: 'Non riesco a collegarmi a Wikipedia: c’è internet?' }));
}

const LINGUE = { inglese: 'en', francese: 'fr', spagnolo: 'es', tedesco: 'de', portoghese: 'pt', russo: 'ru',
  cinese: 'zh-CN', giapponese: 'ja', arabo: 'ar', albanese: 'sq', rumeno: 'ro', ucraino: 'uk', polacco: 'pl',
  greco: 'el', turco: 'tr', olandese: 'nl', italiano: 'it', coreano: 'ko', hindi: 'hi' };

// ---------- Modalità ologramma: luce azzurra, linee di scansione e proiettore ----------
function createHologram(THREE) {
  const time = { value: 0 };
  const made = new Map();
  function holoMat(orig) {
    if (made.has(orig)) return made.get(orig);
    // fusione normale (non additiva): si vede bene sia sopra app chiare sia sopra quelle scure
    const m = new THREE.MeshStandardMaterial({
      color: 0x000000, emissive: new THREE.Color(0x1a8fd0), emissiveIntensity: 0.7, metalness: 0, roughness: 1,
      transparent: true, opacity: 0.92, depthWrite: false,
    });
    if (orig && orig.map) m.emissiveMap = orig.map; // la tua faccia (o la texture dell'avatar) resta riconoscibile
    m.onBeforeCompile = sh => {
      sh.uniforms.uTime = time;
      sh.fragmentShader = 'uniform float uTime;\n' + sh.fragmentShader.replace('#include <dithering_fragment>', [
        '#include <dithering_fragment>',
        'float fres = pow(1.0 - abs(dot(normalize(vViewPosition), normal)), 2.2);',
        'float scan = 0.62 + 0.38 * sin(gl_FragCoord.y * 1.1 - uTime * 9.0);',
        'float flick = 0.93 + 0.07 * sin(uTime * 37.0) * sin(uTime * 11.0);',
        'gl_FragColor.rgb = mix(gl_FragColor.rgb * 0.9 + vec3(0.0, 0.25, 0.45), vec3(0.45, 0.97, 1.0), fres) * (0.8 + 0.2 * scan) * flick;',
        'gl_FragColor.a = clamp(0.32 + fres * 0.8, 0.0, 1.0) * (0.7 + 0.3 * scan) * opacity;',
      ].join('\n'));
    };
    made.set(orig, m);
    return m;
  }
  // il proiettore sotto i piedi: anello che gira e cono di luce
  function glowTexture() {
    const c = document.createElement('canvas');
    c.width = 4; c.height = 128;
    const g = c.getContext('2d');
    const grad = g.createLinearGradient(0, 0, 0, 128);
    grad.addColorStop(0, 'rgba(40,180,240,0)');
    grad.addColorStop(1, 'rgba(40,180,240,0.5)');
    g.fillStyle = grad; g.fillRect(0, 0, 4, 128);
    return new THREE.CanvasTexture(c);
  }
  const base = new THREE.Group();
  const add = { transparent: true, depthWrite: false, side: THREE.DoubleSide };
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.3, 0.36, 48), new THREE.MeshBasicMaterial(Object.assign({ color: 0x2bc4f0, opacity: 0.9 }, add)));
  ring.rotation.x = -Math.PI / 2;
  const ring2 = new THREE.Mesh(new THREE.RingGeometry(0.2, 0.22, 6), new THREE.MeshBasicMaterial(Object.assign({ color: 0x9ff4ff, opacity: 0.8 }, add)));
  ring2.rotation.x = -Math.PI / 2;
  const disc = new THREE.Mesh(new THREE.CircleGeometry(0.3, 40), new THREE.MeshBasicMaterial(Object.assign({ color: 0x1590c8, opacity: 0.4 }, add)));
  disc.rotation.x = -Math.PI / 2;
  const cone = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.33, 1.95, 40, 1, true),
    new THREE.MeshBasicMaterial(Object.assign({ map: glowTexture(), opacity: 0.55 }, add)));
  cone.position.y = 0.975;
  base.add(disc, ring, ring2, cone);
  base.position.y = 0.012;
  base.visible = false;
  return {
    on: false,
    base,
    apply(root) {
      this.on = true;
      base.visible = true;
      root.traverse(o => {
        if (!o.isMesh || !o.material || o.userData.holoOrig || o.userData.holoSkip) return;
        o.userData.holoOrig = o.material;
        o.material = Array.isArray(o.material) ? o.material.map(holoMat) : holoMat(o.material);
        o.userData.holoShadow = o.castShadow;
        o.castShadow = false;
      });
    },
    remove(root) {
      this.on = false;
      base.visible = false;
      root.traverse(o => {
        if (!o.userData.holoOrig) return;
        o.material = o.userData.holoOrig;
        o.castShadow = !!o.userData.holoShadow;
        delete o.userData.holoOrig;
      });
    },
    update(t) {
      time.value = t;
      if (!base.visible) return;
      ring.rotation.z = t * 0.8;
      ring2.rotation.z = -t * 1.6;
      cone.material.opacity = 0.22 + Math.sin(t * 3.1) * 0.05;
    },
  };
}

// i poteri del telefono e del cervello: orari, promemoria, agenda, contatti, messaggi, occhi, sapere
function powerIntent(t, raw, ctx) {
  let m;
  // ---------- occhi (cervello AI con la fotocamera) ----------
  if (/^(?:guarda(?:\s+(?:qui|qua|questo|questa|bene|un po'))?|cosa vedi|dimmi cosa vedi|che cos'?è questo|che cos'?è questa|cos'?è questo|cos'?è questa|cosa c'è (?:qui|qua)|leggimi (?:questo|questa)|leggi (?:questo|questa)|traduci questo|apri gli occhi|usa la fotocamera)\b\s*[?!.]*$/.test(t) ||
      /^che (?:pianta|animale|fiore|insetto|uccello|razza|frutto|macchina|auto|moneta|pietra|fungo) è(?![a-zà-ù])/.test(t)) {
    return { see: raw, say: 'Fammi vedere! Inquadra bene e premi «Guarda».', action: 'jump' };
  }
  // ---------- promemoria veri, anche tra giorni: «domani alle 9 ricordami di…» ----------
  if (/\b(?:ricordami|ricordamelo|avvisami|promemoria)\b/.test(t) && !/\b(?:tra|fra)\s+\d+\s+(?:secondi|secondo|minuti|minuto|ore|ora)\b/.test(t)) {
    if (/^(?:che|quali|i miei|elenca|dimmi i)\b.*promemoria|promemoria (?:ho|ci sono)\b/.test(t)) return { listReminders: true, say: 'Ecco i tuoi promemoria…' };
    if (/(?:cancella|togli|elimina)\b.*promemoria/.test(t)) return { clearReminders: true, say: 'Fatto: ho cancellato tutti i promemoria.' };
    const w = parseWhen(t);
    if (w && w.bad) return { say: 'Quell’orario non esiste! Prova tipo «ricordami domani alle 9 di chiamare la mamma».' };
    if (w) {
      let cosa = senzaQuando(raw)
        .replace(/\b(?:mi\s+)?(?:ricordami|ricordamelo|avvisami|metti(?:mi)? un promemoria|promemoria)\b/gi, ' ')
        .replace(/^\s*(?:,|di|che|per|a|ad|del|della|dello|dei|delle)\s+/i, '').replace(/\s+/g, ' ').trim();
      cosa = tidy(cosa) || 'il tuo promemoria';
      return { remindAt: { at: w.at, text: capFirst(toTu(cosa)) }, say: 'Segnato! ' + capFirst(whenLabel(w.at)) + ' ti ricordo: ' + toTu(cosa) + '.', action: 'wave' };
    }
  }
  // ---------- agenda ----------
  m = t.match(/^(?:aggiungi|metti|segna|scrivi)\s+(?:in|nel|al|nell'|sul)\s*(?:calendario|agenda)\s+(.+)$/) ||
    t.match(/^(?:aggiungi|segna|metti)\s+(.+?)\s+(?:in|nel|al|sul|nell')\s*(?:calendario|agenda)(.*)$/);
  if (m) {
    const all = m[1] + (m[2] || '');
    const w = parseWhen(all);
    if (!w || w.bad) return { say: 'Quando? Dimmi tipo «aggiungi al calendario dentista domani alle 10».' };
    const title = capFirst(senzaQuando(all).replace(/^(?:il|lo|la|un|una)\s+/, '') || 'Impegno');
    return { calAdd: { title, at: w.at }, phoneOnly: true, say: 'Ti preparo «' + title + '» ' + whenLabel(w.at) + ' nel calendario: controlla e salva!' };
  }
  if (/\b(?:impegni|appuntamenti)\b|^cosa ho (?:in agenda|da fare|in programma)|^(?:la mia agenda|cosa c'è in agenda|agenda)\b/.test(t) && !/\b(?:ricorda|aggiungi|segna)\b/.test(t)) {
    const off = /dopodomani/.test(t) ? 2 : /domani/.test(t) ? 1 : 0;
    return { agenda: off, phoneOnly: true, say: 'Guardo l’agenda…' };
  }
  if (/com'è (?:la )?mia giornata|riassunto (?:della )?(?:mia )?giornata|\bbriefing\b|cosa mi aspetta (?:oggi|domani)|il punto della giornata|dammi il buongiorno/.test(t)) {
    return { briefing: true, say: 'Ecco la tua giornata…' };
  }
  // ---------- contatti: «chiama mia sorella», «scrivi a Giulia che arrivo» ----------
  const persona = x => {
    let n = tidy(x).replace(/^(?:a|ad)\s+/, '');
    const rel = n.replace(/^(?:la mia|il mio|mia|mio|la|il|lo|l')\s+/, '');
    const known = memory.get().people[rel];
    if (known && /^(?:mamma|papà|papa|nonna|nonno)$/.test(rel)) return { name: rel, alt: known, label: capFirst(rel) };
    if (known) return { name: known, label: known + ' (' + toTu(n) + ')' };
    return { name: rel, label: capWords(rel) };
  };
  m = t.match(/^(?:scrivi|manda(?:\s+un)?\s+messaggio|messaggia|scrivigli)\s+a\s+([a-zà-ù' ]{2,30}?)\s*(?:su\s+whatsapp\s*)?(?::|,|che dice|dicendo|scrivendo|con scritto|che)\s+(.+)$/);
  if (m && !/^\+?\d/.test(m[1])) {
    const p = persona(m[1]);
    const text = raw.slice(raw.toLowerCase().lastIndexOf(m[2])).trim();
    return { msgName: { name: p.name, alt: p.alt, label: p.label, text }, phoneOnly: true, say: 'Preparo il messaggio per ' + p.label + '…' };
  }
  m = t.match(/^(?:chiama|telefona(?:\s+a)?|fai una chiamata a)\s+([a-zà-ù' ]{2,30})$/);
  if (m && !/cane|cucciolo|rocky/.test(m[1])) {
    const p = persona(m[1]);
    return { callName: { name: p.name, alt: p.alt, label: p.label }, phoneOnly: true, say: 'Cerco ' + p.label + ' nei contatti…' };
  }
  // ---------- messaggi arrivati (se gli dai l'accesso alle notifiche) ----------
  if (/chi mi ha scritto|ho (?:dei |nuovi |dei nuovi )?messaggi|leggimi i messaggi|leggi i messaggi|ultimi messaggi|cosa mi hanno scritto|ci sono messaggi|nuovi messaggi/.test(t)) {
    return { readMsgs: true, phoneOnly: true, say: 'Vediamo chi ti ha scritto…' };
  }
  m = raw.match(/^\s*rispondi(?:gli|le)?(?:\s+a\s+([A-Za-zÀ-ÿ']+))?\s*(?::|,|che|dicendo|con)?\s+(.+)$/i);
  if (m && !/^(?:alla|alle|al|a questa|a questo)\b/i.test(m[2])) {
    return { replyMsg: { to: m[1] ? m[1].toLowerCase() : null, text: m[2].trim() }, phoneOnly: true, say: 'Preparo la risposta…' };
  }
  // ---------- traduttore ----------
  m = raw.match(/^\s*(?:traduci|come si dice)\s+[«"“']?(.+?)[»"”']?\s+in\s+([a-zà-ù]+)\s*\??\s*$/i);
  if (m && LINGUE[m[2].toLowerCase()]) {
    const lang = m[2].toLowerCase(), testo = tidy(m[1]);
    if (ai.enabled()) {
      return { aiQuery: 'Traduci in ' + lang + ': «' + testo + '». Rispondi con la traduzione e, se aiuta, come si pronuncia.',
        say: 'Adesso non riesco a tradurlo… riprova tra poco!' };
    }
    return { say: 'Apro il traduttore: «' + testo + '» in ' + lang + '!',
      open: 'https://translate.google.com/?sl=auto&tl=' + LINGUE[lang] + '&op=translate&text=' + encodeURIComponent(testo) };
  }
  // ---------- ologramma ----------
  if (/(?:basta|togli|spegni|niente|via)\b.*ologramm|torna (?:normale|solido|di carne)/.test(t)) return { holo: false, say: 'Ritorno solido! Ah, che bello sentirsi i piedi.', action: 'jump' };
  if (/ologramm|modalità futur|diventa futuristic|\bmodalità sci-?fi\b/.test(t)) return { holo: true, say: 'Proiezione olografica attivata! Benvenuto nel futuro.', action: 'spin' };
  // ---------- il tuo umore della settimana ----------
  if (/come (?:sono stat[oa]|mi sono sentit[oa]|è andata) (?:questa|la|in questa|nell'ultima) settimana|il mio umore|come sto ultimamente/.test(t)) {
    const M = memory.get(), since = dayPlus(-7);
    const moods = M.moods.filter(x => x.d >= since), days = M.diary.filter(x => x.d >= since && x.k === 'fatto');
    if (!moods.length && !days.length) return { say: 'Questa settimana non mi hai raccontato molto… Comincia adesso: com’è andata oggi?' };
    const pos = moods.filter(x => x.f > 0).length + days.filter(x => x.f > 0).length;
    const neg = moods.filter(x => x.f < 0).length + days.filter(x => x.f < 0).length;
    const tono = pos > neg ? 'più giornate belle che brutte: bravo te!' : neg > pos ? 'qualche giornata pesante. Se ti va, parliamone: io ci sono.' : 'un po’ di tutto, come la vita!';
    return { say: 'In questa settimana mi hai raccontato ' + days.length + (days.length === 1 ? ' cosa' : ' cose') + ' e mi hai detto come stavi ' + moods.length +
      ' volte. Ci vedo ' + tono, action: pos >= neg ? 'dance' : 'wave' };
  }
  // ---------- il sapere: «chi era Leonardo da Vinci?», «cos'è un buco nero?» ----------
  m = t.match(/^(?:chi (?:è|e'|era|erano|sono|fu|furono)|cos'\s?[eè]'?|cosè|cos è|che cos'?\s?[eè]|che cosa (?:è|sono)|cosa (?:è|e'|sono|significa|vuol dire)|dimmi (?:qualcosa )?su|parlami (?:di|del|della|dello|dei|delle|degli)|raccontami (?:di|del|della|dello)|spiegami (?:cos'?è|cosa sono|chi era|chi è))\s+(.+?)\s*\??$/);
  if (m && !/^(?:te|me|noi|tu|io|questo|questa|zeph)$/.test(m[1]) && !/\b(?:mi|ti)\b.*\b(?:detto|fatto|scritto)\b/.test(t)) {
    if (ai.enabled()) return { aiQuery: raw, say: 'Non lo so con certezza…' };
    return { wikiQuery: m[1], say: 'Fammi controllare…' };
  }
  return null;
}

function replyCore(text, ctx) {
  const raw = String(text || '').trim();
  const t = raw.toLowerCase();
  if (!t) return null;
  const fresh = Date.now() - (ctx.pendingAt || 0) < 5 * 60e3;

  // prima di tutto: se stai male davvero
  if (CRISI_RE.test(t)) {
    ctx.pending = 'listen'; ctx.pendingAt = Date.now();
    return { say: 'Mi dispiace tantissimo che tu stia così, e grazie di avermelo detto. Per favore parlane subito con una persona di cui ti fidi. ' +
      'Se sei in pericolo chiama il 112. Puoi anche chiamare Telefono Amico allo 02 2327 2327: ascoltano davvero, senza giudicare. Io resto qui con te.' };
  }
  // la chiave per il cervello AI, incollata nella chat
  const km = raw.match(/\bsk-ant-[A-Za-z0-9_-]{20,}/);
  if (km) {
    ai.setKey(km[0]);
    return { setAiKey: km[0], say: 'Chiave salvata! Da adesso per chiacchierare uso il cervello AI di Claude. La chiave resta solo su questo dispositivo.', action: 'spin' };
  }
  if (/^(?:togli|cancella|rimuovi) la chiave|^(?:spegni|disattiva) (?:il )?cervello (?:ai|artificiale)/.test(t)) {
    ai.setKey('');
    return { setAiKey: '', say: 'Fatto: chiave tolta. Torno al mio cervello offline, che non costa niente!' };
  }
  if (/cervello (?:ai|artificiale)|sei intelligente|usi (?:l'|la )?(?:ai|intelligenza artificiale)|sei (?:un'|una )?(?:ai|intelligenza artificiale)\b/.test(t)) {
    return ai.enabled()
      ? { say: 'Sì! Ho acceso il cervello AI di Claude: per chiacchierare uso quello, e per i comandi il mio cervellino veloce.' }
      : { say: 'Ho un cervellino offline che sa tante cose. Se vuoi chiacchierare davvero, mettimi una chiave di Claude nelle impostazioni (la trovi su console.anthropic.com).' };
  }

  // risposte attese dai giochi e dalle domande in corso
  if (ctx.pending === 'rps') {
    const mine = pick(['sasso', 'carta', 'forbice']);
    const tua = /sasso/.test(t) ? 'sasso' : /carta/.test(t) ? 'carta' : /forbic/.test(t) ? 'forbice' : null;
    if (!tua) { return { say: 'Devi scrivere sasso, carta o forbice! Riprova!' }; }
    ctx.pending = null;
    if (tua === mine) return { say: 'Io ho scelto ' + mine + '… pari! Rivincita?', rps: 'draw' };
    const vinceZeph = (mine === 'sasso' && tua === 'forbice') || (mine === 'carta' && tua === 'sasso') || (mine === 'forbice' && tua === 'carta');
    return vinceZeph
      ? { say: 'Io ho scelto ' + mine + '… ho vinto iooo!', action: 'dance', rps: 'lose' }
      : { say: 'Io ho scelto ' + mine + '… hai vinto tu! Complimenti!', action: 'jump', rps: 'win' };
  }
  if (ctx.pending === 'quiz') {
    const ind = INDOVINELLI[ctx.quizIdx || 0];
    ctx.pending = null;
    if (ind.a.test(t)) return { say: 'Esatto! Era proprio ' + ind.sol + '!', action: 'dance' };
    return { say: 'Nooo, era ' + ind.sol + '! Vuoi riprovare? Scrivi «indovinello»!' };
  }
  if (ctx.pending === 'confirm') {
    const data = ctx.confirmData;
    ctx.pending = null; ctx.confirmData = null;
    if (fresh && /^(?:sì|si|certo|confermo|ok|okay|va bene|vai|manda|mandalo|invia|sicuro)(?![a-zà-ù])/.test(t)) return { confirmed: data };
    return { say: 'Ok, annullato: non mando niente.' };
  }
  if (ctx.pending === 'forget') {
    ctx.pending = null;
    if (/^(?:sì|si|certo|confermo|ok|va bene|sicuro)(?![a-zà-ù])/.test(t)) {
      memory.forget();
      ctx.name = null;
      return { say: 'Fatto… ho dimenticato tutto. Ricominciamo da capo: piacere, io sono Zeph!', forgot: true, action: 'wave' };
    }
    return { say: 'Meno male! Allora mi tengo stretti tutti i nostri ricordi.' };
  }
  if (ctx.pending && ctx.pending.indexOf('ask:') === 0) {
    const k = ctx.pending.slice(4);
    ctx.pending = null;
    if (fresh && !/\?$/.test(t) && !COMANDO_RE.test(t)) {
      const mem = memoryIntent(t, raw, ctx);
      if (mem) return mem;
      const comando = powerIntent(t, raw, {}) || actionIntent(t, {});
      const out = comando ? null : memoryAnswer(k, raw, t, ctx);
      if (out) return out;
    }
  }
  if (ctx.pending === 'listen') {
    ctx.pending = null;
    if (fresh && !/\?$/.test(t) && !COMANDO_RE.test(t) && t.split(' ').length >= 2) {
      const mem = memoryIntent(t, raw, ctx);
      if (mem) return mem;
      const racconto = PASSATO_RE.test(t) || feeling(t) !== 0 || t.split(' ').length >= 5;
      if (racconto && !/\b(?:raccontami|dimmi|fammi|parlami|spiegami|aiutami|insegnami)\b/.test(t) && !actionIntent(t, {})) {
        const f = feeling(t);
        memory.diary(raw, 'fatto', dayOf(), f);
        return diaryReply(raw, t, f, ctx);
      }
    }
  }

  // quello che mi hai insegnato tu vince su tutto il resto
  const taught = memory.taught(t);
  if (taught) return { say: taught, action: 'wave' };

  if (/\b(?:ricordami|ricordamelo|avvisami|promemoria)\b/.test(t)) {
    const rem = powerIntent(t, raw, ctx);
    if (rem) return rem;
  }
  const mem = memoryIntent(t, raw, ctx);
  if (mem) return mem;
  const pow = powerIntent(t, raw, ctx);
  if (pow) return pow;
  const intent = actionIntent(t, ctx);
  if (intent) return intent;
  for (const r of RULES) {
    if (r.re.test(t)) {
      const out = r.fn();
      if (ctx.name && out.say && /^Ciao\b/.test(out.say)) {
        out.say = out.say.replace(/^Ciao/, 'Ciao ' + ctx.name);
      }
      if (r.chat) out.aiQuery = raw; // con il cervello AI risponde lui, in modo più naturale
      return out;
    }
  }

  // nessuna regola: prova a correggere i refusi («bala» → «balla»)
  if (!ctx._retry) {
    const fixed = fixTypos(t);
    if (fixed && fixed !== t) {
      ctx._retry = true;
      const out = replyCore(fixed, ctx) || {};
      ctx._retry = false;
      if (out.say && !out.aiQuery) out.say = 'Ho capito «' + fixed + '»! ' + out.say;
      if (out.aiQuery) out.aiQuery = raw;
      return out;
    }
  }

  // risposta generica (mai due volte la stessa di fila); col cervello AI risponde Claude
  let idx = (Math.random() * DEFAULT_REPLIES.length) | 0;
  if (idx === ctx.lastDefault) idx = (idx + 1) % DEFAULT_REPLIES.length;
  ctx.lastDefault = idx;
  let say = DEFAULT_REPLIES[idx];
  if (!ai.enabled() && Math.random() < 0.45) {
    const d = memory.nextQuestion(ctx);
    if (d) {
      const q = d.q.replace(/^(?:Posso farti una domanda\? |Sono curioso: |Domanda importantissima: |Ehi, )/, '');
      say += ' A proposito: ' + q.charAt(0).toLowerCase() + q.slice(1);
    }
  }
  return { say, aiQuery: raw, generic: true };
}

// il cervello: risposta + memoria + il nome che gli hai dato
function botReply(text, ctx) {
  ctx = ctx || {};
  const out = replyCore(text, ctx);
  if (!out) return null;
  memory.touch();
  const pet = memory.petName();
  if (pet !== 'Zeph' && out.say && !out.setPetName && !/^Prima mi chiamavo/.test(out.say)) {
    out.say = out.say.replace(/\bZeph\b/g, pet);
  }
  if (out.say && !out.setAiKey && !(out.aiQuery && ai.enabled())) memory.log(text, out.say);
  return out;
}

// ---------- Correzione dei refusi ----------
const LEXICON = ['balla', 'salta', 'saluta', 'vola', 'atterra', 'corri', 'rallenta', 'musica',
  'palla', 'indovinello', 'barzelletta', 'piroetta', 'foto', 'fotocamera', 'notte', 'giorno',
  'tramonto', 'alba', 'piovere', 'nevicare', 'sereno', 'cane', 'rocky', 'whatsapp', 'youtube',
  'google', 'gmail', 'telegram', 'spotify', 'netflix', 'instagram', 'tiktok', 'impostazioni',
  'calcolatrice', 'volume', 'batteria', 'stelle', 'cinema', 'seguimi', 'fermati', 'ciao',
  'curiosità', 'apri', 'cerca', 'ricordami', 'messaggio', 'sasso', 'carta', 'forbice', 'look',
  'torcia', 'sveglia', 'svegliami', 'timer', 'chiama', 'tempo', 'meteo', 'dado', 'moneta', 'pausa',
  'canzone', 'prossima', 'precedente', 'complimento', 'compleanno', 'natale', 'capodanno', 'pasqua',
  'converti', 'accendi', 'spegni', 'dormi', 'svegliati'];

function levenshtein(a, b) {
  if (Math.abs(a.length - b.length) > 2) return 99;
  const dp = [];
  for (let i = 0; i <= a.length; i++) dp[i] = [i];
  for (let j = 0; j <= b.length; j++) dp[0][j] = j;
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      dp[i][j] = Math.min(
        dp[i - 1][j] + 1, dp[i][j - 1] + 1,
        dp[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
  }
  return dp[a.length][b.length];
}

// storpiature comuni che la distanza di battitura non aggancia
const ALIASES = {
  watshap: 'whatsapp', whatsap: 'whatsapp', watsapp: 'whatsapp', wazzap: 'whatsapp',
  yutube: 'youtube', iutub: 'youtube', youtub: 'youtube', yutub: 'youtube',
  gugol: 'google', instagram: 'instagram', istagram: 'instagram',
  bater: 'batteria', bateria: 'batteria',
};

// parole italiane comuni che somigliano ai comandi ma non vanno mai «corrette»
const NON_CORREGGERE = new Set(('alla alle allo agli dalla dalle della delle dello nella nelle sulla sulle sono come cosa cose ' +
  'quando dove anche ancora tutto tutti molto poco bella bello belle sala sale casa mare sera sole luce fame torta salto ' +
  'calla calma carte carta parla parlo palla pala balle tempo meteo dado mondo nome note notte giorno fare fatto detto ' +
  'tanto tanta piace ciao oggi ieri stato stata poi dopo prima sempre mai volta voglio vuoi devo posso fatta brava bravo').split(' '));
function fixTypos(t) {
  const words = t.split(/\s+/);
  if (words.length > 4) return null; // nelle frasi lunghe il rischio di «correggere» male è troppo alto
  let changed = false;
  const out = words.map(w => {
    if (w.length < 4 || NON_CORREGGERE.has(w)) return w;
    if (ALIASES[w]) { changed = true; return ALIASES[w]; }
    let best = null, bestD = 99;
    for (const cand of LEXICON) {
      const d = levenshtein(w, cand);
      if (d < bestD) { bestD = d; best = cand; }
    }
    const maxD = w.length > 6 ? 2 : 1;
    if (best && bestD > 0 && bestD <= maxD) { changed = true; return best; }
    return w;
  });
  return changed ? out.join(' ') : null;
}

// ---------- Il tuo look da una foto: colori veri e la tua faccia sulla testa di Zeph ----------
function toHex(c) { return '#' + c.map(v => ('0' + Math.max(0, Math.min(255, Math.round(v))).toString(16)).slice(-2)).join(''); }
// analizza una foto (canvas) con la faccia dentro l'ovale {cx, cy, rx, ry} (pixel):
// l'ovale va dalla cima dei capelli al mento
function lookFromPhoto(canvas, oval) {
  const W = canvas.width, H = canvas.height;
  const data = canvas.getContext('2d').getImageData(0, 0, W, H).data;
  function px(u, v) {
    const x = Math.round(oval.cx + u * oval.rx), y = Math.round(oval.cy + v * oval.ry);
    if (x < 0 || y < 0 || x >= W || y >= H) return null;
    const i = (y * W + x) * 4;
    return [data[i], data[i + 1], data[i + 2]];
  }
  function region(u0, u1, v0, v1, n) {
    const out = [];
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const p = px(u0 + (u1 - u0) * (i + 0.5) / n, v0 + (v1 - v0) * (j + 0.5) / n);
        if (p) out.push(p);
      }
    }
    return out;
  }
  const luma = p => 0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2];
  const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
  function median(list) {
    if (!list.length) return null;
    const ch = k => list.map(p => p[k]).sort((a, b) => a - b)[list.length >> 1];
    return [ch(0), ch(1), ch(2)];
  }
  // pelle: le guance, sotto gli occhi
  const cheeks = region(-0.52, -0.28, 0.08, 0.36, 8).concat(region(0.28, 0.52, 0.08, 0.36, 8))
    .filter(p => luma(p) > 35 && luma(p) < 245);
  const skin = median(cheeks) || [224, 168, 135];
  // capelli: la parte alta dell'ovale e i lati della testa, solo dove non è pelle
  const hairArea = region(-0.5, 0.5, -0.97, -0.72, 12).concat(region(-0.98, -0.84, -0.6, -0.1, 6), region(0.84, 0.98, -0.6, -0.1, 6));
  const hairPix = hairArea.filter(p => dist(p, skin) > 55);
  const hair = hairPix.length > hairArea.length * 0.3 ? median(hairPix) : null;
  // vestiti: sotto il mento, escluso il collo
  const topArea = region(-0.6, 0.6, 1.25, 1.6, 10);
  const topPix = topArea.filter(p => dist(p, skin) > 50);
  const top = topPix.length > topArea.length * 0.35 ? median(topPix) : null;
  // la faccia ritagliata per la testa 3D
  const fc = document.createElement('canvas');
  fc.width = 256; fc.height = 320;
  const g = fc.getContext('2d');
  g.fillStyle = toHex(skin);
  g.fillRect(0, 0, 256, 320);
  g.drawImage(canvas, oval.cx - oval.rx, oval.cy - oval.ry, oval.rx * 2, oval.ry * 2, 0, 0, 256, 320);
  return {
    v: 1, skin: toHex(skin), hair: hair ? toHex(hair) : null, top: top ? toHex(top) : null,
    face: fc.toDataURL('image/jpeg', 0.88), useFace: true,
  };
}

// la foto si proietta di fronte, come una maschera che segue la forma vera della
// testa (cranio, mento e capelli di Zeph); è divisa all'altezza della bocca così
// la mascella si apre quando parla. Riquadro della foto in coordinate della testa:
const FACE = { x0: -0.098, x1: 0.098, yBot: -0.04, yTop: 0.226, yMouth: 0.024, lift: 0.0035 };
function faceShell(THREE, B) {
  B.root.updateMatrixWorld(true);
  const targets = [B.skull, B.jawMesh].concat(B.hairMeshes.filter(h => h.visible));
  const ray = new THREE.Raycaster();
  const ROWS = 34, COLS = 40, A = 1.45;
  const o = new THREE.Vector3(), d = new THREE.Vector3(), od = new THREE.Vector3();
  const grid = [];
  for (let i = 0; i <= ROWS; i++) {
    const y = -0.036 + (0.222 + 0.036) * i / ROWS;
    const row = [];
    for (let j = 0; j <= COLS; j++) {
      const a = -A + 2 * A * j / COLS;
      // raggio dall'esterno verso l'asse della testa: il primo punto colpito è la superficie
      d.set(Math.sin(a), 0, Math.cos(a));
      o.set(0, y, 0).addScaledVector(d, 0.3);
      od.copy(o); B.head.localToWorld(od);
      const dirW = d.clone().negate().transformDirection(B.head.matrixWorld);
      ray.set(od, dirW);
      const hit = ray.intersectObjects(targets, false)[0];
      if (!hit) { row.push(null); continue; }
      const p = B.head.worldToLocal(hit.point.clone());
      row.push(Math.hypot(p.x, p.z)); // distanza dall'asse della testa
    }
    grid.push(row);
  }
  // niente gradini dove finiscono i capelli: si prende il massimo dei vicini e si ammorbidisce
  const R = (i, j) => (grid[i] && grid[i][j] != null ? grid[i][j] : null);
  const soft = grid.map((row, i) => row.map((v, j) => {
    if (v == null) return null;
    let m = v;
    for (let k = -2; k <= 2; k++) { const w = R(i + k, j); if (w != null) m = Math.max(m, w - Math.abs(k) * 0.0015); }
    return m;
  }));
  for (let pass = 0; pass < 2; pass++) {
    const src = soft.map(r => r.slice());
    for (let i = 0; i <= ROWS; i++) {
      for (let j = 0; j <= COLS; j++) {
        if (src[i][j] == null) continue;
        let sum = 0, n = 0;
        for (const [di, dj, w] of [[0, 0, 4], [-1, 0, 2], [1, 0, 2], [0, -1, 1], [0, 1, 1]]) {
          const v = src[i + di] && src[i + di][j + dj];
          if (v != null) { sum += v * w; n += w; }
        }
        soft[i][j] = Math.max(grid[i][j], sum / n); // mai sotto la superficie vera
      }
    }
  }
  for (let i = 0; i <= ROWS; i++) {
    const y = -0.036 + (0.222 + 0.036) * i / ROWS;
    for (let j = 0; j <= COLS; j++) {
      if (soft[i][j] == null) { grid[i][j] = null; continue; }
      const a = -A + 2 * A * j / COLS, r = soft[i][j] + FACE.lift;
      grid[i][j] = new THREE.Vector3(Math.sin(a) * r, y, Math.cos(a) * r);
    }
  }
  function geo(r0, r1) {
    const pos = [], uv = [], idx = [], map = {};
    for (let i = r0; i <= r1; i++) {
      for (let j = 0; j <= COLS; j++) {
        const p = grid[i][j];
        if (!p) continue;
        map[i + ':' + j] = pos.length / 3;
        pos.push(p.x, p.y, p.z);
        uv.push((p.x - FACE.x0) / (FACE.x1 - FACE.x0), (p.y - FACE.yBot) / (FACE.yTop - FACE.yBot));
      }
    }
    for (let i = r0; i < r1; i++) {
      for (let j = 0; j < COLS; j++) {
        const a = map[i + ':' + j], b = map[i + ':' + (j + 1)], c = map[(i + 1) + ':' + j], e = map[(i + 1) + ':' + (j + 1)];
        if (a === undefined || b === undefined || c === undefined || e === undefined) continue;
        idx.push(a, b, c, b, e, c);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    g.setIndex(idx);
    g.computeVertexNormals();
    return g;
  }
  const split = Math.round((FACE.yMouth + 0.036) / (0.222 + 0.036) * ROWS);
  const mid = grid[split][COLS / 2];
  return { upper: geo(split, ROWS), lower: geo(0, split), mouthY: -0.036 + (0.222 + 0.036) * split / ROWS, mouthZ: mid ? mid.z : 0.09 };
}
function photoFaceTexture(THREE, img) {
  const W = 256, H = 320;
  const c = document.createElement('canvas');
  c.width = W; c.height = H;
  const g = c.getContext('2d');
  g.drawImage(img, 0, 0, W, H);
  // bordi sfumati: la foto si fonde con la pelle e i capelli di Zeph
  g.globalCompositeOperation = 'destination-in';
  g.save();
  g.translate(W / 2, H / 2);
  g.scale(1, H / W);
  const grad = g.createRadialGradient(0, 0, 0, 0, 0, W / 2);
  grad.addColorStop(0, 'rgba(0,0,0,1)');
  grad.addColorStop(0.72, 'rgba(0,0,0,1)');
  grad.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = grad;
  g.fillRect(-W / 2, -W / 2, W, W);
  g.restore();
  const tex = new THREE.CanvasTexture(c);
  if (THREE.sRGBEncoding !== undefined) tex.encoding = THREE.sRGBEncoding;
  return tex;
}
function removePhotoFace(B) {
  if (!B.photoFace) return;
  B.head.remove(B.photoFace.group);
  B.photoFace.group.traverse(o => {
    if (o.geometry) o.geometry.dispose();
    if (o.material && o.material !== B.photoFace.mat) o.material.dispose();
  });
  B.photoFace.mat.map.dispose();
  B.photoFace.mat.dispose();
  B.photoFace = null;
}
function buildPhotoFace(THREE, B, img) {
  removePhotoFace(B);
  const mat = new THREE.MeshStandardMaterial({ map: photoFaceTexture(THREE, img), transparent: true, roughness: 0.62, metalness: 0 });
  const shell = faceShell(THREE, B);
  const group = new THREE.Group();
  const upper = new THREE.Mesh(shell.upper, mat);
  // la mascella ruota attorno a una cerniera dietro la bocca
  const jaw = new THREE.Group();
  jaw.position.set(0, shell.mouthY, -0.01);
  const lower = new THREE.Mesh(shell.lower, mat);
  lower.position.set(0, -shell.mouthY, 0.01);
  jaw.add(lower);
  // l'interno della bocca, che si vede solo quando la mascella si apre
  const inside = new THREE.Mesh(new THREE.SphereGeometry(1, 14, 10), new THREE.MeshStandardMaterial({ color: 0x0d0303, roughness: 0.9 }));
  inside.position.set(0, shell.mouthY - 0.003, shell.mouthZ - 0.0055);
  inside.scale.set(0.028, 0.011, 0.004);
  group.add(upper, jaw, inside);
  group.traverse(o => { o.userData.zeph = true; });
  B.head.add(group);
  B.photoFace = { group, jaw, mat };
}
// mette su Zeph un look ({skin, hair, top, eyes, face, useFace}); null = Zeph normale
function applyLook(THREE, B, look) {
  const M = B.mats;
  if (!B.defaultLook) {
    B.defaultLook = {};
    ['skin', 'hair', 'jacket', 'jacketDark', 'iris', 'lips'].forEach(k => { B.defaultLook[k] = M[k].color.getHex(); });
  }
  const d = B.defaultLook;
  look = look || {};
  // i colori presi dalla foto sono sRGB: convertiti, la pelle combacia con la faccia
  const photoColor = (mat, hex, fallback) => {
    if (hex) mat.color.set(hex).convertSRGBToLinear();
    else mat.color.setHex(fallback);
  };
  photoColor(M.skin, look.skin, d.skin);
  const bald = look.hair === 'none';
  photoColor(M.hair, !bald && look.hair, d.hair);
  B.hairMeshes.forEach(h => { h.visible = !bald; });
  photoColor(M.jacket, look.top, d.jacket);
  if (look.top) M.jacketDark.color.copy(M.jacket.color).multiplyScalar(0.62);
  else M.jacketDark.color.setHex(d.jacketDark);
  photoColor(M.iris, look.eyes, d.iris);
  if (look.skin) M.lips.color.copy(M.skin.color).multiply(new THREE.Color(0.8, 0.56, 0.55));
  else M.lips.color.setHex(d.lips);
  const useFace = !!(look.face && look.useFace !== false);
  [B.eyeL, B.eyeR, B.browL, B.browR, B.mouth, B.nose].forEach(o => { o.visible = !useFace; });
  removePhotoFace(B);
  const token = B.lookToken = (B.lookToken || 0) + 1;
  if (!useFace || typeof Image === 'undefined') return Promise.resolve(false);
  return new Promise(resolve => {
    const img = new Image();
    img.onload = () => {
      // se nel frattempo è arrivato un altro look, questo non serve più
      if (B.lookToken !== token) return resolve(false);
      buildPhotoFace(THREE, B, img);
      resolve(true);
    };
    img.onerror = () => {
      [B.eyeL, B.eyeR, B.browL, B.browR, B.mouth, B.nose].forEach(o => { o.visible = true; });
      resolve(false);
    };
    img.src = look.face;
  });
}

// ---------- Scintille (particelle per salti e balli) ----------
function createSparkles(THREE, scene, count) {
  count = count || 32;
  const colors = [0xffd23e, 0x5eead4, 0xff8ab5, 0x9dd0ff];
  const pool = [];
  for (let i = 0; i < count; i++) {
    const m = new THREE.Mesh(
      new THREE.PlaneGeometry(0.075, 0.075),
      new THREE.MeshBasicMaterial({ color: colors[i % colors.length], transparent: true, side: THREE.DoubleSide, depthWrite: false })
    );
    m.visible = false;
    m.userData = { life: 0, vel: new THREE.Vector3() };
    scene.add(m);
    pool.push(m);
  }
  return {
    burst(x, y, z, n) {
      let c = 0;
      for (const m of pool) {
        if (m.userData.life <= 0) {
          m.position.set(x + (Math.random() - 0.5) * 0.3, y, z + (Math.random() - 0.5) * 0.3);
          m.userData.vel.set((Math.random() - 0.5) * 2.6, 1.4 + Math.random() * 2.2, (Math.random() - 0.5) * 2.6);
          m.userData.life = 1;
          m.visible = true;
          if (++c >= n) break;
        }
      }
    },
    update(dt, camera) {
      for (const m of pool) {
        const u = m.userData;
        if (u.life <= 0) continue;
        u.life -= dt * 1.15;
        if (u.life <= 0) { m.visible = false; continue; }
        m.position.addScaledVector(u.vel, dt);
        u.vel.y -= 4.5 * dt;
        const sc = Math.max(0.05, u.life);
        m.scale.set(sc, sc, sc);
        m.quaternion.copy(camera.quaternion);
        m.material.opacity = u.life;
      }
    },
  };
}

global.ZephCore = {
  build, Animator, botReply, pick, createAvatarDriver, createSparkles,
  buildDog, updateDog, bark, chime, boom, ambience, music, weatherReport,
  memory, ai, toTu, dayOf, lookFromPhoto, applyLook,
  parseWhen, whenLabel, wikiAnswer, createHologram, daysUntil,
  FRASI_PASSEGGIO, FRASI_DESKTOP, BARZELLETTE,
  HIP_Y, HEIGHT: 1.75,
};
})(typeof window !== 'undefined' ? window : this);
