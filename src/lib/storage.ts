import { openDB, type DBSchema } from 'idb'
import type { CompanyNote } from '../types'

interface KpiScopeDb extends DBSchema {
  preferences: {
    key: string
    value: string[]
  }
  notes: {
    key: string
    value: CompanyNote
  }
}

const dbPromise = openDB<KpiScopeDb>('kpi-scope', 1, {
  upgrade(db) {
    db.createObjectStore('preferences')
    db.createObjectStore('notes')
  },
})

export const loadWatchlist = async () =>
  (await dbPromise).get('preferences', 'watchlist').then((value) => value ?? [])

export const saveWatchlist = async (companyIds: string[]) => {
  await (await dbPromise).put('preferences', companyIds, 'watchlist')
}

export const loadCompareList = async () =>
  (await dbPromise).get('preferences', 'compare').then((value) => value ?? [])

export const saveCompareList = async (companyIds: string[]) => {
  await (await dbPromise).put('preferences', companyIds, 'compare')
}

export const loadNote = async (companyId: string) =>
  (await dbPromise).get('notes', companyId)

export const saveNote = async (companyId: string, note: CompanyNote) => {
  await (await dbPromise).put(
    'notes',
    { ...note, updatedAt: new Date().toISOString() },
    companyId,
  )
}
