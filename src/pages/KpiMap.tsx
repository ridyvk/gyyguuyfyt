import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Bookmark,
  ChevronRight,
  GitCompareArrows,
  LineChart,
  ListFilter,
  Map,
  Search,
  Sparkles,
  Target,
  TrendingUp,
  X,
  Zap,
} from 'lucide-react'
import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import AnimatedNumber from '../components/AnimatedNumber'
import ScoreBadge from '../components/ScoreBadge'
import ScoreBar from '../components/ScoreBar'
import { useApp } from '../context/AppContext'
import { industriesList, marketsList } from '../lib/companyUniverse'
import {
  formatChangePercent,
  formatMetric,
  formatStockPrice,
  formatVolume,
} from '../lib/formatters'
import { hasFinancialData, hasScorableData } from '../lib/liveData'
import type { Company, KpiKey, Market } from '../types'

type FocusMode = 'balanced' | 'quality' | 'capital' | 'cash' | 'momentum'

interface KpiMapFilter {
  query: string
  market: Market | 'all'
  industry: string | 'all'
  watchOnly: boolean
  warningsOnly: boolean
  dataOnly: boolean
}

interface FocusConfig {
  label: string
  shortLabel: string
  description: string
  xLabel: string
  yLabel: string
  score: (company: Company) => number
  axis: (company: Company) => { x: number; y: number }
}

interface RankedCompany {
  company: Company
  score: number
  reasons: string[]
  tone: 'strong' | 'steady' | 'watch'
  hasEstimate: boolean
}

interface Lane {
  key: string
  title: string
  subtitle: string
  icon: typeof Sparkles
  items: RankedCompany[]
}

const initialFilter: KpiMapFilter = {
  query: '',
  market: 'all',
  industry: 'all',
  watchOnly: false,
  warningsOnly: false,
  dataOnly: true,
}

const metricLabels: Partial<Record<KpiKey, string>> = {
  roic: 'ROIC',
  wacc: 'WACC',
  roicWaccSpread: 'ROIC-WACC',
  operatingMargin: '営業利益率',
  operatingCfMargin: '営業CF率',
  cashProfitGap: 'CF利益差',
  equityRatio: '自己資本比率',
  netCash: 'ネット現金',
}

const scoreLabels = {
  profitability: '収益性',
  safety: '安全性',
  cashGeneration: '現金創出',
} as const

const visibleMetricKeys: KpiKey[] = [
  'roic',
  'wacc',
  'roicWaccSpread',
  'operatingCfMargin',
  'cashProfitGap',
  'equityRatio',
]

const clamp = (value: number, min = 0, max = 100) =>
  Math.max(min, Math.min(max, value))

const finiteMetric = (company: Company, key: KpiKey) => {
  const metric = company.metrics[key]
  if (!metric || metric.available === false || !Number.isFinite(metric.value)) {
    return undefined
  }
  return metric.value
}

const hasMetric = (company: Company, key: KpiKey) =>
  finiteMetric(company, key) !== undefined

const normalizeRange = (value: number | undefined, min: number, max: number) => {
  if (value === undefined || min === max) return 50
  return clamp(((value - min) / (max - min)) * 100)
}

const latestRevenue = (company: Company) =>
  [...company.history].reverse().find((point) => Number.isFinite(point.revenue))
    ?.revenue

const qualitySignal = (company: Company) => {
  if (!hasScorableData(company)) return 0
  return clamp(
    company.scores.profitability * 0.42 +
      company.scores.safety * 0.32 +
      company.scores.cashGeneration * 0.26,
  )
}

const capitalSignal = (company: Company) => {
  if (!hasFinancialData(company)) return 0
  const roic = normalizeRange(finiteMetric(company, 'roic'), -4, 22)
  const spread = normalizeRange(finiteMetric(company, 'roicWaccSpread'), -12, 12)
  const wacc = 100 - normalizeRange(finiteMetric(company, 'wacc'), 3, 14)
  return clamp(roic * 0.46 + spread * 0.38 + wacc * 0.16)
}

const cashSignal = (company: Company) => {
  if (!hasFinancialData(company)) return 0
  const cf = normalizeRange(finiteMetric(company, 'operatingCfMargin'), -8, 24)
  const gap = normalizeRange(finiteMetric(company, 'cashProfitGap'), -12, 12)
  const netCash = normalizeRange(finiteMetric(company, 'netCash'), -250, 650)
  return clamp(cf * 0.52 + gap * 0.34 + netCash * 0.14)
}

