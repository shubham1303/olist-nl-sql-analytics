import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchStatus, postQuery } from './api/client.ts'
import type { QueryResult } from './api/types.ts'
import { AccessGate } from './components/AccessGate.tsx'
import { DatabaseStarting } from './components/DatabaseStarting.tsx'
import { QuestionForm } from './components/QuestionForm.tsx'
import { ResultPanel } from './components/ResultPanel.tsx'

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
  const [result, setResult] = useState<QueryResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [now, setNow] = useState(() => Date.now())

  const lock = useCallback((wrongCode: boolean) => {
    writeCode(null)
    setCode(null)
    setRejected(wrongCode)
    setDb({ phase: 'idle' })
    setResult(null)
    pending.current = null
  }, [])

  const ask = useCallback(
    async (question: string) => {
      if (!code) return
      setBusy(true)
      setError(null)
      const outcome = await postQuery(code, question)
      setBusy(false)
      if (outcome.kind === 'unauthorized') return lock(true)
      if (outcome.kind === 'resuming') {
        pending.current = question // asked again once /status says ready
        setDb({ phase: 'starting', since: Date.now(), attempt: 0 })
        return
      }
      if (outcome.kind === 'error') {
        setResult(null)
        return setError(outcome.message)
      }
      setResult(outcome.value)
    },
    [code, lock],
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
        const question = pending.current
        pending.current = null
        if (question) void ask(question)
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

  const enter = (value: string) => {
    writeCode(value)
    setCode(value)
    setRejected(false)
    setDb({ phase: 'checking' })
  }

  return (
    <main className="app">
      <header className="header">
        <div>
          <h1>Olist NL-to-SQL Analytics</h1>
          <p className="muted">Ask business questions about the Olist e-commerce dataset in plain English.</p>
        </div>
        {code && (
          <button type="button" className="link" onClick={() => lock(false)}>
            Change access code
          </button>
        )}
      </header>

      {!code ? (
        <AccessGate onSubmit={enter} rejected={rejected} />
      ) : (
        <>
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
          <QuestionForm busy={busy} disabled={db.phase !== 'ready'} onAsk={ask} />
          {busy && (
            <p className="muted" role="status">
              Writing the SQL, checking it and running it. This usually takes a few seconds.
            </p>
          )}
          {error && (
            <p className="card failure" role="alert">
              {error}
            </p>
          )}
          {result && !busy && <ResultPanel key={result.question + result.timings.total_ms} result={result} />}
        </>
      )}
    </main>
  )
}

export default App
