window.GL = window.GL || {};

(() => {
  'use strict';

  const { $, toast, log, haptic, fmt } = GL.ui;

  // Minimal EXIF reader: parses the JPEG APP1 TIFF block for the tags that matter to privacy.
  const TAGS = {
    0x010f: 'Make', 0x0110: 'Model', 0x0112: 'Orientation', 0x0132: 'DateTime',
    0x8827: 'ISO', 0x829a: 'ExposureTime', 0x829d: 'FNumber', 0x920a: 'FocalLength',
    0x9003: 'DateTimeOriginal', 0xa002: 'PixelXDimension', 0xa003: 'PixelYDimension',
    0x0131: 'Software', 0x8825: 'GPSIFD',
  };
  const GPS = { 1: 'GPSLatitudeRef', 2: 'GPSLatitude', 3: 'GPSLongitudeRef', 4: 'GPSLongitude', 5: 'GPSAltitudeRef', 6: 'GPSAltitude', 7: 'GPSTimeStamp', 29: 'GPSDateStamp' };
  const TYPE_SIZE = { 1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8 };

  function findExif(view) {
    if (view.getUint16(0) !== 0xffd8) return -1; // not a JPEG
    let off = 2;
    while (off < view.byteLength - 1) {
      if (view.getUint8(off) !== 0xff) break;
      const marker = view.getUint8(off + 1);
      const size = view.getUint16(off + 2);
      if (marker === 0xe1) {
        // APP1; check "Exif\0\0"
        if (view.getUint32(off + 4) === 0x45786966) return off + 10; // start of TIFF header
      }
      off += 2 + size;
    }
    return -1;
  }

  function readIFD(view, tiffStart, ifdOffset, little, into, map) {
    const count = view.getUint16(tiffStart + ifdOffset, little);
    for (let i = 0; i < count; i++) {
      const entry = tiffStart + ifdOffset + 2 + i * 12;
      const tag = view.getUint16(entry, little);
      const type = view.getUint16(entry + 2, little);
      const num = view.getUint32(entry + 4, little);
      const size = (TYPE_SIZE[type] || 1) * num;
      let valueOffset = entry + 8;
      if (size > 4) valueOffset = tiffStart + view.getUint32(entry + 8, little);
      const name = map[tag];
      if (tag === 0x8825) { // GPS IFD pointer
        const gpsOff = view.getUint32(entry + 8, little);
        readIFD(view, tiffStart, gpsOff, little, into, GPS);
        continue;
      }
      if (!name) continue;
      into[name] = readValue(view, valueOffset, type, num, little);
    }
    return count;
  }

  function readValue(view, off, type, num, little) {
    if (type === 2) { // ASCII
      let s = '';
      for (let i = 0; i < num - 1; i++) s += String.fromCharCode(view.getUint8(off + i));
      return s.trim();
    }
    const read1 = o => {
      if (type === 3) return view.getUint16(o, little);
      if (type === 4) return view.getUint32(o, little);
      if (type === 5) return view.getUint32(o, little) / view.getUint32(o + 4, little);
      if (type === 10) return view.getInt32(o, little) / view.getInt32(o + 4, little);
      return view.getUint8(o);
    };
    const step = TYPE_SIZE[type] || 1;
    if (num === 1) return read1(off);
    const arr = [];
    for (let i = 0; i < num; i++) arr.push(read1(off + i * step));
    return arr;
  }

  function dms(arr, ref) {
    if (!Array.isArray(arr)) return null;
    const [d, m, s] = arr;
    let v = d + m / 60 + s / 3600;
    if (ref === 'S' || ref === 'W') v = -v;
    return v;
  }

  function parse(buffer) {
    const view = new DataView(buffer);
    const tiff = findExif(view);
    if (tiff < 0) throw new Error('none');
    const little = view.getUint16(tiff) === 0x4949;
    const ifd0 = view.getUint32(tiff + 4, little);
    const data = {};
    readIFD(view, tiff, ifd0, little, data, TAGS);
    // ExifIFD pointer (0x8769) for camera settings
    const exifPtrEntry = findTag(view, tiff, ifd0, little, 0x8769);
    if (exifPtrEntry != null) readIFD(view, tiff, exifPtrEntry, little, data, TAGS);
    return data;
  }

  function findTag(view, tiffStart, ifdOffset, little, wanted) {
    const count = view.getUint16(tiffStart + ifdOffset, little);
    for (let i = 0; i < count; i++) {
      const entry = tiffStart + ifdOffset + 2 + i * 12;
      if (view.getUint16(entry, little) === wanted) return view.getUint32(entry + 8, little);
    }
    return null;
  }

  function render(data) {
    const box = $('#meta-out');
    box.replaceChildren();
    const lat = dms(data.GPSLatitude, data.GPSLatitudeRef);
    const lon = dms(data.GPSLongitude, data.GPSLongitudeRef);

    if (lat != null && lon != null) {
      const card = document.createElement('div');
      card.className = 'card';
      card.style.borderColor = 'var(--magenta)';
      card.innerHTML = `<div class="eyebrow" style="color:var(--magenta)">⚠ Posizione nascosta nella foto</div>
        <p>Questa foto è stata scattata qui:</p>
        <div class="kv"><span>Coordinate</span><b class="hot">${lat.toFixed(6)}, ${lon.toFixed(6)}</b></div>`;
      const a = document.createElement('a');
      a.className = 'btn ghost wide'; a.target = '_blank'; a.rel = 'noopener';
      a.href = `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=16/${lat}/${lon}`;
      a.textContent = 'Apri sulla mappa';
      card.append(a);
      const note = document.createElement('p'); note.className = 'note';
      note.textContent = 'Ecco perché condividere una foto originale può rivelare dove sei stato. Le app di chat di solito la rimuovono, ma il file originale no.';
      card.append(note);
      box.append(card);
      GL.sfx.play('err');
      haptic([40, 40, 60]);
    }

    const rows = [
      ['Fotocamera', [data.Make, data.Model].filter(Boolean).join(' ')],
      ['Software', data.Software],
      ['Scattata il', data.DateTimeOriginal || data.DateTime],
      ['Dimensioni', data.PixelXDimension && `${data.PixelXDimension} × ${data.PixelYDimension} px`],
      ['Diaframma', data.FNumber && `f/${fmt.num(data.FNumber, 1)}`],
      ['Tempo', data.ExposureTime && (data.ExposureTime < 1 ? `1/${Math.round(1 / data.ExposureTime)} s` : `${data.ExposureTime} s`)],
      ['ISO', data.ISO],
      ['Focale', data.FocalLength && `${Math.round(data.FocalLength)} mm`],
      ['Altitudine', data.GPSAltitude && `${Math.round(data.GPSAltitude)} m`],
    ].filter(r => r[1]);

    const info = document.createElement('div');
    info.className = 'card';
    const h = document.createElement('div'); h.className = 'eyebrow'; h.textContent = 'Dati tecnici (EXIF)';
    info.append(h);
    if (!rows.length && lat == null) {
      info.innerHTML += '<p class="note">Questa foto non contiene dati EXIF: forse è già stata ripulita (per esempio scaricata da una chat) o è uno screenshot.</p>';
    } else {
      rows.forEach(([k, v]) => {
        const d = document.createElement('div'); d.className = 'kv';
        const s = document.createElement('span'); s.textContent = k;
        const b = document.createElement('b'); b.textContent = v;
        d.append(s, b); info.append(d);
      });
    }
    box.append(info);
  }

  function init() {
    $('#meta-file').addEventListener('change', e => {
      const f = e.target.files[0];
      if (!f) return;
      const prev = $('#meta-preview');
      prev.src = URL.createObjectURL(f); prev.hidden = false;
      const reader = new FileReader();
      reader.onload = () => {
        GL.sfx.play('hack');
        try { render(parse(reader.result)); log('Metadati foto letti', 'ok'); GL.app?.xp(6, 'metadati'); }
        catch { render({}); log('Foto senza metadati', 'warn'); }
      };
      reader.readAsArrayBuffer(f);
    });
  }

  GL.metadata = { init };
})();
