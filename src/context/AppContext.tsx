import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import {
  loadCompareList,
  loadReadDisclosureIds,
  loadWatchlist,
  saveCompareList,
  saveReadDisclosureIds,
  saveWatchlist,
} from '../lib/storage'
import type {
  Company,
  DisclosureEvent,
  DisclosureSnapshot,
  FinancialSnapshot,
  MarketSnapshot,
  UpdateStatus,
} from '../types'
import {
  hasFinancialData,
  loadDisclosureSnapshot,
  loadFinancialSnapshot,
  loadMarketSnapshot,
  loadUpdateStatus,
  mergeLiveCompanies,
} from '../lib/liveData'

interface AppContextValue {
  companies: Company[]
  watchlist: string[]
  compareList: string[]
  storageReady: boolean
  financialSnapshot: FinancialSnapshot | null
  marketSnapshot: MarketSnapshot | null
  updateStatus: UpdateStatus | null
  disclosureSnapshot: DisclosureSnapshot | null
  disclosures: DisclosureEvent[]
  readDisclosureIds: string[]
  unreadDisclosureCount: number
  toggleWatchlist: (companyId: string) => void
  toggleCompare: (companyId: string) => boolean
  removeFromCompare: (companyId: string) => void
  clearCompare: () => void
  isWatched: (companyId: string) => boolean
  isCompared: (companyId: string) => boolean
  isDisclosureRead: (eventId: string) => boolean
  markDisclosureRead: (eventId: string) => void
  markDisclosuresRead: (eventIds: string[]) => void
}

const AppContext = createContext<AppContextValue | null>(null)
const MARKET_REFRESH_INTERVAL_MS = 15 * 60 * 1000

const marketVersion = (snapshot: MarketSnapshot | null) =>
  snapshot?.generatedAt ?? snapshot?.latestQuoteTimestamp ?? null

const disclosureVersion = (snapshot: DisclosureSnapshot | null) =>
  snapshot?.generatedAt ?? snapshot?.latestFiledAt ?? null