const momentumSignal = (company: Company) => {
  const change = company.stockPrice?.changePercent
  const quote = change === undefined ? 50 : normalizeRange(change, -10, 10)
  const base = hasScorableData(company) ? company.scores.overall : 42
  return clamp(base * 0.58 + quote * 0.42)
}

const balancedSignal = (company: Company) => {
  if (!hasFinancialData(company)) return 0
  const base = hasScorableData(company) ? company.scores.overall : 50
  return clamp(
    base * 0.36 +
      qualitySignal(company) * 0.2 +
      capitalSignal(company) * 0.22 +
      cashSignal(company) * 0.16 +
      momentumSignal(company) * 0.06,
  )
}

const focusModes: Record<FocusMode, FocusConfig> = {
  balanced: {
    label: 'Smart Shortlist',
    shortLabel: '総合',
    description: '財務・資本効率・現金品質・株価反応を軽く合成',
    xLabel: '収益性',
    yLabel: '安全性',
    score: balancedSignal,
    axis: (company) => ({
      x: hasScorableData(company) ? company.scores.profitability : 50,
      y: hasScorableData(company) ? company.scores.safety : 50,
    }),
  },
  quality: {
    label: 'Quality Check',
    shortLabel: '安全・収益',
    description: '収益性と安全性を優先して安定候補を抽出',
    xLabel: '収益性',
    yLabel: '安全性',
    score: qualitySignal,
    axis: (company) => ({
      x: hasScorableData(company) ? company.scores.profitability : 50,
      y: hasScorableData(company) ? company.scores.safety : 50,
    }),
  },
  capital: {
    label: 'Capital Edge',
    shortLabel: '資本効率',
    description: 'ROIC、WACC、ROIC-WACCで資本効率を比較',
    xLabel: 'ROIC',
    yLabel: 'ROIC-WACC',
    score: capitalSignal,
    axis: (company) => ({
      x: normalizeRange(finiteMetric(company, 'roic'), -4, 22),
      y: normalizeRange(finiteMetric(company, 'roicWaccSpread'), -12, 12),
    }),
  },
  cash: {
    label: 'Cash Quality',
    shortLabel: '現金品質',
    description: '利益がキャッシュで裏付けられている企業を上に出す',
    xLabel: '営業CF率',
    yLabel: 'CF利益差',
    score: cashSignal,
    axis: (company) => ({
      x: normalizeRange(finiteMetric(company, 'operatingCfMargin'), -8, 24),
      y: normalizeRange(finiteMetric(company, 'cashProfitGap'), -12, 12),
    }),
  },
  momentum: {
    label: 'Market Reaction',
    shortLabel: '株価反応',
    description: 'KPIの強さと直近の株価反応を並べて確認',
    xLabel: 'KPI score',
    yLabel: '株価変化',
    score: momentumSignal,
    axis: (company) => ({
      x: hasScorableData(company) ? company.scores.overall : 50,
      y: normalizeRange(company.stockPrice?.changePercent, -10, 10),
    }),
  },
}

const toneForScore = (score: number): RankedCompany['tone'] => {
  if (score >= 72) return 'strong'
  if (score >= 54) return 'steady'
  return 'watch'
}

const metricText = (company: Company, key: KpiKey) => {
  const metric = company.metrics[key]
  return metric ? formatMetric(metric) : '—'
}

const metricChip = (company: Company, key: KpiKey) => {
  if (!hasMetric(company, key)) return null
  const metric = company.metrics[key]
  const label = metricLabels[key] ?? key
  return `${label} ${formatMetric(metric)}${metric.estimated ? ' 推定' : ''}`
}

const buildReasons = (company: Company, focus: FocusMode) => {
  const candidates: Array<string | null> = [
    focus === 'capital' || focus === 'balanced'
      ? metricChip(company, 'roicWaccSpread') ?? metricChip(company, 'roic')
      : null,
    focus === 'cash' || focus === 'balanced'
      ? metricChip(company, 'operatingCfMargin') ?? metricChip(company, 'cashProfitGap')
      : null,
    focus === 'quality' || focus === 'balanced'
      ? `収益 ${Math.round(company.scores.profitability)} / 安全 ${Math.round(
          company.scores.safety,
        )}`
      : null,
    focus === 'momentum'
      ? `株価 ${formatChangePercent(company.stockPrice?.changePercent)}`
      : null,
    hasMetric(company, 'equityRatio')
      ? `自己資本 ${metricText(company, 'equityRatio')}`
      : null,
  ]
  return candidates.filter((item): item is string => Boolean(item)).slice(0, 3)
}

