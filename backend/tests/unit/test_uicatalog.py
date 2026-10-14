import json

from olist_nlsql import uicatalog
from olist_nlsql.catalog import load_catalog
from olist_nlsql.evaluation import benchmark as bm


def test_committed_ui_catalog_is_up_to_date() -> None:
    committed = uicatalog.OUTPUT.read_text(encoding="utf-8")
    assert committed == uicatalog.render(), "run: uv run python -m olist_nlsql.uicatalog"


def test_only_what_the_model_sees_is_exported() -> None:
    data = json.loads(uicatalog.render())
    catalog = load_catalog()
    assert [r["name"] for r in data["relations"]] == [r.name for r in catalog.exposed_relations]
    hidden = {
        (r.name, c.name)
        for r in catalog.relations
        for c in r.columns
        if not (r.exposed and c.exposed)
    }
    exported = {(r["name"], c["name"]) for r in data["relations"] for c in r["columns"]}
    assert not exported & hidden


def _norm(question: str) -> str:
    return " ".join(question.split())


def test_example_questions_come_from_dev_only() -> None:
    data = json.loads(uicatalog.render())
    shown = {q for topic in data["topics"] for q in topic["questions"]}
    assert shown == {_norm(i.question) for i in bm.load("dev").items}
    assert not shown & {_norm(i.question) for i in bm.load("test").items}


def test_topic_follows_the_first_matching_tag() -> None:
    assert uicatalog._topic(("seller", "delivery")) == "Sellers"
    assert uicatalog._topic(("customer", "time_series")) == "Customers"
    assert uicatalog._topic(("aggregation",)) == "Orders and revenue"


def test_complete_months_match_the_dataset_notes() -> None:
    notes = " ".join(load_catalog().dataset_notes)
    first, last = uicatalog.COMPLETE_MONTHS
    assert f"{first}-01 to {last}-31" in " ".join(notes.split())
