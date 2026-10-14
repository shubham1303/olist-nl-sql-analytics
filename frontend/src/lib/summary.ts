// The answer headline and takeaways, computed from the result rows: the model never sees
// results (ADR 0002), so nothing here comes from the model. Neutral wording only: the
// SQL decides what "top" means, so the summary says "highest" and "lowest", not "best".

import type { Cell, Column, QueryResult } from '../api/types.ts'
import { formatTimeLabel, formatValue, humanise } from '../charts/format.ts'
import { isNumeric, toNumber, type ChartSpec } from '../charts/selectChart.ts'
import { CATALOG } from './catalog.ts'

export interface Stat {
  label: string
  value: string
}

export interface Summary {
  headline: string | null
  takeaways: string[]
  stats: Stat[] | null // one-row results with several columns
}

export const MAX_STATS = 8

// Values that add up to a meaningful total (counts, money), unlike rates and averages.
const NOT_ADDITIVE = /(avg|average|mean|median|rate|share|ratio|pct|percent|score|days|per_|growth)/i

function cellText(cell: Cell | undefined, column: Column): string {
  if (cell === null || cell === undefined) return '—'
  if (isNumeric(column)) {
    const n = toNumber(cell)
    return n === null ? String(cell) : formatValue(n, column.name)
  }
  if (typeof cell === 'boolean') return cell ? 'yes' : 'no'
  return String(cell)
}

function percent(part: number, whole: number): string {
  return `${Math.round((part / whole) * 100)}%`
}

function barSummary(spec: Extract<ChartSpec, { kind: 'bar' }>, columns: Column[], rows: Cell[][]): Summary {
  const valueColumn = columns[spec.value]!
  const name = humanise(valueColumn.name)
  const points = rows.flatMap((row) => {
    const value = toNumber(row[spec.value])
    return value === null ? [] : [{ label: String(row[spec.label] ?? '(none)'), value }]
  })
  if (points.length === 0) return { headline: null, takeaways: [], stats: null }
  const top = points.reduce((a, b) => (b.value > a.value ? b : a))
  const bottom = points.reduce((a, b) => (b.value < a.value ? b : a))
  const fmt = (v: number) => formatValue(v, valueColumn.name)
  const takeaways: string[] = []
  if (points.length > 1) {
    takeaways.push(`Lowest: ${bottom.label} at ${fmt(bottom.value)}.`)
    const total = points.reduce((sum, p) => sum + p.value, 0)
    if (!NOT_ADDITIVE.test(valueColumn.name) && points.every((p) => p.value >= 0) && total > 0) {
      takeaways.push(`${top.label} is ${percent(top.value, total)} of the total shown (${fmt(total)}).`)
    }
    takeaways.push(`${points.length} ${humanise(columns[spec.label]!.name).toLowerCase()} values shown.`)
  }
  return { headline: `${top.label} has the highest ${name.toLowerCase()}: ${fmt(top.value)}`, takeaways, stats: null }
}

function isCompleteMonth(raw: string): boolean {
  const month = raw.slice(0, 7) // 'YYYY-MM' from a month label, date or timestamp
  return month >= CATALOG.complete_months.first && month <= CATALOG.complete_months.last
}

function lineSummary(spec: Extract<ChartSpec, { kind: 'line' }>, columns: Column[], rows: Cell[][]): Summary {
  const seriesColumn = columns[spec.series[0]!]!
  const name = humanise(seriesColumn.name)
  const fmt = (v: number) => formatValue(v, seriesColumn.name)
  const all = [...rows]
    .sort((a, b) => String(a[spec.x]).localeCompare(String(b[spec.x])))
    .flatMap((row) => {
      const value = toNumber(row[spec.series[0]!])
      const raw = String(row[spec.x])
      return value === null ? [] : [{ raw, x: formatTimeLabel(raw), value }]
    })
  if (all.length === 0) return { headline: null, takeaways: [], stats: null }
  // Partial months (e.g. Oct 2018 has 4 orders) would dominate peak, low and change:
  // measure over complete months when at least two are present, and say so.
  const complete = all.filter((p) => isCompleteMonth(p.raw))
  const left = complete.length >= 2 ? all.filter((p) => !isCompleteMonth(p.raw)) : []
  const points = left.length > 0 ? complete : all
  const peak = points.reduce((a, b) => (b.value > a.value ? b : a))
  const low = points.reduce((a, b) => (b.value < a.value ? b : a))
  const first = points[0]!
  const last = points.at(-1)!
  const takeaways: string[] = []
  if (points.length > 1) {
    const change = first.value !== 0 ? ` (${last.value >= first.value ? '+' : ''}${percent(last.value - first.value, Math.abs(first.value))})` : ''
    takeaways.push(`From ${fmt(first.value)} in ${first.x} to ${fmt(last.value)} in ${last.x}${change}.`)
    takeaways.push(`Lowest: ${fmt(low.value)} in ${low.x}.`)
  }
  if (left.length > 0) {
    const names = left.length <= 3 ? left.map((p) => p.x).join(', ') : `${left.length} periods`
    takeaways.push(`Measured over complete months only; ${names} left out (partial data).`)
  }
  if (spec.series.length > 1) {
    const others = spec.series.slice(1).map((i) => humanise(columns[i]!.name).toLowerCase())
    takeaways.push(`Also charted: ${others.join(', ')}.`)
  }
  return { headline: `${name} peaked at ${fmt(peak.value)} in ${peak.x}`, takeaways, stats: null }
}

export function summarise(result: QueryResult, spec: ChartSpec): Summary {
  const { columns, rows } = result
  if (rows.length === 0) return { headline: null, takeaways: [], stats: null }
  if (spec.kind === 'kpi') return { headline: null, takeaways: [], stats: null } // the tile is the answer
  if (spec.kind === 'bar') return barSummary(spec, columns, rows)
  if (spec.kind === 'line') return lineSummary(spec, columns, rows)
  if (rows.length === 1 && columns.length <= MAX_STATS) {
    const stats = columns.map((c, i) => ({ label: humanise(c.name), value: cellText(rows[0]![i], c) }))
    return { headline: null, takeaways: [], stats }
  }
  const count = result.row_count.toLocaleString('en-US')
  const headline = result.truncated
    ? `More than ${count} rows; the first ${count} are shown`
    : `${count} ${result.row_count === 1 ? 'row' : 'rows'} × ${columns.length} columns`
  return { headline, takeaways: [], stats: null }
}
