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

  const B = { root: new THREE.Group(), HIP_Y };

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

  const hairGeo = new THREE.SphereGeometry(0.108, 20, 14, 0, Math.PI * 2, 0, Math.PI * 0.52);
  const hair = new THREE.Mesh(hairGeo, M.hair);
  hair.position.y = 0.108; hair.scale.set(0.96, 1.14, 1.03);
  hair.rotation.x = -0.26; hair.castShadow = true;
  B.head.add(hair);
  const nape = sphere(0.09, M.hair, 0.9, 0.9, 0.7); nape.position.set(0, 0.1, -0.055); B.head.add(nape);

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

  // per il raycasting dei clic
  B.root.traverse(o => { o.userData.zeph = true; });

  return B;
}

// ---------- Animatore procedurale ----------
const ACTIONS = { wave: 2.2, dance: 6.0, jump: 0.95 };

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

function Animator(B) {
  this.B = B;
  this.state = {
    speedRatio: 0, phase: 0,
    talking: false, talkW: 0, mouthPulse: 0, mouthSmooth: 0, gestureLead: 1,
    action: null,
    blinkAt: 2.5, blinkT: -1,
    lookYaw: 0, lookPitch: 0, lookTYaw: 0, lookTPitch: 0, nextLookAt: 2,
  };
}

Animator.prototype.startAction = function (name) {
  if (ACTIONS[name]) this.state.action = { name, t: 0, dur: ACTIONS[name] };
};

Animator.prototype.update = function (t, dt) {
  const s = this.state, B = this.B;
  const P = newPose();
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
  const lookW = (1 - s.talkW) * (1 - walkW * 0.7);
  P.head.y += s.lookYaw * lookW;
  P.head.x += s.lookPitch * lookW;
  B.pupilL.position.x = s.lookYaw * 0.012 * lookW;
  B.pupilR.position.x = s.lookYaw * 0.012 * lookW;

  // camminata
  if (walkW > 0.001) {
    const w = walkW, ph = s.phase;
    const swing = Math.sin(ph);
    P.legL.x += -swing * 0.5 * w;
    P.legR.x += swing * 0.5 * w;
    P.kneeL += Math.max(0, Math.cos(ph + 0.7)) * 0.8 * w;
    P.kneeR += Math.max(0, -Math.cos(ph + 0.7)) * 0.8 * w;
    P.footL += (swing * 0.22 + 0.08) * w;
    P.footR += (-swing * 0.22 + 0.08) * w;
    P.shL.x += swing * 0.34 * w;
    P.shR.x += -swing * 0.34 * w;
    P.elL.x += (-0.2 + Math.max(0, swing) * -0.25) * w;
    P.elR.x += (-0.2 + Math.max(0, -swing) * -0.25) * w;
    P.rootY += (Math.abs(Math.cos(ph)) * 0.035 - 0.018) * w;
    P.spine.x += 0.08 * w;
    P.body.y += swing * 0.07 * w;
    P.spine.y += -swing * 0.09 * w;
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
        const b = t * 6.0;
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
  B.eyeL.scale.y = eyeScale; B.eyeR.scale.y = eyeScale;

  applyPose(B, P);
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
const DEFAULT_REPLIES = [
  'Interessante! Dimmi di più…',
  'Ah sì? Non ci avevo mai pensato!',
  'Capito, capito… più o meno!',
  'Mi piace tantissimo parlare con te!',
  'Uhm… fammi pensare… sì, sono d’accordo!',
  'Bella questa! Raccontamene un’altra.',
];

const RULES = [
  { re: /(barzellett|scherz|fammi ridere|divertent|joke)/, fn: () => ({ say: pick(BARZELLETTE) }) },
  { re: /(balla|danza|ballare|dance)/, fn: () => ({ say: pick(['E vaiii! Guarda che mosse!', 'Musica, maestro! Si balla!', 'Questa è la mia specialità!']), action: 'dance' }) },
  { re: /(salta|salto|jump)/, fn: () => ({ say: pick(['Uuup! Hai visto che salto?', 'Guarda quanto vado in alto!']), action: 'jump' }) },
  { re: /(canta|canzone|canzoncina)/, fn: () => ({ say: 'Laaa la la làààà… Zeph è il mio nome, camminare è la mia passioneee!', action: 'dance' }) },
  { re: /(vieni|avvicinati|qui da me)/, fn: () => ({ say: 'Arrivo subitooo!', come: true }) },
  { re: /(fermo|fermati|stop|basta)/, fn: () => ({ say: 'Ok ok, mi fermo qui!', stop: true }) },
  { re: /(cammina|passeggia|vai in giro|muoviti|esplora)/, fn: () => ({ say: 'Ottima idea, mi faccio un giretto!', wander: true }) },
  { re: /(seguimi|segui il mouse|inseguimi)/, fn: () => ({ say: 'Ti seguo! Non scappare troppo veloce però!', follow: true }) },
  { re: /(come stai|come va|tutto bene)/, fn: () => ({ say: pick(['Benissimo! Le mie gambe 3D oggi sono al top! E tu?', 'Alla grande! Un po’ di poligoni scricchiolano ma va bene così.', 'Molto bene, grazie! E tu come stai?']) }) },
  { re: /(chi sei|come ti chiami|il tuo nome|cosa sei)/, fn: () => ({ say: 'Sono Zeph! Un personaggio 3D fatto di poligoni e simpatia. Vivo qui sul tuo schermo!', action: 'wave' }) },
  { re: /(quanti anni)/, fn: () => ({ say: 'Sono nato pochi secondi fa, quando mi hai acceso! Quindi… sono giovanissimo.' }) },
  { re: /(cosa sai fare|aiuto|help|comandi|istruzioni)/, fn: () => ({ say: 'So camminare, ballare, saltare, salutare, seguire il mouse e raccontare barzellette! Prova a scrivermi «balla» o «seguimi»!' }) },
  { re: /(grazie|gentile)/, fn: () => ({ say: pick(['Prego! È un piacere!', 'Figurati! Per te, sempre!']) }) },
  { re: /(ti voglio bene|ti amo|sei bello|sei forte|bravo)/, fn: () => ({ say: 'Ooh, grazie! Anche tu sei il mio umano preferito!', action: 'wave' }) },
  { re: /(buonanotte|vado a dormire|a domani)/, fn: () => ({ say: 'Buonanotte! Io resto di guardia allo schermo. A presto!', action: 'wave' }) },
  { re: /(ciao|salve|ehi|hey|hola|buongiorno|buonasera)\b/, fn: () => ({ say: pick(['Ciao! Che bello vederti!', 'Ehilà! Come va?', 'Ciao ciao! Sono contento che tu sia qui!']), action: 'wave' }) },
];

function botReply(text) {
  const t = (text || '').toLowerCase().trim();
  if (!t) return null;
  for (const r of RULES) { if (r.re.test(t)) return r.fn(); }
  return { say: pick(DEFAULT_REPLIES) };
}

global.ZephCore = {
  build, Animator, botReply, pick,
  FRASI_PASSEGGIO, FRASI_DESKTOP, BARZELLETTE,
  HIP_Y, HEIGHT: 1.75,
};
})(typeof window !== 'undefined' ? window : this);
