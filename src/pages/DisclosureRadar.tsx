import {
  AlertTriangle,
  BellRing,
  Bookmark,
  CheckCheck,
  ChevronDown,
  CircleDotDashed,
  Clock3,
  FilePenLine,
  Filter,
  Radar,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import DisclosureEventCard from '../components/DisclosureEventCard'
import { useApp } from '../context/AppContext'
import type {
  DisclosureCategory,
  DisclosureEvent,
  DisclosureImportance,
  DisclosureSource,
} from '../types'

const categories: { value: DisclosureCategory | 'all'; label: string }[] = [
  { value: 'all', label: 'すべてのカテゴリ' },
  { value: 'earnings', label: '決算' },
  { value: 'guidance', label: '業績予想' },
  { value: 'dividend', label: '配当' },
  { value: 'buyback', label: '自己株式' },
  { value: 'ma', label: 'M&A・提携' },
  { value: 'capital', label: '資本政策' },
  { value: 'finance', label: '資金調達' },
  { value: 'governance', label: 'ガバナンス' },
  { value: 'personnel', label: '人事' },
  { value: 'large-holding', label: '大量保有' },
  { value: 'annual-report', label: '法定開示' },
  { value: 'correction', label: '訂正' },
  { value: 'other', label: 'その他' },
]

const importanceFilters: {
  value: DisclosureImportance | 'all' | 'important'
  label: string
}[] = [
  { value: 'all', label: 'すべて' },
  { value: 'important', label: '重要以上' },
  { value: 'critical', label: '最重要' },
  { value: 'high', label: '重要' },
  { value: 'medium', label: '要確認' },
]

const importanceWeight: Record<DisclosureImportance, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
}

