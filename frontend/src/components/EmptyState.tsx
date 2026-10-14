import { CATALOG } from '../lib/catalog.ts'

interface Props {
  disabled: boolean
  onAsk: (question: string) => void
  onOpenCatalog: () => void
}

export const TOPICS_SHOWN = 6
export const QUESTIONS_PER_TOPIC = 2

export function EmptyState({ disabled, onAsk, onOpenCatalog }: Props) {
  return (
    <section className="empty-state" aria-label="Getting started">
      <div className="hero">
        <h2>Ask the Olist data a question</h2>
        <p className="muted">
          Ask in plain English about orders, revenue, products, sellers, customers, delivery or reviews. Every
          answer shows the SQL that ran, the metrics it used and any assumptions.
        </p>
      </div>
      <div className="topic-grid">
        {CATALOG.topics.slice(0, TOPICS_SHOWN).map((topic) => (
          <div key={topic.topic} className="card topic">
            <h3>{topic.topic}</h3>
            <ul>
              {topic.questions.slice(0, QUESTIONS_PER_TOPIC).map((q) => (
                <li key={q}>
                  <button type="button" className="example" disabled={disabled} onClick={() => onAsk(q)}>
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <p className="muted small">
        Complete months run from January 2017 to August 2018.{' '}
        <button type="button" className="link small" onClick={onOpenCatalog}>
          See every metric, table and example
        </button>
      </p>
    </section>
  )
}
