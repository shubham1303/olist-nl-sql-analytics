"""Every catalog metric executes as analytics_reader and returns its verified value.

Values marked "audit" were computed independently (pandas + SQL Server) in the
earlier olist-delivery-analytics project and reconcile exactly here.
"""

from decimal import Decimal

import pytest

from olist_nlsql.catalog import Metric, load_catalog
from tests.integration.helpers import Conn, scalar

METRICS = load_catalog().metrics
VARIANTS = [(m, v) for m in METRICS for v in m.variants]

EXPECTED: dict[str, Decimal | int] = {
    "order_count": 99_441,
    "delivered_order_count": 96_478,  # audit
    "canceled_order_count": 625,  # audit
    "cancellation_rate": Decimal(625) / Decimal(99_441),
    "revenue": Decimal("13494400.74"),
    "average_order_value": Decimal("13494400.74") / Decimal(98_199),
    "items_sold": 112_101,
    "freight_value": Decimal("2241126.29"),
    "total_order_value": Decimal("15735527.03"),
    "payment_value": Decimal("15738221.95"),
    "customer_count": 96_096,
    "average_review_score": Decimal("4.0864"),  # audit, 4 dp
    "low_rating_rate": Decimal(14_494) / Decimal(98_673),  # audit counts
    "late_delivery_rate": Decimal(6_534) / Decimal(96_470),  # audit counts
    "average_delivery_days": Decimal("12.5582"),  # 4 dp
    "repeat_customer_rate": Decimal(2_801) / Decimal(93_358),  # audit counts
}

ROUNDED_TO_4DP = {"average_review_score", "average_delivery_days"}


def evaluate(conn: Conn, relation: str, expression: str) -> object:
    return scalar(conn, f"SELECT {expression} FROM analytics.{relation}")


def test_every_metric_has_an_expected_value() -> None:
    assert {m.name for m in METRICS} == set(EXPECTED)


@pytest.mark.parametrize("metric", METRICS, ids=lambda m: m.name)
def test_metric_value(reader: Conn, metric: Metric) -> None:
    value = evaluate(reader, metric.relation, metric.expression)
    expected = EXPECTED[metric.name]
    if metric.name in ROUNDED_TO_4DP:
        assert isinstance(value, Decimal)
        assert round(value, 4) == expected
    elif isinstance(expected, Decimal) and metric.unit in {"ratio", "BRL"}:
        assert isinstance(value, Decimal)
        assert abs(value - expected) < Decimal("1e-12"), (value, expected)
    else:
        assert value == expected


@pytest.mark.parametrize("pair", VARIANTS, ids=lambda p: f"{p[0].name}@{p[1].relation}")
def test_variant_equals_primary(reader: Conn, pair: tuple[Metric, object]) -> None:
    metric, variant = pair
    primary = evaluate(reader, metric.relation, metric.expression)
    assert evaluate(reader, variant.relation, variant.expression) == primary  # type: ignore[attr-defined]


@pytest.mark.parametrize("metric", [m for m in METRICS if m.numerator], ids=lambda m: m.name)
def test_ratio_equals_numerator_over_denominator(reader: Conn, metric: Metric) -> None:
    numerator = evaluate(reader, metric.relation, str(metric.numerator))
    denominator = evaluate(reader, metric.relation, str(metric.denominator))
    value = evaluate(reader, metric.relation, metric.expression)
    assert isinstance(value, Decimal)
    assert abs(value - Decimal(str(numerator)) / Decimal(str(denominator))) < Decimal("1e-12")


def test_average_order_value_is_revenue_over_revenue_orders(reader: Conn) -> None:
    revenue, orders = (
        scalar(reader, "SELECT sum(revenue) FROM orders"),
        scalar(reader, "SELECT count(*) FROM orders WHERE is_revenue_order"),
    )
    assert orders == 98_199
    aov = scalar(reader, "SELECT avg(revenue) FROM orders")
    assert abs(aov - revenue / orders) < Decimal("1e-12")


def test_delivered_revenue_matches_audit(reader: Conn) -> None:
    # Audit's "delivered-order item GMV" and freight.
    assert scalar(reader, "SELECT sum(revenue) FROM orders WHERE is_delivered") == Decimal(
        "13221498.11"
    )
    assert scalar(reader, "SELECT sum(freight_total) FROM orders WHERE is_delivered") == Decimal(
        "2198275.64"
    )


def test_sellers_scorecard_uses_catalog_definition(reader: Conn) -> None:
    # sellers.late_delivery_rate must equal the metric computed on order_sellers.
    mismatches = scalar(
        reader,
        """SELECT count(*) FROM sellers s
           JOIN (SELECT seller_id,
                        (count(*) FILTER (WHERE is_late))::numeric / NULLIF(count(is_late), 0) AS rate
                 FROM order_sellers GROUP BY seller_id) x USING (seller_id)
           WHERE s.late_delivery_rate IS DISTINCT FROM x.rate""",
    )
    assert mismatches == 0
    assert scalar(reader, "SELECT count(*) FROM sellers WHERE has_min_20_delivered_orders") == 804
