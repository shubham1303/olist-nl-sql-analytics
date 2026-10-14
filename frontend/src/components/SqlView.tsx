import { useMemo, useState } from 'react'
import { metric, relationsUsed } from '../lib/catalog.ts'
import { tokenize } from '../lib/sqlTokens.ts'

export type CatalogTarget = { kind: 'metric' | 'relation'; name: string }

interface Props {
  sql: string
  metrics?: string[]
  onOpenCatalog?: (target: CatalogTarget) => void
}

export function SqlView({ sql, metrics = [], onOpenCatalog }: Props) {
  const [copied, setCopied] = useState(false)
  const tokens = useMemo(() => tokenize(sql), [sql])
  const relations = useMemo(() => relationsUsed(sql), [sql])
  const known = metrics.filter((m) => metric(m) !== undefined)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(sql)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // clipboard blocked: the SQL is still selectable
    }
  }

  return (
    <div className="sql-view">
      {(relations.length > 0 || known.length > 0) && (
        <div className="uses" aria-label="Uses">
          <span className="muted">Uses</span>
          {relations.map((name) => (
            <button
              key={`r-${name}`}
              type="button"
              className="chip chip-view"
              title="Open this view in “What can I ask?”"
              onClick={() => onOpenCatalog?.({ kind: 'relation', name })}
            >
              {name}
            </button>
          ))}
          {known.map((name) => (
            <button
              key={`m-${name}`}
              type="button"
              className="chip chip-metric"
              title={metric(name)?.definition}
              onClick={() => onOpenCatalog?.({ kind: 'metric', name })}
            >
              {metric(name)?.label ?? name}
            </button>
          ))}
        </div>
      )}
      <div className="sql-body">
        <button type="button" className="copy" onClick={copy}>
          {copied ? 'Copied' : 'Copy'}
        </button>
        <pre className="sql-code">
          <code>
            {tokens.map((t, i) =>
              t.kind === 'space' || t.kind === 'punct' || t.kind === 'identifier' ? (
                t.text
              ) : (
                <span key={i} className={`tok-${t.kind}`}>
                  {t.text}
                </span>
              ),
            )}
          </code>
        </pre>
      </div>
    </div>
  )
}
