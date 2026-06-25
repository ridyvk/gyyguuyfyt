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

  let lastDetailScrollKey = ''
  let detailScrollFrame = 0

  const scrollToPageTop = () => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
    document.documentElement.scrollTop = 0
    document.body.scrollTop = 0
  }

  const getCompanyDetailKey = () => {
    const hero = document.querySelector('.company-hero')
    const backLink = document.querySelector('.back-link')
    if (!hero || !backLink) return null

    const code = hero.querySelector('.company-hero__meta span')?.textContent?.trim() ?? ''
    const name = hero.querySelector('h1')?.textContent?.trim() ?? ''
    if (!code && !name) return null

    return `${window.location.pathname}${window.location.search}:${code}:${name}`
  }

  const syncCompanyDetailScroll = () => {
    const detailKey = getCompanyDetailKey()
    if (!detailKey) {
      lastDetailScrollKey = ''
      return
    }
    if (detailKey === lastDetailScrollKey) return

    lastDetailScrollKey = detailKey
    scrollToPageTop()
    window.setTimeout(scrollToPageTop, 0)
    window.setTimeout(scrollToPageTop, 80)
  }

  const scheduleCompanyDetailScroll = () => {
    if (detailScrollFrame) window.cancelAnimationFrame(detailScrollFrame)
    detailScrollFrame = window.requestAnimationFrame(() => {
      detailScrollFrame = window.requestAnimationFrame(() => {
        detailScrollFrame = 0
        syncCompanyDetailScroll()
      })
    })
  }

  const patchHistoryMethod = (method) => {
    const nativeMethod = window.history[method]
    window.history[method] = function patchedHistoryMethod(...args) {
      const result = nativeMethod.apply(this, args)
      scheduleCompanyDetailScroll()
      return result
    }
  }

  patchHistoryMethod('pushState')
  patchHistoryMethod('replaceState')
  window.addEventListener('popstate', scheduleCompanyDetailScroll)
  window.addEventListener('hashchange', scheduleCompanyDetailScroll)
  window.addEventListener('load', scheduleCompanyDetailScroll)

  const root = document.getElementById('root') ?? document.documentElement
  new MutationObserver(scheduleCompanyDetailScroll).observe(root, {
    childList: true,
    subtree: true,
  })

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
