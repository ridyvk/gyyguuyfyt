const ROUTES = [
  { route: '/', title: 'DASHBOARD', icon: 'spark' },
  { route: '/map', title: 'KPI FINDER', icon: 'finder' },
  { route: '/universe', title: 'UNIVERSE', icon: 'orbit' },
  { route: '/radar', title: 'RADAR', icon: 'radar' },
  { route: '/watchlist', title: 'WATCHLIST', icon: 'focus' },
  { route: '/compare', title: 'COMPARE', icon: 'compare' },
]

const ICONS = {
  spark: '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 3 19 13 29 16 19 19 16 29 13 19 3 16 13 13Z"/></svg>',
  finder: '<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="13" cy="13" r="7"/><path d="m18.5 18.5 7 7M13 9v8M9 13h8"/></svg>',
  orbit: '<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="5"/><ellipse cx="16" cy="16" rx="13" ry="6"/><path d="M16 3c4 3 6 8 6 13s-2 10-6 13"/></svg>',
  radar: '<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="12"/><circle cx="16" cy="16" r="7"/><circle cx="16" cy="16" r="2"/><path d="m16 16 9-8"/></svg>',
  focus: '<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="12" cy="16" r="8"/><circle cx="20" cy="16" r="8"/></svg>',
  compare: '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M5 10h20M21 6l4 4-4 4M27 22H7M11 18l-4 4 4 4"/></svg>',
}

const searchIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6.7"/><path d="m16 16 5 5"/></svg>'
const bellIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 7h18s-3 0-3-7M10 20h4"/></svg>'
const chevron = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 5 7 7-7 7"/></svg>'

