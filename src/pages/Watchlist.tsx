import { ArrowRight, BellRing, Bookmark, GitCompareArrows } from 'lucide-react'
import { Link } from 'react-router-dom'
import CompanyCard from '../components/CompanyCard'
import DisclosureEventCard from '../components/DisclosureEventCard'
import MotionPageHeader from '../components/MotionPageHeader'
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
    disclosures,
    isDisclosureRead,
    markDisclosureRead,
  } = useApp()
  const watchedCompanies = watchlist
    .map((id) => companies.find((company) => company.id === id))
    .filter((company) => company !== undefined)
  const watchedDisclosures = disclosures
    .filter((event) => watchlist.includes(event.code))
    .sort((a, b) => {
      const importance = { critical: 4, high: 3, medium: 2, low: 1 }
      const weight = importance[b.importance] - importance[a.importance]
      return weight || b.filedAt.localeCompare(a.filedAt)
    })
    .slice(0, 6)
  const unreadWatchedDisclosures = watchedDisclosures.filter(
    (event) => !isDisclosureRead(event.id),
  ).length

  return (
    <div className="page">
      <MotionPageHeader title="Watchlist" variant="watchlist" />
      <div className="motion-page-actions">
        <Link className="button button--primary" to="/compare">
          <GitCompareArrows size={17} />
          比較画面へ
        </Link>
      </div>

      {!storageReady ? (
        <div className="empty-state"><p>ウォッチリストを読み込んでいます...</p></div>
      ) : watchedCompanies.length ? (
        <>
          <section className="watchlist-disclosure-inbox">
            <div className="watchlist-disclosure-inbox__head">
              <div>
                <span className="section-kicker">WATCHLIST ALERTS</span>
                <h2>監視企業の開示</h2>
                <p>重要度を優先し、最新の開示をまとめています。</p>
              </div>
              <div>
                <span><BellRing size={14} /> 未読 {unreadWatchedDisclosures}</span>
                <Link className="button button--secondary" to="/radar?watched=1">
                  すべて見る <ArrowRight size={13} />
                </Link>
              </div>
            </div>
            {watchedDisclosures.length ? (
              <div className="watchlist-disclosure-grid">
                {watchedDisclosures.map((event) => (
                  <DisclosureEventCard
                    compact
                    event={event}
                    read={isDisclosureRead(event.id)}
                    onRead={markDisclosureRead}
                    key={event.id}
                  />
                ))}
              </div>
            ) : (
              <div className="watchlist-disclosure-empty">
                登録企業の開示は、次回の自動更新でここに表示されます。
              </div>
            )}
          </section>

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
        </>
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
