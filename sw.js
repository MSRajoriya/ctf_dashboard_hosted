// Minimal offline support: try the network first (so you always get the
// freshest 15-min snapshot when online), fall back to the cached copy only
// when there's no connection at all. Cache is updated on every successful
// fetch, so it never gets more than one visit stale.
const CACHE_NAME = "ctf-dashboard-v1";
const CORE_ASSETS = ["./", "./index.html", "./manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  // Only handle same-origin GET requests — let CDN/API calls pass through untouched.
  if (event.request.method !== "GET" || new URL(event.request.url).origin !== location.origin) {
    return;
  }
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
