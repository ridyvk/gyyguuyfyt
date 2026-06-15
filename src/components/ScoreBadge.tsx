import { formatScore } from '../lib/formatters'
import { scoreLabel } from '../lib/scoring'

interface ScoreBadgeProps {
  score: number
  compact?: boolean
  available?: boolean
}

export default function ScoreBadge({
  score,
  compact = false,
  available = true,
}: ScoreBadgeProps) {
  const tone = available
    ? score >= 70
      ? 'high'
      : score >= 50
        ? 'mid'
        : 'low'
    : 'unknown'
  return (
    <div
      className={`score-badge score-badge--${tone} ${compact ? 'score-badge--compact' : ''}`}
      aria-label={
        available ? `総合スコア ${formatScore(score)}点` : '総合スコア 未取得'
      }
    >
      <span>{available ? formatScore(score) : '—'}</span>
      {!compact && <small>{available ? scoreLabel(score) : '未取得'}</small>}
    </div>
  )
}
