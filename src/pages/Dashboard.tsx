import {
  AlertTriangle,
  ArrowRight,
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
import ScoreBadge from '../components/ScoreBadge'
import StockQuoteCard from '../components/StockQuoteCard'
import { useApp } from '../context/AppContext'
import { listedCompanySource } from '../lib/companySource'
import { hasFinancialData } from '../lib/liveData'
import '../dashboard-charts.css'

const themePalette = [
  { from: '#78BEF4', to: '#3A8FD8' },
  { from: '#8DDDD4', to: '#4BAEA9' },
  { from: '#AAA8ED', to: '#7570D4' },
  { from: '#DAB4E8', to: '#AA75C5' },
  { from: '#F4CCA2', to: '#E4A263' },
]

export default function Dashboard() {
  const {
    companies,
    watchlist,
    financialSnapshot,
    marketSnapshot,
    updateStatus,
  } = useApp()
  const analyzableCompanies = companies.filter(
    hasFinancialData,
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
  const statusReady = analyzableCompanies.length > 0 && ['ready', 'partial', 'building'].includes(financialStatus)
  const coverageCompanies = analyzableCompanies.length
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

  return (
    <div className="page">
      <section className="hero-panel">
        <div>
          <span className="page-eyebrow">
            OVERVIEW / JPX {listedCompanySource.date.slice(0, 4)}.
            {listedCompanySource.date.slice(4, 6)}
          </span>
          <h1>企業の現在地を、<br />数字の輪郭からつかむ。</h1>
          <p>
            財務KPI、業種別の着眼点、強みと違和感をひとつの視界に。
            株価ではなく、事業の変化を追う企業分析ワークスペースです。
          </p>
        </div>
        <div className="hero-panel__score">
          <span>Universe 平均</span>
          <ScoreBadge
            score={averageScore}
            available={analyzableCompanies.length > 0}
          />
          <small>
            {statusReady
              ? `財務KPI取得 ${coverageCompanies.toLocaleString('ja-JP')} / ${targetCompanies.toLocaleString('ja-JP')}社`
              : '財務データ取得待ち'}
          </small>
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
              ? `${marketSnapshot.source} / ${marketSnapshot.latestTradingDate ?? '更新日未取得'}`
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
                    stroke="rgba(88, 116, 136, 0.11)"
                    strokeDasharray="2 8"
                  />
                  <XAxis
                    dataKey="name"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#87959F', fontSize: 10 }}
                    interval={0}
                    angle={-18}
                    textAnchor="end"
                    height={58}
                    tickMargin={9}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#9AA5AD', fontSize: 10 }}
                    allowDecimals={false}
                    tickMargin={8}
                  />
                  <Tooltip
                    cursor={{ fill: 'rgba(91, 174, 219, 0.055)' }}
                    contentStyle={{
                      backdropFilter: 'blur(18px)',
                      background: 'rgba(255,255,255,0.84)',
                      color: '#25333B',
                      border: '1px solid rgba(104,148,174,0.16)',
                      borderRadius: 13,
                      boxShadow: '0 14px 35px rgba(44,79,99,0.12)',
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
                      stroke="rgba(255,255,255,0.88)"
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
                        background: 'rgba(255,255,255,0.84)',
                        color: '#25333B',
                        border: '1px solid rgba(104,148,174,0.16)',
                        borderRadius: 13,
                        boxShadow: '0 14px 35px rgba(44,79,99,0.12)',
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
