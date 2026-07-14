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
  loadWatchlist,
  saveCompareList,
  saveWatchlist,
} from '../lib/storage'
import type {
  Company,
  FinancialSnapshot,
  MarketSnapshot,
  UpdateStatus,
} from '../types'
import {
  hasFinancialData,
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
  toggleWatchlist: (companyId: string) => void
  toggleCompare: (companyId: string) => boolean
  removeFromCompare: (companyId: string) => void
  clearCompare: () => void
  isWatched: (companyId: string) => boolean
  isCompared: (companyId: string) => boolean
}

const AppContext = createContext<AppContextValue | null>(null)
const MARKET_REFRESH_INTERVAL_MS = 15 * 60 * 1000

const marketVersion = (snapshot: MarketSnapshot | null) =>
  snapshot?.generatedAt ?? snapshot?.latestQuoteTimestamp ?? null

export function AppProvider({ children }: { children: ReactNode }) {
  const [companies, setCompanies] = useState<Company[]>([])
  const [watchlist, setWatchlist] = useState<string[]>([])
  const [compareList, setCompareList] = useState<string[]>([])
  const [storageReady, setStorageReady] = useState(false)
  const [financialSnapshot, setFinancialSnapshot] =
    useState<FinancialSnapshot | null>(null)
  const [marketSnapshot, setMarketSnapshot] = useState<MarketSnapshot | null>(
    null,
  )
  const [updateStatus, setUpdateStatus] = useState<UpdateStatus | null>(null)
  const companyUniverseRef = useRef<Company[]>([])
  const financialSnapshotRef = useRef<FinancialSnapshot | null>(null)
  const marketVersionRef = useRef<string | null>(null)

  useEffect(() => {
    let active = true
    Promise.all([
      import('../lib/companyUniverse'),
      loadWatchlist(),
      loadCompareList(),
      loadFinancialSnapshot().catch(() => null),
      loadMarketSnapshot().catch(() => null),
      loadUpdateStatus().catch(() => null),
    ])
      .then(
        ([
          companyModule,
          storedWatchlist,
          storedCompare,
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
    if (!storageReady) return

    let active = true
    let refreshInFlight = false

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

    const intervalId = window.setInterval(() => {
      void refreshMarket()
    }, MARKET_REFRESH_INTERVAL_MS)
    const handleFocus = () => {
      void refreshMarket()
    }
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') void refreshMarket()
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

  const value = useMemo<AppContextValue>(
    () => ({
      companies,
      watchlist,
      compareList,
      storageReady,
      financialSnapshot,
      marketSnapshot,
      updateStatus,
      toggleWatchlist,
      toggleCompare,
      removeFromCompare,
      clearCompare,
      isWatched: (companyId) => watchlist.includes(companyId),
      isCompared: (companyId) => compareList.includes(companyId),
    }),
    [
      companies,
      watchlist,
      compareList,
      storageReady,
      financialSnapshot,
      marketSnapshot,
      updateStatus,
      toggleWatchlist,
      toggleCompare,
      removeFromCompare,
      clearCompare,
    ],
  )

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export const useApp = () => {
  const context = useContext(AppContext)
  if (!context) throw new Error('useApp must be used inside AppProvider')
  return context
}
