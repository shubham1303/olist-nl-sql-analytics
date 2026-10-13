export interface TooltipRow {
  key: string
  label: string
  value: string
  color?: string
}

interface Props {
  x: number
  y: number
  title: string
  rows: TooltipRow[]
}

/** Values lead, labels follow; series keyed with a short line in the series colour. */
export function Tooltip({ x, y, title, rows }: Props) {
  return (
    <div className="tooltip" role="status" style={{ left: x, top: y }}>
      <div className="tooltip-title">{title}</div>
      {rows.map((row) => (
        <div className="tooltip-row" key={row.key}>
          {row.color && <span className="line-key" style={{ background: row.color }} />}
          <strong>{row.value}</strong>
          <span className="tooltip-label">{row.label}</span>
        </div>
      ))}
    </div>
  )
}
