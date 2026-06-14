import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import { formatDelta, formatMetric, statusLabel } from '../lib/formatters'
import type { KpiMetric } from '../types'
import MiniTrendChart from './MiniTrendChart'

interface KpiTileProps {
  label: string
  metric: KpiMetric
}

const statusColors = {
  good: '#34C759',
  normal: '#FF9F0A',
  warning: '#FF3B30',
  unknown: '#8E8E93',
}

export default function KpiTile({ label, metric }: KpiTileProps) {
  const delta = metric.value - metric.previousValue
  const DeltaIcon = delta > 0.05 ? ArrowUpRight : delta < -0.05 ? ArrowDownRight : Minus

  return (
    <article className={`kpi-tile kpi-tile--${metric.status}`}>
      <div className="kpi-tile__top">
        <span className="kpi-tile__label">{label}</span>
        <span className={`status-pill status-pill--${metric.status}`}>
          {statusLabel[metric.status]}
        </span>
      </div>
      <div className="kpi-tile__value">{formatMetric(metric)}</div>
      <div className={`kpi-tile__delta ${delta >= 0 ? 'is-up' : 'is-down'}`}>
        <DeltaIcon size={14} />
        前年差 {formatDelta(metric)}
      </div>
      <MiniTrendChart
        data={metric.trend}
        color={statusColors[metric.status]}
        height={52}
      />
      <p>{metric.comment}</p>
    </article>
  )
}
