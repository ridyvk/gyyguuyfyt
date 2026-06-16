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

if (import.meta.env.PROD) {
  void Promise.all([
    'serviceWorker' in navigator
      ? navigator.serviceWorker
          .getRegistrations()
          .then((registrations) =>
            Promise.all(
              registrations.map((registration) => registration.unregister()),
            ),
          )
      : Promise.resolve([]),
    'caches' in window
      ? caches
          .keys()
          .then((keys) => Promise.all(keys.map((key) => caches.delete(key))))
      : Promise.resolve([]),
  ])
}
