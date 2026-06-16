import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Minus,
} from 'lucide-react'
import { useId } from 'react'
import {
  formatChangePercent,
  formatStockPrice,
  formatVolume,
} from '../lib/formatters'
import type { MarketQuote } from '../types'

interface StockQuoteCardProps {
  quote?: MarketQuote
  label?: string
  variant?: 'card' | 'hero' | 'compare' | 'mini'
}

const trendPath = (quote: MarketQuote) => {
  const previous = quote.previousClose ?? quote.close
  const values = [previous, quote.close]
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || Math.max(1, quote.close * 0.01)
  return values
    .map((value, index) => {
      const x = 8 + index * 104
      const y = 38 - ((value - min) / range) * 26
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`
    })
    .join(' ')
}

export default function StockQuoteCard({
  quote,
  label = '最新終値',
  variant = 'card',
}: StockQuoteCardProps) {
  const gradientId = useId().replace(/:/g, '')
  if (!quote) {
    return (
      <div className={`stock-quote-card stock-quote-card--${variant} stock-quote-card--empty`}>
        <div className="stock-quote-card__top">
          <span className="stock-quote-card__label">
            <Activity size={13} />
            株価データ
          </span>
          <span>未取得</span>
        </div>
        <strong>—</strong>
        <small>次回の自動更新で取得します</small>
      </div>
    )
  }

  const change = quote.changePercent ?? 0
  const direction =
    change > 0 ? 'up' : change < 0 ? 'down' : 'flat'
  const ChangeIcon =
    direction === 'up' ? ArrowUpRight : direction === 'down' ? ArrowDownRight : Minus

  return (
    <div
      className={`stock-quote-card stock-quote-card--${variant} stock-quote-card--${direction}`}
    >
      <span className="stock-quote-card__aurora" aria-hidden="true" />
      <div className="stock-quote-card__top">
        <span className="stock-quote-card__label">
          <i />
          {label}
        </span>
        <span>{quote.source}</span>
      </div>

      <div className="stock-quote-card__value-row">
        <strong>{formatStockPrice(quote.close)}</strong>
        <b>
          <ChangeIcon size={14} />
          {formatChangePercent(quote.changePercent)}
        </b>
      </div>

      <svg
        className="stock-quote-card__spark"
        viewBox="0 0 120 46"
        role="img"
        aria-label="前日終値から最新終値への変化"
      >
        <defs>
          <linearGradient id={`${gradientId}-line`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.22" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0.95" />
          </linearGradient>
          <linearGradient id={`${gradientId}-fill`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.18" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path
          className="stock-quote-card__area"
          d={`${trendPath(quote)} L 112 45 L 8 45 Z`}
          fill={`url(#${gradientId}-fill)`}
        />
        <path
          className="stock-quote-card__line"
          d={trendPath(quote)}
          fill="none"
          stroke={`url(#${gradientId}-line)`}
          strokeLinecap="round"
          strokeWidth="3.2"
        />
        <circle
          className="stock-quote-card__dot"
          cx="112"
          cy={quote.previousClose === undefined ? 25 : change >= 0 ? 12 : 38}
          r="3.8"
          fill="currentColor"
        />
      </svg>

      <div className="stock-quote-card__meta">
        <span>{quote.date}</span>
        <span>出来高 {formatVolume(quote.volume)}</span>
      </div>
    </div>
  )
}
