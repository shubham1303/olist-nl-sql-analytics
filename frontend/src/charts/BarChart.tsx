import { useState } from 'react'
import { formatCompact, formatValue, humanise, niceTicks } from './format.ts'
import { Tooltip } from './Tooltip.tsx'
import { useWidth } from './useWidth.ts'

export interface Bar {
  label: string
  value: number | null
}

interface Props {
  bars: Bar[]
  valueName: string
  horizontal: boolean
}

const THICKNESS = 24 // max bar thickness (px)
const RADIUS = 4 // rounded data end; square at the baseline

/** A bar from `base` to `end` along the value axis, rounded only at the data end. */
function barPath(horizontal: boolean, cross: number, thick: number, base: number, end: number): string {
  const r = Math.min(RADIUS, Math.abs(end - base), thick / 2)
  const back = Math.sign(base - end) * r // from the data end back toward the baseline
  if (horizontal) {
    const [y0, y1] = [cross, cross + thick]
    return [
      `M${base},${y0}`,
      `H${end + back}`,
      `Q${end},${y0} ${end},${y0 + r}`,
      `V${y1 - r}`,
      `Q${end},${y1} ${end + back},${y1}`,
      `H${base}`,
      'Z',
    ].join(' ')
  }
  const [x0, x1] = [cross, cross + thick]
  return [
    `M${x0},${base}`,
    `V${end + back}`,
    `Q${x0},${end} ${x0 + r},${end}`,
    `H${x1 - r}`,
    `Q${x1},${end} ${x1},${end + back}`,
    `V${base}`,
    'Z',
  ].join(' ')
}

export function BarChart({ bars, valueName, horizontal }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [active, setActive] = useState<number | null>(null)
  const values = bars.map((b) => b.value ?? 0)
  const ticks = niceTicks(Math.min(0, ...values), Math.max(0, ...values))
  const lo = ticks[0]!
  const hi = ticks[ticks.length - 1]!

  const longest = Math.max(...bars.map((b) => b.label.length))
  const labelSpace = horizontal ? Math.min(220, 12 + longest * 7) : 0
  const margin = horizontal
    ? { top: 8, right: 72, bottom: 24, left: labelSpace }
    : { top: 20, right: 12, bottom: 64, left: 56 }
  const plotW = width - margin.left - margin.right
  const band = horizontal ? 32 : plotW / bars.length
  const height = horizontal ? margin.top + margin.bottom + band * bars.length : 300
  const plotH = height - margin.top - margin.bottom
  const scale = (v: number) =>
    horizontal
      ? margin.left + ((v - lo) / (hi - lo)) * plotW
      : margin.top + plotH - ((v - lo) / (hi - lo)) * plotH
  const thick = Math.min(THICKNESS, band * 0.7)
  const labelEvery = horizontal || bars.length <= 12

  const activeBar = active === null ? null : bars[active]
  const crossOf = (i: number) => (horizontal ? margin.top : margin.left) + i * band + (band - thick) / 2

  return (
    <div className="chart" ref={ref}>
      <svg width={width} height={height} role="img" aria-label={`Bar chart of ${humanise(valueName)}`}>
        {ticks.map((t) => {
          const p = scale(t)
          return horizontal ? (
            <g key={t}>
              <line className="grid" x1={p} x2={p} y1={margin.top} y2={margin.top + plotH} />
              <text className="tick" x={p} y={height - 6} textAnchor="middle">
                {formatCompact(t)}
              </text>
            </g>
          ) : (
            <g key={t}>
              <line className="grid" x1={margin.left} x2={margin.left + plotW} y1={p} y2={p} />
              <text className="tick" x={margin.left - 8} y={p + 4} textAnchor="end">
                {formatCompact(t)}
              </text>
            </g>
          )
        })}
        {bars.map((bar, i) => {
          const cross = crossOf(i)
          const base = scale(0)
          const end = scale(bar.value ?? 0)
          const valueText = bar.value === null ? '—' : formatValue(bar.value, valueName)
          const hit = horizontal
            ? { x: margin.left, y: margin.top + i * band, width: plotW, height: band }
            : { x: margin.left + i * band, y: margin.top, width: band, height: plotH }
          return (
            <g
              key={`${bar.label}-${i}`}
              className={active === i ? 'bar active' : 'bar'}
              tabIndex={0}
              aria-label={`${bar.label}: ${valueText}`}
              onMouseEnter={() => setActive(i)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
            >
              <rect className="hit" {...hit} />
              {bar.value !== null && bar.value !== 0 && (
                <path className="mark" d={barPath(horizontal, cross, thick, base, end)} />
              )}
              {horizontal ? (
                <text className="category" x={margin.left - 8} y={cross + thick / 2 + 4} textAnchor="end">
                  {bar.label}
                </text>
              ) : (
                <text
                  className="category"
                  x={cross + thick / 2}
                  y={margin.top + plotH + 16}
                  textAnchor="end"
                  transform={`rotate(-35 ${cross + thick / 2} ${margin.top + plotH + 16})`}
                >
                  {bar.label}
                </text>
              )}
              {labelEvery &&
                bar.value !== null &&
                (horizontal ? (
                  <text className="value" x={Math.max(end, base) + 6} y={cross + thick / 2 + 4}>
                    {formatCompact(bar.value)}
                  </text>
                ) : (
                  <text className="value" x={cross + thick / 2} y={Math.min(end, base) - 6} textAnchor="middle">
                    {formatCompact(bar.value)}
                  </text>
                ))}
            </g>
          )
        })}
        <line
          className="baseline"
          {...(horizontal
            ? { x1: scale(0), x2: scale(0), y1: margin.top, y2: margin.top + plotH }
            : { x1: margin.left, x2: margin.left + plotW, y1: scale(0), y2: scale(0) })}
        />
      </svg>
      {activeBar && active !== null && (
        <Tooltip
          x={horizontal ? Math.min(width - 160, scale(activeBar.value ?? 0) + 12) : crossOf(active)}
          y={horizontal ? crossOf(active) - 8 : margin.top}
          title={activeBar.label}
          rows={[
            {
              key: 'v',
              label: humanise(valueName),
              value: activeBar.value === null ? 'no value' : formatValue(activeBar.value, valueName),
            },
          ]}
        />
      )}
    </div>
  )
}
