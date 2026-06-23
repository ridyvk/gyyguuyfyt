const CACHE_NAME = 'kpi-scope-v6-network-first-recovery'
const STATIC_ASSETS = [
  './manifest.webmanifest',
  './icon-180-photo1.png',
  './icon-192-photo1.png',
  './icon-512-photo1.png',
  './icon-maskable-192-photo1.png',
  './icon-maskable-512-photo1.png',
]
const APP_ASSET_EXTENSIONS = ['.html', '.js', '.css', '.json']

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)))
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  )
})

const isSameOrigin = (url) => url.origin === self.location.origin
const isDataRequest = (url) => isSameOrigin(url) && url.pathname.includes('/data/')
const isAppAsset = (url) =>
  isSameOrigin(url) && APP_ASSET_EXTENSIONS.some((extension) => url.pathname.endsWith(extension))

const cacheSuccessfulResponse = async (request, response) => {
  if (!response || !response.ok || !isSameOrigin(new URL(request.url))) return response
  const cache = await caches.open(CACHE_NAME)
  await cache.put(request, response.clone())
  return response
}

const networkFirst = async (request, options = {}) => {
  const cached = await caches.match(request)
  try {
    const response = await fetch(request, options)
    return cacheSuccessfulResponse(request, response)
  } catch (error) {
    if (cached) return cached
    throw error
  }
}

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return

  const requestUrl = new URL(event.request.url)

  if (isDataRequest(requestUrl)) {
    event.respondWith(fetch(event.request, { cache: 'no-store' }))
    return
  }

  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request, { cache: 'no-store' }).catch(
        () =>
          new Response(
            '<!doctype html><meta charset="utf-8"><title>KPI Scope</title><p>KPI Scopeを再読み込みしてください。</p>',
            { headers: { 'Content-Type': 'text/html; charset=utf-8' } },
          ),
      ),
    )
    return
  }

  if (isAppAsset(requestUrl)) {
    event.respondWith(networkFirst(event.request, { cache: 'reload' }))
    return
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached
      return fetch(event.request).then((response) => cacheSuccessfulResponse(event.request, response))
    }),
  )
})