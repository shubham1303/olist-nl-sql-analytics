import type { FormEvent, Ref } from 'react'
import { MAX_QUESTION_CHARS } from '../questions.ts'

interface Props {
  value: string
  onChange: (value: string) => void
  busy: boolean
  disabled: boolean
  onAsk: (question: string) => void
  ref?: Ref<HTMLTextAreaElement>
}

export function QuestionForm({ value, onChange, busy, disabled, onAsk, ref }: Props) {
  const trimmed = value.trim()
  const tooLong = value.length > MAX_QUESTION_CHARS
  const canAsk = trimmed.length > 0 && !tooLong && !busy && !disabled

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (canAsk) onAsk(trimmed)
  }

  return (
    <form className="ask" onSubmit={submit}>
      <label htmlFor="question" className="visually-hidden">
        Ask a question about Olist orders, products, sellers or customers
      </label>
      <textarea
        id="question"
        ref={ref}
        rows={2}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) submit(e)
        }}
        placeholder="Ask about orders, revenue, products, sellers, customers, delivery or reviews…"
        aria-describedby="question-count"
        aria-invalid={tooLong}
      />
      <div className="ask-actions">
        <span id="question-count" className={tooLong ? 'error-text count' : 'muted count'}>
          {value.length}/{MAX_QUESTION_CHARS}
        </span>
        <button type="submit" disabled={!canAsk}>
          {busy ? 'Working…' : 'Ask'}
        </button>
      </div>
    </form>
  )
}
