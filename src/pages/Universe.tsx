import { ChevronLeft, ChevronRight, Database, Sparkles } from 'lucide-react'
import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import CompanyCard from '../components/CompanyCard'
import FilterPanel from '../components/FilterPanel'
import SearchBox from '../components/SearchBox'
import { useApp } from '../context/AppContext'
import { filterCompanies } from '../lib/filterCompanies'
import { listedCompanySource } from '../lib/companySource'
import type { CompanyFilter } from '../types'

const pageSize = 12
const initialFilter: CompanyFilter = { query: '', market: 'all', industry: 'all', theme: 'all', warningsOnly: false, sort: 'score-desc' }

export default function Universe() {
  const { companies, isWatched, toggleWatchlist, financialSnapshot } = useApp()
  const [filter, setFilter] = useState(initialFilter)
  const [page, setPage] = useState(1)
  const deferredQuery = useDeferredValue(filter.query)
  const filtered = useMemo(() => filterCompanies(companies, { ...filter, query: deferredQuery }), [companies, filter, deferredQuery])
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const visibleCompanies = filtered.slice((page - 1) * pageSize, page * pageSize)
  useEffect(() => { setPage(1) }, [filter])

  return (
    <div className="page">
      <header className="page-header page-header--split">
        <div><span className="page-eyebrow">UNIVERSE / {companies.length.toLocaleString('ja-JP')} COMPANIES</span><h1>企業を探す</h1><p>軽量な一覧から、気になる変化と分析対象を絞り込みます。</p></div>
        <div className="universe-stat"><Database size={18} /><span><strong>{filtered.length.toLocaleString('ja-JP')}</strong> / {companies.length.toLocaleString('ja-JP')} companies</span></div>
      </header>
      <div className="universe-layout">
        <aside><FilterPanel filter={filter} onChange={setFilter} /></aside>
        <section className="universe-results">
          <div className="results-toolbar">
            <SearchBox value={filter.query} onChange={(query) => setFilter({ ...filter, query })} />
            <div className="results-toolbar__note"><Sparkles size={15} />JPX {listedCompanySource.date.slice(0, 4)}年{Number(listedCompanySource.date.slice(4, 6))}月末 / {financialSnapshot?.status === 'ready' ? `EDINET ${financialSnapshot.stats.companies.toLocaleString('ja-JP')}社` : 'KPIはモック'}</div>
          </div>
          {visibleCompanies.length ? <div className="company-grid">{visibleCompanies.map((company) => <CompanyCard key={company.id} company={company} watched={isWatched(company.id)} onToggleWatch={() => toggleWatchlist(company.id)} />)}</div> : <div className="empty-state"><Database size={30} /><h2>該当する企業がありません</h2><p>検索語やフィルター条件を調整してください。</p></div>}
          <div className="pagination">
            <button type="button" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page === 1}><ChevronLeft size={17} />前へ</button>
            <span>{page} / {totalPages}</span>
            <button type="button" onClick={() => setPage((value) => Math.min(totalPages, value + 1))} disabled={page === totalPages}>次へ<ChevronRight size={17} /></button>
          </div>
        </section>
      </div>
    </div>
  )
}
