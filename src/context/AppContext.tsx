import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  loadCompareList,
  loadWatchlist,
  saveCompareList,
  saveWatchlist,
} from '../lib/storage'
import type { Company, FinancialSnapshot } from '../types'
import {
  loadFinancialSnapshot,
  loadMarketSnapshot,
  mergeLiveCompanies,
} from '../lib/liveData'

interface AppContextValue {
  companies: Company[]
  watchlist: string[]
  compareList: string[]
  storageReady: boolean
  financialSnapshot: FinancialSnapshot | null
  toggleWatchlist: (companyId: string) => void
  toggleCompare: (companyId: string) => boolean
  removeFromCompare: (companyId: string) => void
  clearCompare: () => void
  isWatched: (companyId: string) => boolean
  isCompared: (companyId: string) => boolean
}

const AppContext = createContext<AppContextValue | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [companies, setCompanies] = useState<Company[]>([])
  const [watchlist, setWatchlist] = useState<string[]>([])
  const [compareList, setCompareList] = useState<string[]>([])
  const [storageReady, setStorageReady] = useState(false)
  const [financialSnapshot, setFinancialSnapshot] =
    useState<FinancialSnapshot | null>(null)

  useEffect(() => {
    let active = true
    Promise.all([
      import('../lib/mockGenerator'),
      loadWatchlist(),
      loadCompareList(),
      loadFinancialSnapshot().catch(() => null),
      loadMarketSnapshot().catch(() => null),
    ])
      .then(
        ([
          companyModule,
          storedWatchlist,
          storedCompare,
          snapshot,
          marketSnapshot,
        ]) => {
          if (!active) return
          const loadedCompanies = snapshot
            ? mergeLiveCompanies(
                companyModule.companies,
                snapshot,
                marketSnapshot,
              )
            : companyModule.companies
          setCompanies(loadedCompanies)
          setFinancialSnapshot(snapshot)
          const validIds = new Set(
            loadedCompanies.map((company) => company.id),
          )
          setWatchlist(storedWatchlist.filter((id) => validIds.has(id)))
          setCompareList(
            storedCompare.filter((id) => validIds.has(id)).slice(0, 5),
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
