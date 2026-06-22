import type { Company, CompanyFilter } from '../types'
import { hasScorableData } from './liveData'

const compareMetric = (
  a: Company,
  b: Company,
  key: 'per' | 'pbr' | 'roe' | 'operatingMargin',
  direction: 'asc' | 'desc',
) => {
  const aMetric = a.metrics[key]
  const bMetric = b.metrics[key]
  const aTrusted =
    aMetric.available !== false &&
    (aMetric.confidence === 'A' || aMetric.confidence === 'B')
  const bTrusted =
    bMetric.available !== false &&
    (bMetric.confidence === 'A' || bMetric.confidence === 'B')
  if (!aTrusted) return !bTrusted ? 0 : 1
  if (!bTrusted) return -1
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
          if (!hasScorableData(a)) {
            return hasScorableData(b) ? 1 : 0
          }
          if (!hasScorableData(b)) return -1
          return b.scores.overall - a.scores.overall
      }
    })
}