const formatDateTime = (value?: string | null) => {
  if (!value) return '未取得'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('ja-JP', {
    timeZone: 'Asia/Tokyo',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

const isWithinDays = (event: DisclosureEvent, days: number) => {
  const time = new Date(event.filedAt).getTime()
  return Number.isFinite(time) && time >= Date.now() - days * 86_400_000
}

export default function DisclosureRadar() {
  const {
    disclosures,
    disclosureSnapshot,
    watchlist,
    readDisclosureIds,
    isDisclosureRead,
    markDisclosureRead,
    markDisclosuresRead,
  } = useApp()
  const [searchParams, setSearchParams] = useSearchParams()
  const [visibleCount, setVisibleCount] = useState(36)
  const query = searchParams.get('q') ?? searchParams.get('company') ?? ''
  const category = (searchParams.get('category') ?? 'all') as DisclosureCategory | 'all'
  const importance = (searchParams.get('importance') ?? 'all') as
    | DisclosureImportance
    | 'all'
    | 'important'
  const source = (searchParams.get('source') ?? 'all') as DisclosureSource | 'all'
  const days = Number(searchParams.get('days') ?? 120)
  const watchedOnly = searchParams.get('watched') === '1'
  const unreadOnly = searchParams.get('unread') === '1'
  const sort = searchParams.get('sort') === 'importance' ? 'importance' : 'latest'
  const readSet = useMemo(() => new Set(readDisclosureIds), [readDisclosureIds])
  const watchSet = useMemo(() => new Set(watchlist), [watchlist])

  const updateParam = (key: string, value: string | null) => {
    setVisibleCount(36)
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      if (!value || value === 'all' || (key === 'days' && value === '120')) {
        next.delete(key)
      } else {
        next.set(key, value)
      }
      if (key === 'q') next.delete('company')
      return next
    }, { replace: true })
  }

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase('ja-JP')
    const selectedDays = Number.isFinite(days) && days > 0 ? days : 120
    return disclosures
      .filter((event) => {
        if (days !== 120 && !isWithinDays(event, selectedDays)) return false
        if (category !== 'all' && event.category !== category) return false
        if (source !== 'all' && event.source !== source) return false
        if (
          importance === 'important' &&
          event.importance !== 'critical' &&
          event.importance !== 'high'
        ) return false
        if (
          importance !== 'all' &&
          importance !== 'important' &&
          event.importance !== importance
        ) return false
        if (watchedOnly && !watchSet.has(event.code)) return false
        if (unreadOnly && readSet.has(event.id)) return false
        if (
          normalizedQuery &&
          !`${event.code} ${event.companyName} ${event.title} ${event.categoryLabel}`
            .toLocaleLowerCase('ja-JP')
            .includes(normalizedQuery)
        ) return false
        return true
      })
      .sort((a, b) => {
        if (sort === 'importance') {
          const weight = importanceWeight[b.importance] - importanceWeight[a.importance]
          if (weight) return weight
          const score = b.importanceScore - a.importanceScore
          if (score) return score
        }
        return b.filedAt.localeCompare(a.filedAt)
      })
  }, [
    category,
    days,
    disclosures,
    importance,
    query,
    readSet,
    sort,
    source,
    unreadOnly,
    watchSet,
    watchedOnly,
  ])

  const last24Hours = disclosures.filter((event) => isWithinDays(event, 1))
  const importantEvents = disclosures.filter(
    (event) =>
      isWithinDays(event, 7) &&
      (event.importance === 'critical' || event.importance === 'high'),
  )
  const watchedImportant = importantEvents.filter((event) => watchSet.has(event.code))
  const correctionCount = disclosures.filter(
    (event) => event.isCorrection && isWithinDays(event, 30),
  ).length
  const unreadImportant = importantEvents.filter(
    (event) =>
      !readSet.has(event.id) &&
      (isWithinDays(event, 1) || watchSet.has(event.code)),
  )
  const activeFilterCount = [
    query,
    category !== 'all',
    importance !== 'all',
    source !== 'all',
    days !== 120,
    watchedOnly,
    unreadOnly,
    sort !== 'latest',
  ].filter(Boolean).length

  const categoryMix = useMemo(() => {
    const counts = new Map<string, { label: string; count: number }>()
    disclosures.forEach((event) => {
      const current = counts.get(event.category) ?? {
        label: event.categoryLabel,
        count: 0,
      }
      current.count += 1
      counts.set(event.category, current)
    })
    return [...counts.values()].sort((a, b) => b.count - a.count).slice(0, 6)
  }, [disclosures])
  const maxCategoryCount = categoryMix[0]?.count ?? 1

  const clearFilters = () => {
    setVisibleCount(36)
    setSearchParams({}, { replace: true })
  }

  return (
    <div className="page disclosure-page">
      <section className="disclosure-hero">
        <div className="disclosure-hero__content">
          <span className="page-eyebrow">DISCLOSURE RADAR / TDnet + EDINET</span>
          <h1>開示の変化を、<br />見逃さない。</h1>
          <p>
            決算、業績修正、配当、自己株式、M&amp;A、資本政策を自動分類。
            重要度と訂正シグナルを添えて、原文まで最短でたどれます。
          </p>
          <div className="disclosure-hero__status">
            <span className={`live-dot live-dot--${disclosureSnapshot?.status ?? 'error'}`} />
            <strong>
              {disclosureSnapshot?.status === 'ready'
                ? '自動監視中'
                : disclosureSnapshot?.status === 'partial'
                  ? '初期データ・一部監視'
                  : '取得状態を確認中'}
            </strong>
            <span>最終生成 {formatDateTime(disclosureSnapshot?.generatedAt)}</span>
            <span>最新開示 {formatDateTime(disclosureSnapshot?.latestFiledAt)}</span>
          </div>
        </div>
        <div className="disclosure-hero__orb">
          <div>
            <Radar size={32} />
            <strong>{unreadImportant.length}</strong>
            <span>未読の重要開示</span>
          </div>
        </div>
      </section>

      {disclosureSnapshot && disclosureSnapshot.status !== 'ready' && (
        <section className={`disclosure-notice disclosure-notice--${disclosureSnapshot.status}`}>
          <RefreshCw size={17} />
          <div>
            <strong>{disclosureSnapshot.message}</strong>
            <span>表示中の判定は開示タイトルと提出メタデータに基づきます。数値は必ず原文で確認できます。</span>
          </div>
        </section>
      )}

      <section className="disclosure-metrics" aria-label="開示レーダー概要">
        <article>
          <span className="disclosure-metric__icon disclosure-metric__icon--blue"><Clock3 /></span>
          <div><small>24時間の新着</small><strong>{last24Hours.length}</strong></div>
          <span>提出ベース</span>
        </article>
        <article>
          <span className="disclosure-metric__icon disclosure-metric__icon--red"><AlertTriangle /></span>
          <div><small>7日間の重要</small><strong>{importantEvents.length}</strong></div>
          <span>最重要・重要</span>
        </article>
        <article>
          <span className="disclosure-metric__icon disclosure-metric__icon--violet"><Bookmark /></span>
          <div><small>Watchlist重要</small><strong>{watchedImportant.length}</strong></div>
          <span>{watchlist.length}社を監視</span>
        </article>
        <article>
          <span className="disclosure-metric__icon disclosure-metric__icon--orange"><FilePenLine /></span>
          <div><small>30日間の訂正</small><strong>{correctionCount}</strong></div>
          <span>照合推奨</span>
        </article>
      </section>

      <section className="disclosure-layout">
        <div className="disclosure-main">
          <div className="disclosure-controls">
            <div className="disclosure-search">
              <Search size={17} />
              <input
                value={query}
                onChange={(event) => updateParam('q', event.target.value || null)}
                placeholder="企業名・証券コード・開示タイトルで検索"
                aria-label="開示を検索"
              />
              {query && (
                <button type="button" onClick={() => updateParam('q', null)} aria-label="検索を消去">
                  <X size={15} />
                </button>
              )}
            </div>

            <div className="disclosure-quick-filters">
              {importanceFilters.map((filter) => (
                <button
                  type="button"
                  className={importance === filter.value ? 'is-active' : ''}
                  onClick={() => updateParam('importance', filter.value)}
                  key={filter.value}
                >
                  {filter.value === 'critical' && <Sparkles size={13} />}
                  {filter.label}
                </button>
              ))}
              <button
                type="button"
                className={watchedOnly ? 'is-active' : ''}
                onClick={() => updateParam('watched', watchedOnly ? null : '1')}
              >
                <Bookmark size={13} /> Watchlist
              </button>
              <button
                type="button"
                className={unreadOnly ? 'is-active' : ''}
                onClick={() => updateParam('unread', unreadOnly ? null : '1')}
              >
                <BellRing size={13} /> 未読
              </button>
            </div>

            <div className="disclosure-select-row">
              <label>
                <Filter size={14} />
                <select value={category} onChange={(event) => updateParam('category', event.target.value)}>
                  {categories.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                </select>
                <ChevronDown size={13} />
              </label>
              <label>
                <select value={source} onChange={(event) => updateParam('source', event.target.value)}>
                  <option value="all">TDnet + EDINET</option>
                  <option value="TDnet">TDnetのみ</option>
                  <option value="EDINET">EDINETのみ</option>
                </select>
                <ChevronDown size={13} />
              </label>
              <label>
                <select value={days} onChange={(event) => updateParam('days', event.target.value)}>
                  <option value="1">24時間</option>
                  <option value="7">7日間</option>
                  <option value="30">30日間</option>
                  <option value="120">全期間</option>
                </select>
                <ChevronDown size={13} />
              </label>
              <label>
                <select value={sort} onChange={(event) => updateParam('sort', event.target.value)}>
                  <option value="latest">新着順</option>
                  <option value="importance">重要度順</option>
                </select>
                <ChevronDown size={13} />
              </label>
            </div>
          </div>

          <div className="disclosure-results-head">
            <div>
              <span className="section-kicker">LIVE FEED</span>
              <h2>{filtered.length.toLocaleString('ja-JP')}件の開示</h2>
            </div>
            <div>
              {activeFilterCount > 0 && (
                <button type="button" className="text-button" onClick={clearFilters}>
                  <X size={13} /> 条件をクリア
                </button>
              )}
              {filtered.some((event) => !readSet.has(event.id)) && (
                <button
                  type="button"
                  className="text-button text-button--primary"
                  onClick={() => markDisclosuresRead(filtered.map((event) => event.id))}
                >
                  <CheckCheck size={14} /> 表示中を既読
                </button>
              )}
            </div>
          </div>

          {filtered.length > 0 ? (
            <div className="disclosure-feed">
              {filtered.slice(0, visibleCount).map((event) => (
                <DisclosureEventCard
                  key={event.id}
                  event={event}
                  read={isDisclosureRead(event.id)}
                  onRead={markDisclosureRead}
                />
              ))}
              {visibleCount < filtered.length && (
                <button
                  type="button"
                  className="disclosure-load-more"
                  onClick={() => setVisibleCount((count) => count + 36)}
                >
                  さらに36件読み込む
                  <span>{visibleCount.toLocaleString('ja-JP')} / {filtered.length.toLocaleString('ja-JP')}</span>
                </button>
              )}
            </div>
          ) : (
            <div className="disclosure-empty">
              <CircleDotDashed size={30} />
              <h2>条件に一致する開示はありません</h2>
              <p>期間や重要度を広げるか、検索条件をクリアして確認できます。</p>
              <button type="button" className="button button--primary" onClick={clearFilters}>すべての開示を見る</button>
            </div>
          )}
        </div>

        <aside className="disclosure-sidebar">
          <section className="radar-side-card radar-side-card--attention">
            <div className="radar-side-card__head">
              <div><span className="section-kicker">ATTENTION</span><h2>優先確認</h2></div>
              <BellRing size={18} />
            </div>
            {unreadImportant.slice(0, 5).map((event) => (
              <Link
                to={`/company/${event.code}`}
                className={`attention-item attention-item--${event.importance}`}
                onClick={() => markDisclosureRead(event.id)}
                key={event.id}
              >
                <span>{event.code}</span>
                <strong>{event.companyName}</strong>
                <small>{event.signals[0]?.label ?? event.categoryLabel}</small>
              </Link>
            ))}
            {unreadImportant.length === 0 && (
              <div className="attention-empty"><ShieldCheck size={22} /><span>未読の重要開示はありません</span></div>
            )}
          </section>

          <section className="radar-side-card">
            <div className="radar-side-card__head">
              <div><span className="section-kicker">CATEGORY MIX</span><h2>開示構成</h2></div>
            </div>
            <div className="category-mix">
              {categoryMix.map((item) => (
                <button
                  type="button"
                  onClick={() => {
                    const matched = disclosures.find((event) => event.categoryLabel === item.label)
                    if (matched) updateParam('category', matched.category)
                  }}
                  key={item.label}
                >
                  <span><b>{item.label}</b><strong>{item.count.toLocaleString('ja-JP')}</strong></span>
                  <i><span style={{ width: `${Math.max(4, item.count / maxCategoryCount * 100)}%` }} /></i>
                </button>
              ))}
            </div>
          </section>

          <section className="radar-side-card">
            <div className="radar-side-card__head">
              <div><span className="section-kicker">DATA SOURCES</span><h2>取得状態</h2></div>
            </div>
            <div className="source-status-list">
              {(['TDnet', 'EDINET'] as DisclosureSource[]).map((item) => {
                const status = disclosureSnapshot?.sourceStatus[item]
                return (
                  <div key={item}>
                    <span className={`source-status-dot source-status-dot--${status?.status ?? 'error'}`} />
                    <strong>{item}</strong>
                    <small>
                      {status?.status === 'ready'
                        ? `${status.eventsFetched ?? 0}件取得`
                        : status?.status === 'bootstrap'
                          ? '初期データ'
                          : '前回値を維持'}
                    </small>
                  </div>
                )
              })}
            </div>
            <p className="radar-method-note">
              重要度と変更シグナルはタイトル・提出情報からルール判定。投資判断ではなく、原文確認の優先順位付けに使います。
            </p>
          </section>
        </aside>
      </section>
    </div>
  )
}
