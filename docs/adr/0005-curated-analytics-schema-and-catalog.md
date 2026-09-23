# 0005. Curated analytics views + one catalog as source of truth

- Status: Accepted
- Date: 2026-09-23

## Context

The raw Olist schema has traps that produce confidently wrong answers:
- `customer_id` is per order, not per customer.
- Orders with multiple payments double-count values when joined.
- Category names are in Portuguese.
- "Revenue", "delivered" and "late" have no single obvious definition.

If the prompt's schema description and the validator's allowlist are maintained
separately, they will drift.

## Decision

**Curated layer:**
- Raw CSVs load into schema `raw`, which the model and `analytics_reader` can't see.
- A small schema `analytics` of views is designed for business questions. The views
  resolve the known modelling problems:
  - expose `customer_unique_id` as the customer key
  - pre-aggregate payments to one row per order
  - join the English category translation
  - use consistent order-status handling

**One catalog file** (`backend/src/olist_nlsql/catalog/catalog.yaml`) is the single
source of truth for:
- approved relations and columns (with types and descriptions)
- business metric definitions (name, definition, SQL expression, grain)
- aliases and synonyms (for example "sales" maps to the revenue metric)

**Both the LLM schema context and the SQL validator allowlist are generated from this
catalog.** A test asserts that every catalog relation and column exists in the database
and every view column is in the catalog.

**Scope:** the raw geolocation table (~1M rows) may be loaded into `raw` for
completeness but is **excluded** from the catalog and the LLM-visible schema. We'll add
a curated geographic view only if benchmark questions show a need.

**Ambiguity:**
- Terms defined in the metric catalog are resolved by the catalog, not by model
  judgement.
- Genuinely ambiguous terms outside the catalog get an explicit assumption and an
  answer (single turn). For example: "Assuming 'best sellers' means sellers with the
  highest total revenue..."
- The response carries `metrics_used` and `assumptions`, and the UI shows both.

## Consequences

- The view definitions and the catalog become the main levers for improving accuracy.
  Changes are measured on the dev benchmark ([ADR 0006](0006-evaluation-methodology.md)).
- Adding a column means editing a view and the catalog. The drift test fails if only
  one changes.
