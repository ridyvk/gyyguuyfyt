import type {
  Company,
  CompanyMetrics,
  FinancialSnapshot,
  KpiKey,
  KpiMetric,
  KpiStatus,
  LiveFinancialRecord,
  LiveMetricValue,
  MarketFundamentals,
  MarketQuote,
  MarketSnapshot,
  Scores,
} from '../types'
import {
  buildAnalysisComment,
  buildStrengths,
  buildWarnings,
} from './analysis'
import { calculateScores, type RawMetrics } from './scoring'

const kpiKeys: KpiKey[] = [
  'revenueGrowth',
  'operatingMargin',
  'netMargin',
  'roe',
  'equityRatio',
  'operatingCfMargin',
  'debtRatio',
  'netCash',
  'inventoryGrowth',
  'receivablesGrowth',
  'per',
  'pbr',
]

const neutralMetrics: RawMetrics = {
  revenueGrowth: 0,
  operatingMargin: 5,
  netMargin: 3,
  roe: 8,
  equityRatio: 40,
  operatingCfMargin: 5,
  debtRatio: 1,
  netCash: 0,
  inventoryGrowth: 0,
  receivablesGrowth: 0,
  per: 20,
  pbr: 1.5,
}

const unavailableScores: Scores = {
  growth: 0,
  profitability: 0,
  safety: 0,
  cashGeneration: 0,
  valuation: 0,
  overall: 0,
}

const units: Record<KpiKey, KpiMetric['unit']> = {
  revenueGrowth: '%',
  operatingMargin: '%',
  netMargin: '%',
  roe: '%',
  equityRatio: '%',
  operatingCfMargin: '%',
  debtRatio: '倍',
  netCash: '億円',
  inventoryGrowth: '%',
  receivablesGrowth: '%',
  per: '倍',
  pbr: '倍',
}

const comments: Record<KpiKey, [string, string, string]> = {
  revenueGrowth: ['成長ペースが強い', '緩やかな成長', '成長鈍化を確認'],
  operatingMargin: ['高い収益力', '標準的な水準', '採算性に注意'],
  netMargin: ['最終利益も堅調', '利益は安定圏', '利益の薄さに注意'],
  roe: ['資本効率が良好', '標準的な効率', '資本効率に課題'],
  equityRatio: ['財務余力が厚い', '一定の安定性', '財務耐性を確認'],
  operatingCfMargin: ['現金創出力が強い', '安定したCF', '利益の質を確認'],
  debtRatio: ['負債負担が軽い', '許容範囲の負債', '返済負担に注意'],
  netCash: ['手元流動性が豊富', '資金余力は中立', '実質有利子負債'],
  inventoryGrowth: ['在庫管理は良好', '売上と概ね連動', '在庫積み上がり'],
  receivablesGrowth: ['回収状況は良好', '売上と概ね連動', '回収条件を確認'],
  per: ['利益比で割安', '市場平均圏', '期待先行の水準'],
  pbr: ['純資産比で割安', '妥当な評価', '資産比で高評価'],
}

const round = (value: number, digits = 1) => {
  const factor = 10 ** digits
  return Math.round(value * factor) / factor
}

const hasFiniteNumber = (value: number | undefined): value is number =>
  value !== undefined && Number.isFinite(value)

const metricStatus = (key: KpiKey, value: number): KpiStatus => {
  const thresholds: Record<KpiKey, [number, number, boolean]> = {
    revenueGrowth: [3, 10, true],
    operatingMargin: [5, 12, true],
    netMargin: [2, 8, true],
    roe: [7, 12, true],
    equityRatio: [30, 50, true],
    operatingCfMargin: [4, 10, true],
    debtRatio: [1.5, 0.8, false],
    netCash: [0, 180, true],
    inventoryGrowth: [15, 7, false],
    receivablesGrowth: [15, 7, false],
    per: [35, 18, false],
    pbr: [3, 1.5, false],
  }
  const [normal, good, higherIsBetter] = thresholds[key]
  if (higherIsBetter) {
    if (value >= good) return 'good'
    if (value >= normal) return 'normal'
    return 'warning'
  }
  if (value <= good) return 'good'
  if (value <= normal) return 'normal'
  return 'warning'
}

