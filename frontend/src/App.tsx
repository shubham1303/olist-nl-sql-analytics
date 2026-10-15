import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchStatus, postQuery } from './api/client.ts'
import type { QueryResult } from './api/types.ts'
import { AccessGate } from './components/AccessGate.tsx'
import { CatalogPanel } from './components/CatalogPanel.tsx'
import { DatabaseStarting } from './components/DatabaseStarting.tsx'
import { EmptyState } from './components/EmptyState.tsx'
import { QuestionForm } from './components/QuestionForm.tsx'
import { ResultPanel } from './components/ResultPanel.tsx'
import { Sidebar } from './components/Sidebar.tsx'
import type { CatalogTarget } from './components/SqlView.tsx'
import { loadHistory, makeEntry, prepend, saveHistory, type HistoryEntry } from './lib/history.ts'

export const CODE_KEY = 'olist-nlsql-access-code'
export const POLL_MS = 3000
// The spike measured about 82 s after a day idle; allow plenty more before giving up.
export const GIVE_UP_MS = 180_000

type Db =
  | { phase: 'idle' }
  | { phase: 'checking' }
  | { phase: 'starting'; since: number; attempt: number }
  | { phase: 'ready' }
  | { phase: 'down'; message: string }

type Panel = { target: CatalogTarget | null } | null

function readCode(): string | null {
  try {
    return sessionStorage.getItem(CODE_KEY)
  } catch {
    return null
  }
}

function writeCode(code: string | null) {
  try {
    if (code === null) sessionStorage.removeItem(CODE_KEY)
    else sessionStorage.setItem(CODE_KEY, code)
  } catch {
    // storage blocked: the code lives only in memory for this page
  }
}

