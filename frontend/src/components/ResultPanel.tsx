import { useState } from 'react'
import type { QueryResult } from '../api/types.ts'
import { ChartView } from '../charts/ChartView.tsx'
import { KpiTile } from '../charts/KpiTile.tsx'
import { selectChart, toNumber } from '../charts/selectChart.ts'
import { metric } from '../lib/catalog.ts'
import { summarise } from '../lib/summary.ts'
import { DataTable } from './DataTable.tsx'
import { SqlView, type CatalogTarget } from './SqlView.tsx'

const FAILURE_TITLES: Partial<Record<QueryResult['status'], string>> = {
  unanswerable: "This question can't be answered from the Olist data",
  invalid_question: 'The question could not be sent',
  generation_failed: "The model couldn't produce an answer",
  rejected: "The generated SQL didn't pass the safety checks",
  validator_error: 'Something went wrong while checking the SQL',
  execution_failed: 'The database could not run the query',
}

const FAILURE_HINTS: Partial<Record<QueryResult['status'], string>> = {
  unanswerable: 'Open “What can I ask?” to see which tables, columns and metrics exist.',
  rejected: 'Nothing was run. Try rephrasing the question, or ask about one thing at a time.',
  execution_failed: 'Try a narrower question, such as a shorter period or a top-N.',
}

interface Props {
  result: QueryResult
  onOpenCatalog?: (target: CatalogTarget) => void
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

function Failure({ result, onOpenCatalog }: Props) {
  const sql = result.validated_sql ?? result.generated_sql
  const hint = FAILURE_HINTS[result.status]
  return (
    <section className="answer" aria-label="Result">
      <div className="card failure">
        <p className="eyebrow">{result.question}</p>
        <h2>{FAILURE_TITLES[result.status] ?? 'The question could not be answered'}</h2>
        {result.interpretation && <p className="muted">{result.interpretation}</p>}
        {result.error && (
          <p role="alert" className="failure-message">
            {result.error.message}
          </p>
        )}
        {hint && <p className="muted">{hint}</p>}
        <RunInfo result={result} />
      </div>
      {sql && (
        <div className="card">
          <h3 className="card-title">{result.validated_sql ? 'SQL' : 'Generated SQL (not run)'}</h3>
          <SqlView sql={sql} metrics={result.metrics_used} onOpenCatalog={onOpenCatalog} />
        </div>
      )}
    </section>
  )
}

export function ResultPanel({ result, onOpenCatalog }: Props) {
  const [tab, setTab] = useState<'table' | 'sql'>('table')
  if (result.status !== 'answered') return <Failure result={result} onOpenCatalog={onOpenCatalog} />

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
