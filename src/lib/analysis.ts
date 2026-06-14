import type { FinancialYearPoint } from '../types'
import type { RawMetrics } from './scoring'

export const buildWarnings = (
  metrics: RawMetrics,
  previousOperatingMargin: number,
  history: FinancialYearPoint[],
) => {
  const warnings: string[] = []

  if (metrics.revenueGrowth > 3 && metrics.operatingMargin < previousOperatingMargin - 0.8) {
    warnings.push('売上は伸びていますが、営業利益率が低下しています')
  }
  if (metrics.netMargin > 0 && metrics.operatingCfMargin < metrics.netMargin * 0.55) {
    warnings.push('純利益は黒字ですが、営業CFが弱い状態です')
  }
  if (metrics.inventoryGrowth > metrics.revenueGrowth + 8) {
    warnings.push('棚卸資産の増加率が売上成長率を大きく上回っています')
  }
  if (metrics.receivablesGrowth > metrics.revenueGrowth + 8) {
    warnings.push('売掛金の増加率が売上成長率を大きく上回っています')
  }
  if (metrics.equityRatio < 25) {
    warnings.push('自己資本比率が低く、財務余力を確認したい状態です')
  }
  if (metrics.debtRatio > 2.5) {
    warnings.push('有利子負債倍率が高い水準です')
  }
  if (metrics.per > 50 || metrics.pbr > 6) {
    warnings.push('PERまたはPBRが極端に高い水準です')
  }
  if (metrics.roe > 18 && metrics.equityRatio < 30) {
    warnings.push('ROEは高い一方、自己資本比率が低い状態です')
  }
  const margins = history.map((point) => point.operatingMargin)
  if (margins.length >= 3 && margins[0] > margins[1] && margins[1] > margins[2]) {
    warnings.push('営業利益率が3年連続で低下しています')
  }

  return warnings
}

export const buildStrengths = (metrics: RawMetrics) => {
  const strengths: string[] = []
  if (metrics.revenueGrowth >= 10) strengths.push('2桁の売上成長を維持')
  if (metrics.operatingMargin >= 15) strengths.push('高い営業利益率')
  if (metrics.roe >= 14) strengths.push('資本効率が良好')
  if (metrics.equityRatio >= 55) strengths.push('厚い自己資本')
  if (metrics.operatingCfMargin >= 12) strengths.push('キャッシュ創出力が強い')
  if (metrics.netCash >= 200) strengths.push('ネットキャッシュが豊富')
  if (metrics.per <= 13 && metrics.pbr <= 1.5) strengths.push('バリュエーションに割安感')

  return strengths.length ? strengths.slice(0, 4) : ['業績は概ね安定圏で推移']
}

export const buildAnalysisComment = (
  metrics: RawMetrics,
  warnings: string[],
  previousOperatingMargin: number,
) => {
  if (
    metrics.operatingMargin > previousOperatingMargin &&
    metrics.operatingCfMargin >= 10
  ) {
    return '営業利益率と営業CFマージンが改善しており、収益性とキャッシュ創出力は良好です。'
  }
  if (warnings.some((warning) => warning.includes('棚卸資産'))) {
    return '棚卸資産の増加率が売上成長率を上回っています。在庫回転と需要見通しを確認したい局面です。'
  }
  if (warnings.some((warning) => warning.includes('営業CF'))) {
    return '純利益は黒字ですが営業CFが弱く、運転資本を含めて利益の質を確認したい状態です。'
  }
  if (warnings.some((warning) => warning.includes('営業利益率'))) {
    return '売上は伸びていますが営業利益率が低下しています。コスト増や価格転嫁の進捗に注意が必要です。'
  }
  return '主要KPIは大きな偏りなく推移しています。次回決算では成長率と利益率の持続性を確認したい状態です。'
}
