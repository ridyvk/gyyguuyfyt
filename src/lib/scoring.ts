import type { Scores } from '../types'

export interface RawMetrics {
  revenueGrowth: number
  operatingMargin: number
  netMargin: number
  roe: number
  equityRatio: number
  operatingCfMargin: number
  debtRatio: number
  netCash: number
  inventoryGrowth: number
  receivablesGrowth: number
  per: number
  pbr: number
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
  if (has('revenueGrowth')) {
    growthValues.push([scale(metrics.revenueGrowth, -8, 20), 0.7])
  }
  if (has('inventoryGrowth', 'revenueGrowth')) {
    growthValues.push([
      scale(metrics.inventoryGrowth - metrics.revenueGrowth, 18, -8),
      0.15,
    ])
  }
  if (has('receivablesGrowth', 'revenueGrowth')) {
    growthValues.push([
      scale(metrics.receivablesGrowth - metrics.revenueGrowth, 18, -8),
      0.15,
    ])
  }

  const profitabilityValues: WeightedValue[] = []
  if (has('operatingMargin')) {
    profitabilityValues.push([scale(metrics.operatingMargin, 0, 24), 0.45])
  }
  if (has('netMargin')) {
    profitabilityValues.push([scale(metrics.netMargin, -2, 16), 0.2])
  }
  if (has('roe')) {
    profitabilityValues.push([scale(metrics.roe, 2, 22), 0.35])
  }

  const safetyValues: WeightedValue[] = []
  if (has('equityRatio')) {
    safetyValues.push([scale(metrics.equityRatio, 15, 75), 0.6])
  }
  if (has('debtRatio')) {
    safetyValues.push([inverseScale(metrics.debtRatio, 0.2, 3.5), 0.4])
  }

  const cashValues: WeightedValue[] = []
  if (has('operatingCfMargin')) {
    cashValues.push([scale(metrics.operatingCfMargin, -2, 22), 0.75])
  }
  if (has('netCash')) {
    cashValues.push([scale(metrics.netCash, -600, 800), 0.25])
  }

  const valuationValues: WeightedValue[] = []
  if (has('per')) {
    valuationValues.push([inverseScale(metrics.per, 8, 55), 0.55])
  }
  if (has('pbr')) {
    valuationValues.push([inverseScale(metrics.pbr, 0.6, 6), 0.45])
  }

  const growth = weightedAverage(growthValues)
  const profitability = weightedAverage(profitabilityValues)
  const safety = weightedAverage(safetyValues)
  const cashGeneration = weightedAverage(cashValues)
  const valuation = weightedAverage(valuationValues)

  const categories: Array<readonly [number, number, boolean]> = [
    [growth, 0.22, growthValues.length > 0],
    [profitability, 0.24, profitabilityValues.length > 0],
    [safety, 0.2, safetyValues.length > 0],
    [cashGeneration, 0.2, cashValues.length > 0],
    [valuation, 0.14, valuationValues.length > 0],
  ]
  const activeCategories = categories.filter(([, , active]) => active)
  const overall = weightedAverage(
    activeCategories.map(([score, weight]) => [score, weight]),
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
