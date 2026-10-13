import type { Cell, Column } from '../api/types.ts'
import { BarChart } from './BarChart.tsx'
import { KpiTile } from './KpiTile.tsx'
import { LineChart } from './LineChart.tsx'
import { toNumber, type ChartSpec } from './selectChart.ts'

interface Props {
  spec: Exclude<ChartSpec, { kind: 'table' }>
  columns: Column[]
  rows: Cell[][]
}

export function ChartView({ spec, columns, rows }: Props) {
  if (spec.kind === 'kpi') {
    const value = toNumber(rows[0]?.[spec.value])
    return value === null ? null : <KpiTile label={columns[spec.value]!.name} value={value} />
  }
  if (spec.kind === 'bar') {
    return (
      <BarChart
        horizontal={spec.horizontal}
        valueName={columns[spec.value]!.name}
        bars={rows.map((row) => ({ label: String(row[spec.label] ?? '(none)'), value: toNumber(row[spec.value]) }))}
      />
    )
  }
  // time order for the x axis (ISO labels sort as text)
  const ordered = [...rows].sort((a, b) => String(a[spec.x]).localeCompare(String(b[spec.x])))
  return (
    <LineChart
      x={ordered.map((row) => String(row[spec.x]))}
      series={spec.series.map((i) => ({ name: columns[i]!.name, values: ordered.map((row) => toNumber(row[i])) }))}
    />
  )
}
