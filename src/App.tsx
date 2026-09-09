import {
  Bookmark,
  Building2,
  CircleAlert,
  DatabaseZap,
  GitCompareArrows,
  LayoutDashboard,
  ListFilter,
  Radar,
} from 'lucide-react'
import {
  lazy,
  Suspense,
  useLayoutEffect,
  type CSSProperties,
} from 'react'
import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import MotionControl from './components/MotionControl'
import PageMotion from './components/PageMotion'
import { useApp } from './context/AppContext'
import { listedCompanySource } from './lib/companySource'
import { hasFinancialData } from './lib/liveData'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Universe = lazy(() => import('./pages/Universe'))
const Watchlist = lazy(() => import('./pages/Watchlist'))
const CompanyDetail = lazy(() => import('./pages/CompanyDetail'))
const Compare = lazy(() => import('./pages/Compare'))
const KpiMap = lazy(() => import('./pages/KpiMap'))
const DisclosureRadar = lazy(() => import('./pages/DisclosureRadar'))

const navigation = [
  { to: '/', label: 'Dashboard', short: 'ホーム', icon: LayoutDashboard },
  { to: '/map', label: 'KPI Finder', short: '指標', icon: ListFilter },
  { to: '/universe', label: 'Universe', short: '企業', icon: Building2 },
  { to: '/radar', label: 'Radar', short: '開示', icon: Radar },
  { to: '/watchlist', label: 'Watchlist', short: '保存', icon: Bookmark },
  { to: '/compare', label: 'Compare', short: '比較', icon: GitCompareArrows },
]

export default function App() {
  const {
    companies,
    watchlist,
    compareList,
    storageReady,
    financialSnapshot,
    marketSnapshot,
    unreadDisclosureCount,
  } = useApp()
  const location = useLocation()
  const navigationIndex = navigation.findIndex((item) => item.to === location.pathname)
  const financialCompanyCount = companies.filter(
    hasFinancialData,
  ).length
  const stockQuoteCount = companies.filter(
    (company) => company.stockPrice,
  ).length
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
      <a className="skip-link" href="#main-content" onClick={(event) => {
        event.preventDefault()
        document.getElementById('main-content')?.focus()
      }}>本文へ移動</a>
      <div className="app-shell">
        <header className="topbar">
        <nav
          id="primary-navigation"
          className="main-nav"
          aria-label="メインナビゲーション"
          style={{ '--active-tab': Math.max(0, navigationIndex) } as CSSProperties}
          data-active={navigationIndex >= 0}
        >
          {navigation.map(({ to, label, short, icon: Icon }, index) => (
            <NavLink
              key={to}
              to={to}
              state={{ deltaDirection: index < navigationIndex ? -1 : 1 }}
              end={to === '/'}
              aria-label={label}
              className={({ isActive }) => isActive ? 'is-active' : ''}
            >
              <Icon size={17} />
              <span className="nav-label">{short}</span>
              <span className="nav-label--short" aria-hidden="true">{short}</span>
              {label === 'Watchlist' && (
                <b>{storageReady ? watchlist.length : '·'}</b>
              )}
              {label === 'Radar' && unreadDisclosureCount > 0 && (
                <b className="nav-badge--alert">
                  {unreadDisclosureCount > 99 ? '99+' : unreadDisclosureCount}
                </b>
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
        <MotionControl />
        </header>

        <main id="main-content" className="page-frame" tabIndex={-1}>
        <Suspense
          fallback={
            <div className="route-loader" role="status">
              <span />
              KPIを読み込んでいます
            </div>
          }
          >
            {storageReady ? (
              <PageMotion
                key={`${location.pathname}${location.search}`}
              >
                <Routes location={location}>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/map" element={<KpiMap />} />
                  <Route path="/universe" element={<Universe />} />
                  <Route path="/radar" element={<DisclosureRadar />} />
                  <Route path="/watchlist" element={<Watchlist />} />
                  <Route path="/company/:companyId" element={<CompanyDetail />} />
                  <Route path="/compare" element={<Compare />} />
                  <Route path="*" element={<Universe />} />
                </Routes>
              </PageMotion>
          ) : (
            <div className="route-loader" role="status">
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
