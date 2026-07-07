import type {
  KpiConfidence,
  KpiKey,
  LiveFinancialRecord,
  LiveMetricValue,
  XbrlSourceFact,
} from '../types'

export const metricFormulaLabels: Record<KpiKey, string> = {
  operatingIncomeGrowth: '(当期営業利益 / 前期営業利益 - 1) × 100',
  epsGrowth: '(当期EPS / 前期EPS - 1) × 100',
  roa: '当期純利益 / 総資産 × 100',
  roic: 'NOPAT / 投下資本 × 100',
  roicWaccSpread: 'ROIC - WACC',
  wacc: '株主資本コスト × 株主資本比率 + 負債コスト × (1 - 税率) × 負債比率',
  ebitda: '営業利益 + 減価償却費',
  evEbitda: 'EV / EBITDA',
  revenueGrowth: '(当期売上高 / 前期売上高 - 1) × 100',
  operatingMargin: '営業利益 / 売上高 × 100',
  netMargin: '親会社株主利益 / 売上高 × 100',
  roe: '開示ROE（未開示時: 親会社株主利益 / 平均自己資本 × 100）',
  equityRatio: '開示自己資本比率（未開示時: 自己資本 / 総資産 × 100）',
  operatingCfMargin: '営業キャッシュフロー / 売上高 × 100',
  cashProfitGap: '営業CFマージン - 純利益率',
  debtRatio: '有利子負債 / 自己資本',
  netCash: '(現金及び現金同等物 - 有利子負債) / 1億',
  inventoryGrowth: '(当期棚卸資産 / 前期棚卸資産 - 1) × 100',
  receivablesGrowth: '(当期売上債権 / 前期売上債権 - 1) × 100',
  per: '株価 / 1株当たり利益（EPS）',
  pbr: '株価 / 1株当たり純資産（BPS）',
}

export interface MetricConfidenceAssessment {
  confidence?: KpiConfidence
  confidenceReason?: string
}

const isCompleteFact = (fact: XbrlSourceFact) =>
  Boolean(
    fact.tag &&
      fact.contextRef &&
      fact.periodEnd &&
      fact.periodType &&
      fact.unitRef &&
      fact.consolidation,
  )

const isMetricQuarantined = (
  key: KpiKey,
  record: LiveFinancialRecord,
) =>
  record.reconciliation?.metrics[key]?.status === 'quarantined' ||
  Boolean(record.quarantine?.sourceReconciliation?.metrics[key]) ||
  (key === 'roe' && record.quality?.roeStatus === 'quarantined-stale-model')

export const assessMetricConfidence = (
  key: KpiKey,
  metric: LiveMetricValue | undefined,
  record: LiveFinancialRecord,
): MetricConfidenceAssessment => {
  if (isMetricQuarantined(key, record)) {
    return {
      confidence: 'review',
      confidenceReason: '開示元の不一致または旧抽出値のため隔離中',
    }
  }
  if (!metric) return {}

  if (metric.confidence) {
    return {
      confidence: metric.confidence,
      confidenceReason: metric.confidenceReason,
    }
  }

  if ((key === 'per' || key === 'pbr') && !metric.provenance) {
    return {
      confidence: 'B',
      confidenceReason: '開示済み1株指標と最新株価から算出',
    }
  }

  const facts = metric.provenance?.sourceFacts ?? []
  if (!metric.provenance || facts.length === 0) {
    return {
      confidence: 'C',
      confidenceReason: '数値は取得済みですが元タグの証跡が未移行',
    }
  }
  if (!facts.every(isCompleteFact)) {
    return {
      confidence: 'review',
      confidenceReason: '元タグのcontext・単位・連結区分が不完全',
    }
  }
  if (facts.some((fact) => fact.consolidation !== 'consolidated')) {
    return {
      confidence: 'review',
      confidenceReason: '連結区分が単体または不明のため確認が必要',
    }
  }

  const currentModel =
    (record.quality?.provenanceModelVersion ?? 0) >= 1 ||
    (record.quality?.dataModelVersion ?? 0) >= 9
  if (currentModel) {
    return {
      confidence: 'A',
      confidenceReason: '元タグ・context・単位・連結区分を確認済み',
    }
  }
  return {
    confidence: 'B',
    confidenceReason: '出典は確認済みですが旧抽出モデル',
  }
}
