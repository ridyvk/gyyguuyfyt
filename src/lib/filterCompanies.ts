import type { Company, CompanyFilter } from '../types'

const compareMetric = (
  a: Company,
  b: Company,
  key: 'per' | 'pbr' | 'roe' | 'operatingMargin',
  direction: 'asc' | 'desc',
) => {
  const aMetric = a.metrics[key]
  const bMetric = b.metrics[key]
  if (aMetric.available === false) return bMetric.available === false ? 0 : 1
  if (bMetric.available === false) return -1
  return direction === 'asc'
    ? aMetric.value - bMetric.value
    : bMetric.value - aMetric.value
}

export const filterCompanies = (
  companies: Company[],
  filter: CompanyFilter,
) => {
  const normalizedQuery = filter.query.trim().toLowerCase()

  return companies
    .filter((company) => {
      const matchesQuery =
        !normalizedQuery ||
        company.name.toLowerCase().includes(normalizedQuery) ||
        company.code.includes(normalizedQuery)
      const matchesMarket =
        filter.market === 'all' || company.market === filter.market
      const matchesIndustry =
        filter.industry === 'all' || company.industry === filter.industry
      const matchesTheme =
        filter.theme === 'all' || company.themes.includes(filter.theme)
      const matchesWarning = !filter.warningsOnly || company.hasWarning

      return (
        matchesQuery &&
        matchesMarket &&
        matchesIndustry &&
        matchesTheme &&
        matchesWarning
      )
    })
    .sort((a, b) => {
      switch (filter.sort) {
        case 'code-asc':
          return a.code.localeCompare(b.code, 'ja-JP', { numeric: true })
        case 'per-asc':
          return compareMetric(a, b, 'per', 'asc')
        case 'pbr-asc':
          return compareMetric(a, b, 'pbr', 'asc')
        case 'roe-desc':
          return compareMetric(a, b, 'roe', 'desc')
        case 'operatingMargin-desc':
          return compareMetric(a, b, 'operatingMargin', 'desc')
        default:
          if (a.dataSource !== 'EDINET') {
            return b.dataSource !== 'EDINET' ? 0 : 1
          }
          if (b.dataSource !== 'EDINET') return -1
          return b.scores.overall - a.scores.overall
      }
    })
}
