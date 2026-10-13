// Deterministic chart choice from the result's shape (ADR 0007). No LLM involved.
//
// First match wins:
//   1. one row, one numeric column             -> KPI tile
//   2. one time column + 1-3 numeric columns   -> line chart (2+ rows)
//   3. one text column (<= 25 distinct values)
//      + one numeric column                    -> bar chart (horizontal for long labels)
//   4. anything else                           -> table only
//
// A text column counts as time when every value is a 'YYYY-MM' or 'YYYY-MM-DD' label:
// models often format months with TO_CHAR, which arrives as text.

import type { Cell, Column } from '../api/types.ts'

export type ChartSpec =
  | { kind: 'kpi'; value: number }
  | { kind: 'line'; x: number; series: number[] }
  | { kind: 'bar'; label: number; value: number; horizontal: boolean }
  | { kind: 'table' }

export const MAX_BAR_CATEGORIES = 25
export const MAX_LINE_SERIES = 3
const LONG_LABEL = 12 // characters; longer labels get a horizontal bar chart

const TIME_LABEL = /^\d{4}-\d{2}(-\d{2})?([T ]00:00:00)?$/

export function isNumeric(column: Column): boolean {
  return column.type === 'integer' || column.type === 'number'
}

function isTime(column: Column, rows: Cell[][], index: number): boolean {
  if (column.type === 'date' || column.type === 'timestamp') return true
  if (column.type !== 'text' || rows.length === 0) return false
  return rows.every((row) => {
    const value = row[index]
    return typeof value === 'string' && TIME_LABEL.test(value)
  })
}

function hasNumbers(rows: Cell[][], index: number): boolean {
  return rows.some((row) => toNumber(row[index]) !== null)
}

export function toNumber(cell: Cell | undefined): number | null {
  if (cell === null || cell === undefined || typeof cell === 'boolean') return null
  const value = typeof cell === 'number' ? cell : Number(cell)
  return Number.isFinite(value) ? value : null
}

export function selectChart(columns: Column[], rows: Cell[][]): ChartSpec {
  if (rows.length === 0 || columns.length === 0) return { kind: 'table' }
  const numeric = columns.flatMap((c, i) => (isNumeric(c) && hasNumbers(rows, i) ? [i] : []))

  // 1. KPI
  if (rows.length === 1 && columns.length === 1 && numeric.length === 1) {
    return { kind: 'kpi', value: 0 }
  }

  const others = columns.flatMap((_, i) => (numeric.includes(i) ? [] : [i]))

  // 2. line
  if (
    others.length === 1 &&
    numeric.length >= 1 &&
    numeric.length <= MAX_LINE_SERIES &&
    rows.length >= 2
  ) {
    const x = others[0]!
    if (isTime(columns[x]!, rows, x)) return { kind: 'line', x, series: numeric }
  }

  // 3. bar
  if (others.length === 1 && numeric.length === 1) {
    const label = others[0]!
    if (columns[label]!.type === 'text') {
      const labels = rows.map((row) => String(row[label] ?? ''))
      if (new Set(labels).size <= MAX_BAR_CATEGORIES) {
        const horizontal = labels.some((l) => l.length > LONG_LABEL)
        return { kind: 'bar', label, value: numeric[0]!, horizontal }
      }
    }
  }

  // 4. table
  return { kind: 'table' }
}
