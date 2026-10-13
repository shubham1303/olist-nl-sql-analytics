import { useState, type KeyboardEvent, type PointerEvent } from 'react'
import { formatCompact, formatTimeLabel, formatValue, humanise, niceTicks } from './format.ts'
import { Tooltip } from './Tooltip.tsx'
import { useWidth } from './useWidth.ts'

export interface Series {
  name: string
  values: (number | null)[]
}

interface Props {
  x: string[] // time labels, already in time order
  series: Series[]
}

const COLORS = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)']
const SCALE_GAP = 10 // series whose ranges differ more than this get their own panel

/** One axis only: series on very different scales go into small multiples instead. */
export function LineChart({ x, series }: Props) {
  const peaks = series.map((s) => Math.max(...s.values.map((v) => Math.abs(v ?? 0))) || 1)
  const together = series.length === 1 || Math.max(...peaks) / Math.min(...peaks) <= SCALE_GAP
  if (together) return <LinePanel x={x} series={series} colors={COLORS} legend={series.length > 1} />
  return (
    <div className="small-multiples">
      {series.map((s, i) => (
        <div key={s.name}>
          <h4 className="panel-title">
            <span className="line-key" style={{ background: COLORS[i] }} />
            {humanise(s.name)}
          </h4>
          <LinePanel x={x} series={[s]} colors={[COLORS[i]!]} legend={false} height={180} />
        </div>
      ))}
    </div>
  )
}

interface PanelProps {
  x: string[]
  series: Series[]
  colors: string[]
  legend: boolean
  height?: number
}

function LinePanel({ x, series, colors, legend, height = 300 }: PanelProps) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [active, setActive] = useState<number | null>(null)
  const all = series.flatMap((s) => s.values.filter((v): v is number => v !== null))
  const ticks = niceTicks(Math.min(0, ...all), Math.max(0, ...all))
  const lo = ticks[0]!
  const hi = ticks[ticks.length - 1]!
  const margin = { top: 16, right: 88, bottom: 28, left: 56 }
  const plotW = width - margin.left - margin.right
  const plotH = height - margin.top - margin.bottom
  const px = (i: number) => margin.left + (x.length === 1 ? plotW / 2 : (i / (x.length - 1)) * plotW)
  const py = (v: number) => margin.top + plotH - ((v - lo) / (hi - lo)) * plotH
  const labelStep = Math.max(1, Math.ceil(x.length / Math.max(2, Math.floor(plotW / 90))))
  // every labelStep-th month plus the last one, unless that would crowd the last label
  const showLabel = (i: number) =>
    i === x.length - 1 || (i % labelStep === 0 && x.length - 1 - i >= labelStep * 0.75)

  const path = (values: (number | null)[]) => {
    let d = ''
    values.forEach((v, i) => {
      if (v === null) return
      d += `${d && values[i - 1] !== null ? 'L' : 'M'}${px(i)},${py(v)} `
    })
    return d.trim()
  }

  const nearest = (clientX: number, rect: DOMRect) => {
    const ratio = (clientX - rect.left - margin.left) / plotW
    return Math.min(x.length - 1, Math.max(0, Math.round(ratio * (x.length - 1))))
  }
  const onMove = (event: PointerEvent<SVGRectElement>) => {
    const svg = event.currentTarget.ownerSVGElement
    if (svg) setActive(nearest(event.clientX, svg.getBoundingClientRect()))
  }
  const onKey = (event: KeyboardEvent<SVGRectElement>) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
    event.preventDefault()
    const step = event.key === 'ArrowLeft' ? -1 : 1
    setActive((a) => Math.min(x.length - 1, Math.max(0, (a ?? (step > 0 ? -1 : x.length)) + step)))
  }

  return (
    <div className="chart" ref={ref}>
      {legend && (
        <ul className="legend">
          {series.map((s, i) => (
            <li key={s.name}>
              <span className="line-key" style={{ background: colors[i] }} />
              {humanise(s.name)}
            </li>
          ))}
        </ul>
      )}
      <svg
        width={width}
        height={height}
        role="img"
        aria-label={`Line chart of ${series.map((s) => humanise(s.name)).join(', ')}`}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line className="grid" x1={margin.left} x2={margin.left + plotW} y1={py(t)} y2={py(t)} />
            <text className="tick" x={margin.left - 8} y={py(t) + 4} textAnchor="end">
              {formatCompact(t)}
            </text>
          </g>
        ))}
        {x.map((label, i) =>
          showLabel(i) ? (
            <text key={label} className="tick" x={px(i)} y={height - 8} textAnchor="middle">
              {formatTimeLabel(label)}
            </text>
          ) : null,
        )}
        {active !== null && (
          <line className="crosshair" x1={px(active)} x2={px(active)} y1={margin.top} y2={margin.top + plotH} />
        )}
        {series.map((s, si) => {
          const last = s.values.findLastIndex((v) => v !== null)
          const lastValue = last >= 0 ? s.values[last]! : null
          return (
            <g key={s.name}>
              <path className="line" d={path(s.values)} style={{ stroke: colors[si] }} />
              {lastValue !== null && (
                <>
                  <circle className="dot" cx={px(last)} cy={py(lastValue)} r={4} style={{ fill: colors[si] }} />
                  <text className="value" x={px(last) + 8} y={py(lastValue) + 4}>
                    {formatCompact(lastValue)}
                  </text>
                </>
              )}
              {active !== null && s.values[active] != null && (
                <circle
                  className="dot"
                  cx={px(active)}
                  cy={py(s.values[active]!)}
                  r={4}
                  style={{ fill: colors[si] }}
                />
              )}
            </g>
          )
        })}
        <rect
          className="overlay"
          x={margin.left}
          y={margin.top}
          width={plotW}
          height={plotH}
          tabIndex={0}
          aria-label="Chart values: use the left and right arrow keys"
          onPointerMove={onMove}
          onPointerLeave={() => setActive(null)}
          onKeyDown={onKey}
          onBlur={() => setActive(null)}
        />
      </svg>
      {active !== null && (
        <Tooltip
          x={Math.min(width - 180, px(active) + 12)}
          y={margin.top}
          title={formatTimeLabel(x[active]!)}
          rows={series.map((s, i) => ({
            key: s.name,
            label: humanise(s.name),
            value: s.values[active] == null ? 'no value' : formatValue(s.values[active]!, s.name),
            color: colors[i],
          }))}
        />
      )}
    </div>
  )
}
