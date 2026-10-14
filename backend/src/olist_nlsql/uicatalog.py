"""The "What can I ask?" panel's data, generated from catalog.yaml and the dev split.

python -m olist_nlsql.uicatalog            write frontend/src/generated/catalog.json
python -m olist_nlsql.uicatalog --check    exit 1 if that file is out of date

Only what the model itself sees is exported: exposed relations and columns, metrics,
dataset notes and the glossary (ADR 0015). Example questions come from the dev split
only; held-out questions never appear in the app (ADR 0006). A unit test fails when the
committed file drifts from this output.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from olist_nlsql.catalog import Catalog, load_catalog
from olist_nlsql.config import Settings
from olist_nlsql.dbsetup.env import REPO_ROOT

OUTPUT = REPO_ROOT / "frontend" / "src" / "generated" / "catalog.json"

# An item goes to the first topic whose tag it has; the rest are "Orders and revenue".
_TOPIC_BY_TAG = (
    ("seller", "Sellers"),
    ("delivery", "Delivery"),
    ("review", "Reviews"),
    ("product_category", "Products and categories"),
    ("join", "Products and categories"),
    ("customer", "Customers"),
    ("time_series", "Trends over time"),
)
_FALLBACK_TOPIC = "Orders and revenue"
_TOPIC_ORDER = (
    _FALLBACK_TOPIC,
    "Trends over time",
    "Customers",
    "Products and categories",
    "Sellers",
    "Delivery",
    "Reviews",
)


def _topic(tags: tuple[str, ...]) -> str:
    return next((topic for tag, topic in _TOPIC_BY_TAG if tag in tags), _FALLBACK_TOPIC)


def _examples() -> list[dict[str, Any]]:
    from olist_nlsql.evaluation import benchmark as bm  # dev split only, never test

    grouped: dict[str, list[str]] = {topic: [] for topic in _TOPIC_ORDER}
    for item in bm.load("dev").items:
        grouped[_topic(item.tags)].append(" ".join(item.question.split()))
    return [{"topic": t, "questions": qs} for t, qs in grouped.items() if qs]


def ui_catalog(catalog: Catalog, settings: Settings) -> dict[str, Any]:
    return {
        "generated_from": "backend/src/olist_nlsql/catalog/catalog.yaml and eval/benchmark/dev.yaml"
        " by python -m olist_nlsql.uicatalog; do not edit",
        "notes": [" ".join(n.split()) for n in catalog.dataset_notes],
        "glossary": [{"term": g.term, "meaning": g.meaning} for g in catalog.glossary],
        "limits": {
            "max_question_chars": settings.max_question_chars,
            "max_result_rows": settings.max_result_rows,
        },
        "topics": _examples(),
        "metrics": [
            {
                "name": m.name,
                "label": m.label,
                "definition": " ".join(m.definition.split()),
                "unit": m.unit,
                "aliases": list(m.aliases),
            }
            for m in catalog.metrics
        ],
        "relations": [
            {
                "name": r.name,
                "description": " ".join(r.description.split()),
                "grain": r.grain,
                "columns": [
                    {"name": c.name, "type": c.type, "description": " ".join(c.description.split())}
                    for c in r.exposed_columns
                ],
            }
            for r in catalog.exposed_relations
        ],
    }


def render(catalog: Catalog | None = None, settings: Settings | None = None) -> str:
    data = ui_catalog(catalog or load_catalog(), settings or Settings())
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m olist_nlsql.uicatalog")
    parser.add_argument("--check", action="store_true", help="fail if the file is out of date")
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    text = render()
    if args.check:
        current = args.out.read_text(encoding="utf-8") if args.out.exists() else ""
        if current != text:
            print(
                f"{args.out} is out of date; run python -m olist_nlsql.uicatalog", file=sys.stderr
            )
            return 1
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
