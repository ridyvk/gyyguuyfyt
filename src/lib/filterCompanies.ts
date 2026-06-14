import type { Company, CompanyFilter } from '../types'

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
        case 'per-asc':
          return a.metrics.per.value - b.metrics.per.value
        case 'pbr-asc':
          return a.metrics.pbr.value - b.metrics.pbr.value
        case 'roe-desc':
          return b.metrics.roe.value - a.metrics.roe.value
        case 'operatingMargin-desc':
          return b.metrics.operatingMargin.value - a.metrics.operatingMargin.value
        default:
          return b.scores.overall - a.scores.overall
      }
    })
}
