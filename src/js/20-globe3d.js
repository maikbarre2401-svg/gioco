'use strict';
/* ════════════════════════════════════════════════════════════════
   MOTORE 3D — CesiumJS
   Globo WGS84 reale, terreno 3D, sole reale (giorno/notte),
   aerei alla loro quota reale, satelliti in orbita, post-processing.
═══════════════════════════════════════════════════════════════════ */
const Globe3D = (() => {
  const VER = '1.146.0';
  const CDN = `https://cdn.jsdelivr.net/npm/cesium@${VER}/Build/Cesium/`;
  let C = null, viewer = null, scene = null, camera = null, ready = false;
  const state = { layers: {}, scene: '3d', vis: 'nrm', spin: false, base: 'sat', exag: 1.5 };
  const ds = {};                    // CustomDataSource per gruppo
  const acMap = new Map();          // hex -> {b, l, ac, cart}
  const satMap = new Map();         // id  -> {p|b, l, cart}
  let acBB, acLbl, satPts, satBB, satLbl, firePts, auroraPts, pulsePts, selPts;
  const imagery = { base: null, night: null, labels: null, radar: null };
  let tilesets = { osm: null, photo: null };
  const stages = {};
  let sel = null, follow = null, cockpit = null, followInit = false;
  const scratch = {};
  let lastAcData = [];

  /* ── Sprite disegnati su canvas (bianchi: il colore si applica col tint) ── */
  const SPR = {};
  function sprite(kind) {
    if (SPR[kind]) return SPR[kind];
    const S = 64, cv = document.createElement('canvas'); cv.width = cv.height = S;
    const x = cv.getContext('2d'); x.translate(S / 2, S / 2); x.scale(S / 48, S / 48);
    x.fillStyle = '#fff'; x.strokeStyle = 'rgba(0,0,0,.85)'; x.lineWidth = 1.6; x.lineJoin = 'round';
    const poly = (pts, mirror = true) => {
      x.beginPath(); x.moveTo(pts[0][0], pts[0][1]); pts.slice(1).forEach(p => x.lineTo(p[0], p[1]));
      if (mirror) for (let i = pts.length - 1; i >= 0; i--) x.lineTo(-pts[i][0], pts[i][1]);
      x.closePath(); x.stroke(); x.fill();
    };
    switch (kind) {
      case 'fighter': poly([[0, -21], [3, -9], [4, -2], [17, 9], [17, 12], [4, 10], [6, 18], [6, 20], [0, 18]]); break;
      case 'heli':
        x.beginPath(); x.ellipse(0, 0, 6, 8, 0, 0, Math.PI * 2); x.stroke(); x.fill();
        x.fillRect(-1.5, 6, 3, 15); x.strokeRect(-1.5, 6, 3, 15);
        x.lineWidth = 2.4; x.strokeStyle = '#fff'; x.beginPath(); x.moveTo(-19, -12); x.lineTo(19, 12); x.moveTo(19, -12); x.lineTo(-19, 12); x.stroke(); break;
      case 'drone': poly([[0, -12], [2, -6], [23, -3], [23, 0], [2, 1], [2, 12], [8, 17], [8, 19], [0, 16]]); break;
      case 'isr':
        poly([[0, -21], [2.6, -16], [2.6, -6], [20, 3], [20, 6], [2.6, 3], [2.4, 13], [8, 18], [8, 20], [0, 18]]);
        x.beginPath(); x.ellipse(0, 4, 9, 3.2, 0, 0, Math.PI * 2); x.stroke(); x.fill(); break;
      case 'heavy': poly([[0, -21], [3.4, -16], [3.4, -6], [22, 2], [22, 6], [3.4, 3], [3, 13], [9, 18], [9, 20], [0, 18]]); break;
      case 'sat':
        x.fillRect(-4, -4, 8, 8); x.strokeRect(-4, -4, 8, 8);
        x.fillRect(-21, -3, 14, 6); x.strokeRect(-21, -3, 14, 6); x.fillRect(7, -3, 14, 6); x.strokeRect(7, -3, 14, 6);
        x.beginPath(); x.moveTo(-7, 0); x.lineTo(-4, 0); x.moveTo(4, 0); x.lineTo(7, 0); x.stroke(); break;
      case 'dot':
        x.beginPath(); x.arc(0, 0, 9, 0, Math.PI * 2); x.fill(); x.stroke(); break;
      case 'ring':
        x.lineWidth = 3; x.strokeStyle = '#fff'; x.beginPath(); x.arc(0, 0, 19, 0, Math.PI * 2); x.stroke();
        x.setLineDash([5, 5]); x.beginPath(); x.arc(0, 0, 23, 0, Math.PI * 2); x.stroke(); break;
      default: poly([[0, -21], [2.6, -16], [2.6, -6], [19, 4], [19, 7], [2.6, 3], [2.2, 13], [7.5, 18], [7.5, 20], [0, 18]]);
    }
    return (SPR[kind] = cv.toDataURL());
  }
  function emojiSprite(emoji, ring = '#00ff41', size = 44) {
    const key = 'e' + emoji + ring + size;
    if (SPR[key]) return SPR[key];
    const cv = document.createElement('canvas'); cv.width = cv.height = size;
    const x = cv.getContext('2d');
    x.fillStyle = 'rgba(0,10,0,.82)'; x.beginPath(); x.arc(size / 2, size / 2, size / 2 - 3, 0, Math.PI * 2); x.fill();
    x.lineWidth = 2.5; x.strokeStyle = ring; x.stroke();
    x.font = `${Math.round(size * 0.5)}px "Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",sans-serif`;
    x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(emoji, size / 2, size / 2 + 1);
    return (SPR[key] = cv.toDataURL());
  }
  function clusterSprite(n) {
    const key = 'cl' + n; if (SPR[key]) return SPR[key];
    const s = 46, cv = document.createElement('canvas'); cv.width = cv.height = s; const x = cv.getContext('2d');
    x.fillStyle = 'rgba(255,34,68,.25)'; x.beginPath(); x.arc(s / 2, s / 2, s / 2 - 2, 0, Math.PI * 2); x.fill();
    x.fillStyle = 'rgba(30,0,6,.9)'; x.beginPath(); x.arc(s / 2, s / 2, s / 2 - 8, 0, Math.PI * 2); x.fill();
    x.strokeStyle = '#ff5577'; x.lineWidth = 2; x.stroke();
    x.fillStyle = '#fff'; x.font = 'bold 15px "Share Tech Mono",monospace'; x.textAlign = 'center'; x.textBaseline = 'middle';
    x.fillText(String(n), s / 2, s / 2 + 1);
    return (SPR[key] = cv.toDataURL());
  }
  const AC_SHAPE = { civil: 'jet', mil: 'heavy', fighter: 'fighter', tanker: 'heavy', isr: 'isr', transport: 'heavy', helo: 'heli', drone: 'drone', vip: 'jet' };

  /* ── colori ── */
  const colCache = new Map();
  const col = (css, a = 1) => { const k = css + a; if (!colCache.has(k)) colCache.set(k, C.Color.fromCssColorString(css).withAlpha(a)); return colCache.get(k); };
  const rad = d => d * Math.PI / 180;
  const cart = (lat, lon, h = 0, res) => C.Cartesian3.fromDegrees(lon, lat, h, C.Ellipsoid.WGS84, res);

  /* ── basi cartografiche ── */
  const yday = () => { const d = new Date(Date.now() - 36 * 3600e3); return d.toISOString().slice(0, 10); };
  const GIBS = (layer, date, tms, ext) => `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/${layer}/default/${date ? date + '/' : ''}${tms}/{z}/{y}/{x}.${ext}`;
  const CANDIDATES = {
    today: () => [GIBS('VIIRS_SNPP_CorrectedReflectance_TrueColor', yday(), 'GoogleMapsCompatible_Level9', 'jpg'), GIBS('VIIRS_NOAA20_CorrectedReflectance_TrueColor', yday(), 'GoogleMapsCompatible_Level9', 'jpg'), GIBS('MODIS_Terra_CorrectedReflectance_TrueColor', yday(), 'GoogleMapsCompatible_Level9', 'jpg')],
    modis: () => [GIBS('MODIS_Terra_CorrectedReflectance_TrueColor', yday(), 'GoogleMapsCompatible_Level9', 'jpg'), GIBS('MODIS_Aqua_CorrectedReflectance_TrueColor', yday(), 'GoogleMapsCompatible_Level9', 'jpg')],
    night: () => [GIBS('VIIRS_Black_Marble', '2016-01-01', 'GoogleMapsCompatible_Level8', 'png'), GIBS('VIIRS_CityLights_2012', '', 'GoogleMapsCompatible_Level8', 'jpg'), GIBS('VIIRS_CityLights_2012', '2012-01-01', 'GoogleMapsCompatible_Level8', 'jpg')]
  };
  const probed = {};
  async function firstOk(key) {           // usa la prima variante GIBS che risponde davvero
    if (probed[key]) return probed[key];
    for (const u of CANDIDATES[key]()) {
      try {
        const r = await Net.raw(u.replace('{z}', '1').replace('{y}', '0').replace('{x}', '1'), 8000);
        if ((r.headers.get('content-type') || '').startsWith('image')) return (probed[key] = u);
      } catch {}
    }
    return null;
  }
  const BASES = {
    sat: { name: '🛰 Satellite (Esri)', make: () => tmpl('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', 19, 'Immagini © Esri, Maxar, Earthstar Geographics') },
    today: { name: '📅 NASA VIIRS (ieri)', probe: 'today', make: u => tmpl(u, 9, 'NASA GIBS / VIIRS') },
    modis: { name: '📅 NASA MODIS (ieri)', probe: 'modis', make: u => tmpl(u, 9, 'NASA GIBS / MODIS') },
    dark: { name: '🌑 Scura (CARTO)', make: () => tmpl('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png', 19, '© OpenStreetMap © CARTO', 'abcd') },
    topo: { name: '⛰ Topografica (Esri)', make: () => tmpl('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', 19, '© Esri') },
    osm: { name: '🗺 OpenStreetMap', make: () => tmpl('https://tile.openstreetmap.org/{z}/{x}/{y}.png', 19, '© OpenStreetMap contributors') },
    night: { name: '🌃 Luci notturne (NASA)', probe: 'night', make: u => tmpl(u, 8, 'NASA Earth Observatory / Black Marble') },
    bing: { name: '🛰 Bing Aerial (ion)', ion: true, make: () => C.IonImageryProvider.fromAssetId(3) }
  };
  function tmpl(url, max, credit, sub) {
    return new C.UrlTemplateImageryProvider({ url, maximumLevel: max, subdomains: sub ? sub.split('') : undefined, credit: new C.Credit(credit, false) });
  }

  /* ── Terreno 3D gratuito: tile Terrarium (AWS Open Data) decodificati in heightmap ── */
  function terrariumProvider() {
    const W = 33, Hh = 33, MAXZ = 13;
    const cache = new Map(); let inflight = 0, errs = 0, okN = 0;
    const ts = new C.GeographicTilingScheme();
    const cv = document.createElement('canvas'); cv.width = cv.height = 256;
    const cx = cv.getContext('2d', { willReadFrequently: true });
    function tile(z, x, y) {
      const k = z + '/' + x + '/' + y;
      if (cache.has(k)) { const v = cache.get(k); cache.delete(k); cache.set(k, v); return v; }
      inflight++;
      const p = (async () => {
        try {
          const r = await fetch(`https://s3.amazonaws.com/elevation-tiles-prod/terrarium/${z}/${x}/${y}.png`, { mode: 'cors', credentials: 'omit' });
          if (!r.ok) throw new Error('HTTP ' + r.status);
          const bmp = await createImageBitmap(await r.blob());
          cx.clearRect(0, 0, 256, 256); cx.drawImage(bmp, 0, 0); bmp.close?.();
          const d = cx.getImageData(0, 0, 256, 256).data, out = new Float32Array(65536);
          for (let i = 0, j = 0; i < 65536; i++, j += 4) out[i] = d[j] * 256 + d[j + 1] + d[j + 2] / 256 - 32768;
          errs = 0; okN++;
          if (okN === 1) Health.ok('terrain', { via: 'AWS Terrain Tiles', msg: 'terreno 3D attivo' });
          return out;
        } catch (e) {
          errs++;
          if (errs === 12 && okN === 0) { Health.fail('terrain', e); Bus.emit('terrain:failed'); }
          return null;
        } finally { inflight--; }
      })();
      cache.set(k, p);
      if (cache.size > 220) cache.delete(cache.keys().next().value);
      return p;
    }
    const MAXLAT = 85.05112878;
    return new C.CustomHeightmapTerrainProvider({
      width: W, height: Hh, tilingScheme: ts, credit: new C.Credit('Terreno: Mapzen/AWS Terrain Tiles', false),
      callback(x, y, level) {
        if (inflight > 10) return undefined;              // Cesium riproverà: mostra il tile padre
        const r = ts.tileXYToRectangle(x, y, level);
        const west = C.Math.toDegrees(r.west), east = C.Math.toDegrees(r.east), north = C.Math.toDegrees(r.north), south = C.Math.toDegrees(r.south);
        const z = clamp(level - 1, 0, MAXZ), n = 1 << z;
        const samples = new Array(W * Hh); const need = new Map();
        for (let j = 0; j < Hh; j++) {
          const lat = clamp(north - (north - south) * j / (Hh - 1), -MAXLAT, MAXLAT);
          const sl = Math.sin(lat * Math.PI / 180);
          const py = (0.5 - Math.log((1 + sl) / (1 - sl)) / (4 * Math.PI)) * n * 256;
          for (let i = 0; i < W; i++) {
            const lon = west + (east - west) * i / (W - 1);
            const px = ((lon + 180) / 360) * n * 256;
            const tx = clamp(Math.floor(px / 256), 0, n - 1), ty = clamp(Math.floor(py / 256), 0, n - 1);
            const ix = clamp(Math.floor(px - tx * 256), 0, 255), iy = clamp(Math.floor(py - ty * 256), 0, 255);
            const key = tx + ',' + ty; if (!need.has(key)) need.set(key, [tx, ty]);
            samples[j * W + i] = [key, iy * 256 + ix];
          }
        }
        const keys = [...need.keys()];
        return Promise.all(keys.map(k => tile(z, need.get(k)[0], need.get(k)[1]))).then(arrs => {
          const m = new Map(keys.map((k, i) => [k, arrs[i]]));
          const out = new Float32Array(W * Hh);
          for (let i = 0; i < out.length; i++) { const [k, idx] = samples[i]; const a = m.get(k); const v = a ? a[idx] : 0; out[i] = v > 0 ? v : 0; }
          return out;
        });
      }
    });
  }

  /* ── post-processing: visore notturno, termico, tattico ── */
  const FS = {
    nvg: `uniform sampler2D colorTexture; uniform float u_time; in vec2 v_textureCoordinates;
      float rnd(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233))) * 43758.5453); }
      void main(){ vec2 uv = v_textureCoordinates; vec3 c = texture(colorTexture, uv).rgb;
        float l = dot(c, vec3(0.299,0.587,0.114)); l = clamp(pow(l, 0.75) * 1.8, 0.0, 1.0);
        float n = (rnd(uv * 640.0 + fract(u_time)) - 0.5) * 0.16; float scan = 0.92 + 0.08 * sin(uv.y * 1500.0);
        float vig = smoothstep(0.82, 0.28, distance(uv, vec2(0.5)));
        out_FragColor = vec4(vec3(0.15, 1.0, 0.32) * (l + n) * scan * vig, 1.0); }`,
    flir: `uniform sampler2D colorTexture; uniform float u_time; in vec2 v_textureCoordinates;
      float rnd(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233))) * 43758.5453); }
      vec3 pal(float t){ t = clamp(t,0.0,1.0); vec3 a = mix(vec3(0.0,0.0,0.06), vec3(0.32,0.0,0.52), smoothstep(0.0,0.28,t));
        a = mix(a, vec3(0.88,0.08,0.12), smoothstep(0.24,0.52,t)); a = mix(a, vec3(1.0,0.62,0.0), smoothstep(0.48,0.78,t));
        return mix(a, vec3(1.0,1.0,0.88), smoothstep(0.76,1.0,t)); }
      void main(){ vec2 uv = v_textureCoordinates; vec2 px = 1.0 / vec2(textureSize(colorTexture, 0));
        vec3 c = (texture(colorTexture, uv).rgb * 4.0 + texture(colorTexture, uv + vec2(px.x,0)).rgb + texture(colorTexture, uv - vec2(px.x,0)).rgb
          + texture(colorTexture, uv + vec2(0,px.y)).rgb + texture(colorTexture, uv - vec2(0,px.y)).rgb) / 8.0;
        float l = dot(c, vec3(0.30,0.59,0.11)); l = smoothstep(0.04, 0.92, l) + (rnd(uv*512.0+fract(u_time))-0.5)*0.03;
        out_FragColor = vec4(pal(l), 1.0); }`,
    crt: `uniform sampler2D colorTexture; in vec2 v_textureCoordinates;
      float L(vec2 p){ return dot(texture(colorTexture, p).rgb, vec3(0.299,0.587,0.114)); }
      void main(){ vec2 uv = v_textureCoordinates; vec2 px = 1.0 / vec2(textureSize(colorTexture, 0));
        float tl=L(uv+px*vec2(-1.,1.)), t=L(uv+px*vec2(0.,1.)), tr=L(uv+px*vec2(1.,1.)), l=L(uv+px*vec2(-1.,0.)), r=L(uv+px*vec2(1.,0.));
        float bl=L(uv+px*vec2(-1.,-1.)), b=L(uv+px*vec2(0.,-1.)), br=L(uv+px*vec2(1.,-1.));
        float gx = -tl - 2.0*l - bl + tr + 2.0*r + br; float gy = -bl - 2.0*b - br + tl + 2.0*t + tr;
        float e = clamp(length(vec2(gx,gy)) * 2.6, 0.0, 1.0); float base = L(uv) * 0.22;
        float scan = 0.85 + 0.15 * sin(uv.y * 1200.0);
        out_FragColor = vec4(vec3(0.0, 1.0, 0.38) * (e + base) * scan, 1.0); }`
  };
  function setVisual(mode) {
    state.vis = mode;
    if (!ready) return;
    setTimeout(() => scene.requestRender(), 30);
    Object.values(stages).forEach(s => s.enabled = false);
    if (mode !== 'nrm' && FS[mode]) {
      if (!stages[mode]) {
        try {
          stages[mode] = scene.postProcessStages.add(new C.PostProcessStage({ name: 'ojo_' + mode, fragmentShader: FS[mode], uniforms: mode === 'crt' ? {} : { u_time: () => (performance.now() / 1000) % 1000 } }));
        } catch (e) { console.warn('post-process', e); Toast.show('⚠ Effetto non supportato dalla GPU', 'orn'); return; }
      }
      stages[mode].enabled = true;
    }
  }

  /* ── inizializzazione ── */
  async function init(container) {
    window.CESIUM_BASE_URL = CDN;
    await loadCSS(CDN + 'Widgets/widgets.css');
    await loadScript(CDN + 'Cesium.js', 60000);
    C = window.Cesium; if (!C) throw new Error('Cesium non caricato');
    const tok = (Settings.get('ionToken') || '').trim();
    if (tok) C.Ion.defaultAccessToken = tok;
    state.base = BASES[Settings.get('base')] && (!BASES[Settings.get('base')].ion || tok) ? Settings.get('base') : 'sat';

    viewer = new C.Viewer(container, {
      baseLayer: false, terrainProvider: new C.EllipsoidTerrainProvider(),
      animation: false, timeline: false, baseLayerPicker: false, geocoder: false, homeButton: false, sceneModePicker: false,
      navigationHelpButton: false, fullscreenButton: false, infoBox: false, selectionIndicator: false, vrButton: false,
      shouldAnimate: true, showRenderLoopErrors: false, creditContainer: $('credits'), msaaSamples: Settings.get('quality') === 'low' ? 1 : 2,
      requestRenderMode: true, maximumRenderTimeChange: 10,
      contextOptions: { webgl: { alpha: false, powerPreference: 'high-performance' } }
    });
    scene = viewer.scene; camera = viewer.camera;
    const g = scene.globe;
    g.enableLighting = Settings.get('lighting') !== false;
    g.dynamicAtmosphereLighting = true; g.dynamicAtmosphereLightingFromSun = true;
    g.showGroundAtmosphere = true; g.depthTestAgainstTerrain = false;
    g.lightingFadeOutDistance = 1.2e6; g.lightingFadeInDistance = 4.5e6;
    g.nightFadeOutDistance = 1.2e6; g.nightFadeInDistance = 4.5e6;
    g.baseColor = C.Color.fromCssColorString('#020a04');
    g.maximumScreenSpaceError = 1.8; g.tileCacheSize = 200;
    scene.skyAtmosphere.show = true; scene.fog.enabled = true; scene.fog.density = 2.0e-4;
    scene.screenSpaceCameraController.minimumZoomDistance = 30;
    scene.screenSpaceCameraController.maximumZoomDistance = 8e7;
    scene.postProcessStages.fxaa.enabled = true;
    scene.verticalExaggeration = state.exag = +Settings.get('exag') || 1.5;
    viewer.targetFrameRate = 60;
    if (Settings.get('quality') === 'low') viewer.resolutionScale = 0.75;

    await setBase(state.base);
    firstOk('night').then(u => {
      if (!u) return;
      addOverlay('night', BASES.night.make(u), l => { l.dayAlpha = 0.0; l.nightAlpha = 0.95; l.brightness = 1.7; });
      viewer.imageryLayers.lowerToBottom(imagery.night); viewer.imageryLayers.raise(imagery.night);   // sopra la base, sotto le etichette
    });
    addOverlay('labels', tmpl('https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}.png', 19, '© CARTO', 'abcd'), l => { l.alpha = 0.85; });

    // primitive collections
    const P = scene.primitives;
    auroraPts = P.add(new C.PointPrimitiveCollection({ blendOption: C.BlendOption.TRANSLUCENT }));
    firePts = P.add(new C.PointPrimitiveCollection());
    satPts = P.add(new C.PointPrimitiveCollection());
    satBB = P.add(new C.BillboardCollection({ scene }));
    satLbl = P.add(new C.LabelCollection({ scene }));
    acBB = P.add(new C.BillboardCollection({ scene }));
    acLbl = P.add(new C.LabelCollection({ scene }));
    pulsePts = P.add(new C.PointPrimitiveCollection({ blendOption: C.BlendOption.TRANSLUCENT }));
    selPts = P.add(new C.BillboardCollection({ scene }));
    for (const k of ['conflict', 'gps', 'choke', 'bases', 'nuclear', 'quakes', 'eonet', 'news', 'trace', 'sel']) {
      ds[k] = new C.CustomDataSource(k); await viewer.dataSources.add(ds[k]);
    }
    const cl = ds.news.clustering; cl.enabled = true; cl.pixelRange = 34; cl.minimumClusterSize = 3;
    cl.clusterEvent.addEventListener((ents, c) => {
      c.label.show = false; c.billboard.show = true; c.billboard.image = clusterSprite(ents.length);
      c.billboard.verticalOrigin = C.VerticalOrigin.CENTER; c.billboard.id = ents;
    });

    camera.setView({ destination: cart(30, 25, 2.2e7) });
    bindInput();
    scene.preUpdate.addEventListener(preUpdate);
    let frames = 0, fpsT = performance.now();
    scene.postRender.addEventListener(() => {
      frames++; const n = performance.now();
      if (n - fpsT > 1000) { setText('sb-fps', Math.round(frames * 1000 / (n - fpsT))); frames = 0; fpsT = n; }
    });
    scene.renderError.addEventListener((s, err) => { console.error('render', err); Bus.emit('engine:fatal', err); });
    camera.percentageChanged = 0.02;
    camera.changed.addEventListener(() => Bus.emit('map:view', getView()));
    setInterval(deadReckon, 500);
    // rendering su richiesta: ridisegna solo quando serve (animazioni attive → 20-30 fps)
    let lastAnim = 0;
    setInterval(() => {
      if (!ready || document.hidden) return;
      const now = performance.now();
      const fast = state.spin || follow || cockpit;
      const slow = (pulsePts.length && pulsePts.show !== false) || selPts.length || state.vis === 'nvg' || state.vis === 'flir';
      if (fast || (slow && now - lastAnim > 48)) { lastAnim = now; scene.requestRender(); }
    }, 33);
    Bus.on('terrain:failed', () => { if (!tok) { viewer.terrainProvider = new C.EllipsoidTerrainProvider(); Toast.show('⚠ Terreno 3D non raggiungibile: globo liscio', 'orn'); } });

    ready = true;
    if (Settings.get('terrain') !== false) setTerrain(true);
    return true;
  }

  function addOverlay(key, provider, cfg) {
    const l = viewer.imageryLayers.addImageryProvider(provider);
    cfg?.(l); imagery[key] = l;
    l.show = state.layers[key] ?? true;
    return l;
  }
  async function setBase(key) {
    const b = BASES[key] || BASES.sat;
    if (b.ion && !C.Ion.defaultAccessToken) { Toast.show('⚠ Serve un token Cesium ion', 'orn'); return; }
    try {
      let url;
      if (b.probe) { url = await firstOk(b.probe); if (!url) { Toast.show('⚠ ' + b.name + ': servizio NASA non raggiungibile ora', 'orn'); if (!imagery.base) return setBase('sat'); return; } }
      const layer = b.ion ? C.ImageryLayer.fromProviderAsync(b.make()) : new C.ImageryLayer(b.make(url));
      viewer.imageryLayers.add(layer, 0);
      const old = imagery.base; imagery.base = layer;
      if (old) setTimeout(() => viewer.imageryLayers.remove(old, true), 1500);
      state.base = key; Settings.set('base', key); scene.requestRender();
    } catch (e) { console.warn(e); Toast.show('⚠ Base non disponibile', 'orn'); }
  }
  async function setTerrain(on) {
    if (!ready) return;
    try {
      if (!on) { viewer.terrainProvider = new C.EllipsoidTerrainProvider(); Health.set('terrain', 'off', 'disattivato'); return; }
      if (C.Ion.defaultAccessToken && Settings.get('ionToken')) {
        viewer.terrainProvider = await C.createWorldTerrainAsync({ requestVertexNormals: true, requestWaterMask: true });
        Health.ok('terrain', { via: 'Cesium World Terrain (ion)' });
      } else {
        viewer.terrainProvider = terrariumProvider();
        Health.set('terrain', 'wait', 'caricamento tile…');
      }
    } catch (e) { console.warn(e); Health.fail('terrain', e); viewer.terrainProvider = new C.EllipsoidTerrainProvider(); }
  }
  async function setTileset(key, on) {
    if (!ready) return false;
    if (!C.Ion.defaultAccessToken || !Settings.get('ionToken')) { Toast.show('⚠ Edifici 3D: serve un token Cesium ion (⚙)', 'orn'); return false; }
    try {
      if (on && !tilesets[key]) {
        tilesets[key] = key === 'osm' ? await C.createOsmBuildingsAsync() : await C.createGooglePhotorealistic3DTileset();
        scene.primitives.add(tilesets[key]);
      }
      if (tilesets[key]) tilesets[key].show = on;
      if (key === 'photo') scene.globe.show = !on;
      Health.ok(key === 'osm' ? 'osm3d' : 'photo3d', { via: 'Cesium ion' });
      return true;
    } catch (e) { console.warn(e); Health.fail(key === 'osm' ? 'osm3d' : 'photo3d', e); Toast.show('⚠ Tileset 3D non disponibile: ' + e.message, 'orn'); return false; }
  }

  /* ── input ── */
  function globePick(pos) {
    try {
      const ray = camera.getPickRay(pos);
      let c = ray && scene.globe.pick(ray, scene);
      if (!c) c = camera.pickEllipsoid(pos, C.Ellipsoid.WGS84);
      if (!c) return null;
      const g = C.Cartographic.fromCartesian(c);
      return { lat: C.Math.toDegrees(g.latitude), lon: C.Math.toDegrees(g.longitude), h: g.height };
    } catch { return null; }
  }
  function refFromPick(p) {
    if (!p) return null;
    const id = p.id;
    if (Array.isArray(id)) return { kind: 'many', items: id.map(e => parseEnt(e)).filter(Boolean) };
    if (id instanceof C.Entity) return parseEnt(id);
    if (id && id.kind) return id;
    return null;
  }
  function parseEnt(e) { const s = String(e.id || ''); const i = s.indexOf(':'); return i > 0 ? { kind: s.slice(0, i), id: s.slice(i + 1) } : null; }
  function bindInput() {
    const H = new C.ScreenSpaceEventHandler(scene.canvas);
    H.setInputAction(e => {
      const ref = refFromPick(scene.pick(e.position));
      if (ref && ref.kind !== 'sel' && ref.kind !== 'trace' && ref.kind !== 'conflict' && ref.kind !== 'gps') { Bus.emit('map:pick', ref); return; }
      const ll = globePick(e.position); if (ll) Bus.emit('map:click', ll);
    }, C.ScreenSpaceEventType.LEFT_CLICK);
    H.setInputAction(e => {
      const ll = globePick(e.position);
      if (ll) Bus.emit('map:context', Object.assign(ll, { x: e.position.x + scene.canvas.getBoundingClientRect().left, y: e.position.y + scene.canvas.getBoundingClientRect().top }));
    }, C.ScreenSpaceEventType.RIGHT_CLICK);
    let mt = 0;
    H.setInputAction(e => {
      const n = performance.now(); if (n - mt < 70) return; mt = n;
      const ll = globePick(e.endPosition); if (ll) Bus.emit('map:move', ll);
      const ref = refFromPick(scene.pick(e.endPosition));
      scene.canvas.style.cursor = ref && !['sel', 'trace', 'conflict', 'gps'].includes(ref.kind) ? 'pointer' : '';
    }, C.ScreenSpaceEventType.MOUSE_MOVE);
    const stopSpin = () => { if (state.spin) { state.spin = false; Bus.emit('spin', false); } };
    scene.canvas.addEventListener('pointerdown', stopSpin);
    scene.canvas.addEventListener('wheel', stopSpin, { passive: true });
  }

  /* ── loop per frame: spin, follow, cockpit, impulsi ── */
  function preUpdate() {
    const t = performance.now();
    if (state.spin && scene.mode === C.SceneMode.SCENE3D && !follow && !cockpit) camera.rotate(C.Cartesian3.UNIT_Z, -0.0009);
    if (cockpit) {
      const e = acMap.get(cockpit.id);
      if (e && e.cart) {
        const g = C.Cartographic.fromCartesian(e.cart);
        camera.setView({ destination: C.Cartesian3.fromRadians(g.longitude, g.latitude, g.height + 25), orientation: { heading: rad(e.ac.trk || 0), pitch: rad(-6), roll: 0 } });
      }
    } else if (follow) {
      const p = refPos(follow);
      if (p) {
        if (!followInit) { camera.lookAt(p, new C.HeadingPitchRange(camera.heading, rad(-40), follow.kind === 'sat' ? 2.5e6 : 60000)); followInit = true; }
        else camera.lookAt(p, C.Cartesian3.clone(camera.position, scratch.off || (scratch.off = new C.Cartesian3())));
      }
    }
    // impulsi (terremoti forti / emergenze)
    const len = pulsePts.length, pc = scratch.pc || (scratch.pc = new C.Color());
    for (let i = 0; i < len; i++) {
      const p = pulsePts.get(i), ph = ((t / 1000 + p._ph) % 2) / 2;
      p.pixelSize = p._base + ph * p._grow;
      p.color = p._col.withAlpha((1 - ph) * 0.75, pc);
    }
    // anello selezione
    if (selPts.length) { const b = selPts.get(0); b.rotation = (t / 1400) % (Math.PI * 2); const p = sel && refPos(sel); if (p) b.position = p; }
  }
  function refPos(ref) {
    if (!ref) return null;
    if (ref.kind === 'ac') return acMap.get(ref.id)?.cart || null;
    if (ref.kind === 'sat') return satMap.get(ref.id)?.cart || null;
    if (ref.lat != null) return cart(ref.lat, ref.lon, ref.h || 0);
    return null;
  }

  /* ── AEREI ── */
  const NFS_AC = () => scratch.nfsAc || (scratch.nfsAc = new C.NearFarScalar(1.5e5, 1.25, 1.2e7, 0.42));
  const DDC_LBL = () => scratch.ddc || (scratch.ddc = new C.DistanceDisplayCondition(0, 2.2e6));
  function acColor(ac) { return ac.emerg ? col('#ff2244') : col((DATA.AC_CLASS[ac.cls] || DATA.AC_CLASS.civil).col); }
  function setAircraft(list) {
    lastAcData = list;
    const seen = new Set();
    const max = Settings.get('maxAircraft') || 15000;
    const lim = Math.min(list.length, max);
    for (let i = 0; i < lim; i++) {
      const ac = list[i]; seen.add(ac.hex);
      let e = acMap.get(ac.hex);
      const pos = cart(ac.lat, ac.lon, ac.altM || 0, scratch.p1 || (scratch.p1 = new C.Cartesian3()));
      if (!e) {
        const b = acBB.add({ position: pos, image: sprite(AC_SHAPE[ac.cls] || 'jet'), color: acColor(ac), rotation: -rad(ac.trk || 0),
          alignedAxis: C.Cartesian3.UNIT_Z, scale: ac.cls === 'civil' ? 0.42 : 0.55, scaleByDistance: NFS_AC(), id: { kind: 'ac', id: ac.hex } });
        e = { b, l: null, ac, cart: C.Cartesian3.clone(pos), cls: ac.cls };
        acMap.set(ac.hex, e);
      } else {
        e.ac = ac; e.b.position = pos; C.Cartesian3.clone(pos, e.cart); e.b.rotation = -rad(ac.trk || 0);
        if (e.cls !== ac.cls || e.emerg !== ac.emerg) { e.b.image = sprite(AC_SHAPE[ac.cls] || 'jet'); e.b.color = acColor(ac); e.cls = ac.cls; e.emerg = ac.emerg; }
      }
      const wantLbl = Settings.get('labels') !== false && (ac.cls !== 'civil' || ac.emerg || (sel && sel.kind === 'ac' && sel.id === ac.hex));
      if (wantLbl && !e.l) {
        e.l = acLbl.add({ position: pos, text: ac.cs || ac.hex, font: '13px "Share Tech Mono",monospace', fillColor: acColor(ac), outlineColor: C.Color.BLACK,
          outlineWidth: 3, style: C.LabelStyle.FILL_AND_OUTLINE, pixelOffset: new C.Cartesian2(14, -10), horizontalOrigin: C.HorizontalOrigin.LEFT,
          distanceDisplayCondition: DDC_LBL(), id: { kind: 'ac', id: ac.hex } });
      } else if (e.l) {
        if (!wantLbl) { acLbl.remove(e.l); e.l = null; } else { e.l.position = pos; e.l.text = ac.cs || ac.hex; }
      }
    }
    for (const [hex, e] of acMap) if (!seen.has(hex)) { acBB.remove(e.b); if (e.l) acLbl.remove(e.l); acMap.delete(hex); }
    acBB.show = acLbl.show = state.layers.adsb !== false;
    refreshPulses();
  }
  function deadReckon() {
    if (!ready || !acMap.size || state.layers.adsb === false) return;
    const now = Date.now(), p = scratch.p2 || (scratch.p2 = new C.Cartesian3());
    for (const e of acMap.values()) {
      const ac = e.ac; if (!ac.gs || ac.gs < 40 || !ac.t) continue;
      const dt = clamp((now - ac.t) / 1000, 0, 75);
      const d = ac.gs * 0.514444 * dt, tr = rad(ac.trk || 0);
      const la = ac.lat + (d * Math.cos(tr)) / 111320, lo = ac.lon + (d * Math.sin(tr)) / (111320 * Math.max(0.05, Math.cos(rad(ac.lat))));
      const alt = (ac.altM || 0) + (ac.vr ? clamp(ac.vr * 0.00508 * dt, -3000, 3000) : 0);
      ac.plat = la; ac.plon = lo;
      cart(la, lo, Math.max(0, alt), p); e.b.position = p; C.Cartesian3.clone(p, e.cart);
      if (e.l) e.l.position = p;
    }
    if (sel?.kind === 'ac') updateSelExtras();
    scene.requestRender();
  }

  /* ── SATELLITI ── */
  const NFS_SAT = () => scratch.nfsSat || (scratch.nfsSat = new C.NearFarScalar(5e5, 1.6, 5e7, 0.7));
  function setSats(list) {
    // list: [{id, name, group, col, x,y,z (km ECEF), special}]
    const seen = new Set();
    for (const s of list) {
      seen.add(s.id);
      let e = satMap.get(s.id);
      const pos = scratch.sp || (scratch.sp = new C.Cartesian3());
      pos.x = s.x * 1000; pos.y = s.y * 1000; pos.z = s.z * 1000;
      if (!e) {
        e = { cart: C.Cartesian3.clone(pos) };
        if (s.special) {
          e.b = satBB.add({ position: pos, image: sprite('sat'), color: col(s.col), scale: 0.62, scaleByDistance: NFS_SAT(), id: { kind: 'sat', id: s.id } });
          e.l = satLbl.add({ position: pos, text: s.name, font: '12px "Share Tech Mono",monospace', fillColor: col(s.col), outlineColor: C.Color.BLACK, outlineWidth: 3,
            style: C.LabelStyle.FILL_AND_OUTLINE, pixelOffset: new C.Cartesian2(16, -8), horizontalOrigin: C.HorizontalOrigin.LEFT, distanceDisplayCondition: new C.DistanceDisplayCondition(0, 3.5e7), id: { kind: 'sat', id: s.id } });
        } else {
          e.p = satPts.add({ position: pos, pixelSize: 4, color: col(s.col), outlineColor: col('#000', 0.8), outlineWidth: 1, scaleByDistance: NFS_SAT(), id: { kind: 'sat', id: s.id } });
        }
        satMap.set(s.id, e);
      } else {
        if (e.b) e.b.position = pos; if (e.p) e.p.position = pos; if (e.l) e.l.position = pos;
        C.Cartesian3.clone(pos, e.cart);
        const vis = s.show !== false; if (e.p) e.p.show = vis; if (e.b) e.b.show = vis; if (e.l) e.l.show = vis;
      }
    }
    for (const [id, e] of satMap) if (!seen.has(id)) { if (e.p) satPts.remove(e.p); if (e.b) satBB.remove(e.b); if (e.l) satLbl.remove(e.l); satMap.delete(id); }
    satPts.show = satBB.show = satLbl.show = state.layers.sats !== false;
    if (sel?.kind === 'sat') updateSelExtras();
    scene.requestRender();
  }

  /* ── TERREMOTI ── */
  function quakeColor(f) {
    const age = (Date.now() - f.time) / 3600e3;
    if (f.mag >= 6) return '#ff1744';
    if (age < 1) return '#ffffff';
    if (age < 6) return '#ffd54f';
    return f.mag >= 5 ? '#ff6d00' : f.mag >= 4 ? '#ff9100' : '#ffb74d';
  }
  function setQuakes(list) {
    const E = ds.quakes.entities; E.suspendEvents(); E.removeAll();
    for (const q of list) {
      const c = col(quakeColor(q));
      const H = q.mag >= 3.5 ? 15000 * Math.pow(2, q.mag - 3) : 0;
      E.add({
        id: 'eq:' + q.id, position: cart(q.lat, q.lon, H),
        point: { pixelSize: clamp(4 + q.mag * 1.9, 4, 22), color: c.withAlpha(0.92), outlineColor: col('#000', 0.8), outlineWidth: 1.2 },
        polyline: H ? { positions: [cart(q.lat, q.lon, 0), cart(q.lat, q.lon, H)], width: q.mag >= 6 ? 10 : 6, arcType: C.ArcType.NONE,
          material: new C.PolylineGlowMaterialProperty({ glowPower: 0.28, taperPower: 1, color: c.withAlpha(0.9) }) } : undefined,
        label: q.mag >= 4.8 ? { text: 'M' + q.mag.toFixed(1), font: 'bold 13px "Share Tech Mono",monospace', fillColor: c, outlineColor: C.Color.BLACK, outlineWidth: 3,
          style: C.LabelStyle.FILL_AND_OUTLINE, verticalOrigin: C.VerticalOrigin.BOTTOM, pixelOffset: new C.Cartesian2(0, -12), distanceDisplayCondition: new C.DistanceDisplayCondition(0, 1.2e7) } : undefined
      });
    }
    E.resumeEvents();
    ds.quakes.show = state.layers.quakes !== false;
    scratch.quakes = list; refreshPulses();
  }
  function refreshPulses() {
    if (!pulsePts) return;
    pulsePts.removeAll();
    if (state.layers.quakes !== false) (scratch.quakes || []).filter(q => q.mag >= 6 || (q.mag >= 4.5 && Date.now() - q.time < 3 * 3600e3)).slice(0, 25).forEach((q, i) => {
      const p = pulsePts.add({ position: cart(q.lat, q.lon, 0), pixelSize: 10, color: col('#ff3355', 0.6) });
      p._base = 8; p._grow = 30 + q.mag * 4; p._col = col(q.mag >= 6 ? '#ff1744' : '#ffab40'); p._ph = i * 0.37;
    });
    if (state.layers.adsb !== false) for (const e of acMap.values()) if (e.ac.emerg) {
      const p = pulsePts.add({ position: e.cart, pixelSize: 10, color: col('#ff2244', 0.6) });
      p._base = 10; p._grow = 34; p._col = col('#ff2244'); p._ph = Math.random() * 2;
    }
  }

  /* ── PUNTI STATICI / ZONE / NOTIZIE / EONET ── */
  const ICON = { bases: ['🏴', '#ff5500'], nuclear: ['☢', '#c040ff'], choke: ['⚓', '#00ccff'] };
  function setPoints(key, list) {
    const d = ds[key]; if (!d) return;
    const E = d.entities; E.suspendEvents(); E.removeAll();
    list.forEach((p, i) => {
      const [ic, ring] = ICON[key] || ['•', '#00ff41'];
      const r = p.risk === 'CRIT' ? '#ff2244' : p.risk === 'HIGH' ? '#ff8c00' : ring;
      E.add({ id: `${key}:${i}`, position: cart(p.lat, p.lon, 0),
        billboard: { image: emojiSprite(ic, r), scale: 0.62, heightReference: C.HeightReference.CLAMP_TO_GROUND, verticalOrigin: C.VerticalOrigin.CENTER,
          scaleByDistance: new C.NearFarScalar(2e5, 1.1, 2e7, 0.45), disableDepthTestDistance: 3e6 },
        label: { text: p.name, font: '12px "Share Tech Mono",monospace', fillColor: col(r), outlineColor: C.Color.BLACK, outlineWidth: 3, style: C.LabelStyle.FILL_AND_OUTLINE,
          pixelOffset: new C.Cartesian2(0, -20), verticalOrigin: C.VerticalOrigin.BOTTOM, heightReference: C.HeightReference.CLAMP_TO_GROUND,
          distanceDisplayCondition: new C.DistanceDisplayCondition(0, 3.2e6), disableDepthTestDistance: 3e6 } });
    });
    E.resumeEvents(); d.show = state.layers[key] !== false;
  }
  function circle(lat, lon, km, n = 72) { const out = []; for (let i = 0; i <= n; i++) { const [a, o] = Geo.dest(lat, lon, i * 360 / n, km); out.push(o, a); } return C.Cartesian3.fromDegreesArray(out); }
  function setZones(key, list) {
    const d = ds[key]; if (!d) return;
    const E = d.entities; E.suspendEvents(); E.removeAll();
    const c = key === 'gps' ? '#00ffcc' : '#ff2244';
    list.forEach((z, i) => {
      E.add({ id: `${key}:${i}`, position: cart(z.lat, z.lon, 0),
        ellipse: { semiMajorAxis: z.r * 1000, semiMinorAxis: z.r * 1000, material: col(c, key === 'gps' ? 0.08 : 0.12) },
        label: { text: (key === 'gps' ? '📡 ' : '⚔ ') + z.name, font: '12px "Share Tech Mono",monospace', fillColor: col(c), outlineColor: C.Color.BLACK, outlineWidth: 3,
          style: C.LabelStyle.FILL_AND_OUTLINE, heightReference: C.HeightReference.CLAMP_TO_GROUND, distanceDisplayCondition: new C.DistanceDisplayCondition(1e5, 9e6), disableDepthTestDistance: 3e6 } });
      E.add({ id: `${key}:${i}:o`, polyline: { positions: circle(z.lat, z.lon, z.r), width: 2, clampToGround: true, material: new C.PolylineDashMaterialProperty({ color: col(c, 0.75), dashLength: 18 }) } });
    });
    E.resumeEvents(); d.show = state.layers[key] !== false;
  }
  function setNews(list) {
    const E = ds.news.entities; E.suspendEvents(); E.removeAll();
    list.forEach(n => {
      const c = n.sev >= 0.7 ? '#ff2244' : n.sev >= 0.45 ? '#ff8c00' : '#00ccff';
      E.add({ id: 'news:' + n.id, position: cart(n.place.lat + n.jlat, n.place.lon + n.jlon, 0),
        billboard: { image: emojiSprite(n.sev >= 0.7 ? '💥' : n.sev >= 0.45 ? '⚠' : '📰', c, 40), scale: 0.6, heightReference: C.HeightReference.CLAMP_TO_GROUND,
          scaleByDistance: new C.NearFarScalar(2e5, 1.1, 2e7, 0.5), disableDepthTestDistance: 3e6 } });
    });
    E.resumeEvents(); ds.news.show = state.layers.news !== false;
  }
  function setEonet(list) {
    const E = ds.eonet.entities; E.suspendEvents(); E.removeAll();
    list.forEach(ev => {
      const [ic, name] = DATA.EONET[ev.cat] || ['⚠', ev.cat];
      E.add({ id: 'eonet:' + ev.id, position: cart(ev.lat, ev.lon, 0),
        billboard: { image: emojiSprite(ic, ev.cat === 'wildfires' ? '#ff5500' : ev.cat === 'volcanoes' ? '#ff2244' : '#00ccff', 40), scale: 0.6,
          heightReference: C.HeightReference.CLAMP_TO_GROUND, scaleByDistance: new C.NearFarScalar(2e5, 1.1, 2e7, 0.45), disableDepthTestDistance: 3e6 },
        label: { text: ev.title.slice(0, 40), font: '11px "Share Tech Mono",monospace', fillColor: col('#ffcc80'), outlineColor: C.Color.BLACK, outlineWidth: 3, style: C.LabelStyle.FILL_AND_OUTLINE,
          pixelOffset: new C.Cartesian2(0, -18), verticalOrigin: C.VerticalOrigin.BOTTOM, heightReference: C.HeightReference.CLAMP_TO_GROUND,
          distanceDisplayCondition: new C.DistanceDisplayCondition(0, 1.8e6), disableDepthTestDistance: 3e6 } });
      void name;
    });
    E.resumeEvents(); ds.eonet.show = state.layers.eonet !== false;
  }
  function setFires(list) {
    firePts.removeAll();
    const nfs = new C.NearFarScalar(2e5, 1.5, 2e7, 0.6);
    for (const f of list) firePts.add({ position: cart(f.lat, f.lon, 0), pixelSize: clamp(2.5 + Math.log2(1 + (f.frp || 1)), 3, 9),
      color: col(f.frp > 100 ? '#ff1a1a' : f.frp > 20 ? '#ff6a00' : '#ffc400', 0.85), scaleByDistance: nfs, id: { kind: 'fire', id: f.id } });
    firePts.show = state.layers.fires !== false;
  }
  function setAurora(grid) {
    auroraPts.removeAll();
    const nfs = new C.NearFarScalar(1e6, 2.2, 3e7, 1.0);
    for (const [lon, lat, v] of grid) {
      if (v < 8) continue;
      const a = clamp(v / 140, 0.05, 0.5), c = v > 60 ? '#ff4fd8' : v > 30 ? '#7dffb0' : '#00ff88';
      auroraPts.add({ position: cart(lat, lon > 180 ? lon - 360 : lon, 110000), pixelSize: 7, color: col(c, a), scaleByDistance: nfs });
    }
    auroraPts.show = state.layers.aurora !== false;
  }
  function setRadar(urlTemplate) {
    if (imagery.radar) { const old = imagery.radar; setTimeout(() => viewer.imageryLayers.remove(old, true), 2500); imagery.radar = null; }
    if (!urlTemplate) return;
    const l = viewer.imageryLayers.addImageryProvider(new C.UrlTemplateImageryProvider({ url: urlTemplate, maximumLevel: 7, credit: new C.Credit('Radar © RainViewer', false) }));
    l.alpha = 0.7; l.show = state.layers.radar !== false; imagery.radar = l;
  }
  function setTrace(t) {
    const E = ds.trace.entities; E.removeAll();
    if (!t) return;
    const path = Geo.gcPath(t.from.lat, t.from.lon, t.to.lat, t.to.lon, 96);
    const dkm = Geo.dist(t.from.lat, t.from.lon, t.to.lat, t.to.lon), hMax = Math.min(1.6e6, dkm * 250);
    const pos = path.map(([a, o], i) => cart(a, o, Math.sin(Math.PI * i / (path.length - 1)) * hMax));
    E.add({ id: 'trace:arc', polyline: { positions: pos, width: 8, arcType: C.ArcType.NONE, material: new C.PolylineGlowMaterialProperty({ glowPower: 0.22, color: col('#00ffcc') }) } });
    [[t.from, 'TU'], [t.to, t.to.label || 'TARGET']].forEach(([p, lbl], i) => E.add({ id: 'trace:' + i, position: cart(p.lat, p.lon, 0),
      point: { pixelSize: 11, color: col(i ? '#ff2244' : '#00ffcc'), outlineColor: C.Color.BLACK, outlineWidth: 2, heightReference: C.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: 3e6 },
      label: { text: lbl, font: '12px "Share Tech Mono",monospace', fillColor: col(i ? '#ff6680' : '#00ffcc'), outlineColor: C.Color.BLACK, outlineWidth: 3, style: C.LabelStyle.FILL_AND_OUTLINE,
        pixelOffset: new C.Cartesian2(0, -16), heightReference: C.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: 3e6 } }));
  }

  /* ── selezione: scia, stelo, orbita, impronta ── */
  function updateSelExtras() {
    if (!sel) return;
    if (sel.kind === 'ac') {
      const e = acMap.get(sel.id); if (!e) return;
      const g = C.Cartographic.fromCartesian(e.cart);
      scratch.selStalk = [C.Cartesian3.fromRadians(g.longitude, g.latitude, 0), C.Cartesian3.clone(e.cart)];
      const hist = (e.ac.hist || []).map(p => cart(p[0], p[1], p[2]));
      hist.push(C.Cartesian3.clone(e.cart)); scratch.selTrail = hist;
    } else if (sel.kind === 'sat') {
      const e = satMap.get(sel.id); if (!e) return;
      const g = C.Cartographic.fromCartesian(e.cart);
      scratch.selStalk = [C.Cartesian3.fromRadians(g.longitude, g.latitude, 0), C.Cartesian3.clone(e.cart)];
      scratch.selFoot = { pos: C.Cartesian3.fromRadians(g.longitude, g.latitude, 0), r: 6371000 * Math.acos(6371000 / (6371000 + Math.max(1, g.height))) };
    }
  }
  function select(ref, extra = {}) {
    sel = ref;
    ds.sel.entities.removeAll(); selPts.removeAll();
    scratch.selTrail = null; scratch.selStalk = null; scratch.selFoot = null;
    if (!ref || !ready) return;
    const p = refPos(ref);
    selPts.add({ position: p || C.Cartesian3.ZERO, image: sprite('ring'), color: col('#ffee33'), scale: 0.8, scaleByDistance: new C.NearFarScalar(1e5, 1.2, 2e7, 0.6), id: { kind: 'sel' } });
    if (!p) selPts.get(0).show = false;
    if (ref.kind === 'ac') {
      const e = acMap.get(ref.id);
      if (e && !e.l) setAircraft(lastAcData);   // garantisce l'etichetta
      updateSelExtras();
      ds.sel.entities.add({ id: 'sel:stalk', polyline: { positions: new C.CallbackProperty(() => scratch.selStalk || [], false), width: 1.5, arcType: C.ArcType.NONE, material: new C.PolylineDashMaterialProperty({ color: col('#ffee33', 0.8), dashLength: 10 }) } });
      ds.sel.entities.add({ id: 'sel:trail', polyline: { positions: new C.CallbackProperty(() => scratch.selTrail || [], false), width: 4, arcType: C.ArcType.NONE, material: new C.PolylineGlowMaterialProperty({ glowPower: 0.2, color: col('#ffee33', 0.9) }) } });
    } else if (ref.kind === 'sat' && extra.orbit) {
      updateSelExtras();
      ds.sel.entities.add({ id: 'sel:orbit', polyline: { positions: extra.orbit.map(o => new C.Cartesian3(o[0] * 1000, o[1] * 1000, o[2] * 1000)), width: 3, arcType: C.ArcType.NONE, material: new C.PolylineGlowMaterialProperty({ glowPower: 0.18, color: col('#ffee33', 0.85) }) } });
      if (extra.ground) ds.sel.entities.add({ id: 'sel:ground', polyline: { positions: C.Cartesian3.fromDegreesArray(extra.ground.flatMap(g => [g[1], g[0]])), width: 1.5, arcType: C.ArcType.GEODESIC, material: new C.PolylineDashMaterialProperty({ color: col('#ffee33', 0.5), dashLength: 14 }) } });
      ds.sel.entities.add({ id: 'sel:stalk', polyline: { positions: new C.CallbackProperty(() => scratch.selStalk || [], false), width: 1.5, arcType: C.ArcType.NONE, material: new C.PolylineDashMaterialProperty({ color: col('#ffee33', 0.7), dashLength: 12 }) } });
      ds.sel.entities.add({ id: 'sel:foot', position: new C.CallbackPositionProperty(() => scratch.selFoot?.pos, false),
        ellipse: { semiMajorAxis: new C.CallbackProperty(() => scratch.selFoot?.r || 1, false), semiMinorAxis: new C.CallbackProperty(() => scratch.selFoot?.r || 1, false), material: col('#ffee33', 0.07), height: 0 } });
    }
  }

  /* ── camera ── */
  function flyTo(lat, lon, range = 1.5e6, { pitch = -90, heading = 0, duration = 2.2 } = {}) {
    if (!ready) return;
    stopFollow();
    if (pitch <= -85) camera.flyTo({ destination: cart(lat, lon, range), orientation: { heading: rad(heading), pitch: rad(-90), roll: 0 }, duration });
    else camera.flyToBoundingSphere(new C.BoundingSphere(cart(lat, lon, 0), 10), { offset: new C.HeadingPitchRange(rad(heading), rad(pitch), range), duration });
  }
  function getView() {
    if (!ready || scene.mode === C.SceneMode.MORPHING) return null;
    const cg = camera.positionCartographic;
    const cw = scene.canvas.clientWidth, ch = scene.canvas.clientHeight;
    const center = globePick(new C.Cartesian2(cw / 2, ch / 2));
    const lat = center ? center.lat : C.Math.toDegrees(cg.latitude), lon = center ? center.lon : C.Math.toDegrees(cg.longitude);
    return { lat, lon, alt: cg.height, heading: C.Math.toDegrees(camera.heading), pitch: C.Math.toDegrees(camera.pitch), centerOnGlobe: !!center };
  }
  function setScene(m) {
    if (!ready) return;
    state.scene = m; stopFollow();
    if (m === '2d') scene.morphTo2D(1.2); else if (m === 'cv') scene.morphToColumbusView(1.2); else scene.morphTo3D(1.2);
  }
  function stopFollow() {
    if (follow || cockpit) { follow = null; cockpit = null; followInit = false; camera.lookAtTransform(C.Matrix4.IDENTITY); scene.screenSpaceCameraController.enableInputs = true; Bus.emit('follow', null); }
  }
  function setFollow(ref) {
    if (!ready) return;
    if (!ref) return stopFollow();
    if (scene.mode !== C.SceneMode.SCENE3D) { scene.morphTo3D(0); }
    cockpit = null; follow = ref; followInit = false; scene.screenSpaceCameraController.enableInputs = true;
    Bus.emit('follow', ref);
  }
  function setCockpit(ref) {
    if (!ready) return;
    if (!ref) return stopFollow();
    if (scene.mode !== C.SceneMode.SCENE3D) scene.morphTo3D(0);
    camera.lookAtTransform(C.Matrix4.IDENTITY);
    follow = null; cockpit = ref; scene.screenSpaceCameraController.enableInputs = false;
    Bus.emit('follow', Object.assign({ cockpit: true }, ref));
  }

  function setLayer(key, on) {
    state.layers[key] = on;
    if (!ready) return;
    setTimeout(() => scene.requestRender(), 30);
    switch (key) {
      case 'adsb': acBB.show = acLbl.show = on; refreshPulses(); break;
      case 'sats': satPts.show = satBB.show = satLbl.show = on; break;
      case 'fires': firePts.show = on; break;
      case 'aurora': auroraPts.show = on; break;
      case 'quakes': ds.quakes.show = on; refreshPulses(); break;
      case 'radar': if (imagery.radar) imagery.radar.show = on; break;
      case 'night': case 'labels': if (imagery[key]) imagery[key].show = on; break;
      case 'terrain': setTerrain(on); break;
      case 'lighting': scene.globe.enableLighting = on; break;
      case 'osm3d': setTileset('osm', on); break;
      case 'photo3d': setTileset('photo', on); break;
      default: if (ds[key]) ds[key].show = on;
    }
  }
  function render(kind, data) {
    if (!ready) return;
    try {
      switch (kind) {
        case 'aircraft': return setAircraft(data);
        case 'sats': return setSats(data);
        case 'quakes': return setQuakes(data);
        case 'news': return setNews(data);
        case 'eonet': return setEonet(data);
        case 'fires': return setFires(data);
        case 'aurora': return setAurora(data);
        case 'radar': return setRadar(data);
        case 'trace': return setTrace(data);
        default:
          if (kind.startsWith('points:')) return setPoints(kind.slice(7), data);
          if (kind.startsWith('zones:')) return setZones(kind.slice(6), data);
      }
    } catch (e) { console.warn('[3d render]', kind, e); }
    finally { scene.requestRender(); }
  }

  return {
    kind: '3d', get ready() { return ready; }, get viewer() { return viewer; }, get C() { return C; },
    bases: () => Object.entries(BASES).map(([k, b]) => ({ key: k, name: b.name, ion: !!b.ion })),
    init, render, setLayer, flyTo, getView, setScene, setBase, setVisual,
    setExag(v) { state.exag = v; if (ready) { scene.verticalExaggeration = v; scene.requestRender(); } Settings.set('exag', v); },
    setSpin(on) { state.spin = on; },
    get spin() { return state.spin; },
    select, setFollow, setCockpit, stopFollow,
    get following() { return cockpit ? Object.assign({ cockpit: true }, cockpit) : follow; },
    home() { if (!ready) return; stopFollow(); if (scene.mode !== C.SceneMode.SCENE3D) scene.morphTo3D(1); const v = getView(); camera.flyTo({ destination: cart(v ? v.lat * 0.5 : 25, v ? v.lon : 15, 2.1e7), duration: 2 }); },
    terrainHeight(lat, lon) { try { return scene.globe.getHeight(C.Cartographic.fromDegrees(lon, lat)); } catch { return null; } },
    async sampleHeight(lat, lon) {
      if (!ready) return null;
      try {
        if (viewer.terrainProvider instanceof C.EllipsoidTerrainProvider) return null;
        const [r] = await C.sampleTerrainMostDetailed(viewer.terrainProvider, [C.Cartographic.fromDegrees(lon, lat)]);
        return r && isFinite(r.height) ? r.height : null;
      } catch { return this.terrainHeight(lat, lon); }
    }
  };
})();
