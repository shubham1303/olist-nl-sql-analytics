// Plain-language wording for answers that didn't work out. The API's error codes and
// messages are written for the model's repair step; people get this instead, with the
// technical detail one click away.

import type { QueryResult } from '../api/types.ts'
import { CATALOG } from './catalog.ts'

export type Tone = 'info' | 'warn' | 'error'

export interface Friendly {
  tone: Tone
  title: string
  body: string
  reason: string | null // the model's own explanation, when it gave one
  examples: boolean // suggest questions that do work
  retry: boolean // a temporary problem: asking again may succeed
}

export const SCOPE =
  'I can look things up in the Olist e-commerce data: orders, revenue, products, sellers, ' +
  'customers, delivery and reviews, from September 2016 to October 2018. I can only read the ' +
  'data, never change it.'

const REJECTED: Record<string, string> = {
  WRITE_OPERATION: "This app only reads data, so it can't add, change or delete anything.",
  UNAPPROVED_SCHEMA: "That needs data this app doesn't have access to.",
  UNAPPROVED_RELATION: "That needs data this app doesn't have access to.",
  UNAPPROVED_COLUMN: "That needs a detail the data doesn't include.",
  UNAPPROVED_FUNCTION: "The query I wrote used something that isn't allowed here, so I didn't run it.",
  FANOUT_RISK:
    'The query I wrote would have counted some orders more than once, so I stopped it before ' +
    'it gave you a wrong number.',
  INVALID_JOIN_PATH:
    'The query I wrote combined the data in a way that could double count, so I stopped it ' +
    'before it gave you a wrong number.',
  RESULT_LIMIT_EXCEEDED: `That would return more than ${CATALOG.limits.max_result_rows.toLocaleString('en-US')} rows. Ask for a top 10 or a summary instead.`,
  QUERY_TOO_LARGE: 'The query I wrote was too complicated to run safely.',
}

export function friendly(result: QueryResult): Friendly {
  const code = result.error?.code ?? ''
  const reason = result.interpretation?.trim() || null
  switch (result.status) {
    case 'unanswerable':
      return { tone: 'info', title: "That's not something I can answer here", body: SCOPE, reason, examples: true, retry: false }
    case 'invalid_question':
      return {
        tone: 'info',
        title: code === 'QUESTION_TOO_LONG' ? 'That question is too long' : 'Type a question first',
        body:
          code === 'QUESTION_TOO_LONG'
            ? `Keep it under ${CATALOG.limits.max_question_chars} characters; one question at a time works best.`
            : 'Ask about the Olist data in plain English.',
        reason: null,
        examples: true,
        retry: false,
      }
    case 'rejected':
      return {
        tone: 'warn',
        title: "I couldn't find a safe way to answer that",
        body: `${REJECTED[code] ?? 'Try rephrasing the question, or ask about one thing at a time.'} Nothing was run.`,
        reason,
        examples: true,
        retry: false,
      }
    case 'execution_failed':
      return {
        tone: 'warn',
        title: code === 'QUERY_TIMEOUT' ? 'That one took too long' : "The database couldn't run that query",
        body:
          code === 'QUERY_TIMEOUT'
            ? 'It needs more than the 10 seconds the database allows. Try a shorter period, one category, or a top 10.'
            : 'Try rephrasing the question, or make it narrower.',
        reason: null,
        examples: false,
        retry: code !== 'QUERY_TIMEOUT',
      }
    case 'generation_failed':
      return {
        tone: 'error',
        title: 'Something went wrong while writing the query',
        body: 'This is usually temporary. Please try again in a moment.',
        reason: null,
        examples: false,
        retry: true,
      }
    case 'validator_error':
      return {
        tone: 'error',
        title: 'Something went wrong on our side',
        body: 'The safety check failed unexpectedly, so nothing was run. Please try again.',
        reason: null,
        examples: false,
        retry: true,
      }
    default:
      return {
        tone: 'error',
        title: "That didn't work",
        body: 'Please try again, or rephrase the question.',
        reason: null,
        examples: false,
        retry: true,
      }
  }
}

/** A few questions that do work, one from each of the first topics. */
export function suggestions(count = 3): string[] {
  return CATALOG.topics.slice(0, count).flatMap((t) => t.questions.slice(0, 1))
}
