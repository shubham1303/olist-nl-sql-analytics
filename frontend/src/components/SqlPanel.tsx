import { useState } from 'react'

interface Props {
  sql: string
  label: string
}

export function SqlPanel({ sql, label }: Props) {
  const [copied, setCopied] = useState(false)
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
    <details className="sql">
      <summary>{label}</summary>
      <div className="sql-body">
        <button type="button" className="copy" onClick={copy}>
          {copied ? 'Copied' : 'Copy'}
        </button>
        <pre>
          <code>{sql}</code>
        </pre>
      </div>
    </details>
  )
}
