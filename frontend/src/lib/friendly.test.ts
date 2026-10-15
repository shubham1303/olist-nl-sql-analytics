import { describe, expect, it } from 'vitest'
import type { QueryResult } from '../api/types.ts'
import { friendly, suggestions } from './friendly.ts'

function failed(status: QueryResult['status'], code?: string, interpretation: string | null = null): QueryResult {
  return {
    question: 'q', status, model_id: 'm', prompt_version: 'v3', interpretation, assumptions: [], metrics_used: [],
    generated_sql: null, validated_sql: null, repair_attempted: false, columns: [], rows: [], row_count: 0,
    truncated: false, warnings: [], timings: { total_ms: 1, model_generation_ms: 1, execution_ms: null },
    error: code ? { stage: 's', code, message: 'technical' } : null,
  }
}

describe('friendly failures', () => {
  it('never shows the technical message as the main text', () => {
    const statuses: QueryResult['status'][] = ['unanswerable', 'invalid_question', 'rejected', 'execution_failed', 'generation_failed', 'validator_error']
    for (const status of statuses) {
      const f = friendly(failed(status, 'SOME_CODE'))
      expect(f.title.length).toBeGreaterThan(5)
      expect(f.body).not.toContain('technical')
      expect(f.body).not.toContain('SOME_CODE')
    }
  })

  it('explains each rejection in plain words', () => {
    expect(friendly(failed('rejected', 'WRITE_OPERATION')).body).toMatch(/only reads data/)
    expect(friendly(failed('rejected', 'FANOUT_RISK')).body).toMatch(/counted some orders more than once/)
    expect(friendly(failed('rejected', 'RESULT_LIMIT_EXCEEDED')).body).toMatch(/more than 1,000 rows/)
    expect(friendly(failed('rejected', 'NEW_CODE')).body).toBe('Try rephrasing the question, or ask about one thing at a time. Nothing was run.')
  })

  it('offers the right way forward', () => {
    expect(friendly(failed('unanswerable', undefined, 'A greeting.'))).toMatchObject({ tone: 'info', reason: 'A greeting.', examples: true, retry: false })
    expect(friendly(failed('generation_failed', 'throttled'))).toMatchObject({ tone: 'error', retry: true, examples: false })
    expect(friendly(failed('execution_failed', 'QUERY_TIMEOUT'))).toMatchObject({ title: 'That one took too long', retry: false })
    expect(friendly(failed('invalid_question', 'QUESTION_TOO_LONG')).body).toMatch(/under 500 characters/)
  })

  it('suggests real dev-split questions', () => {
    expect(suggestions()).toHaveLength(3)
    expect(suggestions()[0]).toBe('How many orders are in the dataset?')
  })
})
