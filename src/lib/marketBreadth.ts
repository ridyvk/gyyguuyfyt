import type { Company } from '../types'

export interface BreadthCounts { up: number; down: number; flat: number }

export function getMarketBreadth(companies: Pick<Company, 'stockPrice'>[], tradingDate?: string | null): BreadthCounts {
  return companies.reduce((counts, { stockPrice: quote }) => {
    if (!tradingDate || !quote || quote.stale || quote.date !== tradingDate
      || typeof quote.changePercent !== 'number' || !Number.isFinite(quote.changePercent)) return counts
    counts[quote.changePercent > 0 ? 'up' : quote.changePercent < 0 ? 'down' : 'flat'] += 1
    return counts
  }, { up: 0, down: 0, flat: 0 })
}
