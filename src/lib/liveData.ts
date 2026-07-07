import type {
  Company,
  CompanyMetrics,
  FinancialIndustryShard,
  FinancialShardManifest,
  FinancialSnapshot,
  KpiComparisonLabel,
  KpiKey,
  KpiMetric,
  KpiStatus,
  LiveFinancialRecord,
  LiveMetricValue,
  MarketFundamentals,
  MarketQuote,
  MarketSnapshot,
  Scores,
  UpdateStatus,
} from '../types'
import {
  buildAnalysisComment,
  buildStrengths,
  buildWarnings,
} from './analysis'
import {
  buildIndustryInsights,
  buildTieredAnalysisComment,
  getAnalysisLevel,
} from './detailInsights'
import { getIndustryKpiPolicy } from './industryKpiPolicy'
import { calculateScores, type RawMetrics } from './scoring'
import {
  assessMetricConfidence,
  metricFormulaLabels,
  type MetricConfidenceAssessment,
} from './metricConfidence'

const kpiKeys: KpiKey[] = [
  'operatingMargin',
  'netMargin',
  'roe',
  'roa',
  'roic',
  'equityRatio',
  'operatingCfMargin',
  'netCash',
  'wacc',
]

const estimatedMetricKeys = new Set<KpiKey>(['roa', 'roic', 'wacc'])

const neutralMetrics: RawMetrics = {
  revenueGrowth: 0,
  operatingIncomeGrowth: 0,
  epsGrowth: 0,
  operatingMargin: 5,
  netMargin: 3,
  roe: 8,
  roa: 3,
  roic: 7,
  equityRatio: 40,
  operatingCfMargin: 5,
  debtRatio: 1,
  netCash: 0,
  wacc: 8,
  ebitda: 0,
  inventoryGrowth: 0,
  receivablesGrowth: 0,
  per: 20,
  pbr: 1.5,
  evEbitda: 10,
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
  operatingIncomeGrowth: '%',
  epsGrowth: '%',
  operatingMargin: '%',
  netMargin: '%',
  roe: '%',
  roa: '%',
  roic: '%',
  equityRatio: '%',
  operatingCfMargin: '%',
  debtRatio: '倍',
  netCash: '億円',
  wacc: '%',
  ebitda: '億円',
  inventoryGrowth: '%',
  receivablesGrowth: '%',
  per: '倍',
  pbr: '倍',
  evEbitda: '倍',
}

const comments: Record<KpiKey, [string, string, string]> = {
  operatingIncomeGrowth: ['利益成長が売上を伴う', '利益成長は中立圏', '利益成長の鈍化に注意'],
  epsGrowth: ['1株利益の伸びが強い', 'EPSは安定成長', 'EPSの伸びを確認'],
  roa: ['資産効率が良好', '資産効率は中立圏', '資産効率を確認'],
  roic: ['投下資本効率が良好', '資本コスト付近の収益力', 'ROIC改善を確認'],
  wacc: ['資本コストは低め', '標準的な資本コスト', '要求利回りが高め'],
  ebitda: ['償却前利益の規模が厚い', 'EBITDAは中立圏', 'EBITDAの薄さを確認'],
  evEbitda: ['EV/EBITDAで割安', 'EV/EBITDAは中立圏', '買収倍率は高め'],
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

const isIsoDate = (value: string | undefined) =>
  Boolean(value && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value)))

const isValidRecordForCompany = (
  company: Company,
  record: LiveFinancialRecord | undefined,
): record is LiveFinancialRecord =>
  Boolean(
    record &&
      record.code === company.code &&
      isIsoDate(record.periodEnd) &&
      isIsoDate(record.filedAt?.slice(0, 10)) &&
      Object.values(record.metrics ?? {}).some(
        (metric) => metric && Number.isFinite(metric.value),
      ),
  )

const isReliableDailyQuoteComparison = (quote: MarketQuote) => {
  if (!hasFiniteNumber(quote.previousClose) || quote.previousClose <= 0) return false
  if (!Number.isFinite(quote.close) || quote.close <= 0) return false
  const change = Math.abs(quote.close / quote.previousClose - 1)
  return change <= 0.35
}

