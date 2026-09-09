const ROUTES = [
  { route: '/', kicker: 'MARKET', title: 'DASHBOARD', subtitle: 'Today’s Pulse', icon: 'spark' },
  { route: '/map', kicker: 'DISCOVER', title: 'KPI FINDER', subtitle: 'Find Signals', icon: 'finder' },
  { route: '/universe', kicker: 'EXPLORE', title: 'UNIVERSE', subtitle: 'Listed Companies', icon: 'orbit' },
  { route: '/radar', kicker: 'MONITOR', title: 'RADAR', subtitle: 'Live Disclosures', icon: 'radar' },
  { route: '/watchlist', kicker: 'FOCUS', title: 'WATCHLIST', subtitle: 'Your Companies', icon: 'focus' },
  { route: '/compare', kicker: 'ANALYZE', title: 'COMPARE', subtitle: 'Side by Side', icon: 'compare' },
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
const globeIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 4.5 6 4.5 9S15 18 12 21M12 3c-3 3-4.5 6-4.5 9S9 18 12 21"/></svg>'

const planetSvg = `
<svg viewBox="0 0 500 500" role="img" aria-label="Interactive market planet">
  <defs>
    <radialGradient id="orbitSea" cx="32%" cy="24%" r="78%">
      <stop offset="0" stop-color="#ffffff"/>
      <stop offset=".32" stop-color="#e8edf0"/>
      <stop offset=".72" stop-color="#9ea8ad"/>
      <stop offset="1" stop-color="#535b61"/>
    </radialGradient>
    <linearGradient id="orbitLand" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#f8faf9"/>
      <stop offset=".58" stop-color="#c7cecc"/>
      <stop offset="1" stop-color="#858e8c"/>
    </linearGradient>
    <clipPath id="orbitClip"><circle cx="250" cy="250" r="225"/></clipPath>
    <filter id="orbitBlur"><feGaussianBlur stdDeviation="5"/></filter>
  </defs>
  <circle cx="250" cy="250" r="225" fill="url(#orbitSea)"/>
  <g clip-path="url(#orbitClip)" class="orbit-planet__continents">
    <path d="M88 124c30-36 73-52 111-44 24 5 38 24 64 29 25 5 51-8 72 10 15 13 7 35-8 44-17 10-43 6-55 22-13 18 1 39-12 55-10 13-35 10-42 27-6 16 10 31 7 47-3 17-25 25-32 41-6 14 1 31-10 42-11 12-33 4-42-8-17-23-21-52-39-74-13-16-34-26-38-46-5-27 21-45 22-71 1-24-20-47 2-74Z" fill="url(#orbitLand)"/>
    <path d="M322 183c21-18 59-20 78 2 10 12 4 29 13 42 8 11 24 13 29 26 8 20-13 37-31 42-15 4-33 1-44 12-12 12-9 34-23 44-16 11-39-3-47-20-9-19 3-38 0-57-4-25-28-41-26-67 2-13 16-18 28-18 8 0 17 1 23-6Z" fill="url(#orbitLand)"/>
    <path d="M290 330c20-7 49 7 54 29 4 17-10 31-11 47-1 13 7 25 4 38-4 17-24 27-40 20-20-9-21-36-31-53-8-14-25-25-23-42 2-18 27-32 47-39Z" fill="url(#orbitLand)" opacity=".86"/>
    <path d="M39 206c83 5 115-44 190-32 69 11 102 59 177 46 35-6 70-23 101-17" fill="none" stroke="#fff" stroke-opacity=".32" stroke-width="12" filter="url(#orbitBlur)"/>
    <path d="M28 286c69-14 117 22 178 15 67-8 101-52 174-40 51 8 82 30 116 22" fill="none" stroke="#fff" stroke-opacity=".22" stroke-width="9" filter="url(#orbitBlur)"/>
    <path d="M68 370c69-21 130 17 191-4 46-15 72-53 134-45" fill="none" stroke="#fff" stroke-opacity=".18" stroke-width="8" filter="url(#orbitBlur)"/>
  </g>
  <circle cx="250" cy="250" r="224" fill="none" stroke="#ffffff" stroke-opacity=".66" stroke-width="2"/>
  <ellipse cx="207" cy="178" rx="112" ry="77" fill="#fff" opacity=".12" transform="rotate(-24 207 178)"/>
</svg>`

function currentPath() {
  const raw = window.location.hash.replace(/^#/, '') || '/'
  const path = raw.split('?')[0].split('#')[0] || '/'
  return path.startsWith('/') ? path : `/${path}`
}

function iconFor(name) {
  return ICONS[name] || ICONS.spark
}

function buildShell() {
  if (document.getElementById('orbit-shell')) return document.getElementById('orbit-shell')

  const shell = document.createElement('div')
  shell.id = 'orbit-shell'
  shell.className = 'orbit-shell'
  shell.innerHTML = `
    <section class="orbit-stage" aria-label="Delta navigation hub">
      <header class="orbit-stage__header">
        <div class="orbit-wordmark">
          <strong>DELTA</strong>
          <span>MARKET INTELLIGENCE</span>
          <small>EXPLORE <i></i> ANALYZE <i></i> DECIDE</small>
        </div>
        <div class="orbit-stage__actions">
          <button type="button" class="orbit-icon-button" data-orbit-action="search" aria-label="Search companies">${searchIcon}</button>
          <button type="button" class="orbit-icon-button orbit-radar-button" data-orbit-action="radar" aria-label="Open disclosure radar">${bellIcon}<b class="orbit-radar-badge" hidden></b></button>
          <button type="button" class="orbit-icon-button orbit-globe-button" data-orbit-action="planet" aria-label="Select universe">${globeIcon}</button>
        </div>
      </header>

      <div class="orbit-menu" role="navigation" aria-label="Delta sections">
        ${ROUTES.map((item, index) => `
          <button type="button" class="orbit-menu-card" data-orbit-index="${index}" data-orbit-route="${item.route}" aria-label="Open ${item.title}">
            <span class="orbit-menu-card__icon">${iconFor(item.icon)}</span>
            <span class="orbit-menu-card__copy">
              <small>${item.kicker}</small>
              <strong>${item.title}</strong>
              <em>${item.subtitle}</em>
            </span>
            <span class="orbit-menu-card__arrow"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 5 7 7-7 7"/></svg></span>
          </button>
        `).join('')}
      </div>

      <button type="button" class="orbit-planet" aria-label="Drag to select a section, tap to open" aria-live="polite">
        <span class="orbit-planet__halo"></span>
        <span class="orbit-planet__surface">${planetSvg}</span>
        <span class="orbit-planet__cue">
          <small>DRAG TO EXPLORE</small>
          <strong class="orbit-planet__selection">UNIVERSE</strong>
          <svg viewBox="0 0 80 16" aria-hidden="true"><path d="M78 8H8M8 8l7-6M8 8l7 6"/></svg>
        </span>
      </button>

      <div class="orbit-stage__foot orbit-stage__foot--left">
        <span class="orbit-crescent"></span>
        <strong>MARKETS<br>IN MOTION</strong>
      </div>
      <div class="orbit-stage__foot orbit-stage__foot--right">
        <div class="orbit-dots" aria-hidden="true">${ROUTES.map((_, index) => `<i data-orbit-dot="${index}"></i>`).join('')}</div>
        <span>MORE<br>AWAITS</span>
      </div>
    </section>

    <nav class="orbit-dock" aria-label="Delta quick navigation">
      <button class="orbit-dock__brand" type="button" data-orbit-action="hub" aria-label="Open planet navigation"><span></span><strong>Δ</strong></button>
      ${ROUTES.map((item, index) => `
        <button type="button" class="orbit-dock__item" data-orbit-index="${index}" data-orbit-route="${item.route}" aria-label="${item.title}">
          <span>${iconFor(item.icon)}</span><small>${item.title}</small>
        </button>
      `).join('')}
    </nav>

    <button type="button" class="orbit-hub-trigger" data-orbit-action="hub" aria-label="Open planet navigation">
      <span class="orbit-hub-trigger__planet">${planetSvg}</span>
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
  const selectionLabel = shell.querySelector('.orbit-planet__selection')
  const cards = [...shell.querySelectorAll('.orbit-menu-card')]
  const dockItems = [...shell.querySelectorAll('.orbit-dock__item')]
  const dots = [...shell.querySelectorAll('[data-orbit-dot]')]
  const radarBadge = shell.querySelector('.orbit-radar-badge')
  const motionReduced = window.matchMedia('(prefers-reduced-motion: reduce)')

  let selectedIndex = Math.max(0, ROUTES.findIndex((item) => item.route === currentPath()))
  if (currentPath() === '/') selectedIndex = 2
  let hubOpen = currentPath() === '/'
  let launching = false
  let dragStartX = 0
  let dragLastX = 0
  let dragMoved = false
  let spin = 0

  function setMetaTheme(open) {
    const meta = document.querySelector('meta[name="theme-color"]')
    if (meta) meta.setAttribute('content', open ? '#f7f7f5' : '#f1f3f4')
  }

  function updateSelection(index, { nudge = false } = {}) {
    selectedIndex = (index + ROUTES.length) % ROUTES.length
    const item = ROUTES[selectedIndex]
    selectionLabel.textContent = item.title
    cards.forEach((card, i) => card.classList.toggle('is-selected', i === selectedIndex))
    dots.forEach((dot, i) => dot.classList.toggle('is-active', i === selectedIndex))
    if (nudge) {
      spin += index > selectedIndex ? -14 : 14
      planet.style.setProperty('--orbit-spin', `${spin}px`)
    }
  }

  function syncRouteState() {
    const path = currentPath()
    const exact = ROUTES.findIndex((item) => item.route === path)
    const company = path.startsWith('/company/') ? 2 : -1
    const activeIndex = exact >= 0 ? exact : company

    dockItems.forEach((item, i) => item.classList.toggle('is-active', i === activeIndex))
    cards.forEach((item, i) => item.classList.toggle('is-route-active', i === activeIndex))
    document.body.dataset.orbitRoute = path.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '') || 'dashboard'

    if (!hubOpen && activeIndex >= 0) updateSelection(activeIndex)
  }

  function openHub() {
    if (launching) return
    hubOpen = true
    shell.classList.add('is-open')
    document.body.classList.add('orbit-hub-open')
    document.body.classList.remove('orbit-hub-closed')
    setMetaTheme(true)
    const exact = ROUTES.findIndex((item) => item.route === currentPath())
    if (exact >= 0 && currentPath() !== '/') updateSelection(exact)
    window.requestAnimationFrame(() => stage.classList.add('is-ready'))
  }

  function closeHub() {
    hubOpen = false
    stage.classList.remove('is-ready')
    shell.classList.remove('is-open', 'is-launching')
    document.body.classList.remove('orbit-hub-open')
    document.body.classList.add('orbit-hub-closed')
    setMetaTheme(false)
    syncRouteState()
  }

  function navigateTo(route, { focusSearch = false } = {}) {
    const same = currentPath() === route
    if (!same) window.location.hash = `#${route}`
    closeHub()
    if (focusSearch) {
      window.setTimeout(() => {
        const input = document.querySelector('.search-box input, .kpi-finder-search input')
        input?.focus({ preventScroll: false })
      }, 520)
    }
  }

  function launch(route, options = {}) {
    if (launching) return
    launching = true
    const index = ROUTES.findIndex((item) => item.route === route)
    if (index >= 0) updateSelection(index)
    shell.classList.add('is-launching')
    stage.style.setProperty('--launch-x', `${Math.max(-30, Math.min(30, (selectedIndex - 2.5) * 7))}px`)
    const delay = motionReduced.matches ? 40 : 520
    window.setTimeout(() => {
      navigateTo(route, options)
      launching = false
    }, delay)
  }

  cards.forEach((card) => {
    card.addEventListener('click', () => launch(card.dataset.orbitRoute))
    card.addEventListener('pointerenter', () => {
      if (!launching) updateSelection(Number(card.dataset.orbitIndex))
    })
  })

  dockItems.forEach((item) => item.addEventListener('click', () => navigateTo(item.dataset.orbitRoute)))

  shell.querySelectorAll('[data-orbit-action="hub"]').forEach((button) => button.addEventListener('click', openHub))
  shell.querySelector('[data-orbit-action="radar"]').addEventListener('click', () => launch('/radar'))
  shell.querySelector('[data-orbit-action="search"]').addEventListener('click', () => launch('/universe', { focusSearch: true }))
  shell.querySelector('[data-orbit-action="planet"]').addEventListener('click', () => updateSelection(2))

  planet.addEventListener('pointerdown', (event) => {
    if (launching) return
    dragStartX = event.clientX
    dragLastX = event.clientX
    dragMoved = false
    planet.setPointerCapture?.(event.pointerId)
    planet.classList.add('is-dragging')
  })

  planet.addEventListener('pointermove', (event) => {
    if (!planet.classList.contains('is-dragging')) return
    const dx = event.clientX - dragStartX
    dragLastX = event.clientX
    if (Math.abs(dx) > 5) dragMoved = true
    planet.style.setProperty('--orbit-drag', `${Math.max(-74, Math.min(74, dx * 0.38))}px`)
    planet.style.setProperty('--orbit-turn', `${Math.max(-7, Math.min(7, dx * 0.018))}deg`)
  })

  function finishDrag(event) {
    if (!planet.classList.contains('is-dragging')) return
    const dx = dragLastX - dragStartX
    planet.classList.remove('is-dragging')
    planet.style.setProperty('--orbit-drag', '0px')
    planet.style.setProperty('--orbit-turn', '0deg')
    try { planet.releasePointerCapture?.(event.pointerId) } catch {}
    if (Math.abs(dx) > 52) {
      spin += dx < 0 ? -38 : 38
      planet.style.setProperty('--orbit-spin', `${spin}px`)
      updateSelection(selectedIndex + (dx < 0 ? 1 : -1))
      dragMoved = true
    }
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
    if (event.key === 'ArrowLeft') {
      event.preventDefault()
      updateSelection(selectedIndex - 1)
    } else if (event.key === 'ArrowRight') {
      event.preventDefault()
      updateSelection(selectedIndex + 1)
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      launch(ROUTES[selectedIndex].route)
    }
  })

  function syncRadarBadge() {
    const source = document.querySelector('#root .main-nav .nav-badge--alert')
    const value = source?.textContent?.trim() || ''
    radarBadge.textContent = value
    radarBadge.hidden = !value
  }

  const root = document.getElementById('root')
  if (root) {
    const observer = new MutationObserver(syncRadarBadge)
    observer.observe(root, { childList: true, subtree: true, characterData: true })
  }

  window.addEventListener('hashchange', () => {
    if (hubOpen) closeHub()
    syncRouteState()
  })

  window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && hubOpen) closeHub()
  })

  updateSelection(selectedIndex)
  syncRouteState()
  syncRadarBadge()
  if (hubOpen) openHub()
  else closeHub()
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot, { once: true })
} else {
  boot()
}