const hasEstimate = (company: Company) =>
  visibleMetricKeys.some((key) => company.metrics[key]?.estimated)

const dataLabel = (company: Company) => {
  if (!hasFinancialData(company)) return '財務未取得'
  const count = company.trustedMetricCount ?? company.liveMetricCount ?? 0
  return `${company.dataSource ?? 'DATA'} / ${count}指標`
}

const rankCompany = (company: Company, focus: FocusMode): RankedCompany => {
  const rawScore = focusModes[focus].score(company)
  const warningPenalty = company.hasWarning ? 5 : 0
  const score = clamp(rawScore - warningPenalty)
  return {
    company,
    score,
    reasons: buildReasons(company, focus),
    tone: toneForScore(score),
    hasEstimate: hasEstimate(company),
  }
}

const compareRanked = (a: RankedCompany, b: RankedCompany) => {
  if (b.score !== a.score) return b.score - a.score
  return a.company.code.localeCompare(b.company.code, 'ja-JP')
}

const formatRevenue = (company: Company) => {
  const revenue = latestRevenue(company)
  if (!revenue) return '売上 —'
  if (revenue >= 10_000) return `売上 ${(revenue / 10_000).toFixed(1)}兆円`
  return `売上 ${Math.round(revenue).toLocaleString('ja-JP')}億円`
}

