"""SQL validator: the shared corpus plus targeted behaviour tests (no database needed)."""

import pytest
import sqlglot
from sqlglot import exp

from olist_nlsql.catalog import load_catalog
from olist_nlsql.config import Settings
from olist_nlsql.sqlsafety import ErrorCode, SqlValidator
from olist_nlsql.sqlsafety.functions import function_name
from tests.sql_cases import ACCEPTED, REJECTED, Case


@pytest.fixture(scope="module")
def validator() -> SqlValidator:
    return SqlValidator.from_catalog()


# --------------------------------------------------------------------- corpus


@pytest.mark.parametrize("case", ACCEPTED, ids=lambda c: c.id)
def test_accepted(validator: SqlValidator, case: Case) -> None:
    result = validator.validate(case.sql)
    assert result.ok, [f"{e.code}: {e.message}" for e in result.errors]
    assert result.sql is not None


@pytest.mark.parametrize("case", REJECTED, ids=lambda c: c.id)
def test_rejected(validator: SqlValidator, case: Case) -> None:
    result = validator.validate(case.sql)
    assert not result.ok, f"accepted: {result.sql}"
    assert result.sql is None
    assert result.errors[0].code == case.code, [f"{e.code}: {e.message}" for e in result.errors]
    assert all(e.message for e in result.errors)


def test_corpus_ids_are_unique() -> None:
    ids = [c.id for c in ACCEPTED + REJECTED]
    assert len(ids) == len(set(ids))


def test_corpus_covers_every_error_code() -> None:
    covered = {c.code for c in REJECTED}
    assert covered >= set(ErrorCode) - {ErrorCode.QUERY_TOO_LARGE}  # tested below


def test_every_catalog_metric_passes_the_validator(validator: SqlValidator) -> None:
    catalog = load_catalog()
    for metric in catalog.metrics:
        result = validator.validate(metric.sql())
        assert result.ok, (metric.name, [e.message for e in result.errors])
        for variant in metric.variants:
            sql = f"SELECT {variant.expression} FROM analytics.{variant.relation}"
            assert validator.validate(sql).ok, (metric.name, variant.relation)


# ------------------------------------------------------------------- functions


EXAMPLES = {
    "COUNT": "COUNT(x)", "SUM": "SUM(x)", "AVG": "AVG(x)", "MIN": "MIN(x)", "MAX": "MAX(x)",
    "STDDEV": "STDDEV(x)", "PERCENTILE_CONT": "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY x)",
    "BOOL_OR": "BOOL_OR(x)", "BOOL_AND": "BOOL_AND(x)", "ROUND": "ROUND(x, 2)",
    "COALESCE": "COALESCE(x, 0)", "NULLIF": "NULLIF(x, 0)", "DATE_TRUNC": "DATE_TRUNC('month', x)",
    "EXTRACT": "EXTRACT(YEAR FROM x)", "TO_CHAR": "TO_CHAR(x, 'YYYY')", "ABS": "ABS(x)",
    "FLOOR": "FLOOR(x)", "CEIL": "CEIL(x)", "GREATEST": "GREATEST(x, 1)", "LEAST": "LEAST(x, 1)",
    "POWER": "POWER(x, 2)", "SQRT": "SQRT(x)", "LOWER": "LOWER(x)", "UPPER": "UPPER(x)",
    "INITCAP": "INITCAP(x)", "LENGTH": "LENGTH(x)", "TRIM": "TRIM(x)",
    "SUBSTRING": "SUBSTRING(x, 1, 2)", "CONCAT": "CONCAT(x, 'a')", "REPLACE": "REPLACE(x, 'a', 'b')",
    "SPLIT_PART": "SPLIT_PART(x, '_', 1)", "POSITION": "POSITION('a' IN x)",
    "ROW_NUMBER": "ROW_NUMBER() OVER (ORDER BY x)", "RANK": "RANK() OVER (ORDER BY x)",
    "DENSE_RANK": "DENSE_RANK() OVER (ORDER BY x)", "NTILE": "NTILE(4) OVER (ORDER BY x)",
    "LAG": "LAG(x) OVER (ORDER BY x)", "LEAD": "LEAD(x) OVER (ORDER BY x)",
    "FIRST_VALUE": "FIRST_VALUE(x) OVER (ORDER BY x)", "LAST_VALUE": "LAST_VALUE(x) OVER (ORDER BY x)",
    "PERCENT_RANK": "PERCENT_RANK() OVER (ORDER BY x)", "CUME_DIST": "CUME_DIST() OVER (ORDER BY x)",
}  # fmt: skip


def test_every_allowlisted_function_has_an_example() -> None:
    assert {f.name for f in load_catalog().functions} == set(EXAMPLES)


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_allowlisted_function_is_recognised_by_its_catalog_name(name: str) -> None:
    # Guards against sqlglot renaming a function in a future version.
    tree = sqlglot.parse_one(f"SELECT {EXAMPLES[name]} FROM t", read="postgres")
    names = {function_name(n) for n in tree.walk() if isinstance(n, exp.Func)}
    assert name in names


def test_operator_nodes_never_borrow_a_column_name() -> None:
    tree = sqlglot.parse_one("SELECT sum ~ 'x' FROM t", read="postgres")
    regex = next(n for n in tree.walk() if isinstance(n, exp.RegexpLike))
    assert function_name(regex) == "<RegexpLike>"


# ------------------------------------------------------------ output and limits


def test_output_sql_is_schema_qualified_and_limited(validator: SqlValidator) -> None:
    result = validator.validate("SELECT order_id FROM orders o JOIN order_items i USING (order_id)")
    assert result.ok and result.sql is not None
    assert "analytics.orders" in result.sql and "analytics.order_items" in result.sql
    assert result.sql.rstrip().endswith("LIMIT 1001")
    assert result.limit_applied
    assert result.relations == ("order_items", "orders")


