import { useMemo, useState } from 'react'
import type { Cell, Column } from '../api/types.ts'
import { formatValue, humanise } from '../charts/format.ts'
import { isNumeric, toNumber } from '../charts/selectChart.ts'
import { csvFilename, nextSort, sortRows, toCsv, type Sort } from '../lib/table.ts'

interface Props {
  columns: Column[]
  rows: Cell[][]
  question?: string
}

function show(cell: Cell | undefined, column: Column): string {
  if (cell === null || cell === undefined) return '—'
  if (isNumeric(column)) {
    const n = toNumber(cell)
    return n === null ? String(cell) : formatValue(n, column.name)
  }
  if (typeof cell === 'boolean') return cell ? 'yes' : 'no'
  return String(cell)
}

function download(text: string, filename: string) {
  try {
    const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 0)
  } catch {
    // downloads unavailable (old browser or test environment)
  }
}

export function DataTable({ columns, rows, question = 'result' }: Props) {
  const [sort, setSort] = useState<Sort | null>(null)
  const sorted = useMemo(() => sortRows(rows, columns, sort), [rows, columns, sort])

  return (
    <div className="data-table">
      <div className="table-tools">
        <span className="muted">
          {rows.length.toLocaleString('en-US')} {rows.length === 1 ? 'row' : 'rows'}
          {sort && ` · sorted by ${humanise(columns[sort.column]!.name).toLowerCase()}`}
        </span>
        <button
          type="button"
          className="secondary small"
          onClick={() => download(toCsv(columns, rows), csvFilename(question))}
        >
          Download CSV
        </button>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((c, i) => {
                const active = sort?.column === i
                const ariaSort = active ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'
                return (
                  <th
                    key={`${c.name}-${i}`}
                    className={isNumeric(c) ? 'num' : undefined}
                    scope="col"
                    aria-sort={ariaSort}
                  >
                    <button type="button" className="sort" onClick={() => setSort(nextSort(sort, i))}>
                      {humanise(c.name)}
                      <span className="sort-mark" aria-hidden="true">
                        {active ? (sort.direction === 'asc' ? '▲' : '▼') : '↕'}
                      </span>
                    </button>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, r) => (
              <tr key={r}>
                {columns.map((c, i) => (
                  <td key={i} className={isNumeric(c) ? 'num' : undefined}>
                    {show(row[i], c)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
