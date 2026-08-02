const CACHE_PREFIX = 'kpi-scope'

self.addEventListener('install', () => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const cacheKeys = await caches.keys()
      await Promise.all(
        cacheKeys
          .filter((key) => key.startsWith(CACHE_PREFIX))
          .map((key) => caches.delete(key)),
      )

      await self.clients.claim()
      const windows = await self.clients.matchAll({ type: 'window' })
      await self.registration.unregister()
      await Promise.all(
        windows.map((client) => client.navigate(client.url).catch(() => undefined)),
      )
    })(),
  )
})

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return
  event.respondWith(fetch(event.request, { cache: 'no-store' }))
})
