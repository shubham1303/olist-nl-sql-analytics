import { useState, type FormEvent } from 'react'
import { EXAMPLES, MAX_QUESTION_CHARS } from '../questions.ts'

interface Props {
  busy: boolean
  disabled: boolean
  onAsk: (question: string) => void
}

export function QuestionForm({ busy, disabled, onAsk }: Props) {
  const [question, setQuestion] = useState('')
  const trimmed = question.trim()
  const tooLong = question.length > MAX_QUESTION_CHARS
  const canAsk = trimmed.length > 0 && !tooLong && !busy && !disabled

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (canAsk) onAsk(trimmed)
  }

  return (
    <form className="card ask" onSubmit={submit}>
      <label htmlFor="question">Ask a question about Olist orders, products, sellers or customers</label>
      <textarea
        id="question"
        rows={3}
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) submit(e)
        }}
        placeholder="e.g. Which 10 sellers had the highest revenue in 2018?"
        aria-describedby="question-count"
        aria-invalid={tooLong}
      />
      <div className="row between">
        <span id="question-count" className={tooLong ? 'error-text' : 'muted'}>
          {question.length}/{MAX_QUESTION_CHARS}
        </span>
        <button type="submit" disabled={!canAsk}>
          {busy ? 'Working…' : 'Ask'}
        </button>
      </div>
      <div className="examples" aria-label="Example questions">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            className="chip"
            disabled={busy || disabled}
            onClick={() => {
              setQuestion(example)
              onAsk(example)
            }}
          >
            {example}
          </button>
        ))}
      </div>
    </form>
  )
}
