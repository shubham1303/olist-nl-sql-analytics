import { describe, expect, it } from 'vitest'
import type { Cell, Column } from '../api/types.ts'
import { selectChart } from './selectChart.ts'

const col = (name: string, type: Column['type']): Column => ({ name, type })
const months = (n: number) => Array.from({ length: n }, (_, i) => `2018-${String(i + 1).padStart(2, '0')}-01`)

describe('selectChart (ADR 0007 rules, first match wins)', () => {
  it('1. one row with one numeric column is a KPI tile', () => {
    expect(selectChart([col('revenue', 'number')], [['13494400.74']])).toEqual({ kind: 'kpi', value: 0 })
    expect(selectChart([col('orders', 'integer')], [[99441]])).toEqual({ kind: 'kpi', value: 0 })
  })

  it('one row with two numbers is a table, not two tiles', () => {
    expect(selectChart([col('a', 'number'), col('b', 'number')], [[1, 2]])).toEqual({ kind: 'table' })
  })

  it('2. a date or timestamp column with 1-3 numeric columns is a line chart', () => {
    const rows: Cell[][] = months(8).map((m, i) => [m, i * 10, i])
    expect(selectChart([col('month', 'date'), col('revenue', 'number'), col('orders', 'integer')], rows)).toEqual({
      kind: 'line',
      x: 0,
      series: [1, 2],
    })
    const ts = months(3).map((m) => [`${m}T00:00:00`, 1])
    expect(selectChart([col('month', 'timestamp'), col('n', 'integer')], ts).kind).toBe('line')
  })

  it("treats 'YYYY-MM' text from TO_CHAR as time", () => {
    const rows = [['2018-01', 5], ['2018-02', 7]]
    expect(selectChart([col('month', 'text'), col('n', 'integer')], rows)).toEqual({ kind: 'line', x: 0, series: [1] })
  })

  it('a time column with four numeric columns falls back to a table', () => {
    const rows = months(4).map((m) => [m, 1, 2, 3, 4])
    const cols = [col('m', 'date'), col('a', 'number'), col('b', 'number'), col('c', 'number'), col('d', 'number')]
    expect(selectChart(cols, rows)).toEqual({ kind: 'table' })
  })

  it('a single dated row is not a line', () => {
    expect(selectChart([col('m', 'date'), col('n', 'integer')], [['2018-01-01', 5]]).kind).toBe('table')
  })

  it('3. one text column with one numeric column is a bar chart', () => {
    const rows = [['SP', 15540], ['RJ', 6882], ['MG', 2773]]
    expect(selectChart([col('state', 'text'), col('orders', 'integer')], rows)).toEqual({
      kind: 'bar',
      label: 0,
      value: 1,
      horizontal: false,
    })
  })

  it('long labels make the bar chart horizontal', () => {
    const rows = [['computers_accessories', 1], ['bed_bath_table', 2]]
    const spec = selectChart([col('product_category', 'text'), col('n', 'integer')], rows)
    expect(spec).toMatchObject({ kind: 'bar', horizontal: true })
  })

  it('more than 25 categories is a table', () => {
    const rows = Array.from({ length: 26 }, (_, i) => [`c${i}`, i])
    expect(selectChart([col('city', 'text'), col('n', 'integer')], rows)).toEqual({ kind: 'table' })
  })

  it('column order does not matter for a bar', () => {
    const rows = [[3, 'x'], [4, 'y']]
    expect(selectChart([col('n', 'integer'), col('label', 'text')], rows)).toMatchObject({ kind: 'bar', label: 1, value: 0 })
  })

  it('4. anything else is a table', () => {
    expect(selectChart([], [])).toEqual({ kind: 'table' })
    expect(selectChart([col('n', 'integer')], [])).toEqual({ kind: 'table' }) // no rows
    const mixed = [['SP', 'x', 1]]
    expect(selectChart([col('a', 'text'), col('b', 'text'), col('n', 'integer')], mixed)).toEqual({ kind: 'table' })
    expect(selectChart([col('late', 'boolean'), col('score', 'number')], [[true, 2.27], [false, 4.29]])).toEqual({
      kind: 'table',
    })
  })

  it('a numeric column holding only NULLs does not count as a measure', () => {
    expect(selectChart([col('revenue', 'number')], [[null]])).toEqual({ kind: 'table' })
  })
})
