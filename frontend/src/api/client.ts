import type { DbState, QueryResult } from './types.ts'

// Local dev: Vite proxies /api to the local API. AWS (Phase 8): the API Gateway URL.
const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api'

export type Outcome<T> =
  | { kind: 'ok'; value: T }
  | { kind: 'unauthorized' }
  | { kind: 'resuming' }
  | { kind: 'error'; message: string }

async function call(path: string, code: string, init: RequestInit = {}): Promise<Response | null> {
  try {
    return await fetch(`${BASE}${path}`, {
      ...init,
      headers: { ...init.headers, 'X-Access-Code': code },
    })
  } catch {
    return null
  }
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { error?: { message?: string } | null }
    if (body.error?.message) return body.error.message
  } catch {
    // not JSON: fall through
  }
  return `The server answered ${response.status}.`
}

export async function fetchStatus(code: string): Promise<Outcome<DbState>> {
  const response = await call('/status', code)
  if (response === null) return { kind: 'error', message: 'Could not reach the server.' }
  if (response.status === 401) return { kind: 'unauthorized' }
  if (response.status === 503) return { kind: 'ok', value: 'unavailable' }
  if (!response.ok) return { kind: 'error', message: await errorMessage(response) }
  const body = (await response.json()) as { db: DbState }
  return body.db === 'resuming' ? { kind: 'resuming' } : { kind: 'ok', value: body.db }
}

export async function postQuery(code: string, question: string): Promise<Outcome<QueryResult>> {
  const response = await call('/query', code, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  if (response === null) return { kind: 'error', message: 'Could not reach the server.' }
  if (response.status === 401) return { kind: 'unauthorized' }
  if (response.status === 503) return { kind: 'resuming' }
  let body: QueryResult | { error: { message: string } }
  try {
    body = (await response.json()) as typeof body
  } catch {
    return { kind: 'error', message: `The server answered ${response.status}.` }
  }
  if ('status' in body) return { kind: 'ok', value: body }
  return { kind: 'error', message: body.error.message }
}
