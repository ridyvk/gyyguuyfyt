import type { KpiMetric } from '../types'

const numberFormat = new Intl.NumberFormat('ja-JP', {
  maximumFractionDigits: 1,
})

export const formatNumber = (value: number, digits = 1) =>
  new Intl.NumberFormat('ja-JP', {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value)

export const comparisonLabelForMetric = (metric: KpiMetric) =>
  metric.comparisonLabel ?? '前年差'

export const hasPreviousMetricValue = (metric: KpiMetric) =>
  metric.previousValue !== undefined && Number.isFinite(metric.previousValue)

export const formatMetric = (metric: KpiMetric) => {
  if (metric.available === false) return '—'
  const sign = metric.unit === '億円' && metric.value > 0 ? '+' : ''
  return `${sign}${numberFormat.format(metric.value)}${metric.unit}`
}

export const formatDelta = (metric: KpiMetric) => {
  if (metric.available === false || !hasPreviousMetricValue(metric)) {
    return `${comparisonLabelForMetric(metric)}なし`
  }
  const delta = metric.value - metric.previousValue!
  const sign = delta > 0 ? '+' : ''
  const suffix = metric.unit === '%' ? 'pt' : metric.unit
  return `${sign}${formatNumber(delta)}${suffix}`
}

export const formatScore = (score: number) => Math.round(score).toString()

export const formatStockPrice = (value: number) =>
  new Intl.NumberFormat('ja-JP', {
    style: 'currency',
    currency: 'JPY',
    maximumFractionDigits: value < 100 ? 1 : 0,
  }).format(value)

export const formatChangePercent = (value?: number) => {
  if (value === undefined) return '前日比なし'
  const sign = value > 0 ? '+' : ''
  return `${sign}${formatNumber(value, 2)}%`
}

export const formatVolume = (value?: number) => {
  if (value === undefined) return '出来高なし'
  if (value >= 100_000_000) {
    return `${formatNumber(value / 100_000_000, 1)}億株`
  }
  if (value >= 10_000) {
    return `${formatNumber(value / 10_000, 1)}万株`
  }
  return `${Math.round(value).toLocaleString('ja-JP')}株`
}

export const statusLabel = {
  good: '良好',
  normal: '普通',
  warning: '注意',
  unknown: '判断不能',
} as const
