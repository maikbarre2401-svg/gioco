// Offline support: the whole app (fonts included) is cached on install.
const VERSION = 'ghostlink-v3';
const SHELL = [
  './',
  'index.html',
  'manifest.webmanifest',
  'css/fonts.css',
  'css/style.css',
  'vendor/leaflet/leaflet.js',
  'vendor/leaflet/leaflet.css',
  'js/app.js',
  'js/ui.js',
  'js/prefs.js',
  'js/sfx.js',
  'js/hacker.js',
  'js/intro.js',
  'js/device.js',
  'js/scan.js',
  'js/cipher.js',
  'js/password.js',
  'js/sensors.js',
  'js/audio.js',
  'js/torch.js',
  'js/map.js',
  'js/profiler.js',
  'js/speed.js',
  'js/terminal.js',
  'js/settings.js',
  'fonts/ChakraPetch-400-latin-ext.woff2',
  'fonts/ChakraPetch-400-latin.woff2',
  'fonts/ChakraPetch-600-latin-ext.woff2',
  'fonts/ChakraPetch-600-latin.woff2',
  'fonts/ChakraPetch-700-latin-ext.woff2',
  'fonts/ChakraPetch-700-latin.woff2',
  'fonts/JetBrainsMono-latin-ext.woff2',
  'fonts/JetBrainsMono-latin.woff2',
  'icons/icon.svg',
  'icons/icon-192.png',
  'icons/icon-512.png',
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);

  // Own files: network first so updates arrive, cache as fallback when offline.
  if (url.origin === self.location.origin) {
    event.respondWith(
      fetch(request).then(res => {
        if (res.ok) { const copy = res.clone(); caches.open(VERSION).then(c => c.put(request, copy)); }
        return res;
      }).catch(() => caches.match(request, { ignoreSearch: true }).then(hit => hit || caches.match('index.html'))),
    );
  }
  // Map tiles: cache first so a visited area stays visible offline.
  if (url.hostname.endsWith('basemaps.cartocdn.com')) {
    event.respondWith(
      caches.match(request).then(hit => hit || fetch(request).then(res => {
        if (res.ok) { const copy = res.clone(); caches.open(VERSION).then(c => c.put(request, copy)); }
        return res;
      }).catch(() => hit)),
    );
    return;
  }
  // Everything else (IP lookup, Overpass, Cloudflare speed test) goes to the network.
});
