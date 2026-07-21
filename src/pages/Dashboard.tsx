import {
  Activity,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  BellRing,
  Bookmark,
  Building2,
  Gauge,
  Layers3,
  RefreshCw,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import ChartReveal from '../components/ChartReveal'
import AnimatedNumber from '../components/AnimatedNumber'
import DisclosureEventCard from '../components/DisclosureEventCard'
import ScoreBadge from '../components/ScoreBadge'
import StockQuoteCard from '../components/StockQuoteCard'
import ThemeSwipeCard from '../components/ThemeSwipeCard'
import { useApp } from '../context/AppContext'
import { hasFinancialData, hasScorableData } from '../lib/liveData'
import '../dashboard-charts.css'

const themePalette = [
  { from: '#78B9FF', to: '#3D75DE' },
  { from: '#67D1FF', to: '#348BC9' },
  { from: '#8C9FFF', to: '#5D62D8' },
  { from: '#A99BFF', to: '#7066D3' },
  { from: '#62BFE7', to: '#3973B8' },
]

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
  const financialCompanies = companies.filter(
    hasFinancialData,
  )
  const analyzableCompanies = companies.filter(
    hasScorableData,
  )
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
  const targetCompanies = updateStatus?.targetCompanies ?? financialSnapshot?.stats?.targetCompanies ?? companies.length
  const missingCompanies = updateStatus?.missingCompanies ?? financialSnapshot?.stats?.missingCompanies ?? Math.max(0, targetCompanies - coverageCompanies)
  const coverageRatio = updateStatus?.coverageRatio ?? financialSnapshot?.stats?.coverageRatio ?? (targetCompanies ? coverageCompanies / targetCompanies * 100 : 0)
  const generatedAt = updateStatus?.generatedAt ?? financialSnapshot?.generatedAt
  const dataUpdatedAt = updateStatus?.dataUpdatedAt ?? financialSnapshot?.dataUpdatedAt
  const sourceLabel = updateStatus?.source ?? financialSnapshot?.source ?? 'EDINET+TDnet'
  const industryData = Object.entries(
    companies.reduce<Record<string, number>>((counts, company) => {
      counts[company.industry] = (counts[company.industry] ?? 0) + 1
      return counts
    }, {}),
  )
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 12)
  const themeData = Object.entries(
    companies.reduce<Record<string, number>>((counts, company) => {
      company.themes.forEach((theme) => {
        counts[theme] = (counts[theme] ?? 0) + 1
      })
      return counts
    }, {}),
  )
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8)
  const topCompanies = [...analyzableCompanies]
    .sort((a, b) => b.scores.overall - a.scores.overall)
    .slice(0, 5)
  const marketPulseCompanies = [...companies]
    .filter((company) => company.stockPrice)
    .sort(
      (a, b) =>
        Math.abs(b.stockPrice?.changePercent ?? 0) -
        Math.abs(a.stockPrice?.changePercent ?? 0),
    )
    .slice(0, 3)
  const marketCoverageCount = companies.filter(
    (company) => company.stockPrice,
  ).length
  const marketIsReady =
    marketSnapshot?.status === 'ready' || marketSnapshot?.status === 'partial'
  const disclosurePulse = disclosures
    .filter(
      (event) => event.importance === 'critical' || event.importance === 'high',
    )
    .slice(0, 4)
  const dashboardDisclosureEvents = disclosurePulse.length
    ? disclosurePulse
    : disclosures.slice(0, 4)

  return (
    <div className="page">
      <section className="delta-home delta-home--swipe" aria-labelledby="delta-home-title">
        <div className="delta-home__card-zone">
          <ThemeSwipeCard />
        </div>

        <div className="delta-home__companion">
          <span className="delta-home__eyebrow">
            <i /> Live intelligence workspace
          </span>
          <p className="delta-home__headline">企業の変化を、一つの視界に。</p>
          <p className="delta-home__description">
            株価、財務KPI、開示情報を横断し、次に見るべき企業と変化を静かに浮かび上がらせます。
          </p>
          <nav className="delta-home__links" aria-label="ホームのクイックアクセス">
            <Link to="/universe">
              企業を探す <ArrowUpRight size={14} />
            </Link>
            <Link to="/map">
              KPIで絞る <ArrowUpRight size={14} />
            </Link>
            <Link to="/radar">
              開示を監視 <ArrowUpRight size={14} />
            </Link>
          </nav>

          <aside className="delta-home__pulse" aria-label="現在のデータ状況">
            <div className="delta-home__pulse-head">
              <span><Activity size={15} /> Market state</span>
              <small className={marketIsReady ? 'is-live' : ''}>
                {marketIsReady ? 'CONNECTED' : 'STANDBY'}
              </small>
            </div>
            <strong>{marketCoverageCount.toLocaleString('ja-JP')}</strong>
            <span>銘柄の株価を追跡</span>
            <dl>
              <div>
                <dt>Trading date</dt>
                <dd>{marketDateLabel(marketSnapshot?.latestTradingDate)}</dd>
              </div>
              <div>
                <dt>Disclosures</dt>
                <dd>{disclosures.length.toLocaleString('ja-JP')}件</dd>
              </div>
              <div>
                <dt>Watchlist</dt>
                <dd>{watchlist.length.toLocaleString('ja-JP')}社</dd>
              </div>
            </dl>
          </aside>
        </div>
      </section>

      <section
        className={`data-status data-status--${financialStatus}`}
      >
        <RefreshCw size={18} />
        <div>
          <strong>
            {statusReady
              ? financialStatus === 'partial'
                ? `${sourceLabel} 財務データは一部更新に失敗`
                : financialStatus === 'building'
                  ? `${sourceLabel} 財務データを構築中`
                  : `${sourceLabel} 財務データを検証済み`
              : '財務データ自動更新の初期設定待ち'}
          </strong>
          <span>
            {statusReady
              ? `${coverageCompanies.toLocaleString('ja-JP')}社を表示可能 / 対象 ${targetCompanies.toLocaleString('ja-JP')}社 / 未取得 ${missingCompanies.toLocaleString('ja-JP')}社 / カバレッジ ${coverageRatio.toFixed(2)}% / 最新開示 ${dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleString('ja-JP') : '未取得'} / 最終検証 ${generatedAt ? new Date(generatedAt).toLocaleString('ja-JP') : '未取得'}`
              : 'EDINET・TDnetから取得できていない企業は、架空値ではなく未取得として表示します。'}
          </span>
        </div>
      </section>

      <section className="market-pulse">
        <div className="market-pulse__head">
          <div>
            <span className="section-kicker">MARKET PULSE</span>
            <h2>株価データ</h2>
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
            <span className="section-kicker">DISCLOSURE PULSE</span>
            <h2>重要開示を、先に見る</h2>
            <p>
              TDnet・EDINETの新着から、業績修正・還元・資本政策などを優先表示。
            </p>
          </div>
          <div className="dashboard-disclosure-panel__status">
            <BellRing size={17} />
            <span>
              {disclosureSnapshot?.status === 'ready' ? '自動監視中' : '初期データ'}
              <small>{disclosures.length.toLocaleString('ja-JP')}件</small>
            </span>
            <Link className="button button--secondary" to="/radar">
              レーダーを開く <ArrowRight size={14} />
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

      <section className="summary-grid">
        <Link
          className="summary-card summary-card--link"
          to="/universe?sort=code-asc"
          aria-label="全企業を証券コード順で見る"
          style={{ color: 'inherit', textDecoration: 'none' }}
        >
          <span className="summary-card__icon"><Building2 /></span>
          <div>
            <small>全企業数</small>
            <strong><AnimatedNumber value={companies.length} /></strong>
          </div>
          <span className="summary-card__note">
            コード順で見る <ArrowRight size={14} />
          </span>
        </Link>
        <article className="summary-card">
          <span className="summary-card__icon summary-card__icon--blue"><Bookmark /></span>
          <div><small>ウォッチリスト</small><strong><AnimatedNumber value={watchlist.length} /></strong></div>
          <Link to="/watchlist">深く見る <ArrowRight size={14} /></Link>
        </article>
        <Link
          className="summary-card summary-card--link"
          to="/universe?warnings=1&sort=code-asc"
          aria-label="注意フラグ企業を見る"
          style={{ color: 'inherit', textDecoration: 'none' }}
        >
          <span className="summary-card__icon summary-card__icon--red"><AlertTriangle /></span>
          <div>
            <small>注意フラグ企業</small>
            <strong><AnimatedNumber value={warningCount} /></strong>
          </div>
          <span className="summary-card__note">
            対象企業を見る <ArrowRight size={14} />
          </span>
        </Link>
        <article className="summary-card">
          <span className="summary-card__icon summary-card__icon--yellow"><Gauge /></span>
          <div><small>平均スコア</small><strong><AnimatedNumber value={averageScore} /></strong></div>
          <span className="summary-card__note">分析補助指標</span>
        </article>
      </section>

      <section className="dashboard-grid">
        <article className="panel panel--wide">
          <div className="panel__heading">
            <div><span className="section-kicker">SECTOR MAP</span><h2>業種別企業数 上位12業種</h2></div>
            <Layers3 size={20} />
          </div>
          <div className="chart-wrap chart-wrap--bar">
            <ChartReveal className="chart-reveal--bar">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={industryData}
                  margin={{ left: -16, right: 8, top: 14, bottom: 0 }}
                  accessibilityLayer={false}
                >
                  <defs>
                    <linearGradient id="industryBarGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#4BA7E7" stopOpacity={0.92} />
                      <stop offset="62%" stopColor="#7FC9EA" stopOpacity={0.68} />
                      <stop offset="100%" stopColor="#B8E6EE" stopOpacity={0.38} />
                    </linearGradient>
                    <filter id="industryBarShadow" x="-40%" y="-20%" width="180%" height="150%">
                      <feDropShadow dx="0" dy="5" stdDeviation="5" floodColor="#4BA7E7" floodOpacity="0.14" />
                    </filter>
                  </defs>
                  <CartesianGrid
                    vertical={false}
                    stroke="rgba(132, 164, 212, 0.14)"
                    strokeDasharray="2 8"
                  />
                  <XAxis
                    dataKey="name"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#7E8CA2', fontSize: 10 }}
                    interval={0}
                    angle={-18}
                    textAnchor="end"
                    height={58}
                    tickMargin={9}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#7E8CA2', fontSize: 10 }}
                    allowDecimals={false}
                    tickMargin={8}
                  />
                  <Tooltip
                    cursor={{ fill: 'rgba(91, 159, 255, 0.08)' }}
                    contentStyle={{
                      backdropFilter: 'blur(18px)',
                      background: 'rgba(9,15,26,0.94)',
                      color: '#EDF4FF',
                      border: '1px solid rgba(129,174,241,0.20)',
                      borderRadius: 13,
                      boxShadow: '0 16px 38px rgba(0,0,0,0.34)',
                    }}
                  />
                  <Bar
                    dataKey="value"
                    name="企業数"
                    fill="url(#industryBarGradient)"
                    radius={[10, 10, 10, 10]}
                    barSize={18}
                    style={{ filter: 'url(#industryBarShadow)' }}
                    isAnimationActive
                    animationBegin={80}
                    animationDuration={860}
                    animationEasing="ease-out"
                  />
                </BarChart>
              </ResponsiveContainer>
            </ChartReveal>
          </div>
        </article>

        <article className="panel">
          <div className="panel__heading">
            <div><span className="section-kicker">THEMES</span><h2>注目テーマ</h2></div>
          </div>
          <div className="theme-chart">
            <div className="theme-chart__donut">
              <ChartReveal className="chart-reveal--pie">
                <ResponsiveContainer width="100%" height={210}>
                  <PieChart accessibilityLayer={false}>
                    <defs>
                      {themePalette.map((color, index) => (
                        <linearGradient
                          id={`themeGradient${index}`}
                          key={color.from}
                          x1="0"
                          y1="0"
                          x2="1"
                          y2="1"
                        >
                          <stop offset="0%" stopColor={color.from} stopOpacity={0.9} />
                          <stop offset="100%" stopColor={color.to} stopOpacity={0.72} />
                        </linearGradient>
                      ))}
                    </defs>
                    <Pie
                      data={themeData.slice(0, 5)}
                      innerRadius={66}
                      outerRadius={87}
                      paddingAngle={5}
                      cornerRadius={7}
                      dataKey="value"
                      startAngle={90}
                      endAngle={-270}
                      stroke="rgba(5,10,18,0.9)"
                      strokeWidth={2}
                      isAnimationActive
                      animationBegin={80}
                      animationDuration={920}
                      animationEasing="ease-out"
                    >
                      {themeData.slice(0, 5).map((entry, index) => (
                        <Cell
                          key={entry.name}
                          fill={`url(#themeGradient${index})`}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backdropFilter: 'blur(18px)',
                        background: 'rgba(9,15,26,0.94)',
                        color: '#EDF4FF',
                        border: '1px solid rgba(129,174,241,0.20)',
                        borderRadius: 13,
                        boxShadow: '0 16px 38px rgba(0,0,0,0.34)',
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </ChartReveal>
              <div className="theme-chart__center" aria-hidden="true">
                <small>TOP</small>
                <strong>5</strong>
              </div>
            </div>
            <div className="theme-list">
              {themeData.slice(0, 5).map((theme, index) => (
                <div key={theme.name}>
                  <i
                    style={{
                      background: `linear-gradient(135deg, ${themePalette[index].from}, ${themePalette[index].to})`,
                      boxShadow: `0 0 0 4px ${themePalette[index].from}18`,
                    }}
                  />
                  <span>{theme.name}</span>
                  <strong>{theme.value}</strong>
                </div>
              ))}
            </div>
          </div>
        </article>

        <article className="panel panel--full">
          <div className="panel__heading">
            <div><span className="section-kicker">TOP SIGNALS</span><h2>総合スコア上位</h2></div>
            <Link className="text-link" to="/universe">Universeを見る <ArrowRight size={15} /></Link>
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
    </div>
  )
}
