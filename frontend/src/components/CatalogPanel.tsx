import { useEffect, useMemo, useRef, useState } from 'react'
import { humanise } from '../charts/format.ts'
import { CATALOG } from '../lib/catalog.ts'
import type { CatalogTarget } from './SqlView.tsx'

interface Props {
  target: CatalogTarget | null // scroll to and highlight this entry
  canAsk: boolean
  onAsk: (question: string) => void
  onClose: () => void
}

function matches(query: string, ...texts: string[]): boolean {
  if (!query) return true
  const q = query.toLowerCase()
  return texts.some((t) => t.toLowerCase().includes(q))
}

export function CatalogPanel({ target, canAsk, onAsk, onClose }: Props) {
  const [query, setQuery] = useState('')
  const closeRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key !== 'Tab' || !panelRef.current) return
      // keep focus inside the dialog
      const focusable = panelRef.current.querySelectorAll<HTMLElement>('button, input, summary, [href]')
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last?.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first?.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      opener?.focus?.()
    }
  }, [onClose])

  useEffect(() => {
    if (!target) return
    const element = document.getElementById(`catalog-${target.kind}-${target.name}`)
    if (element && typeof element.scrollIntoView === 'function') element.scrollIntoView({ block: 'start' })
  }, [target])

  const topics = useMemo(
    () =>
      CATALOG.topics
        .map((t) => ({ ...t, questions: t.questions.filter((q) => matches(query, q, t.topic)) }))
        .filter((t) => t.questions.length > 0),
    [query],
  )
  const metrics = CATALOG.metrics.filter((m) => matches(query, m.name, m.label, m.definition, ...m.aliases))
  const relations = CATALOG.relations.filter((r) =>
    matches(query, r.name, r.description, ...r.columns.map((c) => c.name)),
  )

  return (
    <div className="panel-layer">
      <div className="scrim" aria-hidden="true" onClick={onClose} />
      <div ref={panelRef} className="catalog-panel" role="dialog" aria-modal="true" aria-labelledby="catalog-title">
        <header className="panel-head">
          <h2 id="catalog-title">What can I ask?</h2>
          <button ref={closeRef} type="button" className="secondary small" onClick={onClose}>
            Close
          </button>
        </header>
        <input
          type="search"
          className="panel-search"
          placeholder="Filter metrics, tables, columns and examples"
          aria-label="Filter"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />

        <div className="panel-body">
          <section aria-labelledby="catalog-data">
            <h3 id="catalog-data">The data</h3>
            <ul className="notes">
              {CATALOG.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
              <li>
                Not available: product names, customer or seller names, forecasts, and anything after October
                2018. Results are capped at {CATALOG.limits.max_result_rows.toLocaleString('en-US')} rows;
                questions at {CATALOG.limits.max_question_chars} characters.
              </li>
            </ul>
          </section>

          {topics.length > 0 && (
            <section aria-labelledby="catalog-examples">
              <h3 id="catalog-examples">Example questions</h3>
              {topics.map((t) => (
                <div key={t.topic} className="panel-topic">
                  <h4>{t.topic}</h4>
                  <ul>
                    {t.questions.map((q) => (
                      <li key={q}>
                        <button type="button" className="example" disabled={!canAsk} onClick={() => onAsk(q)}>
                          {q}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </section>
          )}

          {metrics.length > 0 && (
            <section aria-labelledby="catalog-metrics">
              <h3 id="catalog-metrics">Metrics</h3>
              <dl className="glossary">
                {metrics.map((m) => (
                  <div
                    key={m.name}
                    id={`catalog-metric-${m.name}`}
                    className={target?.kind === 'metric' && target.name === m.name ? 'entry targeted' : 'entry'}
                  >
                    <dt>
                      {m.label} <code>{m.name}</code>
                    </dt>
                    <dd>
                      {m.definition}
                      {m.aliases.length > 0 && <span className="muted"> Also: {m.aliases.join(', ')}.</span>}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          )}

          {relations.length > 0 && (
            <section aria-labelledby="catalog-tables">
              <h3 id="catalog-tables">Tables the model can use</h3>
              {relations.map((r) => {
                const targeted = target?.kind === 'relation' && target.name === r.name
                return (
                  <details
                    key={r.name}
                    id={`catalog-relation-${r.name}`}
                    className={targeted ? 'entry targeted' : 'entry'}
                    open={targeted || (query !== '' && relations.length <= 3)}
                  >
                    <summary>
                      <code>{r.name}</code> <span className="muted">{r.grain}</span>
                    </summary>
                    <p>{r.description}</p>
                    <table className="columns">
                      <tbody>
                        {r.columns.map((c) => (
                          <tr key={c.name}>
                            <th scope="row">
                              <code>{c.name}</code>
                            </th>
                            <td className="muted">{c.type}</td>
                            <td>{c.description}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </details>
                )
              })}
            </section>
          )}

          <section aria-labelledby="catalog-terms">
            <h3 id="catalog-terms">Terms</h3>
            <dl className="glossary">
              {CATALOG.glossary.map((g) => (
                <div key={g.term} className="entry">
                  <dt>{humanise(g.term)}</dt>
                  <dd>{g.meaning}</dd>
                </div>
              ))}
            </dl>
          </section>
        </div>
      </div>
    </div>
  )
}