const createUnavailableMetric = (key: KpiKey): KpiMetric => ({
  value: 0,
  unit: units[key],
  status: 'unknown',
  comment: '開示データから取得できません',
  trend: [],
  available: false,
})

const createLiveMetric = (
  key: KpiKey,
  value: number,
  previousValue?: number,
  trend?: number[],
): KpiMetric => {
  const status = metricStatus(key, value)
  const commentIndex = status === 'good' ? 0 : status === 'normal' ? 1 : 2
  const normalizedTrend =
    trend && trend.length >= 2
      ? trend
      : hasFiniteNumber(previousValue)
        ? [previousValue, value]
        : []

  return {
    value: round(value),
    ...(hasFiniteNumber(previousValue)
      ? { previousValue: round(previousValue) }
      : {}),
    unit: units[key],
    status,
    comment: comments[key][commentIndex],
    trend: normalizedTrend.map((point) => round(point)),
    available: true,
  }
}

const isUsableLiveMetric = (
  key: KpiKey,
  value: number,
) => {
  if (!Number.isFinite(value)) return false
  if (
    ['revenueGrowth', 'inventoryGrowth', 'receivablesGrowth'].includes(key) &&
    value < -100
  ) {
    return false
  }
  if (key === 'debtRatio' && value < 0) return false
  if (key === 'equityRatio' && (value < -100 || value > 100)) return false
  return true
}

const calculateLiveScores = (
  rawMetrics: RawMetrics,
  available: ReadonlySet<KpiKey>,
): Scores => {
  const scores = calculateScores(rawMetrics)
  const weighted: Array<[keyof Omit<Scores, 'overall'>, number, boolean]> = [
    ['growth', 0.22, available.has('revenueGrowth')],
    [
      'profitability',
      0.24,
      available.has('operatingMargin') || available.has('roe'),
    ],
    [
      'safety',
      0.2,
      available.has('equityRatio') || available.has('debtRatio'),
    ],
    [
      'cashGeneration',
      0.2,
      available.has('operatingCfMargin') || available.has('netCash'),
    ],
    ['valuation', 0.14, available.has('per') || available.has('pbr')],
  ]
  const active = weighted.filter(([, , isAvailable]) => isAvailable)
  const totalWeight = active.reduce((sum, [, weight]) => sum + weight, 0)
  scores.valuation = available.has('per') || available.has('pbr')
    ? scores.valuation
    : 50
  scores.overall = totalWeight
    ? active.reduce(
        (sum, [key, weight]) => sum + scores[key] * weight,
        0,
      ) / totalWeight
    : 50
  return scores
}

const valuationMetrics = (
  quote?: MarketQuote,
  fundamentals?: MarketFundamentals,
): Partial<Record<KpiKey, LiveMetricValue>> => {
  if (!quote || !fundamentals) return {}
  const metrics: Partial<Record<KpiKey, LiveMetricValue>> = {}
  const eps =
    fundamentals.forecastEps && fundamentals.forecastEps > 0
      ? fundamentals.forecastEps
      : fundamentals.eps
  const { bps } = fundamentals
  if (eps !== undefined && eps > 0) {
    metrics.per = {
      value: quote.close / eps,
      ...(quote.previousClose !== undefined
        ? {
            previousValue: quote.previousClose / eps,
            trend: [quote.previousClose / eps, quote.close / eps],
          }
        : {}),
    }
  }
  if (bps !== undefined && bps > 0) {
    metrics.pbr = {
      value: quote.close / bps,
      ...(quote.previousClose !== undefined
        ? {
            previousValue: quote.previousClose / bps,
            trend: [quote.previousClose / bps, quote.close / bps],
          }
        : {}),
    }
  }
  return metrics
}