export default function KpiMap() {
  const {
    companies,
    watchlist,
    compareList,
    isWatched,
    isCompared,
    toggleWatchlist,
    toggleCompare,
  } = useApp()
  const [filter, setFilter] = useState<KpiMapFilter>(initialFilter)
  const [focus, setFocus] = useState<FocusMode>('balanced')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [visibleCount, setVisibleCount] = useState(28)
  const [compareNotice, setCompareNotice] = useState('')

  const watchedIds = useMemo(() => new Set(watchlist), [watchlist])
  const focusConfig = focusModes[focus]

  const filteredCompanies = useMemo(() => {
    const query = filter.query.trim().toLowerCase()
    return companies.filter((company) => {
      const matchesQuery =
        !query ||
        company.name.toLowerCase().includes(query) ||
        company.code.toLowerCase().includes(query)
      const matchesMarket = filter.market === 'all' || company.market === filter.market
      const matchesIndustry =
        filter.industry === 'all' || company.industry === filter.industry
      const matchesWatch = !filter.watchOnly || watchedIds.has(company.id)
      const matchesWarning = !filter.warningsOnly || company.hasWarning
      const matchesData = !filter.dataOnly || hasFinancialData(company)
      return (
        matchesQuery &&
        matchesMarket &&
        matchesIndustry &&
        matchesWatch &&
        matchesWarning &&
        matchesData
      )
    })
  }, [companies, filter, watchedIds])

  const ranked = useMemo(
    () => filteredCompanies.map((company) => rankCompany(company, focus)).sort(compareRanked),
    [filteredCompanies, focus],
  )

  const selectedRank = useMemo(
    () => ranked.find((item) => item.company.id === selectedId) ?? ranked[0] ?? null,
    [ranked, selectedId],
  )
  const selectedCompany = selectedRank?.company ?? null

  useEffect(() => {
    if (!ranked.length) {
      setSelectedId(null)
      return
    }
    if (!selectedId || !ranked.some((item) => item.company.id === selectedId)) {
      setSelectedId(ranked[0].company.id)
    }
  }, [ranked, selectedId])

  useEffect(() => {
    setVisibleCount(28)
  }, [filter, focus])

  const stats = useMemo(() => {
    const financial = filteredCompanies.filter(hasFinancialData).length
    const quote = filteredCompanies.filter((company) => company.stockPrice).length
    const estimated = filteredCompanies.filter(hasEstimate).length
    const warning = filteredCompanies.filter((company) => company.hasWarning).length
    return { financial, quote, estimated, warning }
  }, [filteredCompanies])

  const lanes = useMemo<Lane[]>(() => {
    const quality = filteredCompanies
      .map((company) => rankCompany(company, 'quality'))
      .sort(compareRanked)
    const capital = filteredCompanies
      .filter((company) => hasMetric(company, 'roic') || hasMetric(company, 'roicWaccSpread'))
      .map((company) => rankCompany(company, 'capital'))
      .sort(compareRanked)
    const cash = filteredCompanies
      .filter((company) => hasMetric(company, 'operatingCfMargin') || hasMetric(company, 'cashProfitGap'))
      .map((company) => rankCompany(company, 'cash'))
      .sort(compareRanked)
    const reaction = filteredCompanies
      .filter((company) => company.stockPrice?.changePercent !== undefined)
      .map((company) => rankCompany(company, 'momentum'))
      .sort(compareRanked)
    return [
      {
        key: 'quality',
        title: '安定して強い',
        subtitle: '収益性と安全性が両立',
        icon: Sparkles,
        items: quality.slice(0, 4),
      },
      {
        key: 'capital',
        title: '資本効率が良い',
        subtitle: 'ROICが資本コストを上回る',
        icon: Target,
        items: capital.slice(0, 4),
      },
      {
        key: 'cash',
        title: '現金品質が高い',
        subtitle: '利益がキャッシュで残る',
        icon: Zap,
        items: cash.slice(0, 4),
      },
      {
        key: 'momentum',
        title: '市場が反応中',
        subtitle: 'KPIと株価反応を同時確認',
        icon: TrendingUp,
        items: reaction.slice(0, 4),
      },
    ]
  }, [filteredCompanies])

  const fieldPoints = useMemo(
    () =>
      ranked
        .filter((item) => hasFinancialData(item.company))
        .slice(0, 24)
        .map((item, index) => {
          const axis = focusConfig.axis(item.company)
          const size = 9 + clamp(item.score, 0, 100) / 8
          const color =
            item.tone === 'strong'
              ? '#14b86a'
              : item.tone === 'steady'
                ? '#1677ff'
                : '#e17b2f'
          return {
            ...item,
            x: clamp(axis.x, 5, 95),
            y: clamp(axis.y, 5, 95),
            size,
            color,
            delay: `${Math.min(index * 18, 320)}ms`,
          }
        }),
    [focusConfig, ranked],
  )

  const visibleRanked = ranked.slice(0, visibleCount)

  const handleCompare = (company: Company) => {
    const ok = toggleCompare(company.id)
    setCompareNotice(ok ? '' : '比較は最大5社までです')
  }

  return (
    <div className="page kpi-map-page">
      <header className="kpi-map-hero">
        <div className="kpi-map-hero__copy">
          <span className="page-eyebrow">KPI MAP / LIGHT SIGNAL BOARD</span>
          <h1>KPI Map</h1>
          <p>
            上場企業の財務シグナルを、資本効率・現金品質・市場反応の軸で整理します。
          </p>
        </div>
        <div className="kpi-map-hero__stats" aria-label="KPI Map summary">
          <div>
            <span>VISIBLE</span>
            <strong><AnimatedNumber value={filteredCompanies.length} /></strong>
          </div>
          <div>
            <span>FINANCIAL</span>
            <strong><AnimatedNumber value={stats.financial} /></strong>
          </div>
          <div>
            <span>QUOTE</span>
            <strong><AnimatedNumber value={stats.quote} /></strong>
          </div>
        </div>
      </header>

      <section className="kpi-map-controls" aria-label="KPI Map filters">
        <label className="kpi-map-search">
          <Search size={17} />
          <input
            value={filter.query}
            onChange={(event) =>
              setFilter((current) => ({ ...current, query: event.target.value }))
            }
            placeholder="企業名・コードで検索"
          />
          {filter.query && (
            <button
              type="button"
              aria-label="検索をクリア"
              onClick={() => setFilter((current) => ({ ...current, query: '' }))}
            >
              <X size={15} />
            </button>
          )}
        </label>

        <div className="kpi-map-selects">
          <label>
            市場
            <select
              value={filter.market}
              onChange={(event) =>
                setFilter((current) => ({
                  ...current,
                  market: event.target.value as KpiMapFilter['market'],
                }))
              }
            >
              <option value="all">すべて</option>
              {marketsList.map((market) => (
                <option value={market} key={market}>
                  {market}
                </option>
              ))}
            </select>
          </label>
          <label>
            業種
            <select
              value={filter.industry}
              onChange={(event) =>
                setFilter((current) => ({ ...current, industry: event.target.value }))
              }
            >
              <option value="all">すべて</option>
              {industriesList.map((industry) => (
                <option value={industry} key={industry}>
                  {industry}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="kpi-map-mode-strip" role="tablist" aria-label="Focus mode">
          {(Object.entries(focusModes) as Array<[FocusMode, FocusConfig]>).map(
            ([key, item]) => (
              <button
                key={key}
                type="button"
                className={focus === key ? 'is-active' : ''}
                onClick={() => setFocus(key)}
              >
                <span>{item.shortLabel}</span>
                <strong>{item.label}</strong>
              </button>
            ),
          )}
        </div>

        <div className="kpi-map-filter-toggles">
          <label>
            <input
              type="checkbox"
              checked={filter.dataOnly}
              onChange={(event) =>
                setFilter((current) => ({ ...current, dataOnly: event.target.checked }))
              }
            />
            財務データあり
          </label>
          <label>
            <input
              type="checkbox"
              checked={filter.watchOnly}
              onChange={(event) =>
                setFilter((current) => ({ ...current, watchOnly: event.target.checked }))
              }
            />
            Watchlist
          </label>
          <label>
            <input
              type="checkbox"
              checked={filter.warningsOnly}
              onChange={(event) =>
                setFilter((current) => ({ ...current, warningsOnly: event.target.checked }))
              }
            />
            注意あり
          </label>
          <button
            type="button"
            onClick={() => {
              setFilter(initialFilter)
              setFocus('balanced')
            }}
          >
            <ListFilter size={15} />
            Reset
          </button>
        </div>
      </section>

      <main className="kpi-map-layout">
        <section className="kpi-map-main">
          <div className="kpi-map-board-head">
            <div>
              <span className="section-kicker">CURRENT FOCUS</span>
              <h2>{focusConfig.label}</h2>
              <p>{focusConfig.description}</p>
            </div>
            <div className="kpi-map-health">
              <span>{stats.estimated}社に推定指標</span>
              <span>{stats.warning}社に注意</span>
            </div>
          </div>

          <section className="kpi-map-lanes" aria-label="Signal lanes">
            {lanes.map((lane) => {
              const Icon = lane.icon
              return (
                <article className="kpi-map-lane" key={lane.key}>
                  <div className="kpi-map-lane__head">
                    <Icon size={17} />
                    <div>
                      <h3>{lane.title}</h3>
                      <p>{lane.subtitle}</p>
                    </div>
                  </div>
                  <div className="kpi-map-lane__list">
                    {lane.items.map((item, index) => (
                      <button
                        type="button"
                        className={
                          selectedCompany?.id === item.company.id
                            ? 'kpi-map-lane-item is-selected'
                            : 'kpi-map-lane-item'
                        }
                        key={`${lane.key}-${item.company.id}`}
                        onClick={() => setSelectedId(item.company.id)}
                      >
                        <span>{index + 1}</span>
                        <strong>{item.company.name}</strong>
                        <em>{Math.round(item.score)}</em>
                      </button>
                    ))}
                    {!lane.items.length && <p className="kpi-map-empty-line">該当なし</p>}
                  </div>
                </article>
              )
            })}
          </section>

          <section className="kpi-map-field" aria-label="Static KPI matrix">
            <div className="kpi-map-field__head">
              <div>
                <Map size={17} />
                <span>Light Matrix</span>
              </div>
              <p>
                上位候補の位置関係
              </p>
            </div>
            <div className="kpi-map-field__plot">
              <span className="kpi-map-axis kpi-map-axis--x">{focusConfig.xLabel}</span>
              <span className="kpi-map-axis kpi-map-axis--y">{focusConfig.yLabel}</span>
              {fieldPoints.map((item) => (
                <button
                  type="button"
                  key={item.company.id}
                  className={
                    selectedCompany?.id === item.company.id
                      ? 'kpi-map-point is-selected'
                      : `kpi-map-point is-${item.tone}`
                  }
                  style={
                    {
                      '--point-x': `${item.x}%`,
                      '--point-y': `${100 - item.y}%`,
                      '--point-size': `${item.size}px`,
                      '--point-color': item.color,
                      '--point-delay': item.delay,
                    } as CSSProperties
                  }
                  onClick={() => setSelectedId(item.company.id)}
                  aria-label={`${item.company.name} ${Math.round(item.score)}点`}
                >
                  <span>{item.company.code}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="kpi-map-shortlist" aria-label="Smart shortlist">
            <div className="kpi-map-section-title">
              <div>
                <span className="section-kicker">SMART LIST</span>
                <h2>候補リスト</h2>
              </div>
              <span>{visibleRanked.length} / {ranked.length}</span>
            </div>

            <div className="kpi-map-company-list">
              {visibleRanked.map((item, index) => (
                <article
                  key={item.company.id}
                  className={
                    selectedCompany?.id === item.company.id
                      ? `kpi-map-company is-${item.tone} is-selected`
                      : `kpi-map-company is-${item.tone}`
                  }
                >
                  <button
                    type="button"
                    className="kpi-map-company__select"
                    onClick={() => setSelectedId(item.company.id)}
                  >
                    <span className="kpi-map-company__rank">{index + 1}</span>
                    <div className="kpi-map-company__name">
                      <span>{item.company.code} / {item.company.market}</span>
                      <strong>{item.company.name}</strong>
                      <em>{item.company.industry}</em>
                    </div>
                    <div className="kpi-map-company__score">
                      <strong>{Math.round(item.score)}</strong>
                      <span>signal</span>
                    </div>
                  </button>

                  <div className="kpi-map-company__meta">
                    <span>{dataLabel(item.company)}</span>
                    <span>{formatRevenue(item.company)}</span>
                    {item.hasEstimate && <span className="is-estimated">推定あり</span>}
                    {item.company.hasWarning && <span className="is-warning">注意</span>}
                  </div>

                  <div className="kpi-map-company__reasons">
                    {item.reasons.map((reason) => (
                      <span key={reason}>{reason}</span>
                    ))}
                  </div>

                  <div className="kpi-map-company__actions">
                    <button
                      type="button"
                      aria-label="ウォッチリスト"
                      className={isWatched(item.company.id) ? 'is-active' : ''}
                      onClick={() => toggleWatchlist(item.company.id)}
                    >
                      <Bookmark
                        size={15}
                        fill={isWatched(item.company.id) ? 'currentColor' : 'none'}
                      />
                    </button>
                    <button
                      type="button"
                      aria-label="比較"
                      className={isCompared(item.company.id) ? 'is-active' : ''}
                      disabled={!hasFinancialData(item.company) || (!isCompared(item.company.id) && compareList.length >= 5)}
                      onClick={() => handleCompare(item.company)}
                    >
                      <GitCompareArrows size={15} />
                    </button>
                    <Link aria-label="詳細" to={`/company/${item.company.id}`}>
                      <ChevronRight size={16} />
                    </Link>
                  </div>
                </article>
              ))}
            </div>

            {visibleCount < ranked.length && (
              <button
                type="button"
                className="kpi-map-load-more"
                onClick={() => setVisibleCount((current) => current + 28)}
              >
                さらに表示
              </button>
            )}

            {!ranked.length && (
              <div className="kpi-map-empty-state">
                <Search size={24} />
                <strong>条件に合う企業がありません</strong>
                <span>検索条件かフィルターを少しゆるめてください。</span>
              </div>
            )}
          </section>
        </section>

        <aside className="kpi-map-detail" aria-label="Selected company detail">
          {selectedCompany ? (
            <>
              <div className="kpi-map-detail__head">
                <div>
                  <span>{selectedCompany.code} / {selectedCompany.market}</span>
                  <h2>{selectedCompany.name}</h2>
                  <p>{selectedCompany.industry}</p>
                </div>
                <ScoreBadge
                  score={selectedCompany.scores.overall}
                  compact
                  available={hasScorableData(selectedCompany)}
                />
              </div>

              <div className="kpi-map-detail__quote">
                <div>
                  <span>株価</span>
                  <strong>
                    {selectedCompany.stockPrice
                      ? formatStockPrice(selectedCompany.stockPrice.close)
                      : '—'}
                  </strong>
                </div>
                <div>
                  <span>変化率</span>
                  <strong
                    className={
                      (selectedCompany.stockPrice?.changePercent ?? 0) >= 0
                        ? 'is-up'
                        : 'is-down'
                    }
                  >
                    {(selectedCompany.stockPrice?.changePercent ?? 0) >= 0 ? (
                      <ArrowUpRight size={16} />
                    ) : (
                      <ArrowDownRight size={16} />
                    )}
                    {formatChangePercent(selectedCompany.stockPrice?.changePercent)}
                  </strong>
                </div>
                <div>
                  <span>出来高</span>
                  <strong>{formatVolume(selectedCompany.stockPrice?.volume)}</strong>
                </div>
              </div>

              <div className="kpi-map-detail__scores">
                <ScoreBar
                  label={scoreLabels.profitability}
                  score={selectedCompany.scores.profitability}
                  available={hasScorableData(selectedCompany)}
                />
                <ScoreBar
                  label={scoreLabels.safety}
                  score={selectedCompany.scores.safety}
                  available={hasScorableData(selectedCompany)}
                />
                <ScoreBar
                  label={scoreLabels.cashGeneration}
                  score={selectedCompany.scores.cashGeneration}
                  available={hasScorableData(selectedCompany)}
                />
              </div>

              <div className="kpi-map-detail__metrics">
                {visibleMetricKeys.map((key) => {
                  const metric = selectedCompany.metrics[key]
                  return (
                    <div key={key}>
                      <span>
                        {metricLabels[key]}
                        {metric?.estimated && <em>推定</em>}
                      </span>
                      <strong>{metric ? formatMetric(metric) : '—'}</strong>
                    </div>
                  )
                })}
              </div>

              <div className="kpi-map-detail__tags">
                <span className={hasFinancialData(selectedCompany) ? 'is-ready' : ''}>
                  {dataLabel(selectedCompany)}
                </span>
                <span className={hasEstimate(selectedCompany) ? 'is-estimated' : 'is-ready'}>
                  {hasEstimate(selectedCompany) ? '推定指標あり' : '実測中心'}
                </span>
                {selectedCompany.hasWarning ? (
                  <span className="is-warning">
                    <AlertTriangle size={13} />
                    注意 {selectedCompany.warnings.length}
                  </span>
                ) : (
                  <span className="is-ready">注意なし</span>
                )}
              </div>

              <div className="kpi-map-detail__memo">
                <h3>見るポイント</h3>
                <ul>
                  {(selectedCompany.strengths.length
                    ? selectedCompany.strengths
                    : selectedRank?.reasons ?? []
                  ).slice(0, 3).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                  {selectedCompany.warnings.slice(0, 2).map((item) => (
                    <li className="is-warning" key={item}>{item}</li>
                  ))}
                </ul>
              </div>

              <div className="kpi-map-detail__actions">
                <button
                  type="button"
                  className={`button ${isWatched(selectedCompany.id) ? 'button--active' : 'button--secondary'}`}
                  onClick={() => toggleWatchlist(selectedCompany.id)}
                >
                  <Bookmark
                    size={16}
                    fill={isWatched(selectedCompany.id) ? 'currentColor' : 'none'}
                  />
                  {isWatched(selectedCompany.id) ? '登録済み' : 'ウォッチ'}
                </button>
                <button
                  type="button"
                  className={`button ${isCompared(selectedCompany.id) ? 'button--active' : 'button--secondary'}`}
                  disabled={!hasFinancialData(selectedCompany) || (!isCompared(selectedCompany.id) && compareList.length >= 5)}
                  onClick={() => handleCompare(selectedCompany)}
                >
                  <GitCompareArrows size={16} />
                  {isCompared(selectedCompany.id) ? '比較中' : '比較'}
                </button>
                <Link className="button button--ghost" to={`/company/${selectedCompany.id}`}>
                  詳細
                  <ChevronRight size={16} />
                </Link>
              </div>
              {compareNotice && <small className="kpi-map-notice">{compareNotice}</small>}
            </>
          ) : (
            <div className="kpi-map-detail__empty">
              <LineChart size={26} />
              <strong>Signal standby</strong>
              <span>候補を選ぶと、ここに主要指標と判断材料が出ます。</span>
            </div>
          )}
        </aside>
      </main>
    </div>
  )
}
