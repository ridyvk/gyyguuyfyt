import { Bookmark, ChevronRight, GitCompareArrows } from 'lucide-react'
import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
} from 'react'
import { Link } from 'react-router-dom'
import { formatMetric } from '../lib/formatters'
import { hasFinancialData } from '../lib/liveData'
import type { Company, ScoreKey } from '../types'
import MiniTrendChart from './MiniTrendChart'
import RadarScoreChart from './RadarScoreChart'
import ScoreBadge from './ScoreBadge'
import ScoreBar, { scoreLabels } from './ScoreBar'
import StockQuoteCard from './StockQuoteCard'
import WarningList from './WarningList'

interface CompanyCardProps {
  company: Company
  watched: boolean
  compared?: boolean
  variant?: 'compact' | 'expanded'
  motionIndex?: number
  onToggleWatch: () => void
  onToggleCompare?: () => void
}

const scoreKeys: ScoreKey[] = [
  'growth',
  'profitability',
  'safety',
  'cashGeneration',
  'valuation',
]

export default function CompanyCard({
  company,
  watched,
  compared = false,
  variant = 'compact',
  motionIndex = 0,
  onToggleWatch,
  onToggleCompare,
}: CompanyCardProps) {
  const expanded = variant === 'expanded'
  const financialAvailable = hasFinancialData(company)
  const sourceLabel =
    company.dataSource === 'TDnet' ? 'TDnet決算短信' : 'EDINET実データ'
  const cardRef = useRef<HTMLElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const card = cardRef.current
    if (!card) return

    let observer: IntersectionObserver | undefined
    const observe = () => {
      if (!('IntersectionObserver' in window)) {
        setVisible(true)
        return
      }

      observer = new IntersectionObserver(
        ([entry]) => {
          if (!entry.isIntersecting) return
          setVisible(true)
          observer?.disconnect()
        },
        { threshold: 0.06, rootMargin: '0px 0px -4% 0px' },
      )
      observer.observe(card)
    }

    if (document.body.classList.contains('startup-active')) {
      window.addEventListener('kpi-startup-complete', observe, { once: true })
    } else {
      observe()
    }

    return () => {
      window.removeEventListener('kpi-startup-complete', observe)
      observer?.disconnect()
    }
  }, [])

  return (
    <article
      ref={cardRef}
      className={`company-card company-card--${variant} company-card--motion${company.hasWarning ? ' company-card--has-warning' : ''}${visible ? ' is-visible' : ''}`}
      style={
        {
          '--card-delay': `${(motionIndex % 6) * 52}ms`,
        } as CSSProperties
      }
    >
      <div className="company-card__header">
        <div>
          <div className="company-card__eyebrow">
            <span>{company.code}</span>
            <span>{company.market}</span>
          </div>
          <Link to={`/company/${company.id}`} className="company-card__name">
            {company.name}
          </Link>
          <p className="company-card__industry">{company.industry}</p>
          <span
            className={`data-badge data-badge--${financialAvailable ? company.dataSource?.toLowerCase() : 'unavailable'}`}
          >
            {financialAvailable ? sourceLabel : '財務データ未取得'}
          </span>
        </div>
        <ScoreBadge
          score={company.scores.overall}
          compact={!expanded}
          available={financialAvailable}
        />
      </div>

      <div className="tag-row">
        {company.themes.map((theme) => (
          <span className="tag" key={theme}>
            {theme}
          </span>
        ))}
      </div>

      <div className="company-card__scores">
        {scoreKeys.map((key) => (
          <ScoreBar
            key={key}
            label={scoreLabels[key]}
            score={company.scores[key]}
            compact
            available={financialAvailable}
          />
        ))}
      </div>

      {company.stockPrice && (
        <StockQuoteCard
          quote={company.stockPrice}
          label="終値"
          variant={expanded ? 'hero' : 'card'}
        />
      )}

      <div className="company-card__metrics">
        <div>
          <span>PER</span>
          <strong>{formatMetric(company.metrics.per)}</strong>
        </div>
        <div>
          <span>PBR</span>
          <strong>{formatMetric(company.metrics.pbr)}</strong>
        </div>
        <div>
          <span>ROE</span>
          <strong>{formatMetric(company.metrics.roe)}</strong>
        </div>
        <div>
          <span>営業利益率</span>
          <strong>{formatMetric(company.metrics.operatingMargin)}</strong>
        </div>
        <div>
          <span>自己資本比率</span>
          <strong>{formatMetric(company.metrics.equityRatio)}</strong>
        </div>
      </div>

      {expanded && financialAvailable && (
        <>
          <div className="company-card__visuals">
            <div className="company-card__radar">
              <RadarScoreChart scores={company.scores} height={220} />
            </div>
            <div className="company-card__trend">
              <span className="section-kicker">営業利益率トレンド</span>
              <strong>{formatMetric(company.metrics.operatingMargin)}</strong>
              <MiniTrendChart
                data={company.metrics.operatingMargin.trend}
                height={100}
                showTooltip
              />
              <p>{company.analysisComment}</p>
            </div>
          </div>
          <div className="company-card__insights">
            <div>
              <span className="section-kicker">強み</span>
              <ul className="strength-list">
                {company.strengths.slice(0, 3).map((strength) => (
                  <li key={strength}>{strength}</li>
                ))}
              </ul>
            </div>
            <div>
              <span className="section-kicker">注意点</span>
              <WarningList warnings={company.warnings.slice(0, 2)} compact />
            </div>
          </div>
        </>
      )}

      {expanded && !financialAvailable && (
        <div className="company-card__unavailable">
          EDINET・TDnetから比較可能な財務データを取得できていません。架空値は表示しません。
        </div>
      )}

      {!expanded && (
        <div className="company-card__warning">
          {!financialAvailable ? (
            <span className="flag flag--unknown">判定不能</span>
          ) : company.hasWarning ? (
            <span className="flag flag--warning">
              注意 {company.warnings.length}件
            </span>
          ) : (
            <span className="flag flag--clear">注意なし</span>
          )}
        </div>
      )}

      <div className="company-card__actions">
        <button
          type="button"
          className={`button ${watched ? 'button--active' : 'button--secondary'}`}
          onClick={onToggleWatch}
        >
          <Bookmark size={16} fill={watched ? 'currentColor' : 'none'} />
          {watched ? '登録済み' : 'ウォッチ'}
        </button>
        {expanded && onToggleCompare && (
          <button
            type="button"
            className={`button ${compared ? 'button--active' : 'button--secondary'}`}
            disabled={!financialAvailable}
            onClick={onToggleCompare}
          >
            <GitCompareArrows size={16} />
            {!financialAvailable
              ? '比較不可'
              : compared
                ? '比較中'
                : '比較に追加'}
          </button>
        )}
        <Link className="button button--ghost" to={`/company/${company.id}`}>
          詳細
          <ChevronRight size={16} />
        </Link>
      </div>
    </article>
  )
}
