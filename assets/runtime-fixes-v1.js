(() => {
  const foldSearchText = (value) =>
    String(value).normalize('NFKC').toLowerCase().replace(/\s+/g, ' ').trim()

  const nativeIncludes = String.prototype.includes

  if (!String.prototype.__kpiScopeFoldedIncludes) {
    Object.defineProperty(String.prototype, '__kpiScopeFoldedIncludes', {
      value: true,
      configurable: false,
      enumerable: false,
    })

    Object.defineProperty(String.prototype, 'includes', {
      value(search, position) {
        const directMatch = nativeIncludes.call(this, search, position)
        if (directMatch || typeof search !== 'string') return directMatch

        const source = foldSearchText(this)
        const needle = foldSearchText(search)
        if (!needle) return true

        return nativeIncludes.call(source, needle)
      },
      configurable: true,
      writable: true,
    })
  }

  const nativeFetch = window.fetch.bind(window)

  window.fetch = async (input, init) => {
    const response = await nativeFetch(input, init)

    try {
      const requestUrl = typeof input === 'string' ? input : input?.url
      const url = new URL(requestUrl, window.location.href)

      if (url.pathname.endsWith('/data/update-status.json')) {
        const data = await response.clone().json()
        const headers = new Headers(response.headers)
        headers.set('content-type', 'application/json; charset=utf-8')

        return new Response(
          JSON.stringify({
            ...data,
            status: 'error',
            message:
              'financials.json must load before financial data is treated as ready.',
          }),
          {
            status: response.status,
            statusText: response.statusText,
            headers,
          },
        )
      }
    } catch {
      // Keep the original response if this compatibility shim cannot inspect it.
    }

    return response
  }
})()
