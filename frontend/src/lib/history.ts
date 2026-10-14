// Questions asked in this browser tab. Kept in sessionStorage (like the access code), so
// it disappears with the tab; storage that is blocked or full only loses the history.

import type { QueryResult } from '../api/types.ts'

export const HISTORY_KEY = 'olist-nlsql-history'
export const MAX_HISTORY = 20

export interface HistoryEntry {
  id: string
  at: number // epoch ms
  result: QueryResult
}

export function loadHistory(): HistoryEntry[] {
  try {
    const raw = sessionStorage.getItem(HISTORY_KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (e): e is HistoryEntry =>
        typeof e === 'object' && e !== null && typeof e.id === 'string' && typeof e.result?.question === 'string',
    )
  } catch {
    return []
  }
}

export function saveHistory(entries: HistoryEntry[]): void {
  // Results can be large: if the quota is hit, keep fewer entries rather than none.
  for (let keep = entries.length; keep >= 0; keep = keep === 0 ? -1 : Math.floor(keep / 2)) {
    try {
      if (keep === 0) sessionStorage.removeItem(HISTORY_KEY)
      else sessionStorage.setItem(HISTORY_KEY, JSON.stringify(entries.slice(0, keep)))
      return
    } catch {
      // try again with fewer
    }
  }
}

export function makeEntry(result: QueryResult, at = Date.now()): HistoryEntry {
  return { id: `${at}-${Math.random().toString(36).slice(2, 8)}`, at, result }
}

/** Newest first, at most MAX_HISTORY. */
export function prepend(entries: HistoryEntry[], entry: HistoryEntry): HistoryEntry[] {
  return [entry, ...entries].slice(0, MAX_HISTORY)
}

export function relativeTime(at: number, now = Date.now()): string {
  const minutes = Math.floor((now - at) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.floor(minutes / 60)
  return `${hours} h ago`
}