function currentPath() {
  const raw = window.location.hash.replace(/^#/, '') || '/'
  const path = raw.split('?')[0].split('#')[0] || '/'
  return path.startsWith('/') ? path : `/${path}`
}

function iconFor(name) {
  return ICONS[name] || ICONS.spark
}

function buildShell() {
  const existing = document.getElementById('orbit-shell')
  if (existing) return existing

  const shell = document.createElement('div')
  shell.id = 'orbit-shell'
  shell.className = 'orbit-shell'
  shell.innerHTML = `
    <section class="orbit-stage" aria-label="Delta navigation">
      <header class="orbit-stage__header">
        <strong class="orbit-wordmark">DELTA</strong>
        <div class="orbit-stage__actions">
          <button type="button" class="orbit-icon-button" data-orbit-action="search" aria-label="Search">${searchIcon}</button>
          <button type="button" class="orbit-icon-button" data-orbit-action="radar" aria-label="Radar">${bellIcon}</button>
        </div>
      </header>

      <div class="orbit-menu" role="navigation" aria-label="Sections">
        ${ROUTES.map((item, index) => `
          <button type="button" class="orbit-menu-card" data-orbit-index="${index}" data-orbit-route="${item.route}" aria-label="${item.title}">
            <span class="orbit-menu-card__icon">${iconFor(item.icon)}</span>
            <strong>${item.title}</strong>
            <span class="orbit-menu-card__arrow">${chevron}</span>
          </button>
        `).join('')}
      </div>

      <button type="button" class="orbit-planet" aria-label="Select section">
        <span class="orbit-planet__halo"></span>
        <span class="orbit-planet__surface"><span class="orbit-planet__sprite"></span></span>
      </button>

      <div class="orbit-dots" aria-hidden="true">${ROUTES.map((_, index) => `<i data-orbit-dot="${index}"></i>`).join('')}</div>
    </section>

    <nav class="orbit-dock" aria-label="Navigation">
      <button class="orbit-dock__brand" type="button" data-orbit-action="hub" aria-label="Menu"><strong>Δ</strong></button>
      ${ROUTES.map((item, index) => `
        <button type="button" class="orbit-dock__item" data-orbit-index="${index}" data-orbit-route="${item.route}" aria-label="${item.title}">
          <span>${iconFor(item.icon)}</span><small>${item.title}</small>
        </button>
      `).join('')}
    </nav>

    <button type="button" class="orbit-hub-trigger" data-orbit-action="hub" aria-label="Menu">
      <span class="orbit-hub-trigger__sprite"></span>
    </button>
  `
  document.body.appendChild(shell)
  return shell
}

function boot() {
  document.documentElement.classList.add('orbit-ui-active')
  const shell = buildShell()
  const stage = shell.querySelector('.orbit-stage')
  const planet = shell.querySelector('.orbit-planet')
  const sprite = shell.querySelector('.orbit-planet__sprite')
  const cards = [...shell.querySelectorAll('.orbit-menu-card')]
  const dockItems = [...shell.querySelectorAll('.orbit-dock__item')]
  const dots = [...shell.querySelectorAll('[data-orbit-dot]')]
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)')

  let selectedIndex = Math.max(0, ROUTES.findIndex((item) => item.route === currentPath()))
  if (currentPath() === '/') selectedIndex = 2
  let hubOpen = currentPath() === '/'
  let launching = false
  let dragStartX = 0
  let dragLastX = 0
  let dragMoved = false
  let frame = 0
  let dragFrame = 0

  function setPlanetFrame(next) {
    frame = ((next % 10) + 10) % 10
    const col = frame % 5
    const row = Math.floor(frame / 5)
    sprite.style.backgroundPosition = `${col * 25}% ${row * 100}%`
    const small = shell.querySelector('.orbit-hub-trigger__sprite')
    if (small) small.style.backgroundPosition = `${col * 25}% ${row * 100}%`
  }

  function updateSelection(index) {
    selectedIndex = ((index % ROUTES.length) + ROUTES.length) % ROUTES.length
    cards.forEach((card, i) => card.classList.toggle('is-selected', i === selectedIndex))
    dots.forEach((dot, i) => dot.classList.toggle('is-active', i === selectedIndex))
  }

  function syncRouteState() {
    const path = currentPath()
    const exact = ROUTES.findIndex((item) => item.route === path)
    const company = path.startsWith('/company/') ? 2 : -1
    const activeIndex = exact >= 0 ? exact : company
    dockItems.forEach((item, i) => item.classList.toggle('is-active', i === activeIndex))
    cards.forEach((item, i) => item.classList.toggle('is-route-active', i === activeIndex))
    if (!hubOpen && activeIndex >= 0) updateSelection(activeIndex)
  }

  function openHub() {
    if (launching) return
    hubOpen = true
    shell.classList.add('is-open')
    document.body.classList.add('orbit-hub-open')
    document.body.classList.remove('orbit-hub-closed')
    const exact = ROUTES.findIndex((item) => item.route === currentPath())
    if (exact >= 0 && currentPath() !== '/') updateSelection(exact)
    requestAnimationFrame(() => stage.classList.add('is-ready'))
  }

  function closeHub() {
    hubOpen = false
    stage.classList.remove('is-ready')
    shell.classList.remove('is-open', 'is-launching')
    document.body.classList.remove('orbit-hub-open')
    document.body.classList.add('orbit-hub-closed')
    syncRouteState()
  }

  function navigateTo(route, { focusSearch = false } = {}) {
    if (currentPath() !== route) window.location.hash = `#${route}`
    closeHub()
    if (focusSearch) {
      window.setTimeout(() => {
        document.querySelector('.search-box input, .kpi-finder-search input')?.focus({ preventScroll: false })
      }, reduceMotion.matches ? 20 : 300)
    }
  }

  function launch(route, options = {}) {
    if (launching) return
    launching = true
    const index = ROUTES.findIndex((item) => item.route === route)
    if (index >= 0) updateSelection(index)
    shell.classList.add('is-launching')
    window.setTimeout(() => {
      navigateTo(route, options)
      launching = false
    }, reduceMotion.matches ? 25 : 360)
  }

  cards.forEach((card) => {
    card.addEventListener('click', () => launch(card.dataset.orbitRoute))
    card.addEventListener('pointerenter', () => updateSelection(Number(card.dataset.orbitIndex)))
  })

  dockItems.forEach((item) => item.addEventListener('click', () => navigateTo(item.dataset.orbitRoute)))
  shell.querySelectorAll('[data-orbit-action="hub"]').forEach((button) => button.addEventListener('click', openHub))
  shell.querySelector('[data-orbit-action="radar"]').addEventListener('click', () => launch('/radar'))
  shell.querySelector('[data-orbit-action="search"]').addEventListener('click', () => launch('/universe', { focusSearch: true }))

  planet.addEventListener('pointerdown', (event) => {
    if (launching) return
    dragStartX = event.clientX
    dragLastX = event.clientX
    dragFrame = frame
    dragMoved = false
    planet.setPointerCapture?.(event.pointerId)
    planet.classList.add('is-dragging')
  })

  planet.addEventListener('pointermove', (event) => {
    if (!planet.classList.contains('is-dragging')) return
    const dx = event.clientX - dragStartX
    dragLastX = event.clientX
    if (Math.abs(dx) > 5) dragMoved = true
    planet.style.setProperty('--orbit-drag', `${Math.max(-56, Math.min(56, dx * 0.25))}px`)
    planet.style.setProperty('--orbit-tilt', `${Math.max(-5, Math.min(5, dx * 0.014))}deg`)
    setPlanetFrame(dragFrame + Math.round(dx / 22))
  })

  function finishDrag(event) {
    if (!planet.classList.contains('is-dragging')) return
    const dx = dragLastX - dragStartX
    planet.classList.remove('is-dragging')
    planet.style.setProperty('--orbit-drag', '0px')
    planet.style.setProperty('--orbit-tilt', '0deg')
    try { planet.releasePointerCapture?.(event.pointerId) } catch {}
    if (Math.abs(dx) > 48) updateSelection(selectedIndex + (dx < 0 ? 1 : -1))
  }

  planet.addEventListener('pointerup', finishDrag)
  planet.addEventListener('pointercancel', finishDrag)
  planet.addEventListener('click', (event) => {
    if (dragMoved) {
      dragMoved = false
      event.preventDefault()
      return
    }
    launch(ROUTES[selectedIndex].route)
  })

  planet.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault()
      const direction = event.key === 'ArrowRight' ? 1 : -1
      setPlanetFrame(frame + direction)
      updateSelection(selectedIndex + direction)
    }
  })

  window.addEventListener('hashchange', () => {
    if (hubOpen) closeHub()
    syncRouteState()
  })

  window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && hubOpen) closeHub()
  })

  setPlanetFrame(0)
  updateSelection(selectedIndex)
  syncRouteState()
  if (hubOpen) openHub()
  else closeHub()
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true })
else boot()
