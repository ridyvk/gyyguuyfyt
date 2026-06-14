import type { ScoreKey } from '../types'

export const scoreLabels: Record<ScoreKey, string> = {
  growth: '成長性',
  profitability: '収益性',
  safety: '安全性',
  cashGeneration: 'CF創出力',
  valuation: '割安性',
}

interface ScoreBarProps {
  label: string
  score: number
  compact?: boolean
}

export default function ScoreBar({
  label,
  score,
  compact = false,
}: ScoreBarProps) {
  const tone = score >= 70 ? 'high' : score >= 50 ? 'mid' : 'low'
  return (
    <div className={`score-bar ${compact ? 'score-bar--compact' : ''}`}>
      <div className="score-bar__label">
        <span>{label}</span>
        <strong>{Math.round(score)}</strong>
      </div>
      <div className="score-bar__track">
        <span
          className={`score-bar__fill score-bar__fill--${tone}`}
          style={{ width: `${Math.max(4, Math.min(score, 100))}%` }}
        />
      </div>
    </div>
  )
}
