import { formatMetric } from './formatters'
import type {
  AnalysisLevel,
  CompanyMetrics,
  IndustryKpi,
  KpiKey,
  KpiMetric,
} from '../types'

const metricLabels: Record<KpiKey, string> = {
  revenueGrowth: '売上成長率',
  operatingIncomeGrowth: '営業利益成長率',
  epsGrowth: 'EPS成長率',
  operatingMargin: '営業利益率',
  netMargin: '純利益率',
  roe: 'ROE',
  roa: 'ROA',
  roic: 'ROIC',
  equityRatio: '自己資本比率',
  operatingCfMargin: '営業CFマージン',
  debtRatio: '有利子負債倍率',
  netCash: 'ネットキャッシュ',
  wacc: 'WACC',
  ebitda: 'EBITDA',
  inventoryGrowth: '棚卸資産増加率',
  receivablesGrowth: '売掛金増加率',
  per: 'PER',
  pbr: 'PBR',
  evEbitda: 'EV/EBITDA',
}

const insightCandidates: readonly KpiKey[] = [
  'revenueGrowth',
  'operatingIncomeGrowth',
  'epsGrowth',
  'operatingMargin',
  'netMargin',
  'roe',
  'roa',
  'roic',
  'equityRatio',
  'debtRatio',
  'operatingCfMargin',
  'netCash',
  'wacc',
  'ebitda',
  'inventoryGrowth',
  'receivablesGrowth',
  'per',
  'pbr',
  'evEbitda',
]

const isAvailable = (metric: KpiMetric) =>
  metric.available !== false && metric.applicable !== false

const signalForMetric = (metric: KpiMetric): IndustryKpi['signal'] => {
  if (metric.status === 'good') return 'positive'
  if (metric.status === 'warning') return 'negative'
  return 'neutral'
}

export const getAnalysisLevel = (
  trustedCount: number,
  displayCount: number,
  applicableCount: number,
): AnalysisLevel => {
  if (displayCount === 0) return 'unavailable'
  if (trustedCount === 0) return 'reference'
  const fullThreshold = Math.min(4, Math.max(1, applicableCount))
  return trustedCount >= fullThreshold ? 'full' : 'limited'
}

export const buildIndustryInsights = (
  metrics: CompanyMetrics,
  applicableKeys: ReadonlySet<KpiKey>,
): IndustryKpi[] => {
  const selected = new Set<KpiKey>()
  const groups: readonly (readonly KpiKey[])[] = [
    ['revenueGrowth', 'operatingIncomeGrowth', 'epsGrowth'],
    ['roic', 'roe', 'roa'],
    ['operatingMargin', 'netMargin'],
    ['equityRatio', 'debtRatio', 'wacc'],
    ['operatingCfMargin', 'ebitda', 'netCash'],
    ['inventoryGrowth'],
    ['receivablesGrowth'],
    ['evEbitda', 'per'],
    ['pbr'],
  ]

  for (const group of groups) {
    const key = group.find(
      (candidate) =>
        !selected.has(candidate) &&
        applicableKeys.has(candidate) &&
        isAvailable(metrics[candidate]),
    )
    if (key) selected.add(key)
    if (selected.size >= 4) break
  }

  if (selected.size < 4) {
    for (const key of insightCandidates) {
      if (
        !selected.has(key) &&
        applicableKeys.has(key) &&
        isAvailable(metrics[key])
      ) {
        selected.add(key)
      }
      if (selected.size >= 4) break
    }
  }

  return Array.from(selected).map((key) => {
    const metric = metrics[key]
    return {
      name: metricLabels[key],
      value: formatMetric(metric),
      signal: signalForMetric(metric),
      confidence: metric.confidence,
      reference:
        metric.confidence === 'C' || metric.confidence === 'review',
      note: metric.confidenceReason,
    }
  })
}

const labelList = (keys: ReadonlySet<KpiKey>, limit = 3) =>
  Array.from(keys)
    .slice(0, limit)
    .map((key) => metricLabels[key])
    .join('・')

export const buildTieredAnalysisComment = (
  baseComment: string,
  level: AnalysisLevel,
  trustedKeys: ReadonlySet<KpiKey>,
  displayKeys: ReadonlySet<KpiKey>,
): string => {
  if (level === 'full') return baseComment

  if (level === 'limited') {
    const trustedLabels = labelList(trustedKeys)
    return `信頼度A/Bの${trustedLabels || '取得済みKPI'}を中心に分析しています。取得項目が限られるため、表示中の参考KPIと原資料もあわせて確認してください。`
  }

  if (level === 'reference') {
    const referenceLabels = labelList(displayKeys)
    return `スコア対象となる信頼度A/BのKPIはまだありません。${referenceLabels || '取得済みKPI'}は参考値として確認できますが、単体開示や元タグ未移行を含むため原資料確認が必要です。`
  }

  return '比較可能な財務KPIを取得できていません。EDINET・TDnetの次回更新と会社の原資料を確認してください。'
}
