// The "What can I ask?" data: generated from catalog.yaml and the dev split by
// `python -m olist_nlsql.uicatalog` (a backend test fails when it drifts).
import data from '../generated/catalog.json'

export interface CatalogMetric {
  name: string
  label: string
  definition: string
  unit: string
  aliases: string[]
}

export interface CatalogColumn {
  name: string
  type: string
  description: string
}

export interface CatalogRelation {
  name: string
  description: string
  grain: string
  columns: CatalogColumn[]
}

export interface Topic {
  topic: string
  questions: string[]
}

export interface UiCatalog {
  notes: string[]
  glossary: { term: string; meaning: string }[]
  limits: { max_question_chars: number; max_result_rows: number }
  topics: Topic[]
  metrics: CatalogMetric[]
  relations: CatalogRelation[]
}

export const CATALOG: UiCatalog = data

const metricsByName = new Map(CATALOG.metrics.map((m) => [m.name, m]))
const relationNames = new Set(CATALOG.relations.map((r) => r.name))

export function metric(name: string): CatalogMetric | undefined {
  return metricsByName.get(name)
}

/** Catalog relations a query reads, in order of first use: `FROM analytics.orders o`. */
export function relationsUsed(sql: string): string[] {
  const found: string[] = []
  for (const match of sql.matchAll(/\b(?:from|join)\s+(?:"?analytics"?\.)?"?([a-z_]+)"?/gi)) {
    const name = match[1]!.toLowerCase()
    if (relationNames.has(name) && !found.includes(name)) found.push(name)
  }
  return found
}
