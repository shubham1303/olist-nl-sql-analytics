import type { Cell, Column } from '../api/types.ts'
import { formatValue, humanise } from '../charts/format.ts'
import { isNumeric, toNumber } from '../charts/selectChart.ts'

interface Props {
  columns: Column[]
  rows: Cell[][]
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

export function DataTable({ columns, rows }: Props) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c, i) => (
              <th key={`${c.name}-${i}`} className={isNumeric(c) ? 'num' : undefined} scope="col">
                {humanise(c.name)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, r) => (
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
  )
}
