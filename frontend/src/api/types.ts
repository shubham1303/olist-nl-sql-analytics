// Shapes returned by the backend API (backend/src/olist_nlsql/api/handlers.py).

export type ColumnType = 'integer' | 'number' | 'text' | 'date' | 'timestamp' | 'boolean' | 'unknown'

export interface Column {
  name: string
  type: ColumnType
}

// Decimals arrive as exact strings, dates as ISO text.
export type Cell = string | number | boolean | null

export type QueryStatus =
  | 'answered'
  | 'unanswerable'
  | 'invalid_question'
  | 'generation_failed'
  | 'rejected'
  | 'validator_error'
  | 'execution_failed'
  | 'database_resuming'

export interface PipelineError {
  stage: string
  code: string
  message: string
}

export interface QueryResult {
  question: string
  status: QueryStatus
  model_id: string
  prompt_version: string
  interpretation: string | null
  assumptions: string[]
  metrics_used: string[]
  generated_sql: string | null
  validated_sql: string | null
  repair_attempted: boolean
  columns: Column[]
  rows: Cell[][]
  row_count: number
  truncated: boolean
  warnings: string[]
  timings: { total_ms: number; model_generation_ms: number; execution_ms: number | null }
  error: PipelineError | null
}

export type DbState = 'ready' | 'resuming' | 'unavailable'
