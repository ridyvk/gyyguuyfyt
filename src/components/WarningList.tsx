import { AlertCircle, AlertTriangle, CheckCircle2 } from 'lucide-react'

interface WarningListProps {
  warnings: string[]
  compact?: boolean
  unavailable?: boolean
}

export default function WarningList({
  warnings,
  compact = false,
  unavailable = false,
}: WarningListProps) {
  if (unavailable) {
    return (
      <div className="empty-signal empty-signal--unknown">
        <AlertCircle size={18} />
        財務データ未取得のため判定できません
      </div>
    )
  }

  if (!warnings.length) {
    return (
      <div className="empty-signal">
        <CheckCircle2 size={18} />
        主要な注意フラグはありません
      </div>
    )
  }

  return (
    <ul className={`warning-list ${compact ? 'warning-list--compact' : ''}`}>
      {warnings.map((warning) => (
        <li key={warning}>
          <AlertTriangle size={16} />
          <span>{warning}</span>
        </li>
      ))}
    </ul>
  )
}
