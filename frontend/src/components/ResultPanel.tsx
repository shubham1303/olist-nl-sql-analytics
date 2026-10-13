import { useState } from 'react'
import type { QueryResult } from '../api/types.ts'
import { ChartView } from '../charts/ChartView.tsx'
import { selectChart } from '../charts/selectChart.ts'
import { DataTable } from './DataTable.tsx'
import { SqlPanel } from './SqlPanel.tsx'

const FAILURE_TITLES: Partial<Record<QueryResult['status'], string>> = {
  unanswerable: "This question can't be answered from the Olist data",
  invalid_question: 'The question could not be sent',
  generation_failed: "The model couldn't produce an answer",
  rejected: "The generated SQL didn't pass the safety checks",
  validator_error: 'Something went wrong while checking the SQL',
  execution_failed: 'The database could not run the query',
}

export function ResultPanel({ result }: { result: QueryResult }) {
  const [view, setView] = useState<'chart' | 'table'>('chart')

  if (result.status !== 'answered') {
    const sql = result.validated_sql ?? result.generated_sql
    return (
      <section className="card result failure" aria-label="Result">
        <h2>{FAILURE_TITLES[result.status] ?? 'The question could not be answered'}</h2>
        {result.interpretation && <p className="muted">{result.interpretation}</p>}
        {result.error && <p role="alert">{result.error.message}</p>}
        {result.status === 'rejected' && (
          <p className="muted">
            Nothing was run. Try rephrasing the question, or ask about one thing at a time.
          </p>
        )}
        {sql && <SqlPanel sql={sql} label={result.validated_sql ? 'SQL' : 'Generated SQL (not run)'} />}
      </section>
    )
  }

  const spec = selectChart(result.columns, result.rows)
  const hasChart = spec.kind !== 'table'
  const shown = hasChart ? view : 'table'

  return (
    <section className="card result" aria-label="Result">
      {result.interpretation && <p className="interpretation">{result.interpretation}</p>}

      {result.row_count === 0 ? (
        <p className="empty">The query ran but returned no rows.</p>
      ) : (
        <>
          {hasChart && (
            <div className="tabs" role="tablist" aria-label="Result view">
              {(['chart', 'table'] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  role="tab"
                  aria-selected={shown === v}
                  className={shown === v ? 'tab active' : 'tab'}
                  onClick={() => setView(v)}
                >
                  {v === 'chart' ? 'Chart' : 'Table'}
                </button>
              ))}
            </div>
          )}
          {shown === 'chart' && spec.kind !== 'table' ? (
            <ChartView spec={spec} columns={result.columns} rows={result.rows} />
          ) : (
            <DataTable columns={result.columns} rows={result.rows} />
          )}
          {result.truncated && (
            <p className="notice" role="note">
              Showing the first {result.row_count.toLocaleString('en-US')} rows. The full result is
              larger; ask a narrower question or for a top-N to see everything.
            </p>
          )}
        </>
      )}

      {(result.assumptions.length > 0 || result.metrics_used.length > 0 || result.warnings.length > 0) && (
        <div className="details">
          {result.metrics_used.length > 0 && (
            <p>
              <span className="muted">Metrics: </span>
              {result.metrics_used.map((m) => (
                <code key={m}>{m}</code>
              ))}
            </p>
          )}
          {result.assumptions.length > 0 && (
            <>
              <h3>Assumptions</h3>
              <ul>
                {result.assumptions.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </>
          )}
          {result.warnings.length > 0 && (
            <ul className="warnings">
              {result.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {result.validated_sql && <SqlPanel sql={result.validated_sql} label="SQL" />}
      <p className="footer muted">
        {(result.timings.total_ms / 1000).toFixed(1)} s · {result.model_id}
        {result.repair_attempted && ' · repaired once'}
      </p>
    </section>
  )
}