const metricStatus = (key: KpiKey, value: number): KpiStatus => {
  const thresholds: Record<KpiKey, [number, number, boolean]> = {
    operatingIncomeGrowth: [0, 10, true],
    epsGrowth: [0, 10, true],
    roa: [2, 6, true],
    roic: [5, 10, true],
    wacc: [9.5, 6.5, false],
    ebitda: [0, 300, true],
    evEbitda: [14, 8, false],
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

const isScoreEligibleAssessment = (assessment: MetricConfidenceAssessment) =>
  assessment.confidence === 'A' || assessment.confidence === 'B'

const createUnavailableMetric = (
  key: KpiKey,
  assessment: MetricConfidenceAssessment = {},
): KpiMetric => ({
  value: 0,
  unit: units[key],
  status: 'unknown',
  comment: '開示データから取得できません',
  trend: [],
  available: false,
  formula: metricFormulaLabels[key],
  ...assessment,
})

const createNotApplicableMetric = (
  key: KpiKey,
  reason: string,
): KpiMetric => ({
  value: 0,
  unit: units[key],
  status: 'unknown',
  comment: reason,
  trend: [],
  available: false,
  applicable: false,
  formula: metricFormulaLabels[key],
})

const createLiveMetric = (
  key: KpiKey,
  value: number,
  previousValue?: number,
  trend?: number[],
  comparisonLabel: KpiComparisonLabel = '前年差',
  source?: LiveMetricValue,
  assessment: MetricConfidenceAssessment = {},
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
      ? { previousValue: round(previousValue), comparisonLabel }
      : { comparisonLabel }),
    unit: units[key],
    status,
    comment: comments[key][commentIndex],
    trend: normalizedTrend.map((point) => round(point)),
    available: true,
    formula: metricFormulaLabels[key],
    ...(estimatedMetricKeys.has(key) && source?.confidence && !source.provenance
      ? { estimated: true }
      : {}),
    ...(source?.provenance ? { provenance: source.provenance } : {}),
    ...assessment,
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
  if ((key === 'per' || key === 'pbr' || key === 'evEbitda') && value <= 0) return false
  if (key === 'wacc' && (value <= 0 || value > 25)) return false
  if ((key === 'roa' || key === 'roic') && (value < -80 || value > 120)) return false
  return true
}

const calculateLiveScores = (
  rawMetrics: RawMetrics,
  available: ReadonlySet<KpiKey>,
): Scores => {
  const scores = calculateScores(rawMetrics, available)
  const weighted: Array<[keyof Omit<Scores, 'overall'>, number, boolean]> = [
    [
      'profitability',
      0.42,
      available.has('operatingMargin') ||
        available.has('netMargin') ||
        available.has('roe') ||
        available.has('roa') ||
        available.has('roic'),
    ],
    [
      'safety',
      0.34,
      available.has('equityRatio') ||
        available.has('netCash') ||
        available.has('wacc'),
    ],
    [
      'cashGeneration',
      0.24,
      available.has('operatingCfMargin') ||
        available.has('netCash'),
    ],
  ]
  const active = weighted.filter(([, , isAvailable]) => isAvailable)
  const totalWeight = active.reduce((sum, [, weight]) => sum + weight, 0)
  scores.growth = 50
  scores.valuation = 50
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
  if (!quote || quote.stale || !fundamentals) return {}
  const metrics: Partial<Record<KpiKey, LiveMetricValue>> = {}
  const canCompareDay = isReliableDailyQuoteComparison(quote)
  const eps =
    fundamentals.forecastEps && fundamentals.forecastEps > 0
      ? fundamentals.forecastEps
      : fundamentals.eps
  const { bps } = fundamentals
  if (eps !== undefined && eps > 0) {
    metrics.per = {
      value: quote.close / eps,
      comparisonLabel: '前日差',
      ...(canCompareDay
        ? {
            previousValue: quote.previousClose! / eps,
            trend: [quote.previousClose! / eps, quote.close / eps],
          }
        : {}),
    }
  }
  if (bps !== undefined && bps > 0) {
    metrics.pbr = {
      value: quote.close / bps,
      comparisonLabel: '前日差',
      ...(canCompareDay
        ? {
            previousValue: quote.previousClose! / bps,
            trend: [quote.previousClose! / bps, quote.close / bps],
          }
        : {}),
    }
  }
  return metrics
}

const metricValue = (
  metrics: Partial<Record<KpiKey, LiveMetricValue>>,
  key: KpiKey,
) => {
  const value = metrics[key]?.value
  return hasFiniteNumber(value) ? value : undefined
}

const previousMetricValue = (
  metrics: Partial<Record<KpiKey, LiveMetricValue>>,
  key: KpiKey,
) => {
  const value = metrics[key]?.previousValue
  return hasFiniteNumber(value) ? value : undefined
}

const clampValue = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(max, value))

