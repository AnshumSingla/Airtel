// Minimal service worker: caches the app shell so the PWA can be installed and opened offline.
// API calls are never cached (they carry session data). Navigations always revalidate with the
// server first, so an upgrade is picked up on the next load instead of serving an old copy.
const SHELL = "udyam-shell-v2";
self.addEventListener("install", (e) => { self.skipWaiting(); e.waitUntil(caches.open(SHELL).then((c) => c.addAll(["/manifest.webmanifest", "/icon.svg"]))); });
self.addEventListener("activate", (e) => e.waitUntil(
  caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== SHELL).map((k) => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/")) return;
  const fresh = e.request.mode === "navigate" ? new Request(e.request, { cache: "no-cache" }) : e.request;
  e.respondWith(fetch(fresh).then((res) => {
    if (res.ok && url.pathname === "/") caches.open(SHELL).then((c) => c.put("/", res.clone()));
    return res;
  }).catch(() => caches.match(e.request).then((r) => r || caches.match("/"))));
});
