import { beforeEach, describe, expect, it } from 'vitest'
import type { QueryResult } from '../api/types.ts'
import { selectChart } from '../charts/selectChart.ts'
import { CATALOG, relationsUsed } from './catalog.ts'
import { HISTORY_KEY, loadHistory, makeEntry, MAX_HISTORY, prepend, relativeTime, saveHistory } from './history.ts'
import { tokenize } from './sqlTokens.ts'
import { summarise } from './summary.ts'
import { csvFilename, nextSort, sortRows, toCsv } from './table.ts'

function result(columns: QueryResult['columns'], rows: QueryResult['rows'], extra: Partial<QueryResult> = {}): QueryResult {
  return {
    question: 'q',
    status: 'answered',
    model_id: 'm',
    prompt_version: 'v3',
    interpretation: null,
    assumptions: [],
    metrics_used: [],
    generated_sql: null,
    validated_sql: null,
    repair_attempted: false,
    columns,
    rows,
    row_count: rows.length,
    truncated: false,
    warnings: [],
    timings: { total_ms: 1, model_generation_ms: 1, execution_ms: 1 },
    error: null,
    ...extra,
  }
}

describe('sql tokens', () => {
  it('round-trips the input and classifies tokens', () => {
    const sql = "SELECT COUNT(*) AS n, 'it''s' -- note\nFROM analytics.orders WHERE x >= 1.5"
    const tokens = tokenize(sql)
    expect(tokens.map((t) => t.text).join('')).toBe(sql)
    const kind = (text: string) => tokens.find((t) => t.text === text)?.kind
    expect(kind('SELECT')).toBe('keyword')
    expect(kind('COUNT')).toBe('function')
    expect(kind("'it''s'")).toBe('string')
    expect(kind('-- note')).toBe('comment')
    expect(kind('1.5')).toBe('number')
    expect(kind('orders')).toBe('identifier')
  })

  it('never loops on unterminated input', () => {
    expect(tokenize("SELECT 'open").map((t) => t.text).join('')).toBe("SELECT 'open")
  })
})

describe('catalog', () => {
  it('finds the views a query reads, once each', () => {
    const sql = 'SELECT 1 FROM analytics.orders o JOIN order_sellers s ON s.order_id = o.order_id JOIN analytics.orders p ON true'
    expect(relationsUsed(sql)).toEqual(['orders', 'order_sellers'])
    expect(relationsUsed('SELECT 1 FROM not_a_view')).toEqual([])
  })

  it('has examples, metrics and relations', () => {
    expect(CATALOG.topics.length).toBeGreaterThan(3)
    expect(CATALOG.metrics.some((m) => m.name === 'average_delivery_delay_days')).toBe(true)
    expect(CATALOG.relations.some((r) => r.name === 'orders')).toBe(true)
  })
})

describe('table', () => {
  const columns = [
    { name: 'state', type: 'text' as const },
    { name: 'orders', type: 'integer' as const },
  ]
  const rows = [
    ['SP', '10'],
    ['RJ', '9'],
    ['MG', null],
    ['AC', '100'],
  ]

  it('sorts numbers numerically with NULLs last, both ways', () => {
    expect(sortRows(rows, columns, { column: 1, direction: 'asc' }).map((r) => r[0])).toEqual(['RJ', 'SP', 'AC', 'MG'])
    expect(sortRows(rows, columns, { column: 1, direction: 'desc' }).map((r) => r[0])).toEqual(['AC', 'SP', 'RJ', 'MG'])
    expect(sortRows(rows, columns, { column: 0, direction: 'asc' }).map((r) => r[0])).toEqual(['AC', 'MG', 'RJ', 'SP'])
    expect(sortRows(rows, columns, null)).toBe(rows)
  })

  it('cycles ascending, descending, unsorted', () => {
    const a = nextSort(null, 1)
    const b = nextSort(a, 1)
    expect([a, b, nextSort(b, 1), nextSort(b, 0)]).toEqual([
      { column: 1, direction: 'asc' },
      { column: 1, direction: 'desc' },
      null,
      { column: 0, direction: 'asc' },
    ])
  })

  it('writes RFC 4180 CSV with exact values and no formula injection', () => {
    const csv = toCsv(
      [
        { name: 'name', type: 'text' },
        { name: 'value', type: 'number' },
      ],
      [
        ['a, "b"', '-1.50'],
        ['=HYPERLINK("x")', null],
      ],
    )
    expect(csv).toBe('name,value\r\n"a, ""b""",-1.50\r\n"\'=HYPERLINK(""x"")",\r\n')
    expect(csvFilename('Which 5 categories?')).toBe('which-5-categories.csv')
  })
})

