window.GL = window.GL || {};

(() => {
  'use strict';

  const { $, toast, log, haptic, copyText } = GL.ui;
  const enc = new TextEncoder();
  const dec = new TextDecoder();
  const MAGIC = [0x47, 0x4c]; // "GL" marker so extraction knows a message is present

  let srcImage = null;    // HTMLImageElement of the carrier
  let resultURL = null;

  // Optional AES layer before hiding, so even a found message stays unreadable without the key.
  async function maybeEncrypt(text, pass) {
    if (!pass) return enc.encode(text);
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const base = await crypto.subtle.importKey('raw', enc.encode(pass), 'PBKDF2', false, ['deriveKey']);
    const key = await crypto.subtle.deriveKey({ name: 'PBKDF2', salt, iterations: 150000, hash: 'SHA-256' }, base, { name: 'AES-GCM', length: 256 }, false, ['encrypt']);
    const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, enc.encode(text)));
    const out = new Uint8Array(1 + salt.length + iv.length + ct.length);
    out[0] = 1; out.set(salt, 1); out.set(iv, 17); out.set(ct, 29);
    return out;
  }
  async function maybeDecrypt(bytes, pass) {
    if (bytes[0] !== 1) return dec.decode(bytes);          // not encrypted
    if (!pass) throw new Error('need-key');
    const salt = bytes.slice(1, 17), iv = bytes.slice(17, 29), ct = bytes.slice(29);
    const base = await crypto.subtle.importKey('raw', enc.encode(pass), 'PBKDF2', false, ['deriveKey']);
    const key = await crypto.subtle.deriveKey({ name: 'PBKDF2', salt, iterations: 150000, hash: 'SHA-256' }, base, { name: 'AES-GCM', length: 256 }, false, ['decrypt']);
    return dec.decode(await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, ct));
  }

  function loadImage(file) {
    return new Promise((res, rej) => {
      const img = new Image();
      img.onload = () => res(img);
      img.onerror = rej;
      img.src = URL.createObjectURL(file);
    });
  }

  // Write bits into the least-significant bit of each RGB channel (alpha left intact).
  function embed(imageData, payload) {
    const header = new Uint8Array(6);
    header[0] = MAGIC[0]; header[1] = MAGIC[1];
    new DataView(header.buffer).setUint32(2, payload.length);
    const all = new Uint8Array(header.length + payload.length);
    all.set(header); all.set(payload, header.length);
    const d = imageData.data;
    const capacity = Math.floor((d.length / 4) * 3 / 8);
    if (all.length > capacity) throw new Error('too-big');
    let bit = 0;
    for (let i = 0; i < d.length && bit < all.length * 8; i += 4) {
      for (let c = 0; c < 3 && bit < all.length * 8; c++) {
        const byte = all[bit >> 3];
        const b = (byte >> (7 - (bit & 7))) & 1;
        d[i + c] = (d[i + c] & 0xfe) | b;
        bit++;
      }
    }
    return imageData;
  }

  function extract(imageData) {
    const d = imageData.data;
    const read = n => {
      const out = new Uint8Array(n);
      let bit = 0;
      const startPixel = 0;
      for (let i = startPixel, done = 0; i < d.length && done < n * 8; i += 4) {
        for (let c = 0; c < 3 && done < n * 8; c++) {
          out[done >> 3] |= (d[i + c] & 1) << (7 - (done & 7));
          done++;
        }
      }
      return out;
    };
    // read 6-byte header first
    const header = read(6);
    if (header[0] !== MAGIC[0] || header[1] !== MAGIC[1]) throw new Error('none');
    const len = new DataView(header.buffer).getUint32(2);
    if (len <= 0 || len > (d.length / 4) * 3 / 8) throw new Error('none');
    const total = read(6 + len);
    return total.slice(6);
  }

  async function hide() {
    if (!srcImage) { toast('Scegli prima una foto'); return; }
    const text = $('#stego-msg').value;
    if (!text) { toast('Scrivi il messaggio da nascondere'); return; }
    const btn = $('#stego-hide');
    btn.disabled = true;
    GL.sfx.play('hack');
    try {
      const canvas = document.createElement('canvas');
      const max = 1600;
      const scale = Math.min(1, max / Math.max(srcImage.width, srcImage.height));
      canvas.width = Math.round(srcImage.width * scale);
      canvas.height = Math.round(srcImage.height * scale);
      const ctx = canvas.getContext('2d');
      ctx.drawImage(srcImage, 0, 0, canvas.width, canvas.height);
      const payload = await maybeEncrypt(text, $('#stego-key').value);
      const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      ctx.putImageData(embed(imgData, payload), 0, 0);
      // toDataURL is synchronous and reliable across engines (unlike toBlob, which can
      // stall under software rendering); PNG keeps every pixel exact so the LSBs survive.
      const dataURL = canvas.toDataURL('image/png');
      resultURL = dataURL;
      const out = $('#stego-result');
      out.src = dataURL;
      out.hidden = false;
      $('#stego-save').hidden = false;
      $('#stego-save').href = dataURL;
      GL.sfx.play('ok');
      haptic([15, 30, 15]);
      log('Messaggio nascosto in un\'immagine', 'ok');
      GL.app?.xp(10, 'steganografia');
      toast('Fatto! Tieni premuto sull\'immagine per salvarla.');
    } catch (e) {
      toast(e.message === 'too-big' ? 'Messaggio troppo lungo per questa foto: usane una più grande' : 'Non è stato possibile nascondere il messaggio');
      GL.sfx.play('err');
    } finally { btn.disabled = false; }
  }

  async function reveal() {
    if (!srcImage) { toast('Scegli prima la foto che contiene il messaggio'); return; }
    GL.sfx.play('hack');
    try {
      const canvas = document.createElement('canvas');
      canvas.width = srcImage.width; canvas.height = srcImage.height;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(srcImage, 0, 0);
      const bytes = extract(ctx.getImageData(0, 0, canvas.width, canvas.height));
      const text = await maybeDecrypt(bytes, $('#stego-key').value);
      $('#stego-msg').value = text;
      GL.sfx.play('ok');
      haptic([10, 30, 10]);
      log('Messaggio nascosto estratto', 'ok');
      GL.app?.xp(10, 'steganografia');
      toast('Messaggio trovato!');
    } catch (e) {
      const msg = e.message === 'none' ? 'Nessun messaggio Ghostlink in questa foto'
        : e.message === 'need-key' ? 'Questo messaggio è protetto: inserisci la chiave'
        : 'Chiave sbagliata o foto modificata dopo l\'invio';
      toast(msg, 3000);
      GL.sfx.play('err');
    }
  }

  function init() {
    $('#stego-file').addEventListener('change', async e => {
      const f = e.target.files[0];
      if (!f) return;
      try {
        srcImage = await loadImage(f);
        const prev = $('#stego-preview');
        prev.src = srcImage.src; prev.hidden = false;
        $('#stego-result').hidden = true; $('#stego-save').hidden = true;
        toast('Foto caricata');
        GL.sfx.play('blip');
      } catch { toast('Immagine non valida'); }
    });
    $('#stego-hide').addEventListener('click', hide);
    $('#stego-reveal').addEventListener('click', reveal);
  }

  GL.stego = { init };
})();
