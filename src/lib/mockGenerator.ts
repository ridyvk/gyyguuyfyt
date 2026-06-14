import type {
  Company,
  CompanyMetrics,
  FinancialYearPoint,
  Industry,
  IndustryKpi,
  KpiKey,
  KpiMetric,
  KpiStatus,
  ListedCompanyMaster,
  Market,
} from '../types'
import listedCompanyData from '../data/listedCompanies.json'
import {
  buildAnalysisComment,
  buildStrengths,
  buildWarnings,
} from './analysis'
import { calculateScores, type RawMetrics } from './scoring'

const markets: Market[] = ['プライム', 'スタンダード', 'グロース']
const companyMaster =
  listedCompanyData.companies as ListedCompanyMaster[]
const industries: Industry[] = Array.from(
  new Set(companyMaster.map((company) => company.industry)),
).sort((a, b) => a.localeCompare(b, 'ja'))

const specialIndustryProfile = (name: string, industry: Industry) => {
  if (industry === '銀行業') return '銀行'
  if (industry === '小売業') return '小売'
  if (industry === '電気・ガス業') return '電力・インフラ'
  if (/三菱重工|川崎重工|ＩＨＩ|IHI|日本製鋼所|新明和/.test(name)) {
    return '防衛・重工業'
  }
  if (
    /東京エレクトロン|ディスコ|アドバンテスト|ＳＣＲＥＥＮ|レーザーテック|ＫＯＫＵＳＡＩ/.test(
      name,
    )
  ) {
    return '半導体製造装置'
  }
  return industry
}

const themesForCompany = (name: string, industry: Industry) => {
  const profile = specialIndustryProfile(name, industry)
  const themesByProfile: Record<string, string[]> = {
    銀行: ['金利正常化', '地方創生', '高配当'],
    小売: ['インバウンド', '省人化', '消費回復'],
    '防衛・重工業': ['防衛', '宇宙', 'エネルギー安全保障'],
    半導体製造装置: ['AI半導体', '半導体国産化', 'データセンター'],
    '電力・インフラ': ['再生可能エネルギー', 'GX', 'インフラ更新'],
    '情報・通信業': ['生成AI', 'DX', 'サイバーセキュリティ'],
    医薬品: ['創薬', 'ヘルスケア', '高齢化'],
    化学: ['素材革新', 'EV', '脱炭素'],
    食料品: ['値上げ', '海外展開', '健康志向'],
    陸運業: ['物流効率化', '自動化', 'EC'],
    海運業: ['運賃市況', '物流網', '株主還元'],
    空運業: ['インバウンド', '旅客需要', '燃料価格'],
    '倉庫・運輸関連業': ['物流効率化', '自動化', 'EC'],
    機械: ['設備投資', '自動化', '海外展開'],
    電気機器: ['AI', '半導体', 'データセンター'],
    輸送用機器: ['EV', '自動運転', '海外展開'],
    建設業: ['国土強靭化', '再開発', '人手不足'],
    不動産業: ['金利', '再開発', 'インバウンド'],
    サービス業: ['人材不足', 'DX', '消費回復'],
  }
  return themesByProfile[profile] ?? ['資本効率', '収益改善', '業界再編']
}

const hashCode = (value: string) =>
  Array.from(value).reduce(
    (hash, character) => Math.imul(hash ^ character.charCodeAt(0), 16777619),
    2166136261,
  ) >>> 0

const round = (value: number, digits = 1) => {
  const factor = 10 ** digits
  return Math.round(value * factor) / factor
}

