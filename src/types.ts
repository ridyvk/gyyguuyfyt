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
export type KpiComparisonLabel = '前年差' | '前日差'

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
  comparisonLabel?: KpiComparisonLabel
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

export interface XbrlSourceFact {
  role: string
  concept: string
  tag: string
  namespace?: string
  contextRef: string
  periodStart?: string
  periodEnd: string
  periodType: 'duration' | 'instant'
  unitRef?: string
  scale?: string
  consolidation: 'consolidated' | 'non-consolidated' | 'unknown'
  dimensions: string[]
  rawValue: number
}

export interface MetricProvenance {
  formula: string
  sourceFacts: XbrlSourceFact[]
}

export interface LiveMetricValue {
  value: number
  previousValue?: number
  comparisonLabel?: KpiComparisonLabel
  trend?: number[]
  provenance?: MetricProvenance
}

export interface ReconciliationFieldComparison {
  edinet: number
  tdnet: number
  difference: number
  allowedDifference: number
  matched: boolean
}

export interface MetricReconciliation {
  status: 'matched' | 'quarantined' | 'edinet-only' | 'tdnet-only'
  selectedSource?: 'EDINET' | 'TDnet' | null
  fields?: Record<string, ReconciliationFieldComparison>
}

export interface SourceReconciliation {
  modelVersion: number
  checkedAt: string
  periodEnd: string
  status: 'matched' | 'quarantined'
  metrics: Partial<Record<KpiKey, MetricReconciliation>>
  quarantinedMetrics: KpiKey[]
}

export interface SourceQuarantine {
  sourceReconciliation?: {
    checkedAt: string
    periodEnd: string
    metrics: Partial<
      Record<
        KpiKey,
        {
          reason: string
          edinet: LiveMetricValue
          tdnet: LiveMetricValue
        }
      >
    >
  }
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
  reconciliation?: SourceReconciliation
  quarantine?: SourceQuarantine
  quality?: {
    dataModelVersion?: number
    roeModelVersion?: number
    provenanceModelVersion?: number
    reconciliationModelVersion?: number
    reconciliationStatus?: 'matched' | 'quarantined'
    reconciliationDocumentId?: string
    reconciliationSourceUrl?: string
    roeStatus?: string
    roeRequiredDataModelVersion?: number
  }
}

export interface FinancialDataPolicy {
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

export interface FinancialStats {
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
  invalidRecordsDropped?: number
  validationFailures?: Record<string, number>
  roeMetricsQuarantined?: number
  metricRangeQuarantined?: number
  metricRangeQuarantinedCompanies?: number
  historyTrendQuarantinedCompanies?: number
  sourceReconciliationCompanies?: number
  sourceMatchedMetrics?: number
  sourceQuarantinedMetrics?: number
  sourceReconciliationChecksThisRun?: number
  sourceMatchedMetricsThisRun?: number
  sourceQuarantinedMetricsThisRun?: number
  dataUpdatedAt?: string | null
  latestPeriodEnd?: string | null
  lastCheckedAt?: string | null
}

export interface FinancialSnapshot {
  schemaVersion: 1 | 2 | 3
  generatedAt: string | null
  dataUpdatedAt?: string | null
  latestPeriodEnd?: string | null
  source: 'EDINET' | 'EDINET+TDnet' | 'TDnet'
  status: 'ready' | 'partial' | 'building' | 'setup-required' | 'error'
  message: string
  dataPolicy?: FinancialDataPolicy
  records: Record<string, LiveFinancialRecord>
  stats: FinancialStats
}

export interface UpdateStatus extends Partial<FinancialStats> {
  generatedAt?: string | null
  dataUpdatedAt?: string | null
  latestPeriodEnd?: string | null
  mode?: string
  status?: 'ready' | 'partial' | 'building' | 'setup-required' | 'error'
  source?: 'EDINET' | 'EDINET+TDnet' | 'TDnet'
  baselineSource?: string
  overlaySource?: string
  edinetMerged?: boolean
  tdnetOverlay?: boolean
  quarterlyMerged?: boolean
  batched?: boolean
  message?: string
}

export interface MarketQuote {
  date: string
  timestamp?: string
  close: number
  previousClose?: number
  changePercent?: number
  volume?: number
  source: 'Yahoo Finance' | 'J-Quants'
  priceType?: 'daily-close' | 'regular-market-price'
  isRealtime?: boolean
  stale?: boolean
}

export type MarketFundamentals = ValuationBasis

export interface MarketSnapshot {
  schemaVersion: 1 | 2 | 3
  generatedAt: string | null
  source: 'Yahoo Finance' | 'J-Quants'
  status: 'ready' | 'partial' | 'setup-required' | 'error'
  message: string
  latestTradingDate: string | null
  quotes: Record<string, MarketQuote>
  fundamentals: Record<string, MarketFundamentals>
  stats: {
    companies: number
    tradingDates: string[]
    fundamentals: number
    quoteUniverse?: number
    quoteFailures?: number
    freshQuotesFetched?: number
    fallbackQuotes?: number
    staleQuotesDropped?: number
    marketDateStaleQuotes?: number
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