const mergeRecord = (
  company: Company,
  record: LiveFinancialRecord,
  quote?: MarketQuote,
  fundamentals?: MarketFundamentals,
): Company => {
  const recordMetrics: Partial<Record<KpiKey, LiveMetricValue>> = {
    ...record.metrics,
    ...valuationMetrics(quote, fundamentals ?? record.valuation),
  }
  kpiKeys.forEach((key) => {
    const metric = recordMetrics[key]
    if (metric && !isUsableLiveMetric(key, metric.value)) {
      delete recordMetrics[key]
    }
  })
  const available = new Set(
    kpiKeys.filter((key) => recordMetrics[key] !== undefined),
  )
  const metrics = Object.fromEntries(
    kpiKeys.map((key) => {
      const live = recordMetrics[key]
      return [
        key,
        live
          ? createLiveMetric(
              key,
              live.value,
              live.previousValue,
              live.trend,
            )
          : createUnavailableMetric(key),
      ]
    }),
  ) as CompanyMetrics
  const rawMetrics = { ...neutralMetrics }
  kpiKeys.forEach((key) => {
    rawMetrics[key] = recordMetrics[key]?.value ?? neutralMetrics[key]
  })
  const history = record.history ?? []
  const previousOperatingMargin =
    recordMetrics.operatingMargin?.previousValue ??
    (history.length >= 2
      ? history[history.length - 2]?.operatingMargin
      : undefined) ??
    rawMetrics.operatingMargin
  const warnings = buildWarnings(
    rawMetrics,
    previousOperatingMargin,
    history,
    available,
  )

  return {
    ...company,
    metrics,
    history,
    industryKpis: [],
    scores: calculateLiveScores(rawMetrics, available),
    strengths: buildStrengths(rawMetrics, available),
    warnings,
    analysisComment: buildAnalysisComment(
      rawMetrics,
      warnings,
      previousOperatingMargin,
      available,
    ),
    hasWarning: warnings.length > 0,
    dataSource: record.source === 'TDnet' ? 'TDnet' : 'EDINET',
    dataUpdatedAt: record.filedAt,
    financialPeriod: record.periodEnd,
    financialSourceUrl: record.sourceUrl,
    liveMetricCount: available.size,
    stockPrice: quote,
  }
}

const createUnavailableCompany = (
  company: Company,
  quote?: MarketQuote,
): Company => ({
  ...company,
  metrics: Object.fromEntries(
    kpiKeys.map((key) => [key, createUnavailableMetric(key)]),
  ) as CompanyMetrics,
  history: [],
  industryKpis: [],
  scores: { ...unavailableScores },
  strengths: [],
  warnings: [],
  analysisComment:
    'EDINET・TDnetからこの企業の比較可能な財務データを取得できていないため、分析コメントは生成していません。',
  hasWarning: false,
  dataSource: 'unavailable',
  dataUpdatedAt: undefined,
  financialPeriod: undefined,
  financialSourceUrl: undefined,
  liveMetricCount: 0,
  stockPrice: quote,
})

export const hasFinancialData = (company: Company) =>
  company.dataSource === 'EDINET' || company.dataSource === 'TDnet'

export const loadFinancialSnapshot = async (): Promise<FinancialSnapshot> => {
  const url = `${import.meta.env.BASE_URL}data/financials.json?v=${Date.now()}`
  const response = await fetch(url, { cache: 'no-store' })
  if (!response.ok) {
    throw new Error(`Financial snapshot could not be loaded: ${response.status}`)
  }
  return response.json() as Promise<FinancialSnapshot>
}

export const loadMarketSnapshot = async (): Promise<MarketSnapshot> => {
  const url = `${import.meta.env.BASE_URL}data/market.json?v=${Date.now()}`
  const response = await fetch(url, { cache: 'no-store' })
  if (!response.ok) {
    throw new Error(`Market snapshot could not be loaded: ${response.status}`)
  }
  return response.json() as Promise<MarketSnapshot>
}

export const mergeLiveCompanies = (
  companies: Company[],
  snapshot: FinancialSnapshot | null,
  marketSnapshot: MarketSnapshot | null = null,
) =>
  companies.map((company) => {
    const record = snapshot?.records[company.code]
    const quote = marketSnapshot?.quotes[company.code]
    const fundamentals = marketSnapshot?.fundamentals[company.code]
    return record && record.code === company.code
      ? mergeRecord(company, record, quote, fundamentals)
      : createUnavailableCompany(company, quote)
  })
