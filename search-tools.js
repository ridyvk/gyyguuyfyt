(() => {
  const STORAGE_KEY = 'kpi-scope-search-history-v1'
  const featured = [
    { label: 'トヨタ自動車', query: '7203', meta: '輸送用機器' },
    { label: '三菱UFJ', query: '8306', meta: '銀行業' },
    { label: 'ソニーグループ', query: '6758', meta: '電気機器' },
    { label: '任天堂', query: '7974', meta: 'その他製品' },
    { label: 'キーエンス', query: '6861', meta: '電気機器' },
    { label: 'アストロスケール', query: '186A', meta: '宇宙関連' },
  ]

  const readHistory = () => {
    try {
      const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
      return Array.isArray(value) ? value.filter(Boolean).slice(0, 6) : []
    } catch {
      return []
    }
  }

  const saveHistory = (query) => {
    const normalized = query.trim()
    if (!normalized) return
    const next = [normalized, ...readHistory().filter((item) => item !== normalized)].slice(0, 6)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  }

  const setSearch = (input, query) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
    setter?.call(input, query)
    input.dispatchEvent(new Event('input', { bubbles: true }))
    input.focus()
    saveHistory(query)
    window.setTimeout(mount, 0)
  }

  const renderHistory = (root, input) => {
    const list = root.querySelector('[data-search-history]')
    const clear = root.querySelector('[data-clear-history]')
    const history = readHistory()
    const signature = JSON.stringify(history)
    if (list.dataset.signature !== signature) {
      list.dataset.signature = signature
      list.innerHTML = history.length
        ? history.map((item) => `<button type="button" class="search-history-chip" data-query="${item.replace(/"/g, '&quot;')}">${item}</button>`).join('')
        : '<span class="search-history-empty">検索履歴はまだありません</span>'
      list.querySelectorAll('[data-query]').forEach((button) => {
        button.addEventListener('click', () => setSearch(input, button.dataset.query || ''))
      })
    }
    clear.hidden = history.length === 0
  }

  const mount = () => {
    const page = document.querySelector('.search-page')
    const input = page?.querySelector('.search-box input')
    if (!page || !input) return

    let root = page.querySelector('[data-search-explorer]')
    if (!root) {
      root = document.createElement('section')
      root.className = 'search-explorer'
      root.dataset.searchExplorer = ''
      root.innerHTML = `
        <div class="search-explorer__heading">
          <div>
            <span>DISCOVERY</span>
            <h2>企業を見つける</h2>
          </div>
          <button type="button" class="search-discover-button" data-random-company>ランダムに発見</button>
        </div>
        <div class="search-featured-grid">
          ${featured.map((company) => `
            <button type="button" class="search-featured-item" data-query="${company.query}">
              <strong>${company.label}</strong>
              <span>${company.query} · ${company.meta}</span>
            </button>
          `).join('')}
        </div>
        <div class="search-history">
          <div class="search-history__title">
            <strong>最近の検索</strong>
            <button type="button" data-clear-history>履歴を消去</button>
          </div>
          <div class="search-history__list" data-search-history></div>
        </div>
        <p class="search-shortcut"><kbd>/</kbd> キーでいつでも検索欄へ移動</p>
      `
      page.insertBefore(root, page.querySelector('.universe-results'))
      root.querySelectorAll('[data-query]').forEach((button) => {
        button.addEventListener('click', () => setSearch(input, button.dataset.query || ''))
      })
      root.querySelector('[data-random-company]').addEventListener('click', () => {
        const company = featured[Math.floor(Math.random() * featured.length)]
        setSearch(input, company.query)
      })
      root.querySelector('[data-clear-history]').addEventListener('click', () => {
        localStorage.removeItem(STORAGE_KEY)
        renderHistory(root, input)
      })
      input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
          saveHistory(input.value)
          renderHistory(root, input)
        }
      })
    }

    root.classList.toggle('is-compact', input.value.trim().length > 0)
    renderHistory(root, input)
  }

  document.addEventListener('keydown', (event) => {
    if (event.key === '/' && !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName || '')) {
      const input = document.querySelector('.search-page .search-box input')
      if (input) {
        event.preventDefault()
        input.focus()
      }
    }
  })

  new MutationObserver(mount).observe(document.documentElement, { childList: true, subtree: true })
  mount()
})()
