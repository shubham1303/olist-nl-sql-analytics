import { relativeTime, type HistoryEntry } from '../lib/history.ts'

interface Props {
  history: HistoryEntry[]
  now: number // for "5 min ago"
  activeId: string | null
  open: boolean // the mobile drawer; always visible on wide screens
  onSelect: (entry: HistoryEntry) => void
  onNew: () => void
  onClear: () => void
  onOpenCatalog: () => void
  onLock: () => void
  onClose: () => void
}

export function Sidebar({ history, now, activeId, open, onSelect, onNew, onClear, onOpenCatalog, onLock, onClose }: Props) {
  return (
    <>
      {open && <div className="scrim" aria-hidden="true" onClick={onClose} />}
      <nav className={open ? 'sidebar open' : 'sidebar'} aria-label="Sidebar">
        <div className="brand">
          <span className="logo" aria-hidden="true">
            ◆
          </span>
          <div>
            <h1>Olist NL-to-SQL Analytics</h1>
            <p className="muted">Ask in plain English</p>
          </div>
        </div>

        <button type="button" className="new-question" onClick={onNew}>
          + New question
        </button>
        <button type="button" className="secondary help-button" onClick={onOpenCatalog}>
          What can I ask?
        </button>

        <div className="history">
          <div className="history-head">
            <h2>History</h2>
            {history.length > 0 && (
              <button type="button" className="link small" onClick={onClear}>
                Clear
              </button>
            )}
          </div>
          {history.length === 0 ? (
            <p className="muted small">Questions you ask in this tab appear here.</p>
          ) : (
            <ul aria-label="Question history">
              {history.map((entry) => {
                const ok = entry.result.status === 'answered'
                return (
                  <li key={entry.id}>
                    <button
                      type="button"
                      className={entry.id === activeId ? 'history-item active' : 'history-item'}
                      aria-current={entry.id === activeId ? 'true' : undefined}
                      onClick={() => onSelect(entry)}
                    >
                      <span className={ok ? 'status-dot ok' : 'status-dot failed'} aria-hidden="true" />
                      <span className="visually-hidden">{ok ? 'Answered:' : 'Not answered:'}</span>{' '}
                      <span className="history-text">
                        <span className="history-question">{entry.result.question}</span>{' '}
                        <span className="history-time muted">{relativeTime(entry.at, now)}</span>
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        <div className="sidebar-foot">
          <p className="muted small">Olist orders, Sep 2016 – Oct 2018. Read-only; results are capped at 1,000 rows.</p>
          <button type="button" className="link small" onClick={onLock}>
            Change access code
          </button>
        </div>
      </nav>
    </>
  )
}
