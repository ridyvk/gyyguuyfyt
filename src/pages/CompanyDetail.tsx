import {
  ArrowLeft,
  Bookmark,
  Check,
  GitCompareArrows,
  Lightbulb,
  Save,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import KpiTile from '../components/KpiTile'
import RadarScoreChart from '../components/RadarScoreChart'
import ScoreBadge from '../components/ScoreBadge'
import ScoreBar, { scoreLabels } from '../components/ScoreBar'
import WarningList from '../components/WarningList'
import { useApp } from '../context/AppContext'
import { loadNote, saveNote } from '../lib/storage'
import {
  formatChangePercent,
  formatStockPrice,
} from '../lib/formatters'
import { hasFinancialData } from '../lib/liveData'
import type { CompanyNote, KpiKey, ScoreKey } from '../types'

const kpiLabels: Record<KpiKey, string> = {
  revenueGrowth: '売上成長率',
  operatingMargin: '営業利益率',
  netMargin: '純利益率',
  roe: 'ROE',
  equityRatio: '自己資本比率',
  operatingCfMargin: '営業CFマージン',
  debtRatio: '有利子負債倍率',
  netCash: 'ネットキャッシュ',
  inventoryGrowth: '棚卸資産増加率',
  receivablesGrowth: '売掛金増加率',
  per: 'PER',
  pbr: 'PBR',
}

const kpiKeys = Object.keys(kpiLabels) as KpiKey[]
const scoreKeys: ScoreKey[] = [
  'growth',
  'profitability',
  'safety',
  'cashGeneration',
  'valuation',
]

const emptyNote: CompanyNote = {
  watchReason: '',
  thesis: '',
  nextEarnings: '',
  buyCondition: '',
  avoidCondition: '',
  exitCondition: '',
  freeNote: '',
}

const noteFields: { key: keyof CompanyNote; label: string; placeholder: string }[] = [
  { key: 'watchReason', label: '監視理由', placeholder: 'なぜこの企業を追うのか' },
  { key: 'thesis', label: '投資仮説', placeholder: '中長期で何が変わると考えるか' },
  { key: 'nextEarnings', label: '次回決算で見るポイント', placeholder: '確認するKPIや会社計画' },
  { key: 'buyCondition', label: '買う条件', placeholder: '仮説が強まる具体的条件' },
  { key: 'avoidCondition', label: '買わない条件', placeholder: '見送る条件や懸念' },
  { key: 'exitCondition', label: '撤退条件', placeholder: '仮説が崩れたと判断する条件' },
  { key: 'freeNote', label: '自由メモ', placeholder: '決算メモ、競合、確認事項など' },
]

export default function CompanyDetail() {
  const { companyId } = useParams()
  const {
    companies,
    isWatched,
    isCompared,
    toggleWatchlist,
    toggleCompare,
  } = useApp()
  const company = useMemo(
    () => {
      const exact = companies.find((item) => item.id === companyId)
      if (exact) return exact
      const legacyIndex = companyId?.match(/^company-(\d+)$/)?.[1]
      return legacyIndex ? companies[Number(legacyIndex) - 1] : undefined
    },
    [companies, companyId],
  )
  const [note, setNote] = useState<CompanyNote>(emptyNote)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!company) return
    setNote(emptyNote)
    void loadNote(company.id).then((stored) => {
      if (stored) setNote(stored)
    })
  }, [company])

  if (!company) {
    return (
      <div className="page">
        <div className="empty-state">
          <h1>企業が見つかりません</h1>
          <Link className="button button--primary" to="/universe">Universeへ戻る</Link>
        </div>
      </div>
    )
  }

  const watched = isWatched(company.id)
  const compared = isCompared(company.id)
  const financialAvailable = hasFinancialData(company)
  const sourceLabel =
    company.dataSource === 'TDnet' ? 'TDnet決算短信' : 'EDINET実データ'
  const handleSave = async () => {
    await saveNote(company.id, note)
    setSaved(true)
    window.setTimeout(() => setSaved(false), 1800)
  }

  return (
    <div className="page">
      <Link to="/universe" className="back-link"><ArrowLeft size={16} /> Universeへ戻る</Link>

      <section className="company-hero">
        <div className="company-hero__main">
          <div className="company-hero__meta">
            <span>{company.code}</span><span>{company.market}</span><span>{company.industry}</span>
          </div>
          <h1>{company.name}</h1>
          <div className="tag-row">
            {company.themes.map((theme) => <span className="tag" key={theme}>{theme}</span>)}
          </div>
          <p>{company.analysisComment}</p>
          <div className="company-data-line">
            <span
              className={`data-badge data-badge--${financialAvailable ? company.dataSource?.toLowerCase() : 'unavailable'}`}
            >
              {financialAvailable ? sourceLabel : '財務データ未取得'}
            </span>
            {company.financialPeriod && <span>対象期 {company.financialPeriod}</span>}
            {company.dataUpdatedAt && (
              <span>
                開示 {new Date(company.dataUpdatedAt).toLocaleDateString('ja-JP')}
              </span>
            )}
            {company.financialSourceUrl && (
              <a
                href={company.financialSourceUrl}
                target="_blank"
                rel="noreferrer"
              >
                {company.dataSource === 'TDnet' ? '決算短信原文' : 'EDINET原文'}
              </a>
            )}
          </div>
          {company.stockPrice && (
            <div className="stock-quote stock-quote--hero">
              <div>
                <span>最新終値</span>
                <strong>{formatStockPrice(company.stockPrice.close)}</strong>
              </div>
              <span
                className={`stock-quote__change ${
                  (company.stockPrice.changePercent ?? 0) >= 0
                    ? 'stock-quote__change--up'
                    : 'stock-quote__change--down'
                }`}
              >
                {formatChangePercent(company.stockPrice.changePercent)}
              </span>
              <small>
                {company.stockPrice.date} · {company.stockPrice.source}
              </small>
            </div>
          )}
        </div>
        <div className="company-hero__score">
          <span>総合スコア</span>
          <ScoreBadge
            score={company.scores.overall}
            available={financialAvailable}
          />
          <small>
            {financialAvailable
              ? `実データ ${company.liveMetricCount ?? 0}/12 KPI`
              : '企業情報のみ収録 / 財務数値は表示しません'}
          </small>
        </div>
        <div className="company-hero__actions">
          <button
            type="button"
            className={`button ${watched ? 'button--active' : 'button--primary'}`}
            onClick={() => toggleWatchlist(company.id)}
          >
            <Bookmark size={17} fill={watched ? 'currentColor' : 'none'} />
            {watched ? 'ウォッチ解除' : 'ウォッチに追加'}
          </button>
          <button
            type="button"
            className={`button ${compared ? 'button--active' : 'button--secondary'}`}
            disabled={!financialAvailable}
            onClick={() => {
              const changed = toggleCompare(company.id)
              if (!changed) window.alert('比較できる企業は最大5社です。')
            }}
          >
            <GitCompareArrows size={17} />
            {!financialAvailable
              ? '財務データ未取得'
              : compared
                ? '比較から外す'
                : '比較に追加'}
          </button>
        </div>
      </section>

      <section className="detail-overview-grid">
        <article className="panel">
          <div className="panel__heading"><div><span className="section-kicker">SCORE SHAPE</span><h2>5分類スコア</h2></div></div>
          {financialAvailable ? (
            <RadarScoreChart scores={company.scores} height={300} />
          ) : (
            <div className="chart-empty">
              財務データ未取得のためスコア形状を表示できません
            </div>
          )}
        </article>
        <article className="panel score-list-panel">
          <div className="panel__heading"><div><span className="section-kicker">SCORE BREAKDOWN</span><h2>評価内訳</h2></div></div>
          <div className="detail-score-list">
            {scoreKeys.map((key) => (
              <ScoreBar
                key={key}
                label={scoreLabels[key]}
                score={company.scores[key]}
                available={financialAvailable}
              />
            ))}
          </div>
          <p className="method-note">業種横断の簡易ルールに基づく0〜100点の相対的な目安です。</p>
        </article>
      </section>

      <section className="section-block">
        <div className="section-heading"><div><span className="section-kicker">KEY METRICS</span><h2>KPIタイル</h2></div><p>数値・前年差・状態・短期トレンド</p></div>
        <div className="kpi-grid">
          {kpiKeys.map((key) => (
            <KpiTile key={key} label={kpiLabels[key]} metric={company.metrics[key]} />
          ))}
        </div>
      </section>

      <section className="detail-insight-grid">
        <article className="panel panel--wide">
          <div className="panel__heading"><div><span className="section-kicker">3 YEAR TREND</span><h2>業績推移</h2></div></div>
          <div className="chart-wrap chart-wrap--line">
            {company.history.length === 0 ? (
              <div className="chart-empty">3年分の比較可能データがありません</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={company.history}
                  margin={{ top: 10, right: 16, left: -8, bottom: 0 }}
                >
                  <CartesianGrid stroke="rgba(60,60,67,0.13)" strokeDasharray="4 4" vertical={false} />
                  <XAxis dataKey="year" tick={{ fill: '#8E8E93', fontSize: 11 }} />
                  <YAxis tick={{ fill: '#8E8E93', fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.96)', color: '#1C1C1E', border: '1px solid rgba(60,60,67,0.14)', borderRadius: 14, boxShadow: '0 12px 32px rgba(31,38,55,0.12)' }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line type="monotone" dataKey="operatingMargin" name="営業利益率" stroke="#007AFF" strokeWidth={3} dot={{ r: 4 }} isAnimationActive={false} />
                  <Line type="monotone" dataKey="roe" name="ROE" stroke="#5856D6" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
                  <Line type="monotone" dataKey="operatingCfMargin" name="営業CFマージン" stroke="#FF9F0A" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </article>
        <article className="panel">
          <div className="panel__heading"><div><span className="section-kicker">INDUSTRY KPIs</span><h2>{company.industry}の着眼点</h2></div></div>
          <div className="industry-kpi-list">
            {company.industryKpis.length ? (
              company.industryKpis.map((kpi) => (
                <div key={kpi.name}>
                  <span><i className={`signal-dot signal-dot--${kpi.signal}`} />{kpi.name}</span>
                  <strong>{kpi.value}</strong>
                </div>
              ))
            ) : (
              <div className="empty-signal empty-signal--unknown">
                業種別KPIは現在データソース未連携です
              </div>
            )}
          </div>
        </article>
      </section>

      <section className="analysis-grid">
        <article className="panel">
          <div className="panel__heading"><div><span className="section-kicker">STRENGTHS</span><h2>強み</h2></div></div>
          <ul className="strength-list strength-list--large">
            {company.strengths.length ? (
              company.strengths.map((strength) => <li key={strength}><Check size={16} />{strength}</li>)
            ) : (
              <li>財務データ未取得のため判定できません</li>
            )}
          </ul>
        </article>
        <article className="panel">
          <div className="panel__heading"><div><span className="section-kicker">WATCH SIGNALS</span><h2>注意点</h2></div></div>
          <WarningList
            warnings={company.warnings}
            unavailable={!financialAvailable}
          />
        </article>
        <article className="panel analysis-comment">
          <span className="analysis-comment__icon"><Lightbulb /></span>
          <div><span className="section-kicker">AUTO ANALYSIS</span><h2>自動分析コメント</h2><p>{company.analysisComment}</p></div>
        </article>
      </section>

      <section className="section-block notes-section">
        <div className="section-heading">
          <div><span className="section-kicker">RESEARCH NOTES</span><h2>分析メモ</h2></div>
          <button type="button" className={`button ${saved ? 'button--active' : 'button--primary'}`} onClick={handleSave}>
            {saved ? <Check size={16} /> : <Save size={16} />}
            {saved ? '保存しました' : 'メモを保存'}
          </button>
        </div>
        <div className="note-grid">
          {noteFields.map((field) => (
            <label key={field.key} className={field.key === 'freeNote' ? 'note-field note-field--wide' : 'note-field'}>
              <span>{field.label}</span>
              <textarea
                rows={field.key === 'freeNote' ? 5 : 3}
                placeholder={field.placeholder}
                value={note[field.key] ?? ''}
                onChange={(event) => setNote({ ...note, [field.key]: event.target.value })}
              />
            </label>
          ))}
        </div>
      </section>
    </div>
  )
}
