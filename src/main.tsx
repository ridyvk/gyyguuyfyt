import { Component, StrictMode, type ErrorInfo, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import App from './App'
import { AppProvider } from './context/AppContext'
import './styles.css'
import './live-data.css'
import './chart-focus.css'
import './motion.css'
import './stock-display.css'

type RecoveryWindow = Window & {
  __KPI_SCOPE_RECOVER__?: (forceNoServiceWorker?: boolean) => void
}

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
            <button
              type="button"
              onClick={() => {
                const recover = (window as RecoveryWindow).__KPI_SCOPE_RECOVER__
                if (typeof recover === 'function') recover(true)
                else window.location.reload()
              }}
            >
              キャッシュを削除して再読み込み
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

const serviceWorkerDisabled = new URLSearchParams(window.location.search).has('no-sw')

if (import.meta.env.PROD && 'serviceWorker' in navigator && !serviceWorkerDisabled) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('./sw-photo1.js').catch((error) => {
      console.warn('KPI Scope service worker registration failed', error)
    })
  })
}
