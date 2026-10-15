import { useState } from 'react'
import type { QueryResult } from '../api/types.ts'
import { ChartView } from '../charts/ChartView.tsx'
import { KpiTile } from '../charts/KpiTile.tsx'
import { selectChart, toNumber } from '../charts/selectChart.ts'
import { metric } from '../lib/catalog.ts'
import { friendly, suggestions } from '../lib/friendly.ts'
import { summarise } from '../lib/summary.ts'
import { DataTable } from './DataTable.tsx'
import { SqlView, type CatalogTarget } from './SqlView.tsx'

interface Props {
  result: QueryResult
  onOpenCatalog?: (target: CatalogTarget | null) => void
  onAsk?: (question: string) => void
}

function RunInfo({ result }: { result: QueryResult }) {
  const seconds = (result.timings.total_ms / 1000).toFixed(1)
  return (
    <p className="run-info muted">
      {seconds} s · {result.model_id} · prompt {result.prompt_version}
      {result.repair_attempted && ' · repaired once'}
    </p>
  )
}

function Failure({ result, onOpenCatalog, onAsk }: Props) {
  const sql = result.validated_sql ?? result.generated_sql
  const message = friendly(result)
  const hasDetails = Boolean(result.error || sql)
  return (
    <section className="answer" aria-label="Result">
      <div className={`card soft-failure tone-${message.tone}`} role={message.tone === 'error' ? 'alert' : 'status'}>
        <p className="eyebrow">{result.question}</p>
        <h2>{message.title}</h2>
        <p>{message.body}</p>
        {message.reason && (
          <p className="muted reason">
            <span className="reason-label">Why: </span>
            {message.reason}
          </p>
        )}
        {(message.retry || message.examples) && (
          <div className="failure-actions">
            {message.retry && onAsk && (
              <button type="button" onClick={() => onAsk(result.question)}>
                Try again
              </button>
            )}
            {message.examples && (
              <button type="button" className="link" onClick={() => onOpenCatalog?.(null)}>
                See everything you can ask
              </button>
            )}
          </div>
        )}
        {message.examples && onAsk && (
          <div className="failure-examples">
            <p className="muted small">Questions that work, for example:</p>
            <ul>
              {suggestions().map((q) => (
                <li key={q}>
                  <button type="button" className="example" onClick={() => onAsk(q)}>
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {hasDetails && (
          <details className="tech-details">
            <summary>Technical details</summary>
            {result.error && (
              <p className="failure-message">
                <code>{result.error.code}</code> {result.error.message}
              </p>
            )}
            {sql && (
              <>
                <h3 className="card-title">{result.validated_sql ? 'SQL' : 'Generated SQL (not run)'}</h3>
                <SqlView sql={sql} metrics={result.metrics_used} onOpenCatalog={onOpenCatalog} />
              </>
            )}
          </details>
        )}
        <RunInfo result={result} />
      </div>
    </section>
  )
}

export function ResultPanel({ result, onOpenCatalog, onAsk }: Props) {
  const [tab, setTab] = useState<'table' | 'sql'>('table')
  if (result.status !== 'answered') return <Failure result={result} onOpenCatalog={onOpenCatalog} onAsk={onAsk} />

  const spec = selectChart(result.columns, result.rows)
  const summary = summarise(result, spec)
  const kpiValue = spec.kind === 'kpi' ? toNumber(result.rows[0]?.[spec.value]) : null
  const chart = spec.kind === 'bar' || spec.kind === 'line' ? spec : null
  const hasDetails = result.assumptions.length > 0 || result.metrics_used.length > 0 || result.warnings.length > 0

  return (
    <section className="answer" aria-label="Result">
      <div className="card answer-head">
        <p className="eyebrow">{result.question}</p>
        {result.row_count === 0 ? (
          <p className="empty">The query ran but returned no rows.</p>
        ) : kpiValue !== null && spec.kind === 'kpi' ? (
          <KpiTile label={result.columns[spec.value]!.name} value={kpiValue} />
        ) : summary.stats ? (
          <dl className="stats">
            {summary.stats.map((s) => (
              <div key={s.label} className="stat">
                <dt>{s.label}</dt>
                <dd>{s.value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          summary.headline && <h2 className="headline">{summary.headline}</h2>
        )}
        {summary.takeaways.length > 0 && (
          <ul className="takeaways">
            {summary.takeaways.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        )}
        {result.interpretation && <p className="interpretation">{result.interpretation}</p>}
        {result.truncated && (
          <p className="notice" role="note">
            Showing the first {result.row_count.toLocaleString('en-US')} rows. The full result is larger; ask a
            narrower question or for a top-N to see everything.
          </p>
        )}
      </div>

      {(chart || hasDetails) && (
        <div className={chart ? 'answer-grid' : 'answer-grid single'}>
          {chart && (
            <div className="card chart-card">
              <ChartView spec={chart} columns={result.columns} rows={result.rows} />
            </div>
          )}
          {hasDetails && (
            <aside className="card details" aria-label="Details">
              {result.metrics_used.length > 0 && (
                <div className="detail-block">
                  <h3>Metrics</h3>
                  <ul className="metric-list">
                    {result.metrics_used.map((m) => (
                      <li key={m}>
                        <button
                          type="button"
                          className="metric-link"
                          onClick={() => onOpenCatalog?.({ kind: 'metric', name: m })}
                        >
                          <code>{m}</code>
                        </button>
                        {metric(m) && <span className="muted"> {metric(m)!.definition}</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {result.assumptions.length > 0 && (
                <div className="detail-block">
                  <h3>Assumptions</h3>
                  <ul>
                    {result.assumptions.map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                </div>
              )}
              {result.warnings.length > 0 && (
                <div className="detail-block">
                  <h3>Warnings</h3>
                  <ul className="warnings">
                    {result.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </aside>
          )}
        </div>
      )}

      <div className="card data-card">
        <div className="tabs" role="tablist" aria-label="Data and SQL">
          {(['table', 'sql'] as const).map((t) => (
            <button
              key={t}
              type="button"
              role="tab"
              id={`tab-${t}`}
              aria-selected={tab === t}
              aria-controls={`panel-${t}`}
              className={tab === t ? 'tab active' : 'tab'}
              onClick={() => setTab(t)}
            >
              {t === 'table' ? 'Table' : 'SQL'}
            </button>
          ))}
        </div>
        <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
          {tab === 'table' ? (
            <DataTable columns={result.columns} rows={result.rows} question={result.question} />
          ) : (
            result.validated_sql && (
              <SqlView sql={result.validated_sql} metrics={result.metrics_used} onOpenCatalog={onOpenCatalog} />
            )
          )}
        </div>
        <RunInfo result={result} />
      </div>
    </section>
  )
}
