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
  dividendYield: number
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
  if (has('revenueGrowth')) {
    growthValues.push([scale(metrics.revenueGrowth, -8, 20), 0.45])
  }
  if (has('operatingIncomeGrowth')) {
    growthValues.push([scale(metrics.operatingIncomeGrowth, -12, 24), 0.28])
  }
  if (has('epsGrowth')) {
    growthValues.push([scale(metrics.epsGrowth, -12, 24), 0.22])
  }
  if (has('inventoryGrowth', 'revenueGrowth')) {
    growthValues.push([
      scale(metrics.inventoryGrowth - metrics.revenueGrowth, 18, -8),
      0.03,
    ])
  }
  if (has('receivablesGrowth', 'revenueGrowth')) {
    growthValues.push([
      scale(metrics.receivablesGrowth - metrics.revenueGrowth, 18, -8),
      0.02,
    ])
  }

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
    safetyValues.push([scale(metrics.equityRatio, 15, 75), 0.45])
  }
  if (has('debtRatio')) {
    safetyValues.push([inverseScale(metrics.debtRatio, 0.2, 3.5), 0.32])
  }
  if (has('netCash')) {
    safetyValues.push([scale(metrics.netCash, -600, 800), 0.13])
  }
  if (has('wacc')) {
    safetyValues.push([inverseScale(metrics.wacc, 5, 12), 0.1])
  }

  const cashValues: WeightedValue[] = []
  if (has('operatingCfMargin')) {
    cashValues.push([scale(metrics.operatingCfMargin, -2, 22), 0.62])
  }
  if (has('netCash')) {
    cashValues.push([scale(metrics.netCash, -600, 800), 0.2])
  }
  if (has('ebitda')) {
    cashValues.push([scale(metrics.ebitda, 0, 900), 0.18])
  }

  const valuationValues: WeightedValue[] = []
  if (has('per')) {
    valuationValues.push([inverseScale(metrics.per, 8, 55), 0.34])
  }
  if (has('pbr')) {
    valuationValues.push([inverseScale(metrics.pbr, 0.6, 6), 0.25])
  }
  if (has('evEbitda')) {
    valuationValues.push([inverseScale(metrics.evEbitda, 5, 22), 0.24])
  }
  if (has('dividendYield')) {
    valuationValues.push([scale(metrics.dividendYield, 0, 4), 0.17])
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
