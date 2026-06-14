import { RotateCcw, SlidersHorizontal } from 'lucide-react'
import { industriesList, marketsList, themeList } from '../lib/mockGenerator'
import type { CompanyFilter } from '../types'

interface FilterPanelProps {
  filter: CompanyFilter
  onChange: (filter: CompanyFilter) => void
}

const defaultFilter: CompanyFilter = {
  query: '',
  market: 'all',
  industry: 'all',
  theme: 'all',
  warningsOnly: false,
  sort: 'score-desc',
}

export default function FilterPanel({
  filter,
  onChange,
}: FilterPanelProps) {
  const update = <K extends keyof CompanyFilter>(
    key: K,
    value: CompanyFilter[K],
  ) => onChange({ ...filter, [key]: value })

  return (
    <section className="filter-panel">
      <div className="filter-panel__title">
        <SlidersHorizontal size={17} />
        <span>絞り込み</span>
      </div>
      <label>
        市場区分
        <select
          value={filter.market}
          onChange={(event) =>
            update('market', event.target.value as CompanyFilter['market'])
          }
        >
          <option value="all">すべて</option>
          {marketsList.map((market) => (
            <option key={market} value={market}>
              {market}
            </option>
          ))}
        </select>
      </label>
      <label>
        業種
        <select
          value={filter.industry}
          onChange={(event) =>
            update('industry', event.target.value as CompanyFilter['industry'])
          }
        >
          <option value="all">すべて</option>
          {industriesList.map((industry) => (
            <option key={industry} value={industry}>
              {industry}
            </option>
          ))}
        </select>
      </label>
      <label>
        投資テーマ
        <select
          value={filter.theme}
          onChange={(event) => update('theme', event.target.value)}
        >
          <option value="all">すべて</option>
          {themeList.map((theme) => (
            <option key={theme} value={theme}>
              {theme}
            </option>
          ))}
        </select>
      </label>
      <label>
        並び順
        <select
          value={filter.sort}
          onChange={(event) =>
            update('sort', event.target.value as CompanyFilter['sort'])
          }
        >
          <option value="code-asc">証券コード順</option>
          <option value="score-desc">総合スコアが高い順</option>
          <option value="per-asc">PERが低い順</option>
          <option value="pbr-asc">PBRが低い順</option>
          <option value="roe-desc">ROEが高い順</option>
          <option value="operatingMargin-desc">営業利益率が高い順</option>
        </select>
      </label>
      <label className="toggle-field">
        <input
          type="checkbox"
          checked={filter.warningsOnly}
          onChange={(event) => update('warningsOnly', event.target.checked)}
        />
        <span>注意フラグありのみ</span>
      </label>
      <button
        type="button"
        className="button button--ghost filter-panel__reset"
        onClick={() => onChange(defaultFilter)}
      >
        <RotateCcw size={15} />
        リセット
      </button>
    </section>
  )
}
