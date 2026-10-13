import { describe, expect, it } from 'vitest'
import { formatCompact, formatTimeLabel, formatValue, humanise, niceTicks } from './format.ts'

describe('format', () => {
  it('compacts big numbers and keeps small ones exact', () => {
    expect(formatCompact(1284)).toBe('1,284')
    expect(formatCompact(12_900)).toBe('12.9K')
    expect(formatCompact(13_494_400.74)).toBe('13.5M')
  })

  it('shows rates as percentages', () => {
    expect(formatValue(0.0677309, 'late_delivery_rate')).toBe('6.77%')
    expect(formatValue(137.4189, 'average_order_value')).toBe('137.42')
    expect(formatValue(12, 'growth_pct')).toBe('12') // already a percentage
  })

  it('names months', () => {
    expect(formatTimeLabel('2018-03-01')).toBe('Mar 2018')
    expect(formatTimeLabel('2018-03-01T00:00:00')).toBe('Mar 2018')
    expect(formatTimeLabel('2018-03')).toBe('Mar 2018')
    expect(formatTimeLabel('2018-03-15')).toBe('Mar 15, 2018')
    expect(formatTimeLabel('not a date')).toBe('not a date')
  })

  it('humanises snake_case', () => {
    expect(humanise('late_delivery_rate')).toBe('Late delivery rate')
  })

  it('ticks are round and cover the data', () => {
    expect(niceTicks(0, 9.9)).toEqual([0, 2.5, 5, 7.5, 10])
    const t = niceTicks(0, 1_003_862)
    expect(t[0]).toBe(0)
    expect(t[t.length - 1]).toBeGreaterThanOrEqual(1_003_862)
    expect(niceTicks(-0.26, 0.52)[0]).toBeLessThanOrEqual(-0.26)
    expect(niceTicks(5, 5).length).toBeGreaterThan(1)
  })
})
