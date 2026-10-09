/* Gli occhi del tuo amico: una foto e una domanda al cervello AI (Claude,
   con la tua chiave). Nel telefono la risposta la dice anche il compagno
   sullo schermo; nel browser la legge la voce del computer. */
(function () {
'use strict';

const P = window.ZephPhoto || null; // ponte dell'app Android (assente nel browser)
const $ = id => document.getElementById(id);
const video = $('video'), shot = $('shot');
if (P && P.aiKey) ZephCore.ai.useStore({ get: () => P.aiKey(), set() {} });

let stream = null;
function startCamera() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { $('err').textContent = 'Qui la fotocamera non c’è: scegli una foto.'; return; }
  navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1600 }, height: { ideal: 1200 } }, audio: false })
    .then(s => { stream = s; video.srcObject = s; return video.play(); })
    .catch(() => { $('err').textContent = 'Non riesco ad aprire la fotocamera (permesso negato?). Puoi scegliere una foto.'; });
}
function stopCamera() { if (stream) stream.getTracks().forEach(t => t.stop()); stream = null; }

// foto ridimensionata (lato lungo 1024 px) in JPEG: basta e avanza, e costa meno
function toJpeg(src, w, h) {
  const k = Math.min(1, 1024 / Math.max(w, h));
  const c = document.createElement('canvas');
  c.width = Math.round(w * k); c.height = Math.round(h * k);
  c.getContext('2d').drawImage(src, 0, 0, c.width, c.height);
  return c.toDataURL('image/jpeg', 0.85);
}
function say(text) {
  if (P && P.say) { P.say(text); return; }
  try {
    const u = new SpeechSynthesisUtterance(text);
    u.lang = 'it-IT';
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
  } catch (e) { /* niente voce */ }
}
let busy = false;
function ask(dataUrl) {
  if (busy) return;
  busy = true;
  shot.src = dataUrl;
  shot.style.display = 'block';
  stopCamera();
  $('scan').style.display = 'block';
  $('look').disabled = true;
  $('answer').textContent = '';
  $('err').textContent = ZephCore.ai.enabled() ? 'Sto guardando…' : '';
  const ctx = { name: (() => { try { return localStorage.getItem('zephName'); } catch (e) { return null; } })() };
  ZephCore.ai.see(dataUrl.split(',')[1], $('q').value, ctx).then(r => {
    $('scan').style.display = 'none';
    $('err').textContent = '';
    $('answer').textContent = r.say;
    $('again').hidden = false;
    say(r.say);
    busy = false;
  });
}
$('look').addEventListener('click', () => {
  if (!video.videoWidth) { $('err').textContent = 'La fotocamera non è pronta: aspetta un attimo, oppure scegli una foto.'; return; }
  ask(toJpeg(video, video.videoWidth, video.videoHeight));
});
$('file').addEventListener('change', e => {
  const f = e.target.files && e.target.files[0];
  if (!f) return;
  const img = new Image();
  img.onload = () => ask(toJpeg(img, img.naturalWidth, img.naturalHeight));
  img.onerror = () => { $('err').textContent = 'Questa immagine non riesco ad aprirla.'; };
  img.src = URL.createObjectURL(f);
});
$('again').addEventListener('click', () => {
  shot.style.display = 'none';
  $('answer').textContent = '';
  $('again').hidden = true;
  $('look').disabled = false;
  startCamera();
});
$('close').addEventListener('click', () => {
  stopCamera();
  if (P && P.close) P.close(); else location.href = 'index.html';
});

const q0 = (P && P.question ? P.question() : new URLSearchParams(location.search).get('q')) || '';
// «guarda», «cosa vedi?» non servono come domanda: meglio lasciarla libera
$('q').value = /^(?:guarda|cosa vedi|dimmi cosa vedi|apri gli occhi|usa la fotocamera)\b/i.test(q0.trim()) ? '' : q0;
if (!ZephCore.ai.enabled()) {
  $('err').textContent = 'Per vedere serve il cervello AI: metti la tua chiave di Claude (nell’app, sezione 🧠; nel browser incollala nella chat).';
}
window.zephOcchi = { ask };
startCamera();
})();
