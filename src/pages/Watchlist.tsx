import { Bookmark, GitCompareArrows } from 'lucide-react'
import { Link } from 'react-router-dom'
import CompanyCard from '../components/CompanyCard'
import { useApp } from '../context/AppContext'

export default function Watchlist() {
  const {
    companies,
    watchlist,
    isWatched,
    isCompared,
    toggleWatchlist,
    toggleCompare,
    storageReady,
  } = useApp()
  const watchedCompanies = watchlist
    .map((id) => companies.find((company) => company.id === id))
    .filter((company) => company !== undefined)

  return (
    <div className="page">
      <header className="page-header page-header--split">
        <div>
          <span className="page-eyebrow">WATCHLIST / DEEP DIVE</span>
          <h1>気になる企業を、深く見る</h1>
          <p>KPIの形、直近の変化、強みと注意点をカード単位で追跡します。</p>
        </div>
        <Link className="button button--primary" to="/compare">
          <GitCompareArrows size={17} />
          比較画面へ
        </Link>
      </header>

      {!storageReady ? (
        <div className="empty-state"><p>ウォッチリストを読み込んでいます...</p></div>
      ) : watchedCompanies.length ? (
        <div className="watchlist-grid">
          {watchedCompanies.map((company) => (
            <CompanyCard
              key={company.id}
              company={company}
              watched={isWatched(company.id)}
              compared={isCompared(company.id)}
              variant="expanded"
              onToggleWatch={() => toggleWatchlist(company.id)}
              onToggleCompare={() => {
                const changed = toggleCompare(company.id)
                if (!changed) window.alert('比較できる企業は最大5社です。')
              }}
            />
          ))}
        </div>
      ) : (
        <div className="empty-state empty-state--large">
          <span className="empty-state__icon"><Bookmark size={30} /></span>
          <h2>ウォッチリストはまだ空です</h2>
          <p>Universeで気になる企業を登録すると、ここで詳しく追跡できます。</p>
          <Link className="button button--primary" to="/universe">
            Universeから探す
          </Link>
        </div>
      )}
    </div>
  )
}
