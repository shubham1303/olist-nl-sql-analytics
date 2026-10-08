"""Prompt construction: deterministic, catalog-derived, compact, hidden relations absent.

Assertions check content, not whitespace, so layout tweaks do not break them.
"""

import re

from olist_nlsql.catalog import load_catalog
from olist_nlsql.config import Settings
from olist_nlsql.llm.prompts import (
    PROMPT_VERSION,
    REPAIRABLE,
    build_sections,
    prompt_stats,
    repair_message,
    system_prompt,
)
from olist_nlsql.sqlsafety import ErrorCode, Issue

CATALOG = load_catalog()
PROMPT = system_prompt(Settings())

# Budget to notice growth, not a target: raise it deliberately if the catalog grows.
MAX_PROMPT_CHARS = 30_000


def test_prompt_is_deterministic() -> None:
    assert build_sections(CATALOG, 1000).render() == build_sections(load_catalog(), 1000).render()
    assert system_prompt(Settings()) == PROMPT


def test_prompt_version_is_set() -> None:
    assert re.fullmatch(r"v\d+", PROMPT_VERSION)


def test_every_exposed_relation_and_column_is_described() -> None:
    for relation in CATALOG.exposed_relations:
        assert f"### {relation.name} — {relation.grain}" in PROMPT
        for column in relation.exposed_columns:
            assert f"- {column.name} ({column.type})" in PROMPT, (relation.name, column.name)


def test_hidden_relations_and_columns_never_appear() -> None:
    visible_names = {c.name for r in CATALOG.exposed_relations for c in r.exposed_columns}
    visible_names |= {m.name for m in CATALOG.metrics}  # e.g. metric order_count
    leaked = []
    for relation in CATALOG.relations:
        if not relation.exposed:
            assert f"### {relation.name}" not in PROMPT
            assert f"analytics.{relation.name}" not in PROMPT
            assert f"FROM {relation.name}" not in PROMPT
        for column in relation.columns:
            hidden = not column.exposed or not relation.exposed
            if (
                hidden
                and column.name not in visible_names
                and re.search(rf"\b{column.name}\b", PROMPT)
            ):
                leaked.append(f"{relation.name}.{column.name}")
    assert not leaked, leaked
    for name in (
        "total_revenue",
        "units_sold",
        "has_min_20_delivered_orders",
        "is_repeat_customer",
    ):
        assert name not in PROMPT


def test_raw_and_internal_schemas_never_appear() -> None:
    assert "raw." not in PROMPT and "analytics_internal" not in PROMPT


def test_relationships_metrics_and_functions_are_included() -> None:
    for r in CATALOG.relationships:
        for k in r.keys:
            assert f"{r.one}.{k.one} = {r.many}.{k.many}" in PROMPT
    for m in CATALOG.metrics:
        assert f"- {m.name} (" in PROMPT
        assert all(alias in PROMPT for alias in m.aliases)
    for f in CATALOG.functions:
        assert f.name in PROMPT


def test_project_semantics_are_stated() -> None:
    lowered = PROMPT.lower()
    for phrase in (
        "merchandise revenue",
        "customer_unique_id",
        "count(is_late) is the denominator",
        "latest review",
        "repeat the order's outcome",
        "keep exactly the period",
        "select *",
        "can_answer to false",
    ):
        assert phrase in lowered, phrase


def test_prompt_size_is_reported_and_within_budget() -> None:
    stats = prompt_stats(Settings())
    assert stats["total_chars"] == len(PROMPT) < MAX_PROMPT_CHARS
    assert stats["approx_tokens"] == stats["total_chars"] // 4
    assert stats["relations"] > stats["metrics"] > stats["relationships"]
    print("\nprompt size:", stats)  # visible with pytest -s


def test_repair_message_is_compact_and_uses_the_code() -> None:
    issue = Issue(
        ErrorCode.FANOUT_RISK,
        "a very long human-facing explanation " * 20,
        {"aggregate": "SUM(o.revenue)", "column": "o.revenue", "relation": "orders"},
    )
    message = repair_message("Revenue by category?", "SELECT SUM(o.revenue) ...", issue, CATALOG)
    assert "Error: FANOUT_RISK" in message and "SUM(o.revenue)" in message
    assert "human-facing explanation" not in message
    assert len(message) < 700


def test_repair_message_explains_bridge_attribution() -> None:
    issue = Issue(
        ErrorCode.FANOUT_RISK,
        "long",
        {
            "aggregate": "AVG(s.review_score)",
            "column": "s.review_score",
            "relation": "order_sellers",
        },
    )
    assert "Group by seller_id" in repair_message("q", "SELECT ...", issue, CATALOG)


def test_write_operations_and_validator_bugs_are_not_repairable() -> None:
    assert ErrorCode.WRITE_OPERATION not in REPAIRABLE
    assert ErrorCode.VALIDATOR_INTERNAL_ERROR not in REPAIRABLE
    assert ErrorCode.FANOUT_RISK in REPAIRABLE