const derivedMetric = (
  value: number | undefined,
  previousValue: number | undefined,
  confidence: 'B' | 'C',
  confidenceReason: string,
): LiveMetricValue | undefined => {
  if (!hasFiniteNumber(value)) return undefined
  return {
    value,
    ...(hasFiniteNumber(previousValue)
      ? {
          previousValue,
          trend: [previousValue, value],
        }
      : {}),
    confidence,
    confidenceReason,
  }
}

const operatingIncomeGrowthFromMargins = (
  revenueGrowth: number | undefined,
  operatingMargin: number | undefined,
  previousOperatingMargin: number | undefined,
) => {
  if (
    !hasFiniteNumber(revenueGrowth) ||
    !hasFiniteNumber(operatingMargin) ||
    !hasFiniteNumber(previousOperatingMargin) ||
    previousOperatingMargin <= 0
  ) {
    return undefined
  }
  return (
    ((1 + revenueGrowth / 100) *
      (operatingMargin / previousOperatingMargin) -
      1) *
    100
  )
}

const profitGrowthFromMargins = (
  revenueGrowth: number | undefined,
  margin: number | undefined,
  previousMargin: number | undefined,
) => {
  if (
    !hasFiniteNumber(revenueGrowth) ||
    !hasFiniteNumber(margin) ||
    !hasFiniteNumber(previousMargin) ||
    previousMargin <= 0
  ) {
    return undefined
  }
  return ((1 + revenueGrowth / 100) * (margin / previousMargin) - 1) * 100
}

const depreciationMarginEstimate = (industry: string) => {
  if (/鉄鋼|非鉄|金属|機械|電気機器|輸送用機器|化学|石油|ガラス|電気・ガス/.test(industry)) {
    return 4
  }
  if (/情報・通信|サービス|小売|卸売/.test(industry)) return 1.8
  return 2.6
}

const latestRevenueOku = (record: LiveFinancialRecord) => {
  const latest = [...(record.history ?? [])]
    .reverse()
    .find((point) => hasFiniteNumber(point.revenue))
  return latest?.revenue
}