function App() {
  const [code, setCode] = useState<string | null>(readCode)
  const [rejected, setRejected] = useState(false)
  const [db, setDb] = useState<Db>(() => (readCode() ? { phase: 'checking' } : { phase: 'idle' }))
  const pending = useRef<string | null>(null) // asked while the database was resuming
  const [busy, setBusy] = useState(false)
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<QueryResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const [history, setHistory] = useState<HistoryEntry[]>(loadHistory)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [drawer, setDrawer] = useState(false)
  const [panel, setPanel] = useState<Panel>(null)
  const input = useRef<HTMLTextAreaElement>(null)

  const lock = useCallback((wrongCode: boolean) => {
    writeCode(null)
    setCode(null)
    setRejected(wrongCode)
    setDb({ phase: 'idle' })
    setResult(null)
    setPanel(null)
    pending.current = null
  }, [])

  const remember = useCallback((answer: QueryResult) => {
    const entry = makeEntry(answer)
    setHistory((entries) => prepend(entries, entry))
    setActiveId(entry.id)
  }, [])

  useEffect(() => saveHistory(history), [history])

  const ask = useCallback(
    async (text: string) => {
      if (!code) return
      setQuestion(text)
      setBusy(true)
      setError(null)
      setResult(null)
      setActiveId(null)
      const outcome = await postQuery(code, text)
      setBusy(false)
      if (outcome.kind === 'unauthorized') return lock(true)
      if (outcome.kind === 'resuming') {
        pending.current = text // asked again once /status says ready
        setDb({ phase: 'starting', since: Date.now(), attempt: 0 })
        return
      }
      if (outcome.kind === 'error') return setError(outcome.message)
      setResult(outcome.value)
      setNow(Date.now())
      remember(outcome.value)
    },
    [code, lock, remember],
  )

  // /status: check once, then poll every POLL_MS while the database is resuming.
  useEffect(() => {
    if (!code || (db.phase !== 'checking' && db.phase !== 'starting')) return
    let cancelled = false
    const timer = setTimeout(
      async () => {
        const outcome = await fetchStatus(code)
        if (cancelled) return
        if (outcome.kind === 'unauthorized') return lock(true)
        if (outcome.kind === 'error') return setDb({ phase: 'down', message: outcome.message })
        if (outcome.kind === 'resuming') {
          const since = db.phase === 'starting' ? db.since : Date.now()
          if (Date.now() - since > GIVE_UP_MS) {
            return setDb({ phase: 'down', message: "The database didn't start within 3 minutes." })
          }
          const attempt = db.phase === 'starting' ? db.attempt + 1 : 1
          return setDb({ phase: 'starting', since, attempt })
        }
        if (outcome.value === 'unavailable') {
          return setDb({ phase: 'down', message: 'The database is unavailable right now.' })
        }
        setDb({ phase: 'ready' })
        const waiting = pending.current
        pending.current = null
        if (waiting) void ask(waiting)
      },
      db.phase === 'checking' ? 0 : POLL_MS,
    )
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [code, db, lock, ask])

  // the elapsed-seconds counter on the starting screen
  useEffect(() => {
    if (db.phase !== 'starting') return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [db.phase])

  // keeps the history's "5 min ago" current
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 60_000)
    return () => clearInterval(timer)
  }, [])

  const enter = (value: string) => {
    writeCode(value)
    setCode(value)
    setRejected(false)
    setDb({ phase: 'checking' })
  }

  const ready = db.phase === 'ready'
  const startNew = () => {
    setResult(null)
    setError(null)
    setActiveId(null)
    setQuestion('')
    setDrawer(false)
    input.current?.focus()
  }
  const select = (entry: HistoryEntry) => {
    setResult(entry.result)
    setQuestion(entry.result.question)
    setError(null)
    setActiveId(entry.id)
    setDrawer(false)
  }
  const clearHistory = () => {
    setHistory([])
    setActiveId(null)
  }
  const openCatalog = useCallback((target: CatalogTarget | null = null) => {
    setDrawer(false)
    setPanel({ target })
  }, [])
  const closeCatalog = useCallback(() => setPanel(null), [])
  const askFromPanel = (q: string) => {
    setPanel(null)
    void ask(q)
  }

  if (!code) {
    return (
      <main className="gate-page">
        <header className="gate-brand">
          <span className="logo" aria-hidden="true">
            ◆
          </span>
          <h1>Olist NL-to-SQL Analytics</h1>
          <p className="muted">Ask business questions about the Olist e-commerce dataset in plain English.</p>
        </header>
        <AccessGate onSubmit={enter} rejected={rejected} />
      </main>
    )
  }

  return (
    <div className="shell">
      <Sidebar
        history={history}
        now={now}
        activeId={activeId}
        open={drawer}
        onSelect={select}
        onNew={startNew}
        onClear={clearHistory}
        onOpenCatalog={() => openCatalog()}
        onLock={() => lock(false)}
        onClose={() => setDrawer(false)}
      />
      <main className="main">
        <div className="topbar">
          <button type="button" className="secondary small menu" aria-expanded={drawer} onClick={() => setDrawer(true)}>
            Menu
          </button>
          <span className="topbar-title">Olist Analytics</span>
          <button type="button" className="link small" onClick={() => openCatalog()}>
            What can I ask?
          </button>
        </div>

        <div className="content">
          {db.phase === 'checking' && <p className="muted">Connecting…</p>}
          {db.phase === 'starting' && (
            <DatabaseStarting elapsedSeconds={Math.max(0, Math.round((now - db.since) / 1000))} />
          )}
          {db.phase === 'down' && (
            <div className="card failure" role="alert">
              <p>{db.message}</p>
              <button type="button" onClick={() => setDb({ phase: 'checking' })}>
                Try again
              </button>
            </div>
          )}

          <QuestionForm ref={input} value={question} onChange={setQuestion} busy={busy} disabled={!ready} onAsk={ask} />

          {busy && (
            <div className="card working" role="status">
              <div className="spinner" aria-hidden="true" />
              <div>
                <p className="working-title">Working on it…</p>
                <p className="muted">Writing the SQL, checking it and running it. This usually takes a few seconds.</p>
              </div>
            </div>
          )}
          {error && (
            <div className="card soft-failure tone-error" role="alert">
              <h2>Couldn't reach the service</h2>
              <p>{error} Check your connection, then try again.</p>
              <div className="failure-actions">
                <button type="button" disabled={!ready || !question.trim()} onClick={() => void ask(question.trim())}>
                  Try again
                </button>
              </div>
            </div>
          )}
          {result && !busy && (
            <ResultPanel key={activeId ?? result.question} result={result} onOpenCatalog={openCatalog} onAsk={ask} />
          )}
          {!result && !busy && !error && db.phase !== 'starting' && (
            <EmptyState disabled={!ready} onAsk={ask} onOpenCatalog={() => openCatalog()} />
          )}
        </div>
      </main>
      {panel && <CatalogPanel target={panel.target} canAsk={ready && !busy} onAsk={askFromPanel} onClose={closeCatalog} />}
    </div>
  )
}

export default App
