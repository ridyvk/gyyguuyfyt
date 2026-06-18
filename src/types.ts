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
  previousValue?: number
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
  dataSource?: 'EDINET' | 'TDnet' | 'unavailable'
  dataUpdatedAt?: string
  financialPeriod?: string
  financialSourceUrl?: string
  liveMetricCount?: number
  stockPrice?: MarketQuote
}

export interface LiveMetricValue {
  value: number
  previousValue?: number
  trend?: number[]
}

export interface ValuationBasis {
  disclosedDate?: string
  disclosedAt?: string
  eps?: number
  forecastEps?: number
  bps?: number
}

export interface LiveFinancialRecord {
  code: string
  companyName: string
  documentId: string
  filedAt: string
  periodEnd: string
  source?: 'EDINET' | 'TDnet'
  sourceUrl: string
  metrics: Partial<Record<KpiKey, LiveMetricValue>>
  history: FinancialYearPoint[]
  valuation?: ValuationBasis
}

export interface FinancialSnapshot {
  schemaVersion: 1 | 2 | 3
  generatedAt: string | null
  source: 'EDINET' | 'EDINET+TDnet' | 'TDnet'
  status: 'ready' | 'building' | 'setup-required' | 'error'
  message: string
  dataPolicy?: {
    mode?: string
    baselineSource?: string
    overlaySource?: string
    primarySource?: string
    acceptedDocumentType?: string
    edinetMerged?: boolean
    tdnetOverlay?: boolean
    quarterlyMerged?: boolean
    batched?: boolean
    note?: string
  }
  records: Record<string, LiveFinancialRecord>
  stats: {
    companies: number
    targetCompanies?: number
    missingCompanies?: number
    coverageRatio?: number
    documentsScanned?: number
    documentsUpdated?: number
    edinetCompanies?: number
    tdnetCompanies?: number
    edinetDocumentsScanned?: number
    edinetDocumentsUpdated?: number
    edinetPendingBeforeBatch?: number
    edinetBatchSize?: number
    edinetEstimatedRemaining?: number
    edinetBatchFailures?: number
    tdnetDocumentsScanned?: number
    tdnetDocumentsUpdated?: number
    tdnetRowsScanned?: number
    tdnetEarningsRows?: number
    tdnetQuarterlyRowsSkipped?: number
    tdnetFullYearFilings?: number
    tdnetStrictFailures?: number
    nonAnnualRecordsDropped?: number
  }
}

export interface MarketQuote {
  date: string
  close: number
  previousClose?: number
  changePercent?: number
  volume?: number
  source: 'Yahoo Finance' | 'J-Quants'
}

export type MarketFundamentals = ValuationBasis

export interface MarketSnapshot {
  schemaVersion: 1
  generatedAt: string | null
  source: 'Yahoo Finance' | 'J-Quants'
  status: 'ready' | 'setup-required' | 'error'
  message: string
  latestTradingDate: string | null
  quotes: Record<string, MarketQuote>
  fundamentals: Record<string, MarketFundamentals>
  stats: {
    companies: number
    tradingDates: string[]
    fundamentals: number
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
    | 'code-asc'
    | 'score-desc'
    | 'per-asc'
    | 'pbr-asc'
    | 'roe-desc'
    | 'operatingMargin-desc'
}
