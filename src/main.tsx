import { Component, StrictMode, type ErrorInfo, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import '@fontsource/barlow-condensed/latin-300.css'
import App from './App'
import { AppProvider } from './context/AppContext'
import './styles.css'
import './live-data.css'
import './chart-focus.css'
import './motion.css'
import './stock-display.css'
import './kpi-map.css'
import './disclosure-radar.css'
import './motion-page-header.css'

class AppErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('KPI Scope failed to render', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="fatal-error">
          <div>
            <strong>KPI Scopeを読み込めませんでした</strong>
            <p>古いキャッシュを削除して再読み込みします。</p>
            <button type="button" onClick={() => window.location.reload()}>
              再読み込み
            </button>
          </div>
        </main>
      )
    }
    return this.props.children
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppErrorBoundary>
      <HashRouter>
        <AppProvider>
          <App />
        </AppProvider>
      </HashRouter>
    </AppErrorBoundary>
  </StrictMode>,
)

if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    const removeLegacyAppCache = async () => {
      const registrations = await navigator.serviceWorker.getRegistrations()
      await Promise.all(registrations.map((registration) => registration.unregister()))

      if ('caches' in window) {
        const cacheKeys = await window.caches.keys()
        await Promise.all(
          cacheKeys
            .filter((key) => key.startsWith('kpi-scope'))
            .map((key) => window.caches.delete(key)),
        )
      }
    }

    void removeLegacyAppCache().catch((error) => {
      console.warn('KPI Scope legacy cache cleanup failed', error)
    })
  })
}
