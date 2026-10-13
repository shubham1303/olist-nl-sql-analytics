import { formatCompact, formatValue, humanise, looksLikeRate } from './format.ts'

interface Props {
  label: string
  value: number
}

export function KpiTile({ label, value }: Props) {
  const shown = looksLikeRate(label) && Math.abs(value) <= 1 ? formatValue(value, label) : formatCompact(value)
  const exact = formatValue(value, label)
  return (
    <figure className="kpi" aria-label={`${humanise(label)}: ${exact}`}>
      <figcaption className="kpi-label">{humanise(label)}</figcaption>
      <div className="kpi-value">{shown}</div>
      {exact !== shown && <div className="kpi-exact">{exact}</div>}
    </figure>
  )
}
