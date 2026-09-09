import { getMarketBreadth } from '../lib/marketBreadth'
import {
  AlertTriangle,
  ArrowRight,
  BellRing,
  Bookmark,
  Building2,
  Gauge,
  RefreshCw,
  Search,
  ChevronDown,
} from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { lazy, Suspense, useMemo, useState } from 'react'
import MotionPageHeader from '../components/MotionPageHeader'
import MarketSculpture from '../components/MarketSculpture'
import ChartReveal from '../components/ChartReveal'
import AnimatedNumber from '../components/AnimatedNumber'
import DisclosureEventCard from '../components/DisclosureEventCard'
import ScoreBadge from '../components/ScoreBadge'
import StockQuoteCard from '../components/StockQuoteCard'
import { useApp } from '../context/AppContext'
import { hasFinancialData, hasScorableData } from '../lib/liveData'
import '../dashboard-charts.css'

const DashboardCharts = lazy(() => import('../components/DashboardCharts'))

const jstDateFormatter = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Tokyo',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

const marketDateLabel = (latestTradingDate: string | null | undefined) => {
  if (!latestTradingDate) return '更新日未取得'
  return latestTradingDate < jstDateFormatter.format(new Date())
    ? `前営業日 ${latestTradingDate}`
    : latestTradingDate
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const {
    companies,
    watchlist,
    financialSnapshot,
    marketSnapshot,
    updateStatus,
    disclosures,
    disclosureSnapshot,
    isDisclosureRead,
    markDisclosureRead,
  } = useApp()
  const financialCompanies = useMemo(() => companies.filter(hasFinancialData), [companies])
  const analyzableCompanies = useMemo(() => companies.filter(hasScorableData), [companies])
  const warningCount = analyzableCompanies.filter(
    (company) => company.hasWarning,
  ).length
  const averageScore =
    analyzableCompanies.length > 0
      ? analyzableCompanies.reduce(
          (sum, company) => sum + company.scores.overall,
          0,
        ) / analyzableCompanies.length
      : 0
  const financialStatus = financialSnapshot?.status ?? updateStatus?.status ?? 'error'
  const statusReady = financialCompanies.length > 0 && ['ready', 'partial', 'building'].includes(financialStatus)
  const coverageCompanies = financialCompanies.length
  const targetCompanies = companies.length
  const missingCompanies = Math.max(0, targetCompanies - coverageCompanies)
  const coverageRatio = targetCompanies ? coverageCompanies / targetCompanies * 100 : 0
  const generatedAt = updateStatus?.generatedAt ?? financialSnapshot?.generatedAt
  const dataUpdatedAt = updateStatus?.dataUpdatedAt ?? financialSnapshot?.dataUpdatedAt
  const sourceLabel = updateStatus?.source ?? financialSnapshot?.source ?? 'EDINET+TDnet'
  const industryData = useMemo(() => Object.entries(
    companies.reduce<Record<string, number>>((counts, company) => {
      counts[company.industry] = (counts[company.industry] ?? 0) + 1
      return counts
    }, {}),
  )
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 12), [companies])
  const themeData = useMemo(() => Object.entries(
    companies.reduce<Record<string, number>>((counts, company) => {
      company.themes.forEach((theme) => {
        counts[theme] = (counts[theme] ?? 0) + 1
      })
      return counts
    }, {}),
  )
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8), [companies])
  const topCompanies = useMemo(() => [...analyzableCompanies]
    .sort((a, b) => b.scores.overall - a.scores.overall)
    .slice(0, 5), [analyzableCompanies])
  const marketPulseCompanies = useMemo(() => [...companies]
    .filter((company) => company.stockPrice)
    .sort(
      (a, b) =>
        Math.abs(b.stockPrice?.changePercent ?? 0) -
        Math.abs(a.stockPrice?.changePercent ?? 0),
    )
    .slice(0, 3), [companies])
  const disclosurePulse = disclosures
    .filter(
      (event) => event.importance === 'critical' || event.importance === 'high',
    )
    .slice(0, 4)
  const dashboardDisclosureEvents = disclosurePulse.length
    ? disclosurePulse
    : disclosures.slice(0, 4)

  const breadth = getMarketBreadth(companies, marketSnapshot?.latestTradingDate)
  const breadthTotal = breadth.up + breadth.down + breadth.flat

  return (
    <div className="page page--dashboard">
      <MotionPageHeader title="Dashboard" variant="dashboard" />
      <div className="dashboard-entry">
        <form className="dashboard-search" role="search" onSubmit={(event) => {
          event.preventDefault()
          navigate(`/universe?q=${encodeURIComponent(query.trim())}`)
        }}>
          <Search size={19} aria-hidden="true" />
          <input type="search" aria-label="企業名・証券コードで検索" placeholder="企業名・証券コード" value={query} onChange={(event) => setQuery(event.target.value)} />
          <button type="submit" aria-label="企業を検索"><ArrowRight size={18} /></button>
        </form>
        <Link className="dashboard-finder-link" to="/map" aria-label="指標から企業を探す"><Gauge size={18} /><span>指標で探す</span></Link>
      </div>

      <section className="dashboard-overview" aria-label="マーケットと保存状況">
        <div className="breadth-card">
          <div className="breadth-card__heading"><span>値動き</span><time>{marketSnapshot?.latestTradingDate ?? '取得待ち'}</time></div>
          <MarketSculpture {...breadth} />
          <div className="breadth-card__numbers">
            <span className="breadth-up"><small>上昇</small><strong>{breadth.up.toLocaleString('ja-JP')}</strong></span>
            <span className="breadth-down"><small>下落</small><strong>{breadth.down.toLocaleString('ja-JP')}</strong></span>
            <span className="breadth-flat"><small>横ばい</small><strong>{breadth.flat.toLocaleString('ja-JP')}</strong></span>
          </div>
          <small className="breadth-card__note">比較可能 {breadthTotal.toLocaleString('ja-JP')} 社</small>
        </div>
        <div className="summary-grid">
          <Link className="summary-card summary-card--link" to="/universe?sort=code-asc" aria-label="全企業を証券コード順で見る">
            <span className="summary-card__icon"><Building2 /></span>
            <div><small>企業数</small><strong><AnimatedNumber value={companies.length} /></strong></div>
            <ArrowRight className="summary-card__arrow" size={15} />
          </Link>
          <Link className="summary-card summary-card--link" to="/watchlist" aria-label="保存した企業を見る">
            <span className="summary-card__icon summary-card__icon--blue"><Bookmark /></span>
            <div><small>保存した企業</small><strong><AnimatedNumber value={watchlist.length} /></strong></div>
            <ArrowRight className="summary-card__arrow" size={15} />
          </Link>
          <Link className="summary-card summary-card--link" to="/universe?warnings=1&sort=code-asc" aria-label="注意フラグ企業を見る">
            <span className="summary-card__icon summary-card__icon--red"><AlertTriangle /></span>
            <div><small>注意フラグ</small><strong><AnimatedNumber value={warningCount} /></strong></div>
            <ArrowRight className="summary-card__arrow" size={15} />
          </Link>
          <article className="summary-card">
            <span className="summary-card__icon summary-card__icon--yellow"><Gauge /></span>
            <div><small>平均スコア</small><strong><AnimatedNumber value={averageScore} /></strong></div>
          </article>
        </div>
      </section>

      <details className={`data-status data-status--${financialStatus}`}>
        <summary><RefreshCw size={16} /><span>データの更新状況</span><b>{financialStatus === 'partial' ? '確認待ちあり · ' : ''}{coverageRatio.toFixed(1)}% 取得</b><ChevronDown size={16} /></summary>
        <div>
          <strong>
            {statusReady
              ? financialStatus === 'partial'
                ? `${sourceLabel} 一部指標を確認待ちとして表示保留`
                : financialStatus === 'building'
                  ? `${sourceLabel} 財務データを構築中`
                  : `${sourceLabel} 財務データ`
              : '財務データ自動更新の初期設定待ち'}
          </strong>
          <span>
            {statusReady
              ? `${coverageCompanies.toLocaleString('ja-JP')}社を表示可能 / 対象 ${targetCompanies.toLocaleString('ja-JP')}社 / 未取得 ${missingCompanies.toLocaleString('ja-JP')}社 / カバレッジ ${coverageRatio.toFixed(2)}% / 最新開示 ${dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleString('ja-JP') : '未取得'} / 最終検証 ${generatedAt ? new Date(generatedAt).toLocaleString('ja-JP') : '未取得'}`
              : 'EDINET・TDnetから取得できていない企業は、架空値ではなく未取得として表示します。'}
          </span>
          <span>{updateStatus?.message ?? financialSnapshot?.message}</span>
        </div>
      </details>

      <section className="market-pulse">
        <div className="market-pulse__head">
          <div>

            <h2>値動きの大きい企業</h2>
          </div>
          <span>
            {marketSnapshot?.status === 'ready' || marketSnapshot?.status === 'partial'
              ? `${marketSnapshot.source} / ${marketDateLabel(marketSnapshot.latestTradingDate)}`
              : '自動更新待ち'}
          </span>
        </div>
        <div className="market-pulse__grid">
          {marketPulseCompanies.length ? (
            marketPulseCompanies.map((company) => (
              <Link
                to={`/company/${company.id}`}
                className="market-pulse__item"
                key={company.id}
              >
                <span>
                  {company.code}
                  <b>{company.name}</b>
                </span>
                <StockQuoteCard quote={company.stockPrice} variant="mini" />
              </Link>
            ))
          ) : (
            <div className="market-pulse__empty">
              <strong>株価データは次回の自動更新で表示されます</strong>
              <span>最新終値、前日比、出来高をカードで表示します。</span>
            </div>
          )}
        </div>
      </section>

      <section className="dashboard-disclosure-panel">
        <div className="dashboard-disclosure-panel__head">
          <div>

            <h2>重要な開示</h2>
          </div>
          <div className="dashboard-disclosure-panel__status">
            <BellRing size={17} />
            <span>
              {disclosureSnapshot?.status === 'ready' ? '自動監視中' : '初期データ'}
              <small>{disclosures.length.toLocaleString('ja-JP')}件</small>
            </span>
            <Link className="button button--secondary" to="/radar">
              すべて見る <ArrowRight size={14} />
            </Link>
          </div>
        </div>
        {dashboardDisclosureEvents.length ? (
          <div className="dashboard-disclosure-grid">
            {dashboardDisclosureEvents.map((event) => (
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
          <div className="market-pulse__empty">
            <strong>開示レーダーは次回の自動更新で表示されます</strong>
            <span>TDnet・EDINETの新着を分類して表示します。</span>
          </div>
        )}
      </section>

      <section className="dashboard-grid">
        <article className="panel panel--full">
          <div className="panel__heading">
            <div><h2>総合スコア上位</h2></div>
            <Link className="text-link" to="/universe">企業一覧 <ArrowRight size={15} /></Link>
          </div>
          <div className="ranking-grid">
            {topCompanies.map((company, index) => (
              <Link to={`/company/${company.id}`} className="ranking-card" key={company.id}>
                <span className="ranking-card__rank">0{index + 1}</span>
                <div><strong>{company.name}</strong><small>{company.code} / {company.industry}</small></div>
                <ScoreBadge score={company.scores.overall} compact />
              </Link>
            ))}
          </div>
        </article>
      </section>
      <ChartReveal className="dashboard-charts-reveal">
        <Suspense fallback={<div className="chart-loading" role="status">グラフを読み込み中</div>}>
          <DashboardCharts industryData={industryData} themeData={themeData} />
        </Suspense>
      </ChartReveal>
    </div>
  )
}
