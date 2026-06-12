/**
 * Service Worker для PWA трекера заказов.
 * Cache First — статика, Network First — API.
 */

const CACHE_NAME = "blinds-tracker-v1";

/** Статические ресурсы для предварительного кэширования */
const STATIC_ASSETS = [
  "/static/track.html",
  "/static/manifest.json",
  "/static/icon-192.png",
  "/static/icon-512.png",
];

/** Проверяет, является ли запрос обращением к API заказов */
function isApiRequest(url) {
  return url.pathname.startsWith("/orders/");
}

/** Проверяет, является ли запрос статическим ресурсом PWA */
function isStaticAsset(url) {
  return STATIC_ASSETS.includes(url.pathname);
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;

  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);

  // Только запросы того же origin
  if (url.origin !== self.location.origin) {
    return;
  }

  if (isApiRequest(url)) {
    event.respondWith(networkFirst(request));
    return;
  }

  if (isStaticAsset(url)) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // Навигация на track.html при офлайне
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match("/static/track.html"))
    );
  }
});

/**
 * Network First: сначала сеть, при ошибке — кэш.
 */
async function networkFirst(request) {
  try {
    const response = await fetch(request);
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) {
      return cached;
    }
    return new Response(
      JSON.stringify({ detail: "Нет подключения к сети" }),
      {
        status: 503,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
}

/**
 * Cache First: сначала кэш, при отсутствии — сеть с сохранением в кэш.
 */
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) {
    return cached;
  }

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return (
      (await caches.match("/static/track.html")) ||
      new Response("Офлайн", { status: 503 })
    );
  }
}
