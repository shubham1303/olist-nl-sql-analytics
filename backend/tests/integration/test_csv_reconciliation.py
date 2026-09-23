"""Recompute key aggregates from the CSV files with plain Python (no SQL) and compare.

This is independent of the loader, the database engine and every view: a
wrong COPY option, type or join would show up as a mismatch here.
"""

import csv
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

import pytest

from tests.integration.helpers import Conn, scalar


def read(csv_dir: Path, name: str) -> list[dict[str, str]]:
    with (csv_dir / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def orders(csv_dir: Path) -> list[dict[str, str]]:
    return read(csv_dir, "olist_orders_dataset.csv")


@pytest.fixture(scope="module")
def items(csv_dir: Path) -> list[dict[str, str]]:
    return read(csv_dir, "olist_order_items_dataset.csv")


def test_revenue(reader: Conn, orders: list[dict[str, str]], items: list[dict[str, str]]) -> None:
    status = {o["order_id"]: o["order_status"] for o in orders}
    revenue = sum(
        (
            Decimal(i["price"])
            for i in items
            if status[i["order_id"]] not in {"canceled", "unavailable"}
        ),
        Decimal(0),
    )
    assert scalar(reader, "SELECT sum(revenue) FROM orders") == revenue


def test_payments(reader: Conn, csv_dir: Path) -> None:
    payments = read(csv_dir, "olist_order_payments_dataset.csv")
    total = sum((Decimal(p["payment_value"]) for p in payments), Decimal(0))
    assert scalar(reader, "SELECT sum(payment_value) FROM order_payments") == total


def test_late_deliveries(reader: Conn, orders: list[dict[str, str]]) -> None:
    comparable = [
        o for o in orders if o["order_status"] == "delivered" and o["order_delivered_customer_date"]
    ]
    late = sum(
        1
        for o in comparable
        if o["order_delivered_customer_date"][:10] > o["order_estimated_delivery_date"][:10]
    )
    assert scalar(reader, "SELECT count(is_late) FROM orders") == len(comparable)
    assert scalar(reader, "SELECT count(*) FILTER (WHERE is_late) FROM orders") == late


def test_repeat_customers(reader: Conn, csv_dir: Path, orders: list[dict[str, str]]) -> None:
    person = {
        c["customer_id"]: c["customer_unique_id"]
        for c in read(csv_dir, "olist_customers_dataset.csv")
    }
    delivered = Counter(
        person[o["customer_id"]] for o in orders if o["order_status"] == "delivered"
    )
    assert scalar(
        reader, "SELECT count(*) FILTER (WHERE delivered_order_count >= 1) FROM customers"
    ) == len(delivered)
    assert scalar(
        reader, "SELECT count(*) FILTER (WHERE is_repeat_customer) FROM customers"
    ) == sum(1 for n in delivered.values() if n >= 2)


def test_revenue_by_seller(
    reader: Conn, orders: list[dict[str, str]], items: list[dict[str, str]]
) -> None:
    status = {o["order_id"]: o["order_status"] for o in orders}
    by_seller: defaultdict[str, Decimal] = defaultdict(Decimal)
    for i in items:
        if status[i["order_id"]] not in {"canceled", "unavailable"}:
            by_seller[i["seller_id"]] += Decimal(i["price"])
    db: dict[str, Decimal] = dict(
        reader.execute("SELECT seller_id, total_revenue FROM sellers WHERE total_revenue > 0")
    )
    assert db == dict(by_seller)


def test_average_latest_review_score(reader: Conn, csv_dir: Path) -> None:
    latest: dict[str, tuple[str, str, str, int]] = {}
    for r in read(csv_dir, "olist_order_reviews_dataset.csv"):
        key = (r["review_answer_timestamp"], r["review_creation_date"], r["review_id"])
        current = latest.get(r["order_id"])
        if current is None or key > current[:3]:
            latest[r["order_id"]] = (*key, int(r["review_score"]))
    mean = Decimal(sum(v[3] for v in latest.values())) / Decimal(len(latest))
    db = scalar(reader, "SELECT avg(review_score) FROM orders")
    assert abs(db - mean) < Decimal("1e-12")
