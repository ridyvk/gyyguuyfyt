export type Market = 'プライム' | 'スタンダード' | 'グロース'

export type Industry = string

export interface ListedCompanyMaster {
  code: string
  name: string
  market: Market
  industry: Industry
}

export type ScoreKey =
  | 'growth'
  | 'profitability'
  | 'safety'
  | 'cashGeneration'
  | 'valuation'

export interface Scores extends Record<ScoreKey, number> {
  overall: number
}

export type KpiStatus = 'good' | 'normal' | 'warning' | 'unknown'

export type KpiKey =
  | 'revenueGrowth'
  | 'operatingMargin'
  | 'netMargin'
  | 'roe'
  | 'equityRatio'
  | 'operatingCfMargin'
  | 'debtRatio'
  | 'netCash'
  | 'inventoryGrowth'
  | 'receivablesGrowth'
  | 'per'
  | 'pbr'

export interface KpiMetric {
  value: number
  previousValue: number
  unit: '%' | '倍' | '億円'
  status: KpiStatus
  comment: string
  trend: number[]
  available?: boolean
}

export type CompanyMetrics = Record<KpiKey, KpiMetric>

export interface FinancialYearPoint {
  year: string
  revenue: number
  operatingMargin: number
  netMargin: number
  roe: number
  operatingCfMargin: number
}

export interface IndustryKpi {
  name: string
  value: string
  signal: 'positive' | 'neutral' | 'negative'
}

export interface Company {
  id: string
  name: string
  code: string
  market: Market
  industry: Industry
  themes: string[]
  scores: Scores
  metrics: CompanyMetrics
  history: FinancialYearPoint[]
  industryKpis: IndustryKpi[]
  strengths: string[]
  warnings: string[]
  analysisComment: string
  hasWarning: boolean
  dataSource?: 'EDINET' | 'mock'
  dataUpdatedAt?: string
  financialPeriod?: string
  liveMetricCount?: number
}

export interface LiveMetricValue {
  value: number
  previousValue?: number
  trend?: number[]
}

export interface LiveFinancialRecord {
  code: string
  companyName: string
  documentId: string
  filedAt: string
  periodEnd: string
  sourceUrl: string
  metrics: Partial<Record<KpiKey, LiveMetricValue>>
  history: FinancialYearPoint[]
}

export interface FinancialSnapshot {
  schemaVersion: 1
  generatedAt: string | null
  source: 'EDINET'
  status: 'ready' | 'setup-required' | 'error'
  message: string
  records: Record<string, LiveFinancialRecord>
  stats: {
    companies: number
    documentsScanned: number
    documentsUpdated: number
  }
}

export interface CompanyNote {
  watchReason: string
  thesis: string
  nextEarnings: string
  buyCondition: string
  avoidCondition: string
  exitCondition: string
  freeNote: string
  updatedAt?: string
}

export interface CompanyFilter {
  query: string
  market: Market | 'all'
  industry: Industry | 'all'
  theme: string | 'all'
  warningsOnly: boolean
  sort:
    | 'score-desc'
    | 'per-asc'
    | 'pbr-asc'
    | 'roe-desc'
    | 'operatingMargin-desc'
}
