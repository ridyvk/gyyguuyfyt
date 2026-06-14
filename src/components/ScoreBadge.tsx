import { formatScore } from '../lib/formatters'
import { scoreLabel } from '../lib/scoring'

interface ScoreBadgeProps {
  score: number
  compact?: boolean
}

export default function ScoreBadge({
  score,
  compact = false,
}: ScoreBadgeProps) {
  const tone = score >= 70 ? 'high' : score >= 50 ? 'mid' : 'low'
  return (
    <div
      className={`score-badge score-badge--${tone} ${compact ? 'score-badge--compact' : ''}`}
      aria-label={`総合スコア ${formatScore(score)}点`}
    >
      <span>{formatScore(score)}</span>
      {!compact && <small>{scoreLabel(score)}</small>}
    </div>
  )
}
