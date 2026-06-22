import { AlertCircle, AlertTriangle, CheckCircle2 } from 'lucide-react'

interface WarningListProps {
  warnings: string[]
  compact?: boolean
  unavailable?: boolean
  indeterminate?: boolean
  limited?: boolean
}

export default function WarningList({
  warnings,
  compact = false,
  unavailable = false,
  indeterminate = false,
  limited = false,
}: WarningListProps) {
  if (unavailable) {
    return (
      <div className="empty-signal empty-signal--unknown">
        <AlertCircle size={18} />
        財務データ未取得のため判定できません
      </div>
    )
  }

  if (indeterminate) {
    return (
      <div className="empty-signal empty-signal--unknown">
        <AlertCircle size={18} />
        参考KPIはありますが、信頼度A/B不足のため注意点は判定保留です
      </div>
    )
  }

  if (!warnings.length) {
    return (
      <div className={`empty-signal${limited ? ' empty-signal--unknown' : ''}`}>
        {limited ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
        {limited
          ? '取得済みの信頼度A/B指標では注意フラグなし。未取得項目は未判定です'
          : '主要な注意フラグはありません'}
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
