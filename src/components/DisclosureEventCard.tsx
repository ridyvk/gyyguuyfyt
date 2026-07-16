import {
  ArrowUpRight,
  Building2,
  CalendarClock,
  Check,
  CircleDollarSign,
  FileCheck2,
  FilePenLine,
  FileText,
  HandCoins,
  Landmark,
  Merge,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
  UserRoundCog,
  UsersRound,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import type {
  DisclosureCategory,
  DisclosureEvent,
  DisclosureSignal,
} from '../types'

const categoryIcons: Record<DisclosureCategory, typeof FileText> = {
  earnings: FileCheck2,
  guidance: Sparkles,
  dividend: HandCoins,
  buyback: CircleDollarSign,
  ma: Merge,
  capital: Landmark,
  finance: Landmark,
  governance: ShieldAlert,
  personnel: UserRoundCog,
  'large-holding': UsersRound,
  'annual-report': FileText,
  correction: FilePenLine,
  other: FileText,
}

const importanceLabels = {
  critical: '最重要',
  high: '重要',
  medium: '確認',
  low: '通常',
}

const signalIcon = (signal: DisclosureSignal) => {
  if (signal.direction === 'positive') return TrendingUp
  if (signal.direction === 'negative') return TrendingDown
  if (signal.direction === 'review') return FilePenLine
  return Check
}

const filedAtLabel = (value: string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const now = new Date()
  const formatter = new Intl.DateTimeFormat('ja-JP', {
    timeZone: 'Asia/Tokyo',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
  const dateKey = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tokyo',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
  const currentKey = dateKey.format(now)
  const targetKey = dateKey.format(date)
  const yesterday = new Date(now)
  yesterday.setDate(yesterday.getDate() - 1)
  const prefix = targetKey === currentKey
    ? '今日 '
    : targetKey === dateKey.format(yesterday)
      ? '昨日 '
      : ''
  return `${prefix}${formatter.format(date)}`
}

interface DisclosureEventCardProps {
  event: DisclosureEvent
  read?: boolean
  compact?: boolean
  onRead?: (eventId: string) => void
}

export default function DisclosureEventCard({
  event,
  read = false,
  compact = false,
  onRead,
}: DisclosureEventCardProps) {
  const CategoryIcon = categoryIcons[event.category]

  return (
    <article
      className={`disclosure-card disclosure-card--${event.importance}${read ? ' is-read' : ' is-unread'}${compact ? ' disclosure-card--compact' : ''}`}
    >
      <div className="disclosure-card__rail" aria-hidden="true">
        <span><CategoryIcon size={16} /></span>
      </div>
      <div className="disclosure-card__body">
        <div className="disclosure-card__meta">
          <span className={`importance-badge importance-badge--${event.importance}`}>
            {importanceLabels[event.importance]}
          </span>
          <span className="category-badge">{event.categoryLabel}</span>
          <span className={`source-badge source-badge--${event.source.toLowerCase()}`}>
            {event.source}
          </span>
          <span className="disclosure-card__time">
            <CalendarClock size={12} />
            {filedAtLabel(event.filedAt)}
          </span>
          {!read && <span className="unread-indicator">NEW</span>}
        </div>

        <div className="disclosure-card__company-line">
          <Link to={`/company/${event.code}`} onClick={() => onRead?.(event.id)}>
            <span>{event.code}</span>
            <strong>{event.companyName}</strong>
          </Link>
        </div>

        <h3>{event.title}</h3>
        {!compact && <p>{event.summary}</p>}

        {event.signals.length > 0 && (
          <div className="disclosure-signals" aria-label="検出した変更シグナル">
            {event.signals.map((signal) => {
              const SignalIcon = signalIcon(signal)
              return (
                <span
                  className={`disclosure-signal disclosure-signal--${signal.direction}`}
                  key={signal.label}
                  title="開示タイトルから判定"
                >
                  <SignalIcon size={12} />
                  {signal.label}
                </span>
              )
            })}
          </div>
        )}

        {!compact && event.previousComparableFiledAt && (
          <div className="disclosure-card__comparison">
            <FilePenLine size={13} />
            <span>
              同カテゴリの前回開示から
              <strong>{event.daysSincePrevious ?? '—'}日</strong>
            </span>
            {event.isCorrection && <b>前回開示との照合推奨</b>}
          </div>
        )}

        <div className="disclosure-card__actions">
          <Link to={`/company/${event.code}`} onClick={() => onRead?.(event.id)}>
            <Building2 size={13} />
            企業分析へ
          </Link>
          <a
            href={event.url}
            target="_blank"
            rel="noreferrer"
            onClick={() => onRead?.(event.id)}
          >
            原文を開く
            <ArrowUpRight size={13} />
          </a>
        </div>
      </div>
    </article>
  )
}
