// Minimal hand-rolled service worker (no build-step precache manifest, so it
// stays correct across Vite rebuilds without needing regeneration).
// Strategy:
// - /api/* : always network — never serve stale market/risk data offline.
// - navigations (SPA routes) : network-first, fall back to the cached shell
//   so a repeat visit still opens the app when offline.
// - everything else (hashed JS/CSS/images) : cache-first, populated the
//   first time it's fetched online, so subsequent offline loads still work.
const SHELL_CACHE = 'finlab-shell-v1';
const RUNTIME_CACHE = 'finlab-runtime-v1';
const SHELL_URLS = ['/', '/index.html', '/manifest.webmanifest', '/favicon.ico'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_URLS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key !== SHELL_CACHE && key !== RUNTIME_CACHE).map((key) => caches.delete(key))
    ))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => caches.match('/index.html'))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(RUNTIME_CACHE).then((cache) => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => cached);
    })
  );
});
