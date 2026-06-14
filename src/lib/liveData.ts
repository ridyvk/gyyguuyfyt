import type {
  Company,
  CompanyMetrics,
  FinancialSnapshot,
  KpiKey,
  KpiMetric,
  KpiStatus,
  LiveFinancialRecord,
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
  previousValue: 0,
  unit: units[key],
  status: 'unknown',
  comment: '開示データから取得できません',
  trend: [],
  available: false,
})

const createLiveMetric = (
  key: KpiKey,
  value: number,
  previousValue = value,
  trend: number[] = [previousValue, value],
): KpiMetric => {
  const status = metricStatus(key, value)
  const commentIndex = status === 'good' ? 0 : status === 'normal' ? 1 : 2
  return {
    value: round(value),
    previousValue: round(previousValue),
    unit: units[key],
    status,
    comment: comments[key][commentIndex],
    trend: trend.map((point) => round(point)),
    available: true,
  }
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
): Partial<
  Record<KpiKey, { value: number; previousValue?: number; trend?: number[] }>
> => {
  if (!quote || !fundamentals) return {}
  const metrics: Partial<
    Record<KpiKey, { value: number; previousValue?: number; trend?: number[] }>
  > = {}
  const prices = [quote.previousClose, quote.close].filter(
    (value): value is number => value !== undefined,
  )
  const eps =
    fundamentals.forecastEps && fundamentals.forecastEps > 0
      ? fundamentals.forecastEps
      : fundamentals.eps
  const { bps } = fundamentals
  if (eps !== undefined && eps > 0) {
    metrics.per = {
      value: quote.close / eps,
      previousValue: quote.previousClose
        ? quote.previousClose / eps
        : quote.close / eps,
      trend: prices.map((price) => price / eps),
    }
  }
  if (bps !== undefined && bps > 0) {
    metrics.pbr = {
      value: quote.close / bps,
      previousValue: quote.previousClose
        ? quote.previousClose / bps
        : quote.close / bps,
      trend: prices.map((price) => price / bps),
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
  const recordMetrics = {
    ...record.metrics,
    ...valuationMetrics(quote, fundamentals),
  }
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
  const previousOperatingMargin =
    recordMetrics.operatingMargin?.previousValue ?? rawMetrics.operatingMargin
  const history = record.history
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
    dataSource: 'EDINET',
    dataUpdatedAt: record.filedAt,
    financialPeriod: record.periodEnd,
    liveMetricCount: available.size,
    stockPrice: quote,
  }
}

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
  snapshot: FinancialSnapshot,
  marketSnapshot: MarketSnapshot | null = null,
) =>
  companies.map((company) => {
    const record = snapshot.records[company.code]
    const quote = marketSnapshot?.quotes[company.code]
    const fundamentals = marketSnapshot?.fundamentals[company.code]
    return record
      ? mergeRecord(company, record, quote, fundamentals)
      : quote
        ? { ...company, stockPrice: quote }
        : company
  })
