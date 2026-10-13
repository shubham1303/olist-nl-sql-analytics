import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { BarChart } from './BarChart.tsx'
import { KpiTile } from './KpiTile.tsx'
import { LineChart } from './LineChart.tsx'

describe('charts', () => {
  it('KPI tile shows a compact value and the exact one', () => {
    render(<KpiTile label="revenue" value={13494400.74} />)
    expect(screen.getByText('13.5M')).toBeInTheDocument()
    expect(screen.getByText('13,494,400.74')).toBeInTheDocument()
    expect(screen.getByLabelText('Revenue: 13,494,400.74')).toBeInTheDocument()
  })

  it('KPI tile shows rates as a percentage', () => {
    render(<KpiTile label="late_delivery_rate" value={0.0677} />)
    expect(screen.getByText('6.77%')).toBeInTheDocument()
  })

  it('bar chart: one focusable mark per category, tooltip on focus', () => {
    render(
      <BarChart
        valueName="orders"
        horizontal={false}
        bars={[
          { label: 'SP', value: 15540 },
          { label: 'RJ', value: 6882 },
          { label: 'XX', value: null },
        ]}
      />,
    )
    const sp = screen.getByLabelText('SP: 15,540')
    expect(screen.getByLabelText('XX: —')).toBeInTheDocument()
    fireEvent.focus(sp)
    expect(screen.getByRole('status')).toHaveTextContent('15,540')
    fireEvent.blur(sp)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('line chart: legend for two series on one axis, arrow keys move the readout', () => {
    render(
      <LineChart
        x={['2018-01-01', '2018-02-01', '2018-03-01']}
        series={[
          { name: 'revenue', values: [100, 120, 90] },
          { name: 'freight', values: [20, 25, 18] },
        ]}
      />,
    )
    expect(screen.getAllByRole('img')).toHaveLength(1) // one panel, one axis
    expect(screen.getByRole('list')).toHaveTextContent('Revenue')
    const overlay = screen.getByLabelText(/arrow keys/)
    fireEvent.keyDown(overlay, { key: 'ArrowRight' })
    const readout = screen.getByRole('status')
    expect(readout).toHaveTextContent('Jan 2018')
    expect(readout).toHaveTextContent('100')
    expect(readout).toHaveTextContent('20')
    fireEvent.keyDown(overlay, { key: 'ArrowRight' })
    expect(screen.getByRole('status')).toHaveTextContent('Feb 2018')
  })

  it('line chart: very different scales become small multiples, never two axes', () => {
    render(
      <LineChart
        x={['2018-01-01', '2018-02-01']}
        series={[
          { name: 'revenue', values: [945456.29, 837895.43] },
          { name: 'orders', values: [7269, 6728] },
        ]}
      />,
    )
    expect(screen.getAllByRole('img')).toHaveLength(2)
    expect(screen.getByRole('heading', { name: 'Orders' })).toBeInTheDocument()
  })
})
