import type {
  Company,
  CompanyMetrics,
  Industry,
  KpiKey,
  KpiMetric,
  ListedCompanyMaster,
  Market,
  Scores,
} from '../types'
import listedCompanyData from '../data/listedCompanies.json'

const markets: Market[] = ['プライム', 'スタンダード', 'グロース']
const companyMaster =
  listedCompanyData.companies as ListedCompanyMaster[]
const industries: Industry[] = Array.from(
  new Set(companyMaster.map((company) => company.industry)),
).sort((a, b) => a.localeCompare(b, 'ja'))

const kpiKeys: KpiKey[] = [
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
]

const units: Record<KpiKey, KpiMetric['unit']> = {
  revenueGrowth: '%',
  operatingMargin: '%',
  netMargin: '%',
  roe: '%',
  equityRatio: '%',
  operatingCfMargin: '%',
  debtRatio: '倍',
  netCash: '億円',
  inventoryGrowth: '%',
  receivablesGrowth: '%',
  per: '倍',
  pbr: '倍',
}

const unavailableScores: Scores = {
  growth: 0,
  profitability: 0,
  safety: 0,
  cashGeneration: 0,
  valuation: 0,
  overall: 0,
}

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

const createUnavailableMetric = (key: KpiKey): KpiMetric => ({
  value: 0,
  previousValue: 0,
  unit: units[key],
  status: 'unknown',
  comment: '開示データから取得できません',
  trend: [],
  available: false,
})

const createUnavailableMetrics = () =>
  Object.fromEntries(
    kpiKeys.map((key) => [key, createUnavailableMetric(key)]),
  ) as CompanyMetrics

const createCompany = (
  master: ListedCompanyMaster,
  index: number,
): Company => {
  const { industry, market, name, code } = master
  const themePool = themesForCompany(name, industry)

  return {
    id: code,
    name,
    code,
    market,
    industry,
    themes: [
      themePool[index % themePool.length],
      themePool[(index + 1) % themePool.length],
    ],
    scores: { ...unavailableScores },
    metrics: createUnavailableMetrics(),
    history: [],
    industryKpis: [],
    strengths: [],
    warnings: [],
    analysisComment:
      'EDINET・TDnetからこの企業の比較可能な財務データを取得できていないため、分析コメントは生成していません。',
    hasWarning: false,
    dataSource: 'unavailable',
    liveMetricCount: 0,
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
