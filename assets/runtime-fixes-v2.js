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
  const financialsFallbackUrl =
    'https://raw.githubusercontent.com/ridyvk/gyyguuyfyt/main/data/financials.json'

  const sanitizeJsonText = (text) =>
    text
      .replace(/^\uFEFF/, '')
      .replace(/([:\[,]\s*)-?Infinity(?=\s*[,}\]])/g, '$1null')
      .replace(/([:\[,]\s*)NaN(?=\s*[,}\]])/g, '$1null')

  const jsonResponse = (text, response) => {
    const sanitized = sanitizeJsonText(text)
    JSON.parse(sanitized)

    const headers = new Headers(response.headers)
    headers.set('content-type', 'application/json; charset=utf-8')

    return new Response(sanitized, {
      status: response.ok ? response.status : 200,
      statusText: response.ok ? response.statusText : 'OK',
      headers,
    })
  }

  window.fetch = async (input, init) => {
    const response = await nativeFetch(input, init)

    try {
      const requestUrl = typeof input === 'string' ? input : input?.url
      if (!requestUrl) return response

      const url = new URL(requestUrl, window.location.href)
      if (!url.pathname.endsWith('/data/financials.json')) return response

      try {
        return jsonResponse(await response.clone().text(), response)
      } catch (primaryError) {
        const fallback = await nativeFetch(`${financialsFallbackUrl}${url.search || ''}`)
        return jsonResponse(await fallback.text(), fallback)
      }
    } catch (error) {
      console.warn('KPI Scope financial data compatibility shim skipped', error)
      return response
    }
  }
})()