const deriveSupplementalMetrics = (
  company: Company,
  record: LiveFinancialRecord,
  metrics: Partial<Record<KpiKey, LiveMetricValue>>,
) => {
  const next = { ...metrics }
  const setIfMissing = (key: KpiKey, metric: LiveMetricValue | undefined) => {
    if (!next[key] && metric) next[key] = metric
  }

  const revenueGrowth = metricValue(next, 'revenueGrowth')
  const operatingMargin = metricValue(next, 'operatingMargin')
  const previousOperatingMargin = previousMetricValue(next, 'operatingMargin')
  const netMargin = metricValue(next, 'netMargin')
  const previousNetMargin = previousMetricValue(next, 'netMargin')
  const roe = metricValue(next, 'roe')
  const previousRoe = previousMetricValue(next, 'roe')
  const equityRatio = metricValue(next, 'equityRatio')
  const previousEquityRatio = previousMetricValue(next, 'equityRatio')
  const debtRatio = metricValue(next, 'debtRatio')
  const netCash = metricValue(next, 'netCash')
  const per = metricValue(next, 'per')
  const revenueOku = latestRevenueOku(record)

  setIfMissing(
    'roa',
    derivedMetric(
      hasFiniteNumber(roe) && hasFiniteNumber(equityRatio)
        ? (roe * equityRatio) / 100
        : undefined,
      hasFiniteNumber(previousRoe) && hasFiniteNumber(previousEquityRatio)
        ? (previousRoe * previousEquityRatio) / 100
        : undefined,
      'B',
      'ROEと自己資本比率から ROA = ROE × 自己資本比率 で算出しています。',
    ),
  )
  setIfMissing(
    'operatingIncomeGrowth',
    derivedMetric(
      operatingIncomeGrowthFromMargins(
        revenueGrowth,
        operatingMargin,
        previousOperatingMargin,
      ),
      undefined,
      'B',
      '売上成長率と営業利益率の前年差から営業利益成長率を推定しています。',
    ),
  )
  setIfMissing(
    'epsGrowth',
    derivedMetric(
      profitGrowthFromMargins(revenueGrowth, netMargin, previousNetMargin),
      undefined,
      'C',
      '株式数の変化を反映できないため、純利益成長率をEPS成長率の近似として表示しています。',
    ),
  )

  const taxAdjustedOperatingReturn =
    hasFiniteNumber(roe) &&
    hasFiniteNumber(operatingMargin) &&
    hasFiniteNumber(netMargin) &&
    netMargin > 0
      ? roe * (operatingMargin / netMargin) * 0.7
      : undefined
  setIfMissing(
    'roic',
    derivedMetric(
      hasFiniteNumber(taxAdjustedOperatingReturn)
        ? taxAdjustedOperatingReturn / (1 + Math.max(0, debtRatio ?? 0))
        : undefined,
      undefined,
      'C',
      'NOPATと投下資本を詳細取得できない会社では、ROE・利益率・D/Eから簡易推定しています。',
    ),
  )

  const debtToEquity =
    hasFiniteNumber(debtRatio)
      ? Math.max(0, debtRatio)
      : hasFiniteNumber(equityRatio) && equityRatio > 0
        ? Math.max(0, (100 - equityRatio) / equityRatio)
        : 0.7
  const equityWeight = 1 / (1 + debtToEquity)
  const debtWeight = debtToEquity / (1 + debtToEquity)
  const betaEstimate = clampValue(
    1 + ((50 - (equityRatio ?? 40)) / 150) + Math.max(0, debtToEquity - 1) * 0.07,
    0.75,
    1.55,
  )
  const costOfEquity = 1.2 + betaEstimate * 5.5
  const afterTaxCostOfDebt = (1.2 + Math.min(2.5, debtToEquity * 0.5)) * 0.7
  setIfMissing(
    'wacc',
    derivedMetric(
      equityWeight * costOfEquity + debtWeight * afterTaxCostOfDebt,
      undefined,
      'C',
      '市場ベータや実効金利が未取得のため、財務レバレッジから簡易推定したWACCです。',
    ),
  )

  const depreciationMargin = depreciationMarginEstimate(company.industry)
  const ebitdaValue =
    hasFiniteNumber(revenueOku) && hasFiniteNumber(operatingMargin)
      ? revenueOku * ((operatingMargin + depreciationMargin) / 100)
      : undefined
  const previousRevenueOku =
    hasFiniteNumber(revenueOku) && hasFiniteNumber(revenueGrowth)
      ? revenueOku / (1 + revenueGrowth / 100)
      : undefined
  const previousEbitda =
    hasFiniteNumber(previousRevenueOku) && hasFiniteNumber(previousOperatingMargin)
      ? previousRevenueOku * ((previousOperatingMargin + depreciationMargin) / 100)
      : undefined
  setIfMissing(
    'ebitda',
    derivedMetric(
      ebitdaValue,
      previousEbitda,
      'C',
      '減価償却費を未取得の会社では、業種別の償却率を営業利益に足して推定しています。',
    ),
  )

  const ebitda = metricValue(next, 'ebitda')
  const netIncomeOku =
    hasFiniteNumber(revenueOku) && hasFiniteNumber(netMargin)
      ? revenueOku * (netMargin / 100)
      : undefined
  const marketCapOku =
    hasFiniteNumber(netIncomeOku) && hasFiniteNumber(per)
      ? netIncomeOku * per
      : undefined
  const enterpriseValueOku =
    hasFiniteNumber(marketCapOku)
      ? marketCapOku - (hasFiniteNumber(netCash) ? netCash : 0)
      : undefined
  setIfMissing(
    'evEbitda',
    derivedMetric(
      hasFiniteNumber(enterpriseValueOku) &&
        hasFiniteNumber(ebitda) &&
        ebitda > 0
        ? enterpriseValueOku / ebitda
        : undefined,
      undefined,
      'C',
      '時価総額はPERと純利益から、EVはネットキャッシュを反映して簡易推定しています。',
    ),
  )

  return next
}

const hasTrustedRoeProvenance = (record: LiveFinancialRecord) => {
  if (record.source !== 'EDINET') return true
  const quality = record.quality
  return (
    (quality?.roeModelVersion ?? 0) >= 1 ||
    (quality?.dataModelVersion ?? 0) >= 6
  )
}

