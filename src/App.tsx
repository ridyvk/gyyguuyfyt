import {
  Bookmark,
  Building2,
  CircleAlert,
  DatabaseZap,
  GitCompareArrows,
  LayoutDashboard,
  Menu,
  Radar,
  ScanSearch,
  Search,
  X,
} from 'lucide-react'
import { lazy, Suspense, useLayoutEffect, useState } from 'react'
import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import StartupSplash from './components/StartupSplash'
import { useApp } from './context/AppContext'
import { listedCompanySource } from './lib/companySource'
import { hasFinancialData } from './lib/liveData'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Universe = lazy(() => import('./pages/Universe'))
const Watchlist = lazy(() => import('./pages/Watchlist'))
const CompanyDetail = lazy(() => import('./pages/CompanyDetail'))
const Compare = lazy(() => import('./pages/Compare'))
const KpiMap = lazy(() => import('./pages/KpiMap'))

const navigation = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/?view=search', label: 'Search', icon: Search },
  { to: '/map', label: 'KPI Map', icon: Radar },
  { to: '/universe', label: 'Universe', icon: Building2 },
  { to: '/watchlist', label: 'Watchlist', icon: Bookmark },
  { to: '/compare', label: 'Compare', icon: GitCompareArrows },
]

export default function App() {
  const {
    companies,
    watchlist,
    compareList,
    storageReady,
    financialSnapshot,
    marketSnapshot,
  } = useApp()
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  const financialCompanyCount = companies.filter(
    hasFinancialData,
  ).length
  const stockQuoteCount = companies.filter(
    (company) => company.stockPrice,
  ).length
  const homeIsSearch =
    location.pathname === '/' &&
    new URLSearchParams(location.search).get('view') === 'search'

  useLayoutEffect(() => {
    if ('scrollRestoration' in window.history) {
      window.history.scrollRestoration = 'manual'
    }
  }, [])

  useLayoutEffect(() => {
    const resetScroll = () => {
      window.scrollTo(0, 0)
      document.documentElement.scrollTop = 0
      document.body.scrollTop = 0
    }

    resetScroll()
    const frameId = window.requestAnimationFrame(resetScroll)

    return () => window.cancelAnimationFrame(frameId)
  }, [location.key])

  return (
    <>
      <StartupSplash />
      <div className="app-shell">
        <header className="topbar">
        <NavLink className="brand" to="/" onClick={() => setMenuOpen(false)}>
          <span className="brand__mark">
            <ScanSearch size={22} />
          </span>
          <span>
            <strong>KPI Scope</strong>
            <small>Company intelligence</small>
          </span>
        </NavLink>
        <button
          type="button"
          className="mobile-menu-button"
          onClick={() => setMenuOpen((open) => !open)}
          aria-label="メニューを開く"
        >
          {menuOpen ? <X /> : <Menu />}
        </button>
        <nav className={menuOpen ? 'main-nav is-open' : 'main-nav'}>
          {navigation.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) => {
                const active =
                  label === 'Search'
                    ? homeIsSearch
                    : label === 'Dashboard'
                      ? isActive && !homeIsSearch
                      : isActive
                return active ? 'is-active' : ''
              }}
            >
              <Icon size={17} />
              <span>{label}</span>
              {label === 'Watchlist' && (
                <b>{storageReady ? watchlist.length : '·'}</b>
              )}
              {label === 'Compare' && compareList.length > 0 && (
                <b>{compareList.length}</b>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="topbar__signal">
          {financialSnapshot && ['ready', 'partial', 'building'].includes(financialSnapshot.status) ? (
            <DatabaseZap size={16} />
          ) : (
            <CircleAlert size={16} />
          )}
          {financialSnapshot && ['ready', 'partial', 'building'].includes(financialSnapshot.status)
            ? `財務 ${financialCompanyCount.toLocaleString('ja-JP')}社 / 株価 ${stockQuoteCount.toLocaleString('ja-JP')}社`
            : marketSnapshot?.status === 'ready'
              ? `株価 ${stockQuoteCount.toLocaleString('ja-JP')}社`
              : `JPX ${listedCompanySource.date.slice(0, 4)}.${listedCompanySource.date.slice(4, 6)}`}
        </div>
        </header>

        <main className="page-frame">
        <Suspense
          fallback={
            <div className="route-loader">
              <span />
              KPIを読み込んでいます
            </div>
          }
          >
            {storageReady ? (
              <div
                key={`${location.pathname}${location.search}`}
                className="route-transition"
              >
                <Routes location={location}>
                  <Route path="/" element={homeIsSearch ? <Universe searchMode /> : <Dashboard />} />
                  <Route path="/map" element={<KpiMap />} />
                  <Route path="/universe" element={<Universe />} />
                  <Route path="/watchlist" element={<Watchlist />} />
                  <Route path="/company/:companyId" element={<CompanyDetail />} />
                  <Route path="/compare" element={<Compare />} />
                  <Route path="*" element={<Universe />} />
                </Routes>
              </div>
          ) : (
            <div className="route-loader">
              <span />
              上場企業データを読み込んでいます
            </div>
          )}
        </Suspense>
        </main>

        <footer className="app-footer">
          <p>このスコアは投資判断ではなく分析補助の目安です。</p>
          <span>
            企業マスター: JPX / 財務KPI:{' '}
            {financialSnapshot && ['ready', 'partial', 'building'].includes(financialSnapshot.status)
              ? `EDINET・TDnet開示（${financialCompanyCount.toLocaleString('ja-JP')}社）`
              : '財務データ未取得'}
            {' '} / 株価:{' '}
            {marketSnapshot?.status === 'ready' || marketSnapshot?.status === 'partial'
              ? `${marketSnapshot.source}終値（${stockQuoteCount.toLocaleString('ja-JP')}社）`
              : '未取得'}
          </span>
        </footer>
      </div>
    </>
  )
}
