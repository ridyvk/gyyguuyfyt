import type { Scores } from '../types'

export interface RawMetrics {
  revenueGrowth: number
  operatingIncomeGrowth: number
  epsGrowth: number
  operatingMargin: number
  netMargin: number
  roe: number
  roa: number
  roic: number
  equityRatio: number
  operatingCfMargin: number
  debtRatio: number
  netCash: number
  wacc: number
  ebitda: number
  inventoryGrowth: number
  receivablesGrowth: number
  per: number
  pbr: number
  evEbitda: number
}

type RawMetricKey = keyof RawMetrics
type WeightedValue = readonly [value: number, weight: number]

const clamp = (value: number) => Math.max(0, Math.min(100, value))

const scale = (value: number, low: number, high: number) =>
  clamp(((value - low) / (high - low)) * 100)

const inverseScale = (value: number, low: number, high: number) =>
  100 - scale(value, low, high)

const weightedAverage = (values: WeightedValue[]) => {
  const totalWeight = values.reduce((sum, [, weight]) => sum + weight, 0)
  if (!totalWeight) return 50
  return clamp(
    values.reduce((sum, [value, weight]) => sum + value * weight, 0) /
      totalWeight,
  )
}

export const calculateScores = (
  metrics: RawMetrics,
  available: ReadonlySet<RawMetricKey> = new Set(
    Object.keys(metrics) as RawMetricKey[],
  ),
): Scores => {
  const has = (...keys: RawMetricKey[]) =>
    keys.every((key) => available.has(key))

  const growthValues: WeightedValue[] = []

  const profitabilityValues: WeightedValue[] = []
  if (has('operatingMargin')) {
    profitabilityValues.push([scale(metrics.operatingMargin, 0, 24), 0.25])
  }
  if (has('netMargin')) {
    profitabilityValues.push([scale(metrics.netMargin, -2, 16), 0.12])
  }
  if (has('roe')) {
    profitabilityValues.push([scale(metrics.roe, 2, 22), 0.23])
  }
  if (has('roa')) {
    profitabilityValues.push([scale(metrics.roa, 0, 9), 0.16])
  }
  if (has('roic')) {
    profitabilityValues.push([scale(metrics.roic, 2, 18), 0.24])
  }

  const safetyValues: WeightedValue[] = []
  if (has('equityRatio')) {
    safetyValues.push([scale(metrics.equityRatio, 15, 75), 0.55])
  }
  if (has('netCash')) {
    safetyValues.push([scale(metrics.netCash, -600, 800), 0.25])
  }
  if (has('wacc')) {
    safetyValues.push([inverseScale(metrics.wacc, 5, 12), 0.2])
  }

  const cashValues: WeightedValue[] = []
  if (has('operatingCfMargin')) {
    cashValues.push([scale(metrics.operatingCfMargin, -2, 22), 0.7])
  }
  if (has('netCash')) {
    cashValues.push([scale(metrics.netCash, -600, 800), 0.3])
  }

  const valuationValues: WeightedValue[] = []

  const growth = weightedAverage(growthValues)
  const profitability = weightedAverage(profitabilityValues)
  const safety = weightedAverage(safetyValues)
  const cashGeneration = weightedAverage(cashValues)
  const valuation = weightedAverage(valuationValues)

  const categories: Array<readonly [number, number, boolean]> = [
    [profitability, 0.42, profitabilityValues.length > 0],
    [safety, 0.34, safetyValues.length > 0],
    [cashGeneration, 0.24, cashValues.length > 0],
  ]
  const activeCategories = categories.filter(([, , active]) => active)
  const overall = weightedAverage(
    activeCategories.map(([score, weight]) => [score, weight] as const),
  )

  return {
    growth,
    profitability,
    safety,
    cashGeneration,
    valuation,
    overall,
  }
}

export const scoreLabel = (score: number) => {
  if (score >= 80) return 'Excellent'
  if (score >= 65) return 'Strong'
  if (score >= 50) return 'Neutral'
  return 'Watch'
}
