import {
  ArrowDownRight,
  ArrowUpRight,
  ChevronDown,
  Database,
  Minus,
  ShieldCheck,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import {
  comparisonLabelForMetric,
  formatDelta,
  formatMetric,
  hasPreviousMetricValue,
  statusLabel,
} from '../lib/formatters'
import type { KpiConfidence, KpiMetric, XbrlSourceFact } from '../types'
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

const confidenceLabels: Record<KpiConfidence, string> = {
  A: '信頼度 A',
  B: '信頼度 B',
  C: '信頼度 C',
  review: '要確認',
}

const consolidationLabels: Record<XbrlSourceFact['consolidation'], string> = {
  consolidated: '連結',
  'non-consolidated': '単体',
  unknown: '不明',
}

function uniqueValues(values: (string | undefined)[]) {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value))))
}

function formatPeriods(facts: XbrlSourceFact[]) {
  return uniqueValues(
    facts.map((fact) =>
      fact.periodStart ? `${fact.periodStart} 〜 ${fact.periodEnd}` : fact.periodEnd,
    ),
  )
}

export default function KpiTile({ label, metric }: KpiTileProps) {
  const tileRef = useRef<HTMLElement>(null)
  const [visible, setVisible] = useState(false)
  const isNotApplicable = metric.applicable === false
  const hasPreviousValue = hasPreviousMetricValue(metric)
  const comparisonLabel = comparisonLabelForMetric(metric)
  const delta = hasPreviousValue ? metric.value - metric.previousValue! : 0
  const DeltaIcon = delta > 0.05 ? ArrowUpRight : delta < -0.05 ? ArrowDownRight : Minus
  const sourceFacts = metric.provenance?.sourceFacts ?? []
  const sourceTags = uniqueValues(sourceFacts.map((fact) => fact.tag))
  const contexts = uniqueValues(sourceFacts.map((fact) => fact.contextRef))
  const units = uniqueValues(sourceFacts.map((fact) => fact.unitRef))
  const consolidations = uniqueValues(
    sourceFacts.map((fact) => consolidationLabels[fact.consolidation]),
  )
  const periods = formatPeriods(sourceFacts)

  useEffect(() => {
    const tile = tileRef.current
    if (!tile || !('IntersectionObserver' in window)) {
      setVisible(true)
      return
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return
        setVisible(true)
        observer.unobserve(entry.target)
      },
      { threshold: 0.08, rootMargin: '0px 0px -6% 0px' },
    )

    observer.observe(tile)
    return () => observer.disconnect()
  }, [])

  return (
    <article
      ref={tileRef}
      className={`kpi-tile kpi-tile--${metric.status} kpi-tile--motion${visible ? ' is-visible' : ''}`}
    >
      <div className="kpi-tile__top">
        <span className="kpi-tile__label">{label}</span>
        <span className="kpi-tile__badges">
          {metric.confidence && (
            <span
              className={`confidence-pill confidence-pill--${metric.confidence}`}
              title={metric.confidenceReason}
            >
              <ShieldCheck size={11} />
              {confidenceLabels[metric.confidence]}
            </span>
          )}
          <span className={`status-pill status-pill--${metric.status}`}>
            {isNotApplicable ? '対象外' : statusLabel[metric.status]}
          </span>
        </span>
      </div>
      <div className="kpi-tile__value">{formatMetric(metric)}</div>
      {isNotApplicable ? (
        <div className="kpi-tile__delta">
          <Minus size={14} />
          業種別の共通評価対象外
        </div>
      ) : metric.available === false || !hasPreviousValue ? (
        <div className="kpi-tile__delta">
          <Minus size={14} />
          {formatDelta(metric)}
        </div>
      ) : (
        <div className={`kpi-tile__delta ${delta >= 0 ? 'is-up' : 'is-down'}`}>
          <DeltaIcon size={14} />
          {comparisonLabel} {formatDelta(metric)}
        </div>
      )}
      {visible ? (
        <MiniTrendChart
          data={metric.trend}
          color={statusColors[metric.status]}
          height={52}
        />
      ) : (
        <div style={{ height: 52 }} aria-hidden="true" />
      )}
      <p className="kpi-tile__comment">{metric.comment}</p>
      {metric.formula && (
        <div className="kpi-tile__formula">
          <span>計算式</span>
          <code>{metric.formula}</code>
        </div>
      )}
      {metric.confidence && (
        <details className="kpi-evidence">
          <summary>
            <span><Database size={13} />信頼度の根拠</span>
            <ChevronDown className="kpi-evidence__chevron" size={14} />
          </summary>
          <div className="kpi-evidence__body">
            <p>{metric.confidenceReason}</p>
            {metric.provenance?.formula && (
              <dl>
                <dt>抽出式</dt>
                <dd>{metric.provenance.formula}</dd>
              </dl>
            )}
            {sourceFacts.length > 0 ? (
              <dl>
                <dt>元タグ</dt>
                <dd>{sourceTags.join(', ')}</dd>
                <dt>context</dt>
                <dd>{contexts.join(', ')}</dd>
                <dt>単位</dt>
                <dd>{units.join(', ') || '単位指定なし'}</dd>
                <dt>連結区分</dt>
                <dd>{consolidations.join(', ')}</dd>
                <dt>対象期間</dt>
                <dd>{periods.join(', ')}</dd>
              </dl>
            ) : (
              <p className="kpi-evidence__empty">保存済みのXBRL元情報はありません。</p>
            )}
          </div>
        </details>
      )}
    </article>
  )
}
