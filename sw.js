/* Hawks Stats 2026 — Service Worker
   CACHE_VERSION is updated automatically by scraper.py on every run.
   Changing it forces iOS to clear the old cache and reload fresh. */

const CACHE_VERSION = 'hawks-20260604';
const CACHE_NAME    = CACHE_VERSION;

// Files to cache for offline use
const STATIC = ['/', '/index.html', '/manifest.json'];

// Install — cache static shell
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME)
      .then(c => c.addAll(STATIC))
      .then(() => self.skipWaiting())   // activate immediately, don't wait
  );
});

// Activate — delete all old caches, take control of all clients
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())  // force all open tabs to use new SW
  );
});

// Fetch strategy:
//   data.json  → always network-first (fresh stats every time)
//   index.html → always network-first (fresh app code every time)
//   everything else → cache-first (fonts, icons, external APIs)
self.addEventListener('fetch', e => {
  const url = e.request.url;
  const isData = url.includes('data.json') || url.includes('news.json') || url.includes('index.html');

  if (isData) {
    e.respondWith(
      fetch(e.request)
        .then(resp => {
          // Update cache with fresh response
          const clone = resp.clone();
          caches.open(CACHE_NAME).then(c => c.put(e.request, clone));
          return resp;
        })
        .catch(() => caches.match(e.request))  // offline fallback
    );
  } else {
    e.respondWith(
      caches.match(e.request)
        .then(cached => cached || fetch(e.request)
          .then(resp => {
            const clone = resp.clone();
            caches.open(CACHE_NAME).then(c => c.put(e.request, clone));
            return resp;
          })
        )
    );
  }
});
