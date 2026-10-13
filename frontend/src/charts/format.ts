// Number and label formatting shared by charts and the table.

const full = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })
const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 })

/** Table cells and tooltips: exact to 2 decimals, thousands separated. */
export function formatNumber(value: number): string {
  return full.format(value)
}

/** KPI tiles and axis ticks: 1,284 / 12.9K / 4.2M. */
export function formatCompact(value: number): string {
  return Math.abs(value) < 10_000 ? formatNumber(value) : compact.format(value)
}

/** Ratios between 0 and 1 named like rates are shown as percentages. */
export function looksLikeRate(columnName: string): boolean {
  return /(rate|share|ratio|pct|percent)/i.test(columnName)
}

export function formatValue(value: number, columnName: string): string {
  if (looksLikeRate(columnName) && Math.abs(value) <= 1) {
    return `${(value * 100).toLocaleString('en-US', { maximumFractionDigits: 2 })}%`
  }
  return formatNumber(value)
}

/** '2018-03-01' / '2018-03-01T00:00:00' / '2018-03' -> 'Mar 2018' when it is a month start. */
export function formatTimeLabel(value: string): string {
  const match = /^(\d{4})-(\d{2})(?:-(\d{2}))?/.exec(value)
  if (!match) return value
  const [, year, month, day] = match
  const date = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day ?? '1')))
  const monthName = date.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' })
  return day === undefined || day === '01' ? `${monthName} ${year}` : `${monthName} ${Number(day)}, ${year}`
}

/** Column names come as snake_case: 'late_delivery_rate' -> 'Late delivery rate'. */
export function humanise(name: string): string {
  const words = name.replace(/_/g, ' ').trim()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

/** Clean axis ticks: about `count` round steps; the first <= min and the last >= max. */
export function niceTicks(min: number, max: number, count = 4): number[] {
  if (min === max) {
    const pad = Math.abs(min) || 1
    return niceTicks(min - pad, max + pad, count)
  }
  const raw = (max - min) / count
  const magnitude = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw) ?? raw
  const start = Math.floor(min / step) * step
  const ticks: number[] = []
  for (let t = start; t < max + step * 0.999; t += step) ticks.push(Number(t.toPrecision(12)))
  return ticks
}
