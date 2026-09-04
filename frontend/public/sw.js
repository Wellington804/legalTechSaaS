/* Public offline shell only. Legal records, authenticated HTML and RSC are never cached. */
const CACHE_NAME = "legalflow-public-v1";
const PUBLIC_FILES = ["/offline.html", "/icons/icon-192.png", "/icons/icon-512.png", "/icons/apple-touch-icon.png"];

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await Promise.all(PUBLIC_FILES.map(async (path) => {
      const response = await fetch(path, { cache: "no-store", credentials: "omit", redirect: "error" });
      if (!response.ok || response.type === "opaque" || response.redirected) throw new Error("Public PWA asset unavailable");
      await cache.put(path, response);
    }));
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter(name => name !== CACHE_NAME && (name.startsWith("legalflow-") || name.startsWith("legaltech"))).map(name => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "ACTIVATE_UPDATE" && event.source?.url && new URL(event.source.url).origin === self.location.origin) {
    event.waitUntil(self.skipWaiting());
  }
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin || request.headers.has("RSC")) return;
  // Never substitute HTML for an API, document, RSC, script, or image request.
  if (request.mode === "navigate" && !url.pathname.startsWith("/api/")) {
    event.respondWith(fetch(request, { cache: "no-store" }).catch(async () => {
      const cache = await caches.open(CACHE_NAME);
      return await cache.match("/offline.html") || new Response("Sem conexão. Reconecte para acessar o LexFlow.", {
        status: 503, headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" },
      });
    }));
  } else if (!url.search && PUBLIC_FILES.includes(url.pathname) && !request.headers.has("RSC")) {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_NAME);
      return await cache.match(url.pathname) || fetch(request, { cache: "no-store" });
    })());
  }
});

self.addEventListener("push", (event) => {
  let payload = {};
  try { payload = event.data?.json() || {}; } catch { /* A malformed payload cannot introduce personal text. */ }
  const tag = typeof payload.tag === "string" && /^[a-zA-Z0-9_-]{1,80}$/.test(payload.tag) ? payload.tag : "legalflow-update";
  event.waitUntil(self.registration.showNotification("LexFlow", {
    body: "Há uma atualização no seu escritório. Entre no LexFlow para consultar.",
    icon: "/icons/icon-192.png",
    badge: "/icons/icon-192.png",
    tag,
    data: { url: "/dashboard" },
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil((async () => {
    // Fixed destination: no payload URL, tokens or customer/case identifiers.
    const target = new URL("/dashboard", self.location.origin).href;
    const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    const existing = windows.find(client => client.url === target);
    if (existing) return existing.focus();
    return self.clients.openWindow(target);
  })());
});
