"""Prompt construction. The only place prompt text lives.

The system prompt is generated deterministically from the catalog (ADR 0005): exposed
relations, columns, relationships, metrics and the function allowlist. Hidden
relations and columns never appear. The same system prompt is sent on both calls, so
Bedrock can cache it; the question or repair instruction goes in the user message.
"""

from dataclasses import dataclass
from functools import cache

from olist_nlsql.catalog import Catalog, Relation, load_catalog
from olist_nlsql.config import Settings
from olist_nlsql.sqlsafety import ErrorCode, Issue

# Bump whenever prompt text or structure changes, so evaluation runs can be compared.
PROMPT_VERSION = "v1"

_INTRO = """\
You translate business questions about the Olist Brazilian e-commerce marketplace into \
one PostgreSQL SELECT query. Money is in BRL. Your SQL is checked by a validator and then \
runs on a read-only database; a query that breaks the rules below is rejected, not run."""

_SQL_RULES = """\
## SQL rules
- Exactly one SELECT statement (CTEs allowed). Never write INSERT, UPDATE, DELETE, DDL, SET or transaction statements.
- Use only the relations and columns listed below, in schema analytics (e.g. analytics.orders). Nothing else exists for you.
- Name every column; never SELECT *.
- Join only through the relationships listed below, with INNER or LEFT JOIN ... ON the listed keys. Give every relation an alias and qualify every column when you join.
- Never aggregate a column after a join that repeats its rows (one-to-many). Aggregate the many side to one row per key in a subquery first, compute the value from its own relation, or use COUNT(DISTINCT key).
- In order_sellers and order_categories the delivery and review columns repeat the order's outcome for every seller or category. Aggregate them or COUNT(*) only when grouping by seller_id / product_category; for totals use orders.
- Use only these functions: {functions}. Casts: {casts}.
- No NOW(), CURRENT_DATE or other "today" functions: the data ends in 2018. Use explicit dates.
- Results are capped at {max_rows} rows. For rankings use ORDER BY with LIMIT.
- Prefer the simplest correct query. Avoid joins the question does not need."""

_BUSINESS_RULES = """\
## Business rules
- "Revenue" and "sales" mean the revenue metric (merchandise revenue: item price, excluding freight, for non-canceled orders with items). Use freight, total order value or payment value only when the question asks for them.
- A customer is customer_unique_id. Count customers with COUNT(DISTINCT customer_unique_id).
- Late delivery rate = late orders / delivered orders that have a delivery date (COUNT(is_late) is the denominator).
- review_score is each order's latest review; average it per order, never per review row.
- Use a catalog metric's definition whenever the question uses its name or an alias; do not add assumptions about it.
- For a term the catalog does not define (e.g. "best sellers"), choose a reasonable meaning, state it in assumptions, and answer.
- Keep exactly the period the question asks for, even outside 2017-01 to 2018-08. Do not filter to that window on your own unless the question asks for a trend or comparison without a period; then say so in assumptions.
- If the question cannot be answered from these relations (e.g. product names, customer names, forecasts), set can_answer to false, leave sql empty and explain in interpretation."""

_OUTPUT = """\
## Output
Answer by calling the submit_answer tool exactly once, with: can_answer; interpretation (one sentence restating \
the question exactly as your SQL answers it); sql; assumptions (empty list when the catalog defines every term); \
metrics_used (catalog metric names you computed)."""


def _relation_section(relation: Relation) -> str:
    key = ", ".join(relation.grain_key)
    lines = [f"### {relation.name} — {relation.grain} Key: {key}.", relation.description]
    for column in relation.exposed_columns:
        values = f" Values: {', '.join(column.values)}." if column.values else ""
        lines.append(f"- {column.name} ({column.type}): {column.description}{values}")
    lines.extend(f"Note: {caveat}" for caveat in relation.caveats)
    return "\n".join(lines)


def _relationships_section(catalog: Catalog) -> str:
    lines = ["## Relationships (the only allowed joins; each is one-to-many)"]
    for r in catalog.relationships:
        on = " AND ".join(f"{r.one}.{k.one} = {r.many}.{k.many}" for k in r.keys)
        lines.append(f"- {r.one} 1→N {r.many}: {on}")
    return "\n".join(lines)


def _metrics_section(catalog: Catalog) -> str:
    lines = ["## Metrics (use these definitions exactly)"]
    for m in catalog.metrics:
        aliases = ", ".join(m.aliases)
        if m.expression is not None:
            how = f"{m.expression} FROM {m.relation}"
        else:
            how = " ".join((m.query or "").split())
        excludes = f" Excludes: {' '.join(m.exclusions)}" if m.exclusions else ""
        caveats = f" Note: {' '.join(m.caveats)}" if m.caveats else ""
        lines.append(f"- {m.name} ({aliases}): {m.definition} SQL: {how}.{excludes}{caveats}")
    return "\n".join(lines)


def _context_section(catalog: Catalog) -> str:
    lines = ["## Dataset"]
    lines.extend(f"- {note}" for note in catalog.dataset_notes)
    lines.extend(f"- {g.term}: {g.meaning}" for g in catalog.glossary)
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class PromptSections:
    intro: str
    sql_rules: str
    business_rules: str
    dataset: str
    relations: str
    relationships: str
    metrics: str
    output: str

    def render(self) -> str:
        return "\n\n".join(
            (
                self.intro,
                self.sql_rules,
                self.business_rules,
                self.dataset,
                self.relations,
                self.relationships,
                self.metrics,
                self.output,
            )
        )


