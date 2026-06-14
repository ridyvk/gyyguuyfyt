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

const clamp = (value: number) => Math.max(0, Math.min(100, value))

const scale = (value: number, low: number, high: number) =>
  clamp(((value - low) / (high - low)) * 100)

const inverseScale = (value: number, low: number, high: number) =>
  100 - scale(value, low, high)

export const calculateScores = (metrics: RawMetrics): Scores => {
  const growth = clamp(
    scale(metrics.revenueGrowth, -8, 20) * 0.7 +
      scale(metrics.inventoryGrowth - metrics.revenueGrowth, 18, -8) * 0.15 +
      scale(metrics.receivablesGrowth - metrics.revenueGrowth, 18, -8) * 0.15,
  )
  const profitability = clamp(
    scale(metrics.operatingMargin, 0, 24) * 0.45 +
      scale(metrics.netMargin, -2, 16) * 0.2 +
      scale(metrics.roe, 2, 22) * 0.35,
  )
  const safety = clamp(
    scale(metrics.equityRatio, 15, 75) * 0.6 +
      inverseScale(metrics.debtRatio, 0.2, 3.5) * 0.4,
  )
  const cashGeneration = clamp(
    scale(metrics.operatingCfMargin, -2, 22) * 0.75 +
      scale(metrics.netCash, -600, 800) * 0.25,
  )
  const valuation = clamp(
    inverseScale(metrics.per, 8, 55) * 0.55 +
      inverseScale(metrics.pbr, 0.6, 6) * 0.45,
  )

  return {
    growth,
    profitability,
    safety,
    cashGeneration,
    valuation,
    overall:
      growth * 0.22 +
      profitability * 0.24 +
      safety * 0.2 +
      cashGeneration * 0.2 +
      valuation * 0.14,
  }
}

export const scoreLabel = (score: number) => {
  if (score >= 80) return 'Excellent'
  if (score >= 65) return 'Strong'
  if (score >= 50) return 'Neutral'
  return 'Watch'
}
