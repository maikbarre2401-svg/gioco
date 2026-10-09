// Offline support: app shell is cached on install, Google Fonts are cached the first time they load.
const VERSION = 'ghostlink-v1';
const SHELL = [
  './',
  'index.html',
  'manifest.webmanifest',
  'css/style.css',
  'js/app.js',
  'js/ui.js',
  'js/device.js',
  'js/scan.js',
  'js/cipher.js',
  'js/password.js',
  'js/sensors.js',
  'js/audio.js',
  'js/torch.js',
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

  // Fonts: cache first, they never change.
  if (url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com') {
    event.respondWith(
      caches.match(request).then(hit => hit || fetch(request).then(res => {
        const copy = res.clone();
        caches.open(VERSION).then(c => c.put(request, copy));
        return res;
      })),
    );
    return;
  }

  // Own files: network first so updates arrive, cache as fallback when offline.
  if (url.origin === self.location.origin) {
    event.respondWith(
      fetch(request).then(res => {
        if (res.ok) { const copy = res.clone(); caches.open(VERSION).then(c => c.put(request, copy)); }
        return res;
      }).catch(() => caches.match(request, { ignoreSearch: true }).then(hit => hit || caches.match('index.html'))),
    );
  }
  // Everything else (IP lookup APIs) goes straight to the network.
});