def build_sections(catalog: Catalog, max_rows: int) -> PromptSections:
    functions = ", ".join(f.name for f in catalog.functions)
    return PromptSections(
        intro=_INTRO,
        sql_rules=_SQL_RULES.format(
            functions=functions, casts=", ".join(catalog.cast_types), max_rows=max_rows
        ),
        business_rules=_BUSINESS_RULES,
        dataset=_context_section(catalog),
        relations="## Relations\n\n"
        + "\n\n".join(_relation_section(r) for r in catalog.exposed_relations),
        relationships=_relationships_section(catalog),
        metrics=_metrics_section(catalog),
        output=_OUTPUT,
    )


@cache
def _cached_system_prompt(max_rows: int) -> str:
    return build_sections(load_catalog(), max_rows).render()


def system_prompt(settings: Settings, catalog: Catalog | None = None) -> str:
    """The catalog prompt; cached for the packaged catalog."""
    if catalog is None:
        return _cached_system_prompt(settings.max_result_rows)
    return build_sections(catalog, settings.max_result_rows).render()


def question_message(question: str) -> str:
    return f"Question: {question}"


# repair

_REPAIR_GUIDANCE: dict[ErrorCode, str] = {
    ErrorCode.PARSE_ERROR: "Write syntactically valid PostgreSQL.",
    ErrorCode.MULTIPLE_STATEMENTS: "Return exactly one SELECT statement.",
    ErrorCode.UNSUPPORTED_CONSTRUCT: "Rewrite with plain SELECT, JOIN, WHERE, GROUP BY, ORDER BY, LIMIT and non-recursive CTEs.",
    ErrorCode.SELECT_STAR: "List the columns explicitly.",
    ErrorCode.UNAPPROVED_SCHEMA: "Use only relations in the analytics schema listed in the catalog.",
    ErrorCode.UNAPPROVED_RELATION: "Use only the listed relations.",
    ErrorCode.UNAPPROVED_COLUMN: "Use only the listed columns of each relation.",
    ErrorCode.AMBIGUOUS_COLUMN: "Qualify every column with its relation alias.",
    ErrorCode.UNAPPROVED_FUNCTION: "Use only the listed functions and cast types.",
    ErrorCode.INVALID_JOIN_PATH: "Join only through the listed relationships, on all of their keys.",
    ErrorCode.FANOUT_RISK: (
        "A join repeats rows before aggregation. Compute the value from its own relation, "
        "aggregate the many side to one row per key in a subquery before joining, or use "
        "COUNT(DISTINCT key)."
    ),
    ErrorCode.RESULT_LIMIT_EXCEEDED: "Use a LIMIT within the maximum, or aggregate.",
    ErrorCode.QUERY_TOO_LARGE: "Write a shorter query with fewer joins.",
}

_ATTRIBUTION_GUIDANCE = (
    "In order_sellers/order_categories, delivery and review outcomes repeat per seller or "
    "category. Group by seller_id / product_category, or compute the total from orders."
)

# Codes where a second model call may help. A write attempt or a validator bug is not
# something the model should get another try at (ADR 0003, docs/nl-to-sql.md).
REPAIRABLE: frozenset[ErrorCode] = frozenset(_REPAIR_GUIDANCE)


def repair_instruction(issue: Issue, catalog: Catalog) -> str:
    """A compact, machine-facing fix for one validator issue."""
    guidance = _REPAIR_GUIDANCE.get(issue.code, "Fix the query.")
    relation = issue.details.get("relation", "")
    column = issue.details.get("column", "").split(".")[-1]
    if issue.code == ErrorCode.FANOUT_RISK:
        bridge = next(
            (r for r in catalog.exposed_relations if r.name == relation and r.attribution_key),
            None,
        )
        if bridge is not None and (
            not column or column in {c.name for c in bridge.columns if c.attributed}
        ):
            guidance = _ATTRIBUTION_GUIDANCE
    facts = ", ".join(f"{k}={v}" for k, v in sorted(issue.details.items()) if k != "exception")
    return f"{guidance} ({facts})" if facts else guidance


def repair_message(question: str, rejected_sql: str, issue: Issue, catalog: Catalog) -> str:
    return (
        f"Question: {question}\n\n"
        f"Your previous SQL was rejected by the validator:\n{rejected_sql}\n\n"
        f"Error: {issue.code}\n"
        f"Fix: {repair_instruction(issue, catalog)}\n\n"
        "Call submit_answer again with the corrected answer."
    )


# diagnostics


def prompt_stats(settings: Settings, catalog: Catalog | None = None) -> dict[str, int]:
    """Characters per section and an approximate token count (chars / 4, English text)."""
    sections = build_sections(catalog or load_catalog(), settings.max_result_rows)
    sizes = {name: len(getattr(sections, name)) for name in sections.__dataclass_fields__}
    total = len(sections.render())
    sizes["total_chars"] = total
    sizes["approx_tokens"] = total // 4
    return sizes