const mulberry32 = (seed: number) => {
  let value = seed
  return () => {
    value += 0x6d2b79f5
    let t = value
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const between = (random: () => number, min: number, max: number) =>
  min + random() * (max - min)

const metricStatus = (key: KpiKey, value: number): KpiStatus => {
  const thresholds: Record<KpiKey, [number, number, boolean]> = {
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

const metricComments: Record<KpiKey, [string, string, string]> = {
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

const createMetric = (
  key: KpiKey,
  value: number,
  previousValue: number,
  unit: KpiMetric['unit'],
  trend: number[],
): KpiMetric => {
  const status = metricStatus(key, value)
  const commentIndex = status === 'good' ? 0 : status === 'normal' ? 1 : 2
  return {
    value: round(value),
    previousValue: round(previousValue),
    unit,
    status,
    comment: metricComments[key][commentIndex],
    trend: trend.map((point) => round(point)),
  }
}

const createIndustryKpis = (
  profile: string,
  random: () => number,
): IndustryKpi[] => {
  const positive = (name: string, value: string): IndustryKpi => ({
    name,
    value,
    signal: random() > 0.25 ? 'positive' : 'neutral',
  })
  const neutral = (name: string, value: string): IndustryKpi => ({
    name,
    value,
    signal: random() > 0.7 ? 'negative' : 'neutral',
  })

  switch (profile) {
    case '銀行':
      return [
        positive('利ざや', `${round(between(random, 0.7, 2.1), 2)}%`),
        neutral('預貸率', `${round(between(random, 55, 88))}%`),
        positive('不良債権比率', `${round(between(random, 0.5, 2.4), 2)}%`),
      ]
    case '小売':
      return [
        positive('既存店売上', `+${round(between(random, 1, 9))}%`),
        neutral('客数', `${round(between(random, -3, 6))}%`),
        positive('客単価', `+${round(between(random, 0, 7))}%`),
        neutral('粗利率', `${round(between(random, 22, 42))}%`),
      ]
    case '防衛・重工業':
      return [
        positive('受注残', `${Math.round(between(random, 3200, 18000))}億円`),
        neutral('官公庁向け比率', `${round(between(random, 18, 62))}%`),
        positive('研究開発費', `${Math.round(between(random, 120, 980))}億円`),
      ]
    case '半導体製造装置':
      return [
        positive('受注高', `${Math.round(between(random, 900, 7600))}億円`),
        positive('受注残', `${Math.round(between(random, 1200, 9200))}億円`),
        neutral('海外売上比率', `${round(between(random, 55, 93))}%`),
      ]
    case '電力・インフラ':
      return [
        neutral('設備投資', `${Math.round(between(random, 800, 6400))}億円`),
        positive('電力需要', `${round(between(random, -2, 5))}%`),
        neutral('燃料費影響', `${Math.round(between(random, -500, 600))}億円`),
        neutral('有利子負債', `${Math.round(between(random, 2200, 18000))}億円`),
      ]
    default:
      return [
        positive('海外売上比率', `${round(between(random, 18, 74))}%`),
        neutral('研究開発比率', `${round(between(random, 1, 12))}%`),
        positive('顧客継続率', `${round(between(random, 76, 98))}%`),
      ]
  }
}

const createCompany = (
  master: ListedCompanyMaster,
  index: number,
): Company => {
  const random = mulberry32(hashCode(master.code) + 104729)
  const { industry, market, name, code } = master
  const profile = specialIndustryProfile(name, industry)
  const riskProfile = random() < 0.36
  const qualityTilt = between(random, -5, 7)
  const revenueGrowth = between(random, -6, 22) + qualityTilt * 0.35
  const previousRevenueGrowth = revenueGrowth + between(random, -6, 6)
  const operatingMargin = between(random, 1, 24) + qualityTilt * 0.4
  const previousOperatingMargin =
    operatingMargin +
    (riskProfile ? between(random, 0.9, 3.5) : between(random, -2.5, 1.2))
  const netMargin = operatingMargin * between(random, 0.35, 0.76) - between(random, 0, 2)
  const roe = between(random, 3, 22) + qualityTilt * 0.35
  const equityRatio =
    industry === '銀行業'
      ? between(random, 8, 26)
      : riskProfile
        ? between(random, 18, 36)
        : between(random, 38, 76) + qualityTilt * 0.5
  const operatingCfMargin =
    netMargin +
    (riskProfile ? between(random, -8, 2) : between(random, -1, 9)) +
    qualityTilt * 0.2
  const debtRatio =
    industry === '電気・ガス業'
      ? riskProfile
        ? between(random, 2.5, 4.2)
        : between(random, 1.1, 2.3)
      : riskProfile
        ? between(random, 2.1, 3.4)
        : between(random, 0.1, 1.8) - qualityTilt * 0.04
  const netCash = between(random, -700, 900) + qualityTilt * 28
  const inventoryGrowth =
    revenueGrowth +
    (riskProfile ? between(random, 9, 18) : between(random, -7, 7))
  const receivablesGrowth =
    revenueGrowth +
    (riskProfile ? between(random, 9, 17) : between(random, -7, 7))
  const per =
    (riskProfile ? between(random, 42, 64) : between(random, 7, 38)) +
    Math.max(revenueGrowth, 0) * 0.2
  const pbr =
    (riskProfile ? between(random, 4.8, 7) : between(random, 0.5, 3.5)) +
    Math.max(roe - 12, 0) * 0.05

  const rawMetrics: RawMetrics = {
    revenueGrowth: round(revenueGrowth),
    operatingMargin: round(operatingMargin),
    netMargin: round(netMargin),
    roe: round(roe),
    equityRatio: round(equityRatio),
    operatingCfMargin: round(operatingCfMargin),
    debtRatio: round(Math.max(0.05, debtRatio), 2),
    netCash: Math.round(netCash),
    inventoryGrowth: round(inventoryGrowth),
    receivablesGrowth: round(receivablesGrowth),
    per: round(per),
    pbr: round(pbr),
  }

  const revenueBase = between(random, 450, 9200)
  const history: FinancialYearPoint[] = [
    {
      year: '2024/3',
      revenue: Math.round(revenueBase),
      operatingMargin: round(previousOperatingMargin + between(random, -2.5, 2.5)),
      netMargin: round(netMargin + between(random, -2.5, 2.5)),
      roe: round(roe + between(random, -4, 4)),
      operatingCfMargin: round(operatingCfMargin + between(random, -5, 5)),
    },
    {
      year: '2025/3',
      revenue: Math.round(revenueBase * (1 + previousRevenueGrowth / 100)),
      operatingMargin: round(previousOperatingMargin),
      netMargin: round(netMargin + between(random, -1.5, 1.5)),
      roe: round(roe + between(random, -2.5, 2.5)),
      operatingCfMargin: round(operatingCfMargin + between(random, -3, 3)),
    },
    {
      year: '2026/3',
      revenue: Math.round(
        revenueBase *
          (1 + previousRevenueGrowth / 100) *
          (1 + revenueGrowth / 100),
      ),
      operatingMargin: rawMetrics.operatingMargin,
      netMargin: rawMetrics.netMargin,
      roe: rawMetrics.roe,
      operatingCfMargin: rawMetrics.operatingCfMargin,
    },
  ]

  const linearTrend = (previous: number, current: number, variance = 1.5) => [
    previous + between(random, -variance, variance),
    previous,
    previous + (current - previous) * 0.45 + between(random, -variance / 2, variance / 2),
    current,
  ]

  const metrics: CompanyMetrics = {
    revenueGrowth: createMetric(
      'revenueGrowth',
      rawMetrics.revenueGrowth,
      round(previousRevenueGrowth),
      '%',
      linearTrend(previousRevenueGrowth, rawMetrics.revenueGrowth, 2.5),
    ),
    operatingMargin: createMetric(
      'operatingMargin',
      rawMetrics.operatingMargin,
      round(previousOperatingMargin),
      '%',
      linearTrend(previousOperatingMargin, rawMetrics.operatingMargin),
    ),
    netMargin: createMetric(
      'netMargin',
      rawMetrics.netMargin,
      round(history[1].netMargin),
      '%',
      history.map((point) => point.netMargin),
    ),
    roe: createMetric(
      'roe',
      rawMetrics.roe,
      round(history[1].roe),
      '%',
      history.map((point) => point.roe),
    ),
    equityRatio: createMetric(
      'equityRatio',
      rawMetrics.equityRatio,
      round(rawMetrics.equityRatio + between(random, -4, 4)),
      '%',
      linearTrend(rawMetrics.equityRatio + between(random, -5, 5), rawMetrics.equityRatio),
    ),
    operatingCfMargin: createMetric(
      'operatingCfMargin',
      rawMetrics.operatingCfMargin,
      round(history[1].operatingCfMargin),
      '%',
      history.map((point) => point.operatingCfMargin),
    ),
    debtRatio: createMetric(
      'debtRatio',
      rawMetrics.debtRatio,
      round(rawMetrics.debtRatio + between(random, -0.35, 0.35), 2),
      '倍',
      linearTrend(rawMetrics.debtRatio + between(random, -0.5, 0.5), rawMetrics.debtRatio, 0.15),
    ),
    netCash: createMetric(
      'netCash',
      rawMetrics.netCash,
      Math.round(rawMetrics.netCash + between(random, -180, 180)),
      '億円',
      linearTrend(rawMetrics.netCash + between(random, -240, 240), rawMetrics.netCash, 60),
    ),
    inventoryGrowth: createMetric(
      'inventoryGrowth',
      rawMetrics.inventoryGrowth,
      round(rawMetrics.inventoryGrowth + between(random, -7, 7)),
      '%',
      linearTrend(rawMetrics.inventoryGrowth + between(random, -9, 9), rawMetrics.inventoryGrowth, 2),
    ),
    receivablesGrowth: createMetric(
      'receivablesGrowth',
      rawMetrics.receivablesGrowth,
      round(rawMetrics.receivablesGrowth + between(random, -7, 7)),
      '%',
      linearTrend(rawMetrics.receivablesGrowth + between(random, -9, 9), rawMetrics.receivablesGrowth, 2),
    ),
    per: createMetric(
      'per',
      rawMetrics.per,
      round(rawMetrics.per + between(random, -8, 8)),
      '倍',
      linearTrend(rawMetrics.per + between(random, -10, 10), rawMetrics.per, 2),
    ),
    pbr: createMetric(
      'pbr',
      rawMetrics.pbr,
      round(rawMetrics.pbr + between(random, -1.1, 1.1)),
      '倍',
      linearTrend(rawMetrics.pbr + between(random, -1.3, 1.3), rawMetrics.pbr, 0.3),
    ),
  }

  const warnings = buildWarnings(rawMetrics, previousOperatingMargin, history)
  const themePool = themesForCompany(name, industry)
  const themes = [
    themePool[index % themePool.length],
    themePool[(index + 1) % themePool.length],
  ]

  return {
    id: code,
    name,
    code,
    market,
    industry,
    themes,
    scores: calculateScores(rawMetrics),
    metrics,
    history,
    industryKpis: createIndustryKpis(profile, random),
    strengths: buildStrengths(rawMetrics),
    warnings,
    analysisComment: buildAnalysisComment(
      rawMetrics,
      warnings,
      previousOperatingMargin,
    ),
    hasWarning: warnings.length > 0,
  }
}

export const companies = companyMaster.map(createCompany)

export const marketsList = markets
export const industriesList = industries
export const themeList = Array.from(
  new Set(
    companyMaster.flatMap((company) =>
      themesForCompany(company.name, company.industry),
    ),
  ),
).sort((a, b) => a.localeCompare(b, 'ja'))