export function AppProvider({ children }: { children: ReactNode }) {
  const [companies, setCompanies] = useState<Company[]>([])
  const [watchlist, setWatchlist] = useState<string[]>([])
  const [compareList, setCompareList] = useState<string[]>([])
  const [readDisclosureIds, setReadDisclosureIds] = useState<string[]>([])
  const [storageReady, setStorageReady] = useState(false)
  const [financialSnapshot, setFinancialSnapshot] =
    useState<FinancialSnapshot | null>(null)
  const [marketSnapshot, setMarketSnapshot] = useState<MarketSnapshot | null>(
    null,
  )
  const [updateStatus, setUpdateStatus] = useState<UpdateStatus | null>(null)
  const [disclosureSnapshot, setDisclosureSnapshot] =
    useState<DisclosureSnapshot | null>(null)
  const companyUniverseRef = useRef<Company[]>([])
  const financialSnapshotRef = useRef<FinancialSnapshot | null>(null)
  const marketVersionRef = useRef<string | null>(null)
  const disclosureVersionRef = useRef<string | null>(null)

  useEffect(() => {
    let active = true
    Promise.all([
      import('../lib/companyUniverse'),
      loadWatchlist(),
      loadCompareList(),
      loadReadDisclosureIds(),
      loadFinancialSnapshot().catch(() => null),
      loadMarketSnapshot().catch(() => null),
      loadUpdateStatus().catch(() => null),
    ])
      .then(
        ([
          companyModule,
          storedWatchlist,
          storedCompare,
          storedReadDisclosureIds,
          snapshot,
          marketSnapshot,
          updateStatus,
        ]) => {
        if (!active) return
        companyUniverseRef.current = companyModule.companies
        financialSnapshotRef.current = snapshot
        marketVersionRef.current = marketVersion(marketSnapshot)
        const loadedCompanies = mergeLiveCompanies(
          companyModule.companies,
          snapshot,
          marketSnapshot,
        )
        setCompanies(loadedCompanies)
        setFinancialSnapshot(snapshot)
        setMarketSnapshot(marketSnapshot)
        setUpdateStatus(updateStatus)
        setReadDisclosureIds(storedReadDisclosureIds)
        const validIds = new Set(
          loadedCompanies.map((company) => company.id),
        )
        setWatchlist(storedWatchlist.filter((id) => validIds.has(id)))
        const comparableIds = new Set(
          loadedCompanies
            .filter(hasFinancialData)
            .map((company) => company.id),
        )
        setCompareList(
          storedCompare.filter((id) => comparableIds.has(id)).slice(0, 5),
        )
        },
      )
      .finally(() => {
        if (active) setStorageReady(true)
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    void loadDisclosureSnapshot()
      .then((snapshot) => {
        if (!active) return
        disclosureVersionRef.current = disclosureVersion(snapshot)
        setDisclosureSnapshot(snapshot)
      })
      .catch(() => undefined)
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!storageReady) return

    let active = true
    let refreshInFlight = false
    let disclosureRefreshInFlight = false

    const refreshMarket = async () => {
      if (refreshInFlight || companyUniverseRef.current.length === 0) return
      refreshInFlight = true
      try {
        const nextSnapshot = await loadMarketSnapshot()
        if (!active) return
        const nextVersion = marketVersion(nextSnapshot)
        if (nextVersion === marketVersionRef.current) return
        marketVersionRef.current = nextVersion
        setMarketSnapshot(nextSnapshot)
        setCompanies(
          mergeLiveCompanies(
            companyUniverseRef.current,
            financialSnapshotRef.current,
            nextSnapshot,
          ),
        )
      } catch {
        return
      } finally {
        refreshInFlight = false
      }
    }

    const refreshDisclosures = async () => {
      if (disclosureRefreshInFlight) return
      disclosureRefreshInFlight = true
      try {
        const nextSnapshot = await loadDisclosureSnapshot()
        if (!active) return
        const nextVersion = disclosureVersion(nextSnapshot)
        if (nextVersion === disclosureVersionRef.current) return
        disclosureVersionRef.current = nextVersion
        setDisclosureSnapshot(nextSnapshot)
      } catch {
        return
      } finally {
        disclosureRefreshInFlight = false
      }
    }

    const intervalId = window.setInterval(() => {
      void refreshMarket()
      void refreshDisclosures()
    }, MARKET_REFRESH_INTERVAL_MS)
    const handleFocus = () => {
      void refreshMarket()
      void refreshDisclosures()
    }
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        void refreshMarket()
        void refreshDisclosures()
      }
    }

    window.addEventListener('focus', handleFocus)
    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      active = false
      window.clearInterval(intervalId)
      window.removeEventListener('focus', handleFocus)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [storageReady])

  const toggleWatchlist = useCallback((companyId: string) => {
    setWatchlist((current) => {
      const next = current.includes(companyId)
        ? current.filter((id) => id !== companyId)
        : [...current, companyId]
      void saveWatchlist(next)
      return next
    })
  }, [])

  const toggleCompare = useCallback(
    (companyId: string) => {
      if (compareList.includes(companyId)) {
        const next = compareList.filter((id) => id !== companyId)
        setCompareList(next)
        void saveCompareList(next)
        return true
      }
      if (compareList.length >= 5) return false
      const next = [...compareList, companyId]
      setCompareList(next)
      void saveCompareList(next)
      return true
    },
    [compareList],
  )

  const removeFromCompare = useCallback((companyId: string) => {
    setCompareList((current) => {
      const next = current.filter((id) => id !== companyId)
      void saveCompareList(next)
      return next
    })
  }, [])

  const clearCompare = useCallback(() => {
    setCompareList([])
    void saveCompareList([])
  }, [])

  const markDisclosuresRead = useCallback((eventIds: string[]) => {
    if (!eventIds.length) return
    setReadDisclosureIds((current) => {
      const next = Array.from(new Set([...current, ...eventIds])).slice(-800)
      void saveReadDisclosureIds(next)
      return next
    })
  }, [])

  const markDisclosureRead = useCallback(
    (eventId: string) => markDisclosuresRead([eventId]),
    [markDisclosuresRead],
  )

  const disclosures = useMemo(
    () => disclosureSnapshot?.events ?? [],
    [disclosureSnapshot],
  )
  const unreadDisclosureCount = useMemo(() => {
    const readIds = new Set(readDisclosureIds)
    const watchedIds = new Set(watchlist)
    const now = Date.now()
    const globalCutoff = now - 24 * 60 * 60 * 1000
    const watchlistCutoff = now - 7 * 24 * 60 * 60 * 1000
    return disclosures.filter(
      (event) => {
        if (
          (event.importance !== 'critical' && event.importance !== 'high') ||
          readIds.has(event.id)
        ) return false
        const filedAt = new Date(event.filedAt).getTime()
        if (!Number.isFinite(filedAt)) return false
        return filedAt >= globalCutoff || (
          watchedIds.has(event.code) && filedAt >= watchlistCutoff
        )
      },
    ).length
  }, [disclosures, readDisclosureIds, watchlist])

  const value = useMemo<AppContextValue>(
    () => ({
      companies,
      watchlist,
      compareList,
      storageReady,
      financialSnapshot,
      marketSnapshot,
      updateStatus,
      disclosureSnapshot,
      disclosures,
      readDisclosureIds,
      unreadDisclosureCount,
      toggleWatchlist,
      toggleCompare,
      removeFromCompare,
      clearCompare,
      isWatched: (companyId) => watchlist.includes(companyId),
      isCompared: (companyId) => compareList.includes(companyId),
      isDisclosureRead: (eventId) => readDisclosureIds.includes(eventId),
      markDisclosureRead,
      markDisclosuresRead,
    }),
    [
      companies,
      watchlist,
      compareList,
      storageReady,
      financialSnapshot,
      marketSnapshot,
      updateStatus,
      disclosureSnapshot,
      disclosures,
      readDisclosureIds,
      unreadDisclosureCount,
      toggleWatchlist,
      toggleCompare,
      removeFromCompare,
      clearCompare,
      markDisclosureRead,
      markDisclosuresRead,
    ],
  )

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export const useApp = () => {
  const context = useContext(AppContext)
  if (!context) throw new Error('useApp must be used inside AppProvider')
  return context
}
