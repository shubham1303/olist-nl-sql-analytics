import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App, { CODE_KEY, GIVE_UP_MS, POLL_MS } from './App.tsx'
import type { QueryResult } from './api/types.ts'

type Reply = { status: number; body: unknown } | 'network'
type Route = (init?: RequestInit) => Reply

let routes: Record<string, Route[]>
let calls: { path: string; init?: RequestInit }[]

function json(status: number, body: unknown): Reply {
  return { status, body }
}

/** Queue replies per path; the last one repeats. */
function on(path: string, ...replies: Reply[]) {
  routes[path] = replies.map((r) => () => r)
}

function answer(overrides: Partial<QueryResult> = {}): QueryResult {
  return {
    question: 'What was total revenue?',
    status: 'answered',
    model_id: 'us.anthropic.claude-sonnet-4-6',
    prompt_version: 'v2',
    interpretation: 'Total merchandise revenue across all orders.',
    assumptions: [],
    metrics_used: ['revenue'],
    generated_sql: 'SELECT SUM(revenue) AS revenue FROM analytics.orders',
    validated_sql: 'SELECT SUM(revenue) AS revenue FROM analytics.orders LIMIT 1001',
    repair_attempted: false,
    columns: [{ name: 'revenue', type: 'number' }],
    rows: [['13494400.74']],
    row_count: 1,
    truncated: false,
    warnings: [],
    timings: { total_ms: 2400, model_generation_ms: 2000, execution_ms: 120 },
    error: null,
    ...overrides,
  }
}

async function flush(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

async function enterCode(code = 'correct-horse-battery') {
  fireEvent.change(screen.getByLabelText('Access code'), { target: { value: code } })
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
  await flush()
}

async function ask(question: string) {
  fireEvent.change(screen.getByLabelText(/Ask a question/), { target: { value: question } })
  fireEvent.click(screen.getByRole('button', { name: 'Ask' }))
  await flush()
}

beforeEach(() => {
  vi.useFakeTimers()
  sessionStorage.clear()
  routes = {}
  calls = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const path = url.replace(/^\/api/, '')
      calls.push({ path, init })
      const queue = routes[path] ?? []
      const route = queue.length > 1 ? queue.shift()! : queue[0]
      const reply = route ? route(init) : json(404, { error: { message: 'no route' } })
      if (reply === 'network') throw new TypeError('Failed to fetch')
      return new Response(JSON.stringify(reply.body), { status: reply.status })
    }),
  )
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('access code', () => {
  it('asks for the code first and sends it on every request', async () => {
    on('/status', json(200, { db: 'ready' }))
    render(<App />)
    expect(screen.getByRole('heading', { level: 1, name: 'Olist NL-to-SQL Analytics' })).toBeInTheDocument()
    expect(screen.queryByLabelText(/Ask a question/)).not.toBeInTheDocument()
    await enterCode()
    expect(sessionStorage.getItem(CODE_KEY)).toBe('correct-horse-battery')
    expect(new Headers(calls[0]!.init?.headers).get('X-Access-Code')).toBe('correct-horse-battery')
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled() // nothing typed yet
  })

  it('a wrong code returns to the gate with a message and is forgotten', async () => {
    on('/status', json(401, { error: { code: 'UNAUTHORIZED', message: 'Missing or wrong access code.' } }))
    render(<App />)
    await enterCode('wrong')
    expect(screen.getByRole('alert')).toHaveTextContent("That code didn't work")
    expect(sessionStorage.getItem(CODE_KEY)).toBeNull()
  })

  it('reuses a code kept for this tab', async () => {
    sessionStorage.setItem(CODE_KEY, 'kept-code-123')
    on('/status', json(200, { db: 'ready' }))
    render(<App />)
    await flush()
    expect(screen.getByLabelText(/Ask a question/)).toBeInTheDocument()
  })
})

