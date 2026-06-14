import { AlertTriangle, ArrowRight, Bookmark, Building2, Gauge, Layers3, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import ScoreBadge from '../components/ScoreBadge'
import { useApp } from '../context/AppContext'
import { listedCompanySource } from '../lib/companySource'

const pieColors = ['#007AFF', '#5856D6', '#FF9F0A', '#AF52DE', '#FF375F']
export default function Dashboard() {
  const { companies, watchlist, financialSnapshot } = useApp()
  const warningCount = companies.filter((company) => company.hasWarning).length
  const averageScore = companies.reduce((sum, company) => sum + company.scores.overall, 0) / companies.length
  const industryData = Object.entries(companies.reduce<Record<string, number>>((counts, company) => { counts[company.industry] = (counts[company.industry] ?? 0) + 1; return counts }, {})).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value).slice(0, 12)
  const themeData = Object.entries(companies.reduce<Record<string, number>>((counts, company) => { company.themes.forEach((theme) => { counts[theme] = (counts[theme] ?? 0) + 1 }); return counts }, {})).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value).slice(0, 8)
  const topCompanies = [...companies].sort((a, b) => b.scores.overall - a.scores.overall).slice(0, 5)
  return <div className="page">
    <section className="hero-panel"><div><span className="page-eyebrow">OVERVIEW / JPX {listedCompanySource.date.slice(0, 4)}.{listedCompanySource.date.slice(4, 6)}</span><h1>企業の現在地を、<br />数字の輪郭からつかむ。</h1><p>財務KPI、業種別の着眼点、強みと違和感をひとつの視界に。株価ではなく、事業の変化を追う企業分析ワークスペースです。</p></div><div className="hero-panel__score"><span>Universe 平均</span><ScoreBadge score={averageScore} /><small>{financialSnapshot?.status === 'ready' ? `EDINET実データ ${financialSnapshot.stats.companies.toLocaleString('ja-JP')}社を含む` : `${companies.length.toLocaleString('ja-JP')}社のモックKPI平均`}</small></div></section>
    <section className={`data-status data-status--${financialSnapshot?.status ?? 'error'}`}><RefreshCw size={18} /><div><strong>{financialSnapshot?.status === 'ready' ? 'EDINET財務データを自動更新中' : 'EDINET自動更新の初期設定待ち'}</strong><span>{financialSnapshot?.status === 'ready' ? `${financialSnapshot.stats.companies.toLocaleString('ja-JP')}社を収録 / 最終生成 ${new Date(financialSnapshot.generatedAt ?? '').toLocaleString('ja-JP')}` : '現在はモックKPIです。APIキー設定後、GitHub Actionsが3時間ごとに開示差分を取得します。'}</span></div></section>
    <section className="summary-grid">
      <article className="summary-card"><span className="summary-card__icon"><Building2 /></span><div><small>全企業数</small><strong>{companies.length.toLocaleString('ja-JP')}</strong></div><span className="summary-card__note">JPX domestic equities</span></article>
      <article className="summary-card"><span className="summary-card__icon summary-card__icon--blue"><Bookmark /></span><div><small>ウォッチリスト</small><strong>{watchlist.length}</strong></div><Link to="/watchlist">深く見る <ArrowRight size={14} /></Link></article>
      <article className="summary-card"><span className="summary-card__icon summary-card__icon--red"><AlertTriangle /></span><div><small>注意フラグ企業</small><strong>{warningCount.toLocaleString('ja-JP')}</strong></div><span className="summary-card__note">{Math.round((warningCount / companies.length) * 100)}% of universe</span></article>
      <article className="summary-card"><span className="summary-card__icon summary-card__icon--yellow"><Gauge /></span><div><small>平均スコア</small><strong>{Math.round(averageScore)}</strong></div><span className="summary-card__note">分析補助指標</span></article>
    </section>
    <section className="dashboard-grid">
      <article className="panel panel--wide"><div className="panel__heading"><div><span className="section-kicker">SECTOR MAP</span><h2>業種別企業数 上位12業種</h2></div><Layers3 size={20} /></div><div className="chart-wrap chart-wrap--bar"><ResponsiveContainer width="100%" height="100%"><BarChart data={industryData} margin={{ left: -12, right: 8, top: 8 }}><XAxis dataKey="name" tick={{ fill: '#8E8E93', fontSize: 10 }} interval={0} angle={-18} textAnchor="end" height={58} /><YAxis tick={{ fill: '#8E8E93', fontSize: 11 }} allowDecimals={false} /><Tooltip cursor={{ fill: 'rgba(0,122,255,0.05)' }} /><Bar dataKey="value" name="企業数" fill="#007AFF" radius={[7,7,2,2]} isAnimationActive={false} /></BarChart></ResponsiveContainer></div></article>
      <article className="panel"><div className="panel__heading"><div><span className="section-kicker">THEMES</span><h2>注目テーマ</h2></div></div><div className="theme-chart"><ResponsiveContainer width="100%" height={210}><PieChart><Pie data={themeData.slice(0,5)} innerRadius={58} outerRadius={88} paddingAngle={3} dataKey="value" isAnimationActive={false}>{themeData.slice(0,5).map((entry,index)=><Cell key={entry.name} fill={pieColors[index]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer><div className="theme-list">{themeData.slice(0,5).map((theme,index)=><div key={theme.name}><i style={{background:pieColors[index]}} /><span>{theme.name}</span><strong>{theme.value}</strong></div>)}</div></div></article>
      <article className="panel panel--full"><div className="panel__heading"><div><span className="section-kicker">TOP SIGNALS</span><h2>総合スコア上位</h2></div><Link className="text-link" to="/universe">Universeを見る <ArrowRight size={15} /></Link></div><div className="ranking-grid">{topCompanies.map((company,index)=><Link to={`/company/${company.id}`} className="ranking-card" key={company.id}><span className="ranking-card__rank">0{index+1}</span><div><strong>{company.name}</strong><small>{company.code} / {company.industry}</small></div><ScoreBadge score={company.scores.overall} compact /></Link>)}</div></article>
    </section>
  </div>
}