def test_existing_limit_is_kept(validator: SqlValidator) -> None:
    result = validator.validate("SELECT order_id FROM orders LIMIT 25")
    assert result.ok and result.sql is not None
    assert result.sql.rstrip().endswith("LIMIT 25")
    assert not result.limit_applied


def test_limit_is_added_only_at_the_top_level(validator: SqlValidator) -> None:
    sql = "SELECT x.order_id FROM (SELECT order_id FROM orders ORDER BY purchased_at LIMIT 3) x"
    result = validator.validate(sql)
    assert result.ok and result.sql is not None
    assert result.sql.count("LIMIT 3") == 1 and result.sql.rstrip().endswith("LIMIT 1001")


def test_union_gets_one_limit(validator: SqlValidator) -> None:
    result = validator.validate("SELECT 1 AS x UNION ALL SELECT 2")
    assert result.ok and result.sql is not None
    assert result.sql.count("LIMIT") == 1


def test_configured_row_limit_is_used() -> None:
    validator = SqlValidator.from_catalog(settings=Settings(max_result_rows=50))
    assert validator.validate("SELECT order_id FROM orders LIMIT 50").ok
    assert validator.validate("SELECT order_id FROM orders LIMIT 51").codes == (
        ErrorCode.RESULT_LIMIT_EXCEEDED,
    )
    sql = validator.validate("SELECT order_id FROM orders").sql
    assert sql is not None and sql.rstrip().endswith("LIMIT 51")


def test_sql_length_limit() -> None:
    validator = SqlValidator.from_catalog(settings=Settings(max_sql_chars=100))
    result = validator.validate("SELECT order_id FROM orders WHERE " + " OR ".join(["true"] * 30))
    assert result.codes == (ErrorCode.QUERY_TOO_LARGE,)


def test_join_count_limit() -> None:
    validator = SqlValidator.from_catalog(settings=Settings(max_joins=1))
    sql = (
        "SELECT COUNT(*) FROM order_items i JOIN orders o ON o.order_id = i.order_id "
        "JOIN products p ON p.product_id = i.product_id"
    )
    assert validator.validate(sql).codes == (ErrorCode.QUERY_TOO_LARGE,)


def test_comments_cannot_smuggle_statements(validator: SqlValidator) -> None:
    result = validator.validate("SELECT order_id FROM orders -- ; DROP TABLE orders")
    assert result.ok and result.sql is not None
    assert "DROP" not in result.sql


def test_executed_sql_is_regenerated_without_comments(validator: SqlValidator) -> None:
    result = validator.validate("select   order_id\nfrom orders /* hi */ where order_id = ';'")
    assert result.ok and result.sql is not None
    assert "hi" not in result.sql and "/*" not in result.sql
    assert "';'" in result.sql  # string literal content is preserved


# ----------------------------------------------------------- result details


def test_parse_error_has_a_location(validator: SqlValidator) -> None:
    error = validator.validate("SELECT order_id\nFROM orders\nWHERE AND").errors[0]
    assert error.code == ErrorCode.PARSE_ERROR
    assert error.location is not None and error.location.line == 3


def test_function_error_names_the_function_and_location(validator: SqlValidator) -> None:
    error = validator.validate("SELECT\n  pg_sleep(5)").errors[0]
    assert error.details["function"] == "PG_SLEEP"
    assert error.location is not None and error.location.line == 2


def test_all_unapproved_functions_are_reported(validator: SqlValidator) -> None:
    result = validator.validate("SELECT pg_sleep(1), version(), md5(order_id) FROM orders")
    assert {e.details["function"] for e in result.errors} == {"PG_SLEEP", "VERSION", "MD5"}


def test_hidden_relation_message_suggests_the_alternative(validator: SqlValidator) -> None:
    message = validator.validate("SELECT COUNT(*) FROM customers").errors[0].message
    assert "orders" in message and "customer_unique_id" in message


def test_unknown_column_message_suggests_close_matches(validator: SqlValidator) -> None:
    message = validator.validate("SELECT revenu FROM orders").errors[0].message
    assert "revenue" in message


def test_wrong_join_message_names_the_approved_join(validator: SqlValidator) -> None:
    sql = "SELECT COUNT(*) FROM orders o JOIN order_items i ON o.order_id = i.product_id"
    message = validator.validate(sql).errors[0].message
    assert "orders.order_id = order_items.order_id" in message


def test_fanout_message_explains_the_fix(validator: SqlValidator) -> None:
    sql = "SELECT SUM(o.revenue) FROM orders o JOIN order_items i ON o.order_id = i.order_id"
    error = validator.validate(sql).errors[0]
    assert error.details == {
        "aggregate": "SUM(o.revenue)",
        "column": "o.revenue",
        "relation": "orders",
    }
    assert "order_items" in error.message and "subquery" in error.message


def test_row_level_fanout_is_a_warning_not_an_error(validator: SqlValidator) -> None:
    sql = "SELECT o.order_id, o.revenue, i.price FROM orders o JOIN order_items i ON o.order_id = i.order_id"
    result = validator.validate(sql)
    assert result.ok
    assert [w.code for w in result.warnings] == [ErrorCode.FANOUT_RISK]
    assert "revenue" in result.warnings[0].message


def test_unexpected_internal_errors_fail_closed(
    validator: SqlValidator, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_: object) -> None:
        raise RuntimeError("bug")

    monkeypatch.setattr(validator, "_check_functions", boom)
    result = validator.validate("SELECT order_id FROM orders")
    assert not result.ok and result.codes == (ErrorCode.UNSUPPORTED_CONSTRUCT,)