describe('database starting', () => {
  it('polls /status while resuming, then enables questions', async () => {
    on('/status', json(200, { db: 'resuming' }), json(200, { db: 'resuming' }), json(200, { db: 'ready' }))
    render(<App />)
    await enterCode()
    expect(screen.getByRole('heading', { name: 'Starting analytics database…' })).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toBeInTheDocument() // can type while waiting
    await flush(POLL_MS)
    expect(screen.getByText('Starting analytics database…')).toBeInTheDocument()
    await flush(POLL_MS)
    expect(screen.queryByText('Starting analytics database…')).not.toBeInTheDocument()
    expect(calls.filter((c) => c.path === '/status')).toHaveLength(3)
  })

  it('explains a long start after 30 s, and gives up after 3 minutes', async () => {
    on('/status', json(200, { db: 'resuming' }))
    render(<App />)
    await enterCode()
    expect(screen.queryByText(/first start after a quiet day/)).not.toBeInTheDocument()
    await flush(33_000)
    expect(screen.getByText(/first start after a quiet day/)).toBeInTheDocument()
    expect(screen.getByText(/^3\d s$/)).toBeInTheDocument()
    // one poll cycle per act(): effects only run when act() finishes
    for (let i = 0; i <= GIVE_UP_MS / POLL_MS; i++) await flush(POLL_MS)
    expect(screen.getByRole('alert')).toHaveTextContent("didn't start within 3 minutes")
    on('/status', json(200, { db: 'ready' }))
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await flush()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('a query that meets a resuming database waits, then is asked again', async () => {
    on('/status', json(200, { db: 'ready' }), json(200, { db: 'resuming' }), json(200, { db: 'ready' }))
    on('/query', json(503, answer({ status: 'database_resuming', rows: [], columns: [] })), json(200, answer()))
    render(<App />)
    await enterCode()
    await ask('What was total revenue?')
    expect(screen.getByText('Starting analytics database…')).toBeInTheDocument()
    await flush(POLL_MS) // resuming
    await flush(POLL_MS) // ready -> question asked again
    await flush()
    expect(calls.filter((c) => c.path === '/query')).toHaveLength(2)
    expect(screen.getByText('13.5M')).toBeInTheDocument()
  })

  it('a server it cannot reach is an error with a retry', async () => {
    on('/status', 'network')
    render(<App />)
    await enterCode()
    expect(screen.getByRole('alert')).toHaveTextContent('Could not reach the server.')
  })
})

describe('results', () => {
  beforeEach(() => on('/status', json(200, { db: 'ready' })))

  it('shows a KPI, the interpretation, metrics and the SQL', async () => {
    on('/query', json(200, answer()))
    render(<App />)
    await enterCode()
    await ask('What was total revenue?')
    expect(JSON.parse(String(calls.at(-1)!.init?.body))).toEqual({ question: 'What was total revenue?' })
    expect(screen.getByText('13.5M')).toBeInTheDocument()
    expect(screen.getByText('Total merchandise revenue across all orders.')).toBeInTheDocument()
    expect(screen.getByText('revenue', { selector: 'code' })).toBeInTheDocument()
    expect(screen.getByRole('table')).toHaveTextContent('13,494,400.74') // Table is the default tab
    fireEvent.click(screen.getByRole('tab', { name: 'SQL' }))
    expect(screen.getByText('LIMIT', { selector: '.tok-keyword' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Views used' })).toHaveTextContent('Vieworders')
    expect(screen.getByRole('button', { name: 'orders (view)' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Merchandise revenue (metric)' })).toBeInTheDocument()
  })

  it('a view and a metric with the same name are told apart', async () => {
    on('/query', json(200, answer({ metrics_used: ['order_count'], validated_sql: 'SELECT COUNT(*) AS orders FROM analytics.orders LIMIT 1001' })))
    render(<App />)
    await enterCode()
    await ask('How many orders?')
    fireEvent.click(screen.getByRole('tab', { name: 'SQL' }))
    expect(screen.getByRole('group', { name: 'Views used' })).toHaveTextContent(/^View\s*orders$/)
    expect(screen.getByRole('group', { name: 'Metrics used' })).toHaveTextContent(/^Metric\s*Orders$/)
    fireEvent.click(screen.getByRole('button', { name: 'Orders (metric)' }))
    expect(document.getElementById('catalog-metric-order_count')).toHaveClass('targeted')
  })

  it('chart choice follows the result shape, with a table always available', async () => {
    on(
      '/query',
      json(
        200,
        answer({
          columns: [
            { name: 'customer_state', type: 'text' },
            { name: 'orders', type: 'integer' },
          ],
          rows: [
            ['SP', 15540],
            ['RJ', 6882],
          ],
          row_count: 2,
        }),
      ),
    )
    render(<App />)
    await enterCode()
    await ask('Orders by state?')
    expect(screen.getByRole('img', { name: 'Bar chart of Orders' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'SP has the highest orders: 15,540' })).toBeInTheDocument()
    expect(screen.getByText('SP is 69% of the total shown (22,422).')).toBeInTheDocument()
    expect(screen.getByRole('table')).toBeInTheDocument() // the data card is always there
  })

  it('a wide result is a table only, with a truncation notice', async () => {
    const rows = Array.from({ length: 3 }, (_, i) => [`order-${i}`, 'delivered', i])
    on(
      '/query',
      json(
        200,
        answer({
          columns: [
            { name: 'order_id', type: 'text' },
            { name: 'order_status', type: 'text' },
            { name: 'items', type: 'integer' },
          ],
          rows,
          row_count: 1000,
          truncated: true,
        }),
      ),
    )
    render(<App />)
    await enterCode()
    await ask('List orders')
    expect(screen.queryByRole('img')).not.toBeInTheDocument() // no chart for a wide result
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByRole('note')).toHaveTextContent('Showing the first 1,000 rows')
  })

  it('an empty result says so', async () => {
    on('/query', json(200, answer({ rows: [], row_count: 0 })))
    render(<App />)
    await enterCode()
    await ask('Orders in 2030?')
    expect(screen.getByText('The query ran but returned no rows.')).toBeInTheDocument()
  })

  it('a rejected query explains why and shows the SQL that was not run', async () => {
    on(
      '/query',
      json(
        200,
        answer({
          status: 'rejected',
          validated_sql: null,
          generated_sql: 'SELECT * FROM sellers',
          columns: [],
          rows: [],
          row_count: 0,
          error: { stage: 'validation', code: 'UNAPPROVED_RELATION', message: 'Use only the listed relations.' },
        }),
      ),
    )
    render(<App />)
    await enterCode()
    await ask('Show sellers')
    expect(screen.getByRole('heading', { name: "I couldn't find a safe way to answer that" })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent("That needs data this app doesn't have access to. Nothing was run.")
    // the technical detail is still there, one click away
    expect(screen.getByText('Technical details')).toBeInTheDocument()
    expect(screen.getByText('UNAPPROVED_RELATION', { selector: 'code' })).toBeInTheDocument()
    expect(screen.getByText(/Use only the listed relations\./)).toBeInTheDocument()
    expect(screen.getByText('Generated SQL (not run)')).toBeInTheDocument()
  })

  it('a request that is not a data question gets a gentle answer and questions that work', async () => {
    const reason = 'The input is a greeting, not a question about the Olist data.'
    on(
      '/query',
      json(200, answer({ question: 'hello', status: 'unanswerable', interpretation: reason, validated_sql: null, generated_sql: null, columns: [], rows: [], row_count: 0 })),
      json(200, answer()),
    )
    render(<App />)
    await enterCode()
    await ask('hello')
    expect(screen.getByRole('heading', { name: "That's not something I can answer here" })).toBeInTheDocument()
    expect(screen.getByText(/I can only read the data, never change it\./)).toBeInTheDocument()
    expect(screen.getByText(reason)).toBeInTheDocument()
    expect(screen.queryByText('Technical details')).not.toBeInTheDocument() // nothing technical to show
    fireEvent.click(screen.getByRole('button', { name: 'How many orders are in the dataset?' }))
    await flush()
    expect(JSON.parse(String(calls.at(-1)!.init?.body))).toEqual({ question: 'How many orders are in the dataset?' })
  })

  it('a write request is explained as read-only, without the jargon', async () => {
    on(
      '/query',
      json(200, answer({
        question: 'delete all canceled orders', status: 'rejected', validated_sql: null, generated_sql: 'DELETE FROM orders',
        columns: [], rows: [], row_count: 0,
        error: { stage: 'validation', code: 'WRITE_OPERATION', message: 'Only SELECT statements are allowed.' },
      })),
    )
    render(<App />)
    await enterCode()
    await ask('delete all canceled orders')
    expect(screen.getByRole('status')).toHaveTextContent("This app only reads data, so it can't add, change or delete anything.")
  })

  it('a temporary failure offers Try again, which asks the same question', async () => {
    on(
      '/query',
      json(200, answer({ status: 'generation_failed', validated_sql: null, generated_sql: null, columns: [], rows: [], row_count: 0, error: { stage: 'generation', code: 'throttled', message: 'Rate exceeded' } })),
      json(200, answer()),
    )
    render(<App />)
    await enterCode()
    await ask('What was total revenue?')
    expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong while writing the query')
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await flush()
    expect(calls.filter((c) => c.path === '/query')).toHaveLength(2)
    expect(screen.getByText('13.5M')).toBeInTheDocument()
  })

  it('a question over 500 characters cannot be sent', async () => {
    render(<App />)
    await enterCode()
    fireEvent.change(screen.getByLabelText(/Ask a question/), { target: { value: 'x'.repeat(501) } })
    expect(screen.getByText('501/500')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled()
  })

  it('an expired code during a query goes back to the gate', async () => {
    on('/query', json(401, { error: { code: 'UNAUTHORIZED', message: 'Missing or wrong access code.' } }))
    render(<App />)
    await enterCode()
    await ask('What was total revenue?')
    expect(screen.getByLabelText('Access code')).toBeInTheDocument()
  })
})

describe('history and the catalog panel', () => {
  beforeEach(() => on('/status', json(200, { db: 'ready' })))

  it('keeps each answer in the history and re-opens it without asking again', async () => {
    on('/query', json(200, answer()), json(200, answer({ question: 'Orders?', rows: [['99441']], columns: [{ name: 'orders', type: 'integer' }] })))
    render(<App />)
    await enterCode()
    await ask('What was total revenue?')
    await ask('Orders?')
    const history = screen.getByRole('list', { name: 'Question history' })
    expect(history).toHaveTextContent('Orders?')
    expect(history).toHaveTextContent('What was total revenue?')
    fireEvent.click(screen.getByRole('button', { name: /^Answered: What was total revenue\? just now$/ }))
    expect(screen.getByText('13.5M')).toBeInTheDocument()
    expect(calls.filter((c) => c.path === '/query')).toHaveLength(2)
    expect(JSON.parse(sessionStorage.getItem('olist-nlsql-history')!)).toHaveLength(2)
  })

  it('New question clears the answer and shows the examples', async () => {
    on('/query', json(200, answer()))
    render(<App />)
    await enterCode()
    await ask('What was total revenue?')
    fireEvent.click(screen.getByRole('button', { name: '+ New question' }))
    expect(screen.queryByText('13.5M')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Ask the Olist data a question' })).toBeInTheDocument()
    expect(screen.getByLabelText(/Ask a question/)).toHaveValue('')
  })

  it('an example question from the start page is asked directly', async () => {
    on('/query', json(200, answer()))
    render(<App />)
    await enterCode()
    fireEvent.click(screen.getByRole('button', { name: 'How many orders are in the dataset?' }))
    await flush()
    expect(JSON.parse(String(calls.at(-1)!.init?.body))).toEqual({ question: 'How many orders are in the dataset?' })
  })

  it('What can I ask? lists metrics and tables, filters, and closes on Escape', async () => {
    render(<App />)
    await enterCode()
    fireEvent.click(screen.getAllByRole('button', { name: 'What can I ask?' })[0]!)
    const dialog = screen.getByRole('dialog', { name: 'What can I ask?' })
    expect(dialog).toHaveTextContent('Late delivery rate')
    expect(dialog).toHaveTextContent('order_sellers')
    fireEvent.change(screen.getByLabelText('Filter'), { target: { value: 'lead time' } })
    expect(dialog).toHaveTextContent('Average delivery time')
    expect(dialog).not.toHaveTextContent('Late delivery rate')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('a metric in the answer opens its catalog entry', async () => {
    on('/query', json(200, answer()))
    render(<App />)
    await enterCode()
    await ask('What was total revenue?')
    fireEvent.click(screen.getByText('revenue', { selector: 'code' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(document.getElementById('catalog-metric-revenue')).toHaveClass('targeted')
  })
})

