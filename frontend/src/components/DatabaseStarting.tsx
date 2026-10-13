interface Props {
  elapsedSeconds: number
}

// Aurora resume spike (docs/spikes/aurora-resume.md): about 15-20 s after a short pause,
// about 80-90 s after a day idle.
const LONG_START_AFTER = 30

export function DatabaseStarting({ elapsedSeconds }: Props) {
  return (
    <div className="card starting" role="status" aria-live="polite">
      <div className="spinner" aria-hidden="true" />
      <div>
        <h2>Starting analytics database…</h2>
        <p className="muted">
          The database pauses when nobody is using it, to keep costs down. It usually takes
          about 20 seconds to wake up.
        </p>
        {elapsedSeconds >= LONG_START_AFTER && (
          <p className="muted">
            The first start after a quiet day can take a minute or two. Still working on it.
          </p>
        )}
        <p className="elapsed">{elapsedSeconds} s</p>
      </div>
    </div>
  )
}
