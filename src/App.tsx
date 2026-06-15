import {
  Bookmark,
  Building2,
  CircleAlert,
  DatabaseZap,
  GitCompareArrows,
  LayoutDashboard,
  Menu,
  ScanSearch,
  X,
} from 'lucide-react'
import { lazy, Suspense, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import StartupSplash from './components/StartupSplash'
import { useApp } from './context/AppContext'
import { listedCompanySource } from './lib/companySource'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Universe = lazy(() => import('./pages/Universe'))
const Watchlist = lazy(() => import('./pages/Watchlist'))
const CompanyDetail = lazy(() => import('./pages/CompanyDetail'))
const Compare = lazy(() => import('./pages/Compare'))

const navigation = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/universe', label: 'Universe', icon: Building2 },
  { to: '/watchlist', label: 'Watchlist', icon: Bookmark },
  { to: '/compare', label: 'Compare', icon: GitCompareArrows },
]

export default function App() {
  const { watchlist, compareList, storageReady, financialSnapshot } = useApp()
  const [menuOpen, setMenuOpen] = useState(false)

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
                className={({ isActive }) => (isActive ? 'is-active' : '')}
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
            {financialSnapshot?.status === 'ready' ? (
              <DatabaseZap size={16} />
            ) : (
              <CircleAlert size={16} />
            )}
            {financialSnapshot?.status === 'ready'
              ? `EDINET ${financialSnapshot.stats.companies.toLocaleString('ja-JP')}社`
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
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/universe" element={<Universe />} />
                <Route path="/watchlist" element={<Watchlist />} />
                <Route path="/company/:companyId" element={<CompanyDetail />} />
                <Route path="/compare" element={<Compare />} />
                <Route path="*" element={<Universe />} />
              </Routes>
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
            {financialSnapshot?.status === 'ready'
              ? `EDINET（${financialSnapshot.stats.companies.toLocaleString('ja-JP')}社）`
              : 'モック（EDINET設定待ち）'}
          </span>
        </footer>
      </div>
    </>
  )
}
