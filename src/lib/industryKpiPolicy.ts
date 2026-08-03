import type { KpiKey } from '../types'

export const allKpiKeys = [
  'revenueGrowth',
  'operatingMargin',
  'netMargin',
  'roe',
  'equityRatio',
  'operatingCfMargin',
  'debtRatio',
  'netCash',
  'inventoryGrowth',
  'receivablesGrowth',
  'per',
  'pbr',
] as const satisfies readonly KpiKey[]

export const jpxIndustries = [
  '水産・農林業',
  '鉱業',
  '建設業',
  '食料品',
  '繊維製品',
  'パルプ・紙',
  '化学',
  '医薬品',
  '石油・石炭製品',
  'ゴム製品',
  'ガラス・土石製品',
  '鉄鋼',
  '非鉄金属',
  '金属製品',
  '機械',
  '電気機器',
  '輸送用機器',
  '精密機器',
  'その他製品',
  '電気・ガス業',
  '陸運業',
  '海運業',
  '空運業',
  '倉庫・運輸関連業',
  '情報・通信業',
  '卸売業',
  '小売業',
  '銀行業',
  '証券、商品先物取引業',
  '保険業',
  'その他金融業',
  '不動産業',
  'サービス業',
] as const

export type JpxIndustry = (typeof jpxIndustries)[number]

export interface IndustryKpiPolicy {
  applicable: readonly KpiKey[]
  excluded: readonly KpiKey[]
  reason: string
}

const createPolicy = (
  applicable: readonly KpiKey[],
  reason: string,
): IndustryKpiPolicy => {
  const applicableSet = new Set<KpiKey>(applicable)
  return {
    applicable,
    excluded: allKpiKeys.filter((key) => !applicableSet.has(key)),
    reason,
  }
}

const operatingCompanyPolicy = createPolicy(
  allKpiKeys,
  '一般事業会社向けの共通KPIを適用',
)

const bankPolicy = createPolicy(
  ['roe', 'per', 'pbr'],
  '銀行は預金・貸出を事業として扱うため、一般事業会社の利益率・負債・キャッシュ・運転資本指標を共通評価しません',
)

const securitiesPolicy = createPolicy(
  ['roe', 'per', 'pbr'],
  '証券会社は市場取引と顧客資産の影響が大きいため、一般事業会社の利益率・負債・キャッシュ・運転資本指標を共通評価しません',
)

const insurancePolicy = createPolicy(
  ['roe', 'per', 'pbr'],
  '保険会社は保険負債と運用資産が中心のため、一般事業会社の利益率・負債・キャッシュ・運転資本指標を共通評価しません',
)

const otherFinancialPolicy = createPolicy(
  ['revenueGrowth', 'netMargin', 'roe', 'per', 'pbr'],
  'その他金融業は資金調達自体が事業構造に含まれるため、負債・ネットキャッシュ・営業CF・運転資本指標を共通評価しません',
)

export const industryKpiPolicies = {
  '水産・農林業': operatingCompanyPolicy,
  鉱業: operatingCompanyPolicy,
  建設業: operatingCompanyPolicy,
  食料品: operatingCompanyPolicy,
  繊維製品: operatingCompanyPolicy,
  'パルプ・紙': operatingCompanyPolicy,
  化学: operatingCompanyPolicy,
  医薬品: operatingCompanyPolicy,
  '石油・石炭製品': operatingCompanyPolicy,
  ゴム製品: operatingCompanyPolicy,
  'ガラス・土石製品': operatingCompanyPolicy,
  鉄鋼: operatingCompanyPolicy,
  非鉄金属: operatingCompanyPolicy,
  金属製品: operatingCompanyPolicy,
  機械: operatingCompanyPolicy,
  電気機器: operatingCompanyPolicy,
  輸送用機器: operatingCompanyPolicy,
  精密機器: operatingCompanyPolicy,
  その他製品: operatingCompanyPolicy,
  '電気・ガス業': operatingCompanyPolicy,
  陸運業: operatingCompanyPolicy,
  海運業: operatingCompanyPolicy,
  空運業: operatingCompanyPolicy,
  '倉庫・運輸関連業': operatingCompanyPolicy,
  '情報・通信業': operatingCompanyPolicy,
  卸売業: operatingCompanyPolicy,
  小売業: operatingCompanyPolicy,
  銀行業: bankPolicy,
  '証券、商品先物取引業': securitiesPolicy,
  保険業: insurancePolicy,
  その他金融業: otherFinancialPolicy,
  不動産業: operatingCompanyPolicy,
  サービス業: operatingCompanyPolicy,
} satisfies Record<JpxIndustry, IndustryKpiPolicy>

export const getIndustryKpiPolicy = (industry: string): IndustryKpiPolicy =>
  industryKpiPolicies[industry as JpxIndustry] ?? operatingCompanyPolicy
