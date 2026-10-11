"""The committed benchmark against the real database.

Every reference query must still produce its stored snapshot (so a view change that
moves an answer is caught), and the harness must score 100% when the "model" answers
with the reference SQL.
"""

from decimal import Decimal

import pytest

from olist_nlsql.config import Settings
from olist_nlsql.db.postgres import PostgresExecutor
from olist_nlsql.evaluation import benchmark as bm
from olist_nlsql.evaluation import runner
from olist_nlsql.evaluation.__main__ import snapshot_item
from olist_nlsql.evaluation.compare import CompareOptions, compare
from olist_nlsql.sqlsafety import SqlValidator

ITEMS = [i for b in bm.load_all().values() for i in b.items]


@pytest.mark.parametrize("item", ITEMS, ids=[i.id for i in ITEMS])
def test_reference_sql_reproduces_its_snapshot(
    item: bm.BenchmarkItem, executor: PostgresExecutor
) -> None:
    assert item.reference_result is not None
    fresh = snapshot_item(item, SqlValidator.from_catalog(), executor)
    assert fresh.reference_result is not None
    exact = CompareOptions(
        order_matters=item.compare.order_matters, abs_tol=Decimal(0), rel_tol=Decimal(0)
    )
    result = compare(item.reference_result, fresh.reference_result, exact)
    assert result.match, result.reason


@pytest.mark.parametrize("split", bm.SPLITS)
def test_reference_model_scores_every_item(split: bm.Split, executor: PostgresExecutor) -> None:
    record = runner.run(
        bm.load(split),
        model_for=runner.reference_model,
        executor=executor,
        settings=Settings(),
        checkpoint="harness self-test" if split == "test" else None,
    )
    wrong = [(o.id, o.category, o.category_note) for o in record.items if not o.correct]
    assert wrong == []
