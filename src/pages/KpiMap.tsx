import {
  AlertTriangle,
  ArrowRight,
  Bookmark,
  Check,
  ChevronRight,
  GitCompareArrows,
  Landmark,
  ListFilter,
  Search,
  ShieldCheck,
  Sparkles,
  WalletCards,
  X,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import AnimatedNumber from '../components/AnimatedNumber'
import { useApp } from '../context/AppContext'
import { industriesList, marketsList } from '../lib/companyUniverse'
import { formatMetric } from '../lib/formatters'
import { hasFinancialData } from '../lib/liveData'
import type { Company, KpiKey, Market } from '../types'

type FinderMode = 'balanced' | 'capital' | 'safety' | 'cash'

interface FinderFilter {
  query: string
  market: Market | 'all'
  industry: string | 'all'
  watchOnly: boolean
  rankableOnly: boolean
  excludeWarnings: boolean
}

interface MetricRule {
  key: KpiKey
  weight: number
  min: number
  max: number
  inverse?: boolean
  signOnly?: boolean
}

interface FinderConfig {
  label: string
  kicker: string
  question: string
  description: string
  formula: string
  icon: typeof Sparkles
  rules: MetricRule[]
  columns: Array<{ key: KpiKey; label: string }>
  minimumMetrics: number
}

interface RankedCompany {
  company: Company
  score: number
  coverage: number
  availableMetrics: number
  rankable: boolean
  estimated: boolean
  reasons: string[]
}

const initialFilter: FinderFilter = {
  query: '',
  market: 'all',
  industry: 'all',
  watchOnly: false,
  rankableOnly: true,
  excludeWarnings: false,
}

const focusConfigs: Record<FinderMode, FinderConfig> = {
  balanced: {
    label: '総合力',
    kicker: 'ALL-ROUND',
    question: '収益・資本・安全・現金がそろう企業は？',
    description:
      '特定の指標だけで決めず、稼ぐ力・資本効率・財務余力・キャッシュの裏付けを均等に確認します。',
    formula: '収益力 25% + 資本効率 30% + 財務安全性 20% + 現金品質 25%',
    icon: Sparkles,
    rules: [
      { key: 'operatingMargin', weight: 0.12, min: -10, max: 30 },
      { key: 'netMargin', weight: 0.08, min: -10, max: 20 },
      { key: 'roe', weight: 0.1, min: -10, max: 30 },
      { key: 'roa', weight: 0.07, min: -5, max: 15 },
      { key: 'roic', weight: 0.14, min: -5, max: 25 },
      { key: 'roicWaccSpread', weight: 0.12, min: -12, max: 15 },
      { key: 'wacc', weight: 0.04, min: 3, max: 14, inverse: true },
      { key: 'equityRatio', weight: 0.13, min: 0, max: 80 },
      { key: 'operatingCfMargin', weight: 0.14, min: -10, max: 30 },
      { key: 'cashProfitGap', weight: 0.06, min: -12, max: 12 },
    ],
    columns: [
      { key: 'roe', label: 'ROE' },
      { key: 'roicWaccSpread', label: 'ROIC−WACC' },
      { key: 'operatingCfMargin', label: '営業CF率' },
    ],
    minimumMetrics: 5,
  },
  capital: {
    label: '資本効率',
    kicker: 'CAPITAL EDGE',
    question: '投じた資本以上の価値を生んでいる企業は？',
    description:
      'ROICが高いだけでなく、資本コストをどれだけ上回れているかまで見て順位付けします。',
    formula: 'ROIC 45% + ROIC−WACC 35% + 低いWACC 20%',
    icon: Landmark,
    rules: [
      { key: 'roic', weight: 0.45, min: -5, max: 25 },
      { key: 'roicWaccSpread', weight: 0.35, min: -12, max: 15 },
      { key: 'wacc', weight: 0.2, min: 3, max: 14, inverse: true },
    ],
    columns: [
      { key: 'roic', label: 'ROIC' },
      { key: 'wacc', label: 'WACC' },
      { key: 'roicWaccSpread', label: '超過収益力' },
    ],
    minimumMetrics: 2,
  },
  safety: {
    label: '財務安全性',
    kicker: 'RESILIENCE',
    question: '逆風でも守りが崩れにくい企業は？',
    description:
      '自己資本の厚さを中心に、資産効率・資本コスト・ネットキャッシュの正負を確認します。',
    formula: '自己資本比率 50% + ROA 20% + 低いWACC 15% + ネットキャッシュ 15%',
    icon: ShieldCheck,
    rules: [
      { key: 'equityRatio', weight: 0.5, min: 0, max: 80 },
      { key: 'roa', weight: 0.2, min: -5, max: 15 },
      { key: 'wacc', weight: 0.15, min: 3, max: 14, inverse: true },
      { key: 'netCash', weight: 0.15, min: 0, max: 1, signOnly: true },
    ],
    columns: [
      { key: 'equityRatio', label: '自己資本比率' },
      { key: 'netCash', label: 'ネットキャッシュ' },
      { key: 'roa', label: 'ROA' },
    ],
    minimumMetrics: 2,
  },
  cash: {
    label: '現金品質',
    kicker: 'CASH QUALITY',
    question: '利益がきちんと現金で残っている企業は？',
    description:
      '営業キャッシュフローの厚さと利益との差を重視し、帳簿上の利益だけに偏らず比べます。',
    formula: '営業CF率 55% + CF利益差 25% + 純利益率 10% + ネットキャッシュ 10%',
    icon: WalletCards,
    rules: [
      { key: 'operatingCfMargin', weight: 0.55, min: -10, max: 30 },
      { key: 'cashProfitGap', weight: 0.25, min: -12, max: 12 },
      { key: 'netMargin', weight: 0.1, min: -10, max: 20 },
      { key: 'netCash', weight: 0.1, min: 0, max: 1, signOnly: true },
    ],
    columns: [
      { key: 'operatingCfMargin', label: '営業CF率' },
      { key: 'cashProfitGap', label: 'CF利益差' },
      { key: 'netCash', label: 'ネットキャッシュ' },
    ],
    minimumMetrics: 2,
  },
}

const clamp = (value: number, min = 0, max = 100) =>
  Math.max(min, Math.min(max, value))

const finiteMetric = (company: Company, key: KpiKey) => {
  const metric = company.metrics[key]
  if (!metric || metric.available === false || !Number.isFinite(metric.value)) {
    return undefined
  }
  return metric.value
}

const metricScore = (value: number, rule: MetricRule) => {
  if (rule.signOnly) {
    if (value > 0) return 82
    if (value < 0) return 22
    return 50
  }
  const normalized = clamp(((value - rule.min) / (rule.max - rule.min)) * 100)
  return rule.inverse ? 100 - normalized : normalized
}

const calculateScore = (company: Company, config: FinderConfig) => {
  let weightedScore = 0
  let availableWeight = 0
  let availableMetrics = 0

  config.rules.forEach((rule) => {
    const value = finiteMetric(company, rule.key)
    if (value === undefined) return
    weightedScore += metricScore(value, rule) * rule.weight
    availableWeight += rule.weight
    availableMetrics += 1
  })

  const totalWeight = config.rules.reduce((sum, rule) => sum + rule.weight, 0)
  const coverage = totalWeight ? availableWeight / totalWeight : 0
  const rawScore = availableWeight ? weightedScore / availableWeight : 0
  const missingDataAdjustment = 0.74 + coverage * 0.26

  return {
    score: clamp(rawScore * missingDataAdjustment),
    coverage,
    availableMetrics,
    rankable: availableMetrics >= config.minimumMetrics,
  }
}

const formatMetricValue = (company: Company, key: KpiKey) => {
  const metric = company.metrics[key]
  return metric ? formatMetric(metric) : '—'
}

const hasEstimatedMetric = (company: Company, config: FinderConfig) =>
  config.rules.some((rule) => company.metrics[rule.key]?.estimated)

const buildReasons = (company: Company, config: FinderConfig) =>
  config.columns
    .filter(({ key }) => finiteMetric(company, key) !== undefined)
    .map(({ key, label }) => `${label} ${formatMetricValue(company, key)}`)
    .slice(0, 2)

const rankCompany = (company: Company, config: FinderConfig): RankedCompany => {
  const result = calculateScore(company, config)
  return {
    company,
    ...result,
    estimated: hasEstimatedMetric(company, config),
    reasons: buildReasons(company, config),
  }
}

const compareRanked = (a: RankedCompany, b: RankedCompany) => {
  if (a.rankable !== b.rankable) return a.rankable ? -1 : 1
  if (b.score !== a.score) return b.score - a.score
  return a.company.code.localeCompare(b.company.code, 'ja-JP')
}

const scoreTone = (score: number) => {
  if (score >= 72) return 'high'
  if (score >= 54) return 'mid'
  return 'low'
}

const dataStatus = (item: RankedCompany) => {
  if (!item.rankable) return '判定データ不足'
  if (item.estimated) return '推定を含む'
  if (item.coverage >= 0.8) return '実測中心'
  return '一部指標なし'
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
  const [mode, setMode] = useState<FinderMode>('balanced')
  const [filter, setFilter] = useState<FinderFilter>(initialFilter)
  const [visibleCount, setVisibleCount] = useState(30)
  const [compareNotice, setCompareNotice] = useState('')

  const config = focusConfigs[mode]
  const MethodIcon = config.icon
  const watchedIds = useMemo(() => new Set(watchlist), [watchlist])

  const allRanked = useMemo(
    () => companies.map((company) => rankCompany(company, config)),
    [companies, config],
  )

  const ranked = useMemo(() => {
    const query = filter.query.trim().toLowerCase()
    return allRanked
      .filter((item) => {
        const { company } = item
        const matchesQuery =
          !query ||
          company.name.toLowerCase().includes(query) ||
          company.code.toLowerCase().includes(query)
        const matchesMarket =
          filter.market === 'all' || company.market === filter.market
        const matchesIndustry =
          filter.industry === 'all' || company.industry === filter.industry
        const matchesWatch = !filter.watchOnly || watchedIds.has(company.id)
        const matchesData =
          !filter.rankableOnly || (hasFinancialData(company) && item.rankable)
        const matchesWarnings =
          !filter.excludeWarnings || !company.hasWarning
        return (
          matchesQuery &&
          matchesMarket &&
          matchesIndustry &&
          matchesWatch &&
          matchesData &&
          matchesWarnings
        )
      })
      .sort(compareRanked)
  }, [allRanked, filter, watchedIds])

  const stats = useMemo(() => {
    const rankable = allRanked.filter(
      (item) => hasFinancialData(item.company) && item.rankable,
    )
    return {
      rankable: rankable.length,
      highCoverage: rankable.filter((item) => item.coverage >= 0.8).length,
      estimated: rankable.filter((item) => item.estimated).length,
    }
  }, [allRanked])

  const topThree = ranked.filter((item) => item.rankable).slice(0, 3)
  const visibleRanked = ranked.slice(0, visibleCount)

  const updateFilter = (next: Partial<FinderFilter>) => {
    setFilter((current) => ({ ...current, ...next }))
    setVisibleCount(30)
  }

  const selectMode = (nextMode: FinderMode) => {
    setMode(nextMode)
    setVisibleCount(30)
    setCompareNotice('')
  }

  const handleCompare = (company: Company) => {
    const ok = toggleCompare(company.id)
    setCompareNotice(ok ? '' : '比較は最大5社までです。登録中の企業を1社外してください。')
  }

  return (
    <div className="page kpi-finder-page">
      <header className="kpi-finder-hero">
        <div className="kpi-finder-hero__copy">
          <span className="page-eyebrow">KPI FINDER / DECISION SHORTLIST</span>
          <h1>目的から、見るべき企業を絞る。</h1>
          <p>
            知りたいことを1つ選ぶと、同じ基準で企業を順位付けします。
            点数だけでなく、順位の根拠と使用データまで確認できます。
          </p>
        </div>
        <ol className="kpi-finder-guide" aria-label="KPI Finderの使い方">
          <li>
            <span>1</span>
            <div><strong>目的を選ぶ</strong><small>4つの観点から選択</small></div>
          </li>
          <li>
            <span>2</span>
            <div><strong>根拠を確認</strong><small>主要KPIとデータ状態</small></div>
          </li>
          <li>
            <span>3</span>
            <div><strong>比較に送る</strong><small>最大5社を横並び</small></div>
          </li>
        </ol>
      </header>

      <section className="kpi-finder-modes" aria-label="分析目的を選ぶ">
        {(Object.entries(focusConfigs) as Array<[FinderMode, FinderConfig]>).map(
          ([key, item]) => {
            const Icon = item.icon
            return (
              <button
                type="button"
                key={key}
                className={mode === key ? 'is-active' : ''}
                onClick={() => selectMode(key)}
                aria-pressed={mode === key}
              >
                <span className="kpi-finder-mode__icon"><Icon size={19} /></span>
                <span className="kpi-finder-mode__text">
                  <small>{item.kicker}</small>
                  <strong>{item.label}</strong>
                  <em>{item.question}</em>
                </span>
                <span className="kpi-finder-mode__check">
                  {mode === key ? <Check size={15} /> : <ChevronRight size={15} />}
                </span>
              </button>
            )
          },
        )}
      </section>

      <section className="kpi-finder-method" aria-live="polite">
        <div className="kpi-finder-method__icon"><MethodIcon size={22} /></div>
        <div className="kpi-finder-method__copy">
          <span>現在の目的</span>
          <h2>{config.label}</h2>
          <p>{config.description}</p>
        </div>
        <div className="kpi-finder-method__formula">
          <span>順位のつくり方</span>
          <strong>{config.formula}</strong>
          <small>欠損が多い企業はスコアを調整。ネットキャッシュは規模差を避けるため正負のみ評価。</small>
        </div>
        <div className="kpi-finder-method__stats">
          <div><span>判定可能</span><strong><AnimatedNumber value={stats.rankable} /></strong><small>社</small></div>
          <div><span>充足度80%+</span><strong><AnimatedNumber value={stats.highCoverage} /></strong><small>社</small></div>
          <div><span>推定を含む</span><strong><AnimatedNumber value={stats.estimated} /></strong><small>社</small></div>
        </div>
      </section>

      <section className="kpi-finder-controls" aria-label="候補を絞り込む">
        <label className="kpi-finder-search">
          <Search size={17} />
          <input
            value={filter.query}
            onChange={(event) => updateFilter({ query: event.target.value })}
            placeholder="この順位表を企業名・コードで絞り込む"
          />
          {filter.query && (
            <button
              type="button"
              onClick={() => updateFilter({ query: '' })}
              aria-label="入力をクリア"
            >
              <X size={15} />
            </button>
          )}
        </label>

        <div className="kpi-finder-selects">
          <label>
            <span>市場</span>
            <select
              value={filter.market}
              onChange={(event) =>
                updateFilter({ market: event.target.value as FinderFilter['market'] })
              }
            >
              <option value="all">すべての市場</option>
              {marketsList.map((market) => (
                <option value={market} key={market}>{market}</option>
              ))}
            </select>
          </label>
          <label>
            <span>業種</span>
            <select
              value={filter.industry}
              onChange={(event) => updateFilter({ industry: event.target.value })}
            >
              <option value="all">すべての業種</option>
              {industriesList.map((industry) => (
                <option value={industry} key={industry}>{industry}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="kpi-finder-toggles">
          <label>
            <input
              type="checkbox"
              checked={filter.rankableOnly}
              onChange={(event) => updateFilter({ rankableOnly: event.target.checked })}
            />
            <span>判定可能のみ</span>
          </label>
          <label>
            <input
              type="checkbox"
              checked={filter.excludeWarnings}
              onChange={(event) => updateFilter({ excludeWarnings: event.target.checked })}
            />
            <span>注意企業を除く</span>
          </label>
          <label>
            <input
              type="checkbox"
              checked={filter.watchOnly}
              onChange={(event) => updateFilter({ watchOnly: event.target.checked })}
            />
            <span>ウォッチのみ</span>
          </label>
          <button
            type="button"
            onClick={() => {
              setFilter(initialFilter)
              setVisibleCount(30)
            }}
          >
            <ListFilter size={15} />
            条件をリセット
          </button>
        </div>
      </section>

      {topThree.length > 0 && (
        <section className="kpi-finder-podium" aria-label={`${config.label}の上位3社`}>
          <div className="kpi-finder-section-head">
            <div>
              <span className="section-kicker">TOP PICKS</span>
              <h2>{config.label}の上位3社</h2>
              <p>まず見るならこの3社。指標値を確認してから比較へ追加できます。</p>
            </div>
            {compareList.length > 0 && (
              <Link className="kpi-finder-compare-link" to="/compare">
                比較中 {compareList.length}/5
                <ArrowRight size={15} />
              </Link>
            )}
          </div>
          <div className="kpi-finder-podium__grid">
            {topThree.map((item, index) => (
              <article className={`kpi-finder-pick is-${index + 1}`} key={item.company.id}>
                <div className="kpi-finder-pick__head">
                  <span className="kpi-finder-pick__rank">{index + 1}</span>
                  <div>
                    <small>{item.company.code} · {item.company.market}</small>
                    <Link to={`/company/${item.company.id}`}>{item.company.name}</Link>
                    <span>{item.company.industry}</span>
                  </div>
                  <div className={`kpi-finder-score is-${scoreTone(item.score)}`}>
                    <strong>{Math.round(item.score)}</strong>
                    <span>適合度</span>
                  </div>
                </div>
                <div className="kpi-finder-pick__metrics">
                  {config.columns.map(({ key, label }) => (
                    <div key={key}>
                      <span>{label}</span>
                      <strong>{formatMetricValue(item.company, key)}</strong>
                    </div>
                  ))}
                </div>
                <div className="kpi-finder-pick__foot">
                  <span className={`kpi-finder-data-state ${item.estimated ? 'is-estimated' : ''}`}>
                    {dataStatus(item)}
                  </span>
                  <div>
                    <button
                      type="button"
                      className={isWatched(item.company.id) ? 'is-active' : ''}
                      onClick={() => toggleWatchlist(item.company.id)}
                      aria-label={`${item.company.name}をウォッチ`}
                    >
                      <Bookmark size={15} fill={isWatched(item.company.id) ? 'currentColor' : 'none'} />
                    </button>
                    <button
                      type="button"
                      className={isCompared(item.company.id) ? 'is-active' : ''}
                      disabled={!isCompared(item.company.id) && compareList.length >= 5}
                      onClick={() => handleCompare(item.company)}
                      aria-label={`${item.company.name}を比較`}
                    >
                      <GitCompareArrows size={15} />
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="kpi-finder-ranking" aria-label={`${config.label}の順位表`}>
        <div className="kpi-finder-section-head">
          <div>
            <span className="section-kicker">RANKING WITH EVIDENCE</span>
            <h2>根拠つき順位表</h2>
            <p>{ranked.length.toLocaleString('ja-JP')}社が現在の条件に一致</p>
          </div>
          <div className="kpi-finder-legend">
            <span><i className="is-high" />72以上</span>
            <span><i className="is-mid" />54–71</span>
            <span><i className="is-low" />53以下</span>
          </div>
        </div>

        {visibleRanked.length > 0 ? (
          <div className="kpi-finder-table-wrap">
            <div className="kpi-finder-table-head" aria-hidden="true">
              <span>順位</span>
              <span>企業</span>
              <span>適合度</span>
              {config.columns.map(({ key, label }) => <span key={key}>{label}</span>)}
              <span>順位の根拠</span>
              <span>操作</span>
            </div>
            <div className="kpi-finder-rows">
              {visibleRanked.map((item, index) => (
                <article className="kpi-finder-row" key={item.company.id}>
                  <span className="kpi-finder-row__rank">{index + 1}</span>
                  <div className="kpi-finder-row__company">
                    <span>{item.company.code} · {item.company.market}</span>
                    <Link to={`/company/${item.company.id}`}>{item.company.name}</Link>
                    <small>{item.company.industry}</small>
                  </div>
                  <div className={`kpi-finder-score is-${scoreTone(item.score)}`}>
                    <strong>{item.rankable ? Math.round(item.score) : '—'}</strong>
                    <span>{item.rankable ? '適合度' : '判定不可'}</span>
                  </div>
                  {config.columns.map(({ key, label }) => (
                    <div className="kpi-finder-row__metric" key={key} data-label={label}>
                      <span>{label}</span>
                      <strong>{formatMetricValue(item.company, key)}</strong>
                      {item.company.metrics[key]?.estimated && <em>推定</em>}
                    </div>
                  ))}
                  <div className="kpi-finder-row__evidence">
                    <div>
                      {item.reasons.length ? item.reasons.map((reason) => (
                        <span key={reason}>{reason}</span>
                      )) : <span>表示できる主要指標なし</span>}
                    </div>
                    <small className={item.company.hasWarning ? 'is-warning' : ''}>
                      {item.company.hasWarning && <AlertTriangle size={12} />}
                      {item.company.hasWarning
                        ? `注意 ${item.company.warnings.length}件`
                        : dataStatus(item)}
                    </small>
                  </div>
                  <div className="kpi-finder-row__actions">
                    <button
                      type="button"
                      className={isWatched(item.company.id) ? 'is-active' : ''}
                      onClick={() => toggleWatchlist(item.company.id)}
                      title="ウォッチ"
                    >
                      <Bookmark size={15} fill={isWatched(item.company.id) ? 'currentColor' : 'none'} />
                    </button>
                    <button
                      type="button"
                      className={isCompared(item.company.id) ? 'is-active' : ''}
                      disabled={!item.rankable || (!isCompared(item.company.id) && compareList.length >= 5)}
                      onClick={() => handleCompare(item.company)}
                      title="比較"
                    >
                      <GitCompareArrows size={15} />
                    </button>
                    <Link to={`/company/${item.company.id}`} title="企業詳細">
                      <ChevronRight size={16} />
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          </div>
        ) : (
          <div className="kpi-finder-empty">
            <Search size={24} />
            <strong>条件に合う企業がありません</strong>
            <span>市場・業種・チェック条件を少しゆるめてください。</span>
          </div>
        )}

        {visibleCount < ranked.length && (
          <button
            type="button"
            className="kpi-finder-more"
            onClick={() => setVisibleCount((current) => current + 30)}
          >
            次の30社を表示
          </button>
        )}
      </section>

      {compareNotice && (
        <div className="kpi-finder-notice" role="status">
          <AlertTriangle size={15} />
          {compareNotice}
          <Link to="/compare">比較画面へ</Link>
        </div>
      )}
    </div>
  )
}
