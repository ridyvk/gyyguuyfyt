const KPI_SCOPE_SW_VERSION = '20260619-photo1'

self.addEventListener('install', () => self.skipWaiting())

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.map((key) => caches.delete(key)))).then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', (event) => {
  if (event.request.method === 'GET') {
    event.respondWith(fetch(event.request))
  }
})
