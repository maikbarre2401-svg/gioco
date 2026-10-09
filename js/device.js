window.GL = window.GL || {};

(() => {
  'use strict';

  // Reads what any web page can learn about this device without asking permission.

  function detectOS() {
    const ua = navigator.userAgent;
    const uaData = navigator.userAgentData;
    let m;
    if ((m = ua.match(/Android\s([\d.]+)/))) return `Android ${m[1]}`;
    if ((m = ua.match(/(?:iPhone|CPU) OS (\d+)[._](\d+)/))) return `iOS ${m[1]}.${m[2]}`;
    if (/iPad|Macintosh/.test(ua) && navigator.maxTouchPoints > 1) return 'iPadOS';
    if ((m = ua.match(/Windows NT ([\d.]+)/))) return m[1] === '10.0' ? 'Windows 10/11' : `Windows NT ${m[1]}`;
    if (/Mac OS X/.test(ua)) return 'macOS';
    if (/CrOS/.test(ua)) return 'ChromeOS';
    if (/Linux/.test(ua)) return 'Linux';
    return uaData?.platform || 'Sconosciuto';
  }

  function detectBrowser() {
    const ua = navigator.userAgent;
    let m;
    if ((m = ua.match(/SamsungBrowser\/([\d]+)/))) return `Samsung Internet ${m[1]}`;
    if ((m = ua.match(/EdgA?\/([\d]+)/))) return `Edge ${m[1]}`;
    if ((m = ua.match(/OPR\/([\d]+)/))) return `Opera ${m[1]}`;
    if ((m = ua.match(/Firefox\/([\d]+)/)) || (m = ua.match(/FxiOS\/([\d]+)/))) return `Firefox ${m[1]}`;
    if ((m = ua.match(/CriOS\/([\d]+)/))) return `Chrome ${m[1]} (iOS)`;
    if ((m = ua.match(/Chrome\/([\d]+)/))) return `Chrome ${m[1]}`;
    if ((m = ua.match(/Version\/([\d.]+).*Safari/))) return `Safari ${m[1]}`;
    return 'Sconosciuto';
  }

  function isStandalone() {
    return matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  }

  function screenInfo() {
    const dpr = window.devicePixelRatio || 1;
    return {
      css: `${screen.width}×${screen.height}`,
      real: `${Math.round(screen.width * dpr)}×${Math.round(screen.height * dpr)}`,
      dpr,
      depth: screen.colorDepth,
    };
  }

  function gpuInfo() {
    try {
      const gl = document.createElement('canvas').getContext('webgl');
      if (!gl) return null;
      const ext = gl.getExtension('WEBGL_debug_renderer_info');
      const renderer = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
      let name = String(renderer);
      const angle = name.match(/^ANGLE \((.*)\)$/); // e.g. "ANGLE (Qualcomm, Adreno (TM) 740, OpenGL ES 3.2)"
      if (angle) { const parts = angle[1].split(', '); name = parts[1] || parts[0]; }
      return name.replace(/\s*\((TM|R)\)/gi, '').replace(/\s+(Direct3D|OpenGL|Vulkan).*$/i, '').trim();
    } catch { return null; }
  }

  // Canvas fingerprint: tiny rendering differences between GPUs/fonts give each device a stable hash.
  function canvasPrint() {
    try {
      const c = document.createElement('canvas');
      c.width = 240; c.height = 60;
      const ctx = c.getContext('2d');
      ctx.textBaseline = 'top';
      ctx.font = '16px Arial';
      ctx.fillStyle = '#f60';
      ctx.fillRect(100, 1, 62, 20);
      ctx.fillStyle = '#069';
      ctx.fillText('Ghostlink ✓ ñ 😀', 2, 15);
      ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
      ctx.fillText('Ghostlink ✓ ñ 😀', 4, 17);
      return c.toDataURL();
    } catch { return ''; }
  }

  async function battery() {
    try {
      if (!navigator.getBattery) return null;
      return await navigator.getBattery();
    } catch { return null; }
  }

  function connection() {
    const c = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (!c) return null;
    return { type: c.type, effective: c.effectiveType, down: c.downlink, rtt: c.rtt, saveData: c.saveData, raw: c };
  }

  // Everything that goes into the fingerprint hash, as label/value pairs.
  function fingerprintParts() {
    const s = screenInfo();
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return [
      ['userAgent', navigator.userAgent],
      ['lingue', (navigator.languages || [navigator.language]).join(',')],
      ['fuso', tz],
      ['schermo', `${s.real}@${s.dpr}x${s.depth}`],
      ['core', navigator.hardwareConcurrency],
      ['memoria', navigator.deviceMemory],
      ['touch', navigator.maxTouchPoints],
      ['gpu', gpuInfo()],
      ['canvas', canvasPrint()],
    ];
  }

  // Rough "how identifiable are you" score from 0 to 100, from the signals that make a device stand out.
  function exposureScore() {
    let score = 25;
    if (navigator.deviceMemory) score += 8;
    if (navigator.hardwareConcurrency) score += 7;
    if (gpuInfo()) score += 20;
    if (canvasPrint()) score += 20;
    if (connection()) score += 8;
    if (navigator.getBattery) score += 6;
    if ((navigator.languages || []).length > 1) score += 6;
    return Math.min(100, score);
  }

  function exposureLabel(score) {
    if (score >= 80) return { text: `ALTA · ${score}/100`, cls: 'hot' };
    if (score >= 55) return { text: `MEDIA · ${score}/100`, cls: 'warn' };
    return { text: `BASSA · ${score}/100`, cls: 'good' };
  }

  GL.device = { detectOS, detectBrowser, isStandalone, screenInfo, gpuInfo, canvasPrint, battery, connection, fingerprintParts, exposureScore, exposureLabel };
})();