const mergeRecord = (
  company: Company,
  record: LiveFinancialRecord,
  quote?: MarketQuote,
  fundamentals?: MarketFundamentals,
): Company => {
  const history = record.history ?? []
  const policy = getIndustryKpiPolicy(company.industry)
  const applicable = new Set<KpiKey>(policy.applicable)
  let recordMetrics: Partial<Record<KpiKey, LiveMetricValue>> = {
    ...record.metrics,
    ...valuationMetrics(quote, fundamentals ?? record.valuation),
  }
  if (!hasTrustedRoeProvenance(record)) {
    delete recordMetrics.roe
  }
  const historyMatchesCurrentPeriod =
    history[history.length - 1]?.year === record.periodEnd.slice(0, 7).replace('-', '/')
  const priorHistoricalRoe =
    historyMatchesCurrentPeriod && history.length >= 2
      ? history[history.length - 2]?.roe
      : undefined
  if (
    recordMetrics.roe &&
    hasFiniteNumber(priorHistoricalRoe)
  ) {
    recordMetrics.roe = {
      ...recordMetrics.roe,
      previousValue: priorHistoricalRoe,
      trend: history.map((point) => point.roe),
    }
  }
  recordMetrics = deriveSupplementalMetrics(company, record, recordMetrics)
  kpiKeys.forEach((key) => {
    const metric = recordMetrics[key]
    if (
      !applicable.has(key) ||
      (metric && !isUsableLiveMetric(key, metric.value))
    ) {
      delete recordMetrics[key]
    }
  })
  const metricAssessments = Object.fromEntries(
    kpiKeys.map((key) => [key, assessMetricConfidence(key, recordMetrics[key], record)]),
  ) as Record<KpiKey, MetricConfidenceAssessment>
  const displayAvailable = new Set<KpiKey>(
    kpiKeys.filter(
      (key) => applicable.has(key) && recordMetrics[key] !== undefined,
    ),
  )
  const scoringAvailable = new Set<KpiKey>(
    kpiKeys.filter(
      (key) =>
        displayAvailable.has(key) &&
        isScoreEligibleAssessment(metricAssessments[key]),
    ),
  )
  const metrics = Object.fromEntries(
    kpiKeys.map((key) => {
      const live = recordMetrics[key]
      const assessment = metricAssessments[key]
      return [
        key,
        !applicable.has(key)
          ? createNotApplicableMetric(key, policy.reason)
          : live
            ? createLiveMetric(
                key,
                live.value,
                live.previousValue,
                live.trend,
                live.comparisonLabel,
                live,
                assessment,
              )
            : createUnavailableMetric(key, assessment),
      ]
    }),
  ) as CompanyMetrics
  const rawMetrics = { ...neutralMetrics }
  kpiKeys.forEach((key) => {
    rawMetrics[key] = scoringAvailable.has(key)
      ? recordMetrics[key]?.value ?? neutralMetrics[key]
      : neutralMetrics[key]
  })
  const previousOperatingMargin =
    scoringAvailable.has('operatingMargin')
      ? recordMetrics.operatingMargin?.previousValue ??
        (history.length >= 2
          ? history[history.length - 2]?.operatingMargin
          : undefined) ??
        rawMetrics.operatingMargin
      : rawMetrics.operatingMargin
  const scoringHistory = scoringAvailable.has('operatingMargin') ? history : []
  const analysisLevel = getAnalysisLevel(
    scoringAvailable.size,
    displayAvailable.size,
    applicable.size,
  )
  const warnings = buildWarnings(
    rawMetrics,
    previousOperatingMargin,
    scoringHistory,
    scoringAvailable,
  )

  return {
    ...company,
    metrics,
    history,
    industryKpis: buildIndustryInsights(metrics, applicable),
    scores: calculateLiveScores(rawMetrics, scoringAvailable),
    strengths: buildStrengths(rawMetrics, scoringAvailable),
    warnings,
    analysisComment: buildTieredAnalysisComment(
      buildAnalysisComment(
        rawMetrics,
        warnings,
        previousOperatingMargin,
        scoringAvailable,
        Math.min(4, applicable.size),
      ),
      analysisLevel,
      scoringAvailable,
      displayAvailable,
    ),
    analysisLevel,
    hasWarning: warnings.length > 0,
    dataSource: record.source === 'TDnet' ? 'TDnet' : 'EDINET',
    dataUpdatedAt: record.filedAt,
    financialPeriod: record.periodEnd,
    financialSourceUrl: record.sourceUrl,
    liveMetricCount: displayAvailable.size,
    trustedMetricCount: scoringAvailable.size,
    stockPrice: quote,
  }
}

