import type { KpiMetric } from '../types'

const numberFormat = new Intl.NumberFormat('ja-JP', {
  maximumFractionDigits: 1,
})

export const formatNumber = (value: number, digits = 1) =>
  new Intl.NumberFormat('ja-JP', {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value)

export const formatMetric = (metric: KpiMetric) => {
  if (metric.available === false) return '—'
  const sign = metric.unit === '億円' && metric.value > 0 ? '+' : ''
  return `${sign}${numberFormat.format(metric.value)}${metric.unit}`
}

export const formatDelta = (metric: KpiMetric) => {
  if (metric.available === false) return '前年差なし'
  const delta = metric.value - metric.previousValue
  const sign = delta > 0 ? '+' : ''
  const suffix = metric.unit === '%' ? 'pt' : metric.unit
  return `${sign}${formatNumber(delta)}${suffix}`
}

export const formatScore = (score: number) => Math.round(score).toString()

export const statusLabel = {
  good: '良好',
  normal: '普通',
  warning: '注意',
  unknown: '判断不能',
} as const