describe('summary', () => {
  it('bar: highest, lowest and share of an additive total', () => {
    const r = result(
      [
        { name: 'customer_state', type: 'text' },
        { name: 'orders', type: 'integer' },
      ],
      [
        ['SP', 60],
        ['RJ', 30],
        ['MG', 10],
      ],
    )
    const s = summarise(r, selectChart(r.columns, r.rows))
    expect(s.headline).toBe('SP has the highest orders: 60')
    expect(s.takeaways).toEqual(['Lowest: MG at 10.', 'SP is 60% of the total shown (100).', '3 customer state values shown.'])
  })

  it('bar: no share of total for rates or averages', () => {
    const r = result(
      [
        { name: 'category', type: 'text' },
        { name: 'late_rate', type: 'number' },
      ],
      [
        ['a', '0.2'],
        ['b', '0.1'],
      ],
    )
    const s = summarise(r, selectChart(r.columns, r.rows))
    expect(s.headline).toBe('a has the highest late rate: 20%')
    expect(s.takeaways.some((t) => t.includes('of the total'))).toBe(false)
  })

  it('line: peak, change and low in time order', () => {
    const r = result(
      [
        { name: 'month', type: 'text' },
        { name: 'revenue', type: 'number' },
      ],
      [
        ['2018-02', '150'],
        ['2018-01', '100'],
        ['2018-03', '120'],
      ],
    )
    const s = summarise(r, selectChart(r.columns, r.rows))
    expect(s.headline).toBe('Revenue peaked at 150 in Feb 2018')
    expect(s.takeaways).toEqual(['From 100 in Jan 2018 to 120 in Mar 2018 (+20%).', 'Lowest: 100 in Jan 2018.'])
  })

  it('one row with several columns becomes stats; wide results count rows', () => {
    const one = result(
      [
        { name: 'groups_compared', type: 'integer' },
        { name: 'share_late_lower', type: 'number' },
      ],
      [[257, '1.0000']],
    )
    expect(summarise(one, selectChart(one.columns, one.rows)).stats).toEqual([
      { label: 'Groups compared', value: '257' },
      { label: 'Share late lower', value: '100%' },
    ])
    const wide = result(
      [
        { name: 'a', type: 'text' },
        { name: 'b', type: 'text' },
      ],
      [
        ['x', 'y'],
        ['z', 'w'],
      ],
      { row_count: 1000, truncated: true },
    )
    expect(summarise(wide, selectChart(wide.columns, wide.rows)).headline).toBe(
      'More than 1,000 rows; the first 1,000 are shown',
    )
  })
})

describe('history', () => {
  beforeEach(() => sessionStorage.clear())

  it('keeps the newest MAX_HISTORY entries and survives a reload', () => {
    let entries = loadHistory()
    for (let i = 0; i < MAX_HISTORY + 3; i++) entries = prepend(entries, makeEntry(result([], [], { question: `q${i}` }), i))
    expect(entries).toHaveLength(MAX_HISTORY)
    expect(entries[0]!.result.question).toBe(`q${MAX_HISTORY + 2}`)
    saveHistory(entries)
    expect(loadHistory()).toEqual(entries)
  })

  it('ignores corrupt storage', () => {
    sessionStorage.setItem(HISTORY_KEY, '{not json')
    expect(loadHistory()).toEqual([])
    sessionStorage.setItem(HISTORY_KEY, JSON.stringify([{ id: 1 }, 'x']))
    expect(loadHistory()).toEqual([])
  })

  it('says how long ago', () => {
    expect(relativeTime(0, 30_000)).toBe('just now')
    expect(relativeTime(0, 5 * 60_000)).toBe('5 min ago')
    expect(relativeTime(0, 3 * 3_600_000)).toBe('3 h ago')
  })
})