const createUnavailableCompany = (
  company: Company,
  quote?: MarketQuote,
): Company => {
  const policy = getIndustryKpiPolicy(company.industry)
  const applicable = new Set<KpiKey>(policy.applicable)

  return {
    ...company,
    metrics: Object.fromEntries(
      kpiKeys.map((key) => [
        key,
        applicable.has(key)
          ? createUnavailableMetric(key)
          : createNotApplicableMetric(key, policy.reason),
      ]),
    ) as CompanyMetrics,
    history: [],
    industryKpis: [],
    scores: { ...unavailableScores },
    strengths: [],
    warnings: [],
    analysisComment:
      '比較可能な財務KPIを取得できていません。EDINET・TDnetの次回更新と会社の原資料を確認してください。',
    analysisLevel: 'unavailable',
    hasWarning: false,
    dataSource: 'unavailable',
    dataUpdatedAt: undefined,
    financialPeriod: undefined,
    financialSourceUrl: undefined,
    liveMetricCount: 0,
    trustedMetricCount: 0,
    stockPrice: quote,
  }
}

export const hasFinancialData = (company: Company) =>
  company.dataSource === 'EDINET' || company.dataSource === 'TDnet'

export const hasScorableData = (company: Company) =>
  company.analysisLevel === 'full' || company.analysisLevel === 'limited'

const fetchFinancialJson = async <T>(url: string): Promise<T> => {
  const response = await fetch(url, { cache: 'no-store' })
  if (!response.ok) {
    throw new Error(`Financial data could not be loaded: ${response.status}`)
  }
  return response.json() as Promise<T>
}

const loadShardedFinancialSnapshot = async (
  version: number,
): Promise<FinancialSnapshot> => {
  const baseUrl = `${import.meta.env.BASE_URL}data/financials`
  const manifest = await fetchFinancialJson<FinancialShardManifest>(
    `${baseUrl}/manifest.json?v=${version}`,
  )
  if (
    manifest.schemaVersion !== 1 ||
    !Array.isArray(manifest.shards) ||
    !Number.isInteger(manifest.recordCount)
  ) {
    throw new Error('Financial shard manifest is invalid')
  }

  const shardPayloads = await Promise.all(
    manifest.shards.map(async (entry) => {
      if (!/^industry-\d{2}\.json$/.test(entry.file)) {
        throw new Error(`Unexpected financial shard file: ${entry.file}`)
      }
      const shard = await fetchFinancialJson<FinancialIndustryShard>(
        `${baseUrl}/${entry.file}?v=${encodeURIComponent(
          manifest.generatedAt ?? String(version),
        )}`,
      )
      if (
        shard.schemaVersion !== 1 ||
        shard.industry !== entry.industry ||
        Object.keys(shard.records).length !== entry.recordCount
      ) {
        throw new Error(`Financial shard metadata mismatch: ${entry.file}`)
      }
      return shard
    }),
  )

  const records: FinancialSnapshot['records'] = {}
  shardPayloads.forEach((shard) => {
    Object.entries(shard.records).forEach(([code, record]) => {
      if (records[code]) {
        throw new Error(`Duplicate company in financial shards: ${code}`)
      }
      records[code] = record
    })
  })
  if (Object.keys(records).length !== manifest.recordCount) {
    throw new Error('Financial shard record count mismatch')
  }

  return {
    ...manifest.snapshot,
    records,
  }
}

const loadLegacyFinancialSnapshot = async (
  version: number,
): Promise<FinancialSnapshot> =>
  fetchFinancialJson<FinancialSnapshot>(
    `${import.meta.env.BASE_URL}data/financials.json?v=${version}`,
  )

export const loadFinancialSnapshot = async (): Promise<FinancialSnapshot> => {
  const version = Date.now()
  try {
    return await loadShardedFinancialSnapshot(version)
  } catch {
    return loadLegacyFinancialSnapshot(version)
  }
}

export const loadUpdateStatus = async (): Promise<UpdateStatus> => {
  const url = `${import.meta.env.BASE_URL}data/update-status.json?v=${Date.now()}`
  const response = await fetch(url, { cache: 'no-store' })
  if (!response.ok) {
    throw new Error(`Update status could not be loaded: ${response.status}`)
  }
  return response.json() as Promise<UpdateStatus>
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
    return isValidRecordForCompany(company, record)
      ? mergeRecord(company, record, quote, fundamentals)
      : createUnavailableCompany(company, quote)
  })
