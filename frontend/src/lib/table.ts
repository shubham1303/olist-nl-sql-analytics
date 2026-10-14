// Sorting and CSV export for the result table. Pure functions over the API's cells.

import type { Cell, Column } from '../api/types.ts'
import { isNumeric, toNumber } from '../charts/selectChart.ts'

export type SortDirection = 'asc' | 'desc'
export interface Sort {
  column: number
  direction: SortDirection
}

/** A stable sort; NULLs always last, numbers numerically, everything else as text. */
export function sortRows(rows: Cell[][], columns: Column[], sort: Sort | null): Cell[][] {
  if (sort === null) return rows
  const numeric = isNumeric(columns[sort.column] ?? { name: '', type: 'unknown' })
  const sign = sort.direction === 'asc' ? 1 : -1
  return rows
    .map((row, index) => ({ row, index }))
    .sort((a, b) => {
      const x = a.row[sort.column] ?? null
      const y = b.row[sort.column] ?? null
      if (x === null || y === null) return x === y ? a.index - b.index : x === null ? 1 : -1
      let order: number
      if (numeric) order = (toNumber(x) ?? 0) - (toNumber(y) ?? 0)
      else order = String(x).localeCompare(String(y), 'en', { numeric: true })
      return order === 0 ? a.index - b.index : sign * order
    })
    .map(({ row }) => row)
}

/** Next state when a header is clicked: ascending, then descending, then unsorted. */
export function nextSort(current: Sort | null, column: number): Sort | null {
  if (current?.column !== column) return { column, direction: 'asc' }
  return current.direction === 'asc' ? { column, direction: 'desc' } : null
}

function csvField(cell: Cell | undefined): string {
  if (cell === null || cell === undefined) return ''
  const text = String(cell)
  // quote fields with separators, quotes or line breaks; neutralise spreadsheet formulas
  const safe = /^[=+\-@\t\r]/.test(text) && !/^-?\d/.test(text) ? `'${text}` : text
  return /[",\r\n]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe
}

/** RFC 4180 CSV with exact values (decimals stay as the API sent them). */
export function toCsv(columns: Column[], rows: Cell[][]): string {
  const lines = [columns.map((c) => csvField(c.name)).join(',')]
  for (const row of rows) lines.push(columns.map((_, i) => csvField(row[i])).join(','))
  return lines.join('\r\n') + '\r\n'
}

export function csvFilename(question: string): string {
  const slug = question
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 50)
  return `${slug || 'result'}.csv`
}
