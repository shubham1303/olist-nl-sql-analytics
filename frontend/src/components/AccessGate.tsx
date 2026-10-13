import { useState, type FormEvent } from 'react'

interface Props {
  onSubmit: (code: string) => void
  rejected: boolean
}

export function AccessGate({ onSubmit, rejected }: Props) {
  const [code, setCode] = useState('')
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (code.trim()) onSubmit(code.trim())
  }
  return (
    <form className="card gate" onSubmit={submit}>
      <h2>Enter the access code</h2>
      <p className="muted">This demo is shared with a code. It is kept only for this browser tab.</p>
      <label htmlFor="access-code">Access code</label>
      <div className="row">
        <input
          id="access-code"
          type="password"
          autoComplete="off"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          aria-invalid={rejected}
          aria-describedby={rejected ? 'access-error' : undefined}
        />
        <button type="submit" disabled={!code.trim()}>
          Continue
        </button>
      </div>
      {rejected && (
        <p id="access-error" className="error-text" role="alert">
          That code didn't work. Check it and try again.
        </p>
      )}
    </form>
  )
}
