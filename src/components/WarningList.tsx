import { AlertTriangle, CheckCircle2 } from 'lucide-react'

interface WarningListProps {
  warnings: string[]
  compact?: boolean
}

export default function WarningList({
  warnings,
  compact = false,
}: WarningListProps) {
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
