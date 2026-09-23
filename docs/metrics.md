# Metrics

Metric definitions live in [catalog.yaml](../backend/src/olist_nlsql/catalog/catalog.yaml),
which is the source of truth. This page explains them.
[test_metrics.py](../backend/tests/integration/test_metrics.py) runs every metric
expression as `analytics_reader` and checks its value. Values marked † were computed
independently in an earlier project (pandas + SQL Server) and reconcile exactly.

## Four kinds of money

Olist records money in four ways. The application treats them as separate metrics,
and only one of them is "revenue": **merchandise revenue**
([ADR 0010](adr/0010-canonical-revenue.md)).

| Concept | Where | What it is | Total (revenue orders) |
|---|---|---|---:|
| **Item price** → **merchandise revenue** | `order_items.price` | Price of the product, excluding shipping | R$13,494,400.74 |
| Freight value | `order_items.freight_value` | Shipping charged per item | R$2,241,126.29 |
| Total order value | `orders.order_total_value` | Item price + freight | R$15,735,527.03 |
| Payment value | `order_payments.payment_value` | What was paid, including installment interest and vouchers | R$15,738,221.95 |

### Why revenue is merchandise revenue (item price)

1. **It attributes exactly.** Price belongs to one item, so it splits cleanly by
   product, category and seller. Revenue by category sums to total revenue, and so do
   revenue by seller and by customer. Tests assert this across all seven views.
   Payments can't be split by item, and freight is shipping, not sales.
2. **It matches the usual meaning of GMV** in marketplace reporting and in the earlier
   project's KPI dictionary.
3. **Payment differences are financing, not sales.** Payments exceed price plus freight
   only through installment interest (264 orders) and fall short through vouchers
   (39 orders).

If a question asks for sales "including shipping", use `total_order_value`, and state
that choice in the answer.

### The revenue population

An order is a **revenue order** (`is_revenue_order`) when its status is **not**
`canceled` or `unavailable` **and** it has at least one item. That's 98,199 of 99,441
orders.

- **Included:** delivered, shipped, invoiced, processing and approved orders. Sales are
  booked at purchase, not at delivery.
- **Excluded:** 625 canceled and 609 unavailable orders, plus 8 orders with no items.
- The `revenue` column is NULL outside this population. That makes `SUM(revenue)` and
  `AVG(revenue)` correct without a filter. Freight, total order value and payment value
  filter on `is_revenue_order` explicitly, so every money metric uses the same
  population.
- For delivered-only revenue, add `WHERE is_delivered` (R$13,221,498.11 †).

## Metric reference

| Metric | Definition | SQL (relation) | Value |
|---|---|---|---:|
| `order_count` | Orders, all statuses | `COUNT(*)` (orders) | 99,441 |
| `delivered_order_count` | Status delivered | `COUNT(*) FILTER (WHERE is_delivered)` | 96,478 † |
| `canceled_order_count` | Status canceled (not `unavailable`) | `COUNT(*) FILTER (WHERE is_canceled)` | 625 † |
| `cancellation_rate` | Canceled ÷ all orders | numerator ÷ `COUNT(*)` | 0.63% |
| `revenue` | Merchandise revenue: item price, revenue orders | `SUM(revenue)` | R$13,494,400.74 |
| `average_order_value` | Revenue ÷ revenue orders | `AVG(revenue)` | R$137.42 |
| `items_sold` | Units in revenue orders | `COUNT(revenue)` (order_items) | 112,101 |
| `freight_value` | Freight, revenue orders | `SUM(freight_total) FILTER (WHERE is_revenue_order)` | R$2,241,126.29 |
| `total_order_value` | Price + freight, revenue orders | `SUM(order_total_value) FILTER (…)` | R$15,735,527.03 |
| `payment_value` | Payments, revenue orders | `SUM(payment_total) FILTER (…)` | R$15,738,221.95 |
| `customer_count` | Distinct real customers | `COUNT(*)` (customers) | 96,096 |
| `average_review_score` | Mean latest-review score per reviewed order | `AVG(review_score)` | 4.0864 † |
| `low_rating_rate` | Latest review 1–2 ÷ reviewed orders | 14,494 ÷ 98,673 † | 14.69% |
| `late_delivery_rate` | Late ÷ delivered orders with a delivery date | 6,534 ÷ 96,470 † | 6.77% |
| `average_delivery_days` | Mean purchase → delivery days | `AVG(delivery_days)` | 12.56 days |
| `repeat_customer_rate` | Customers with ≥ 2 delivered orders ÷ those with ≥ 1 | 2,801 ÷ 93,358 † | 3.00% |

The catalog also gives each metric its exclusions, caveats and aliases, and for ratios
the numerator and denominator. Metrics that make sense at other grains list
**variants**, such as `revenue` on `order_categories` or `items_sold` on `orders`. The
tests check that each variant returns exactly the primary value.

## Definitions worth knowing

- **Late** compares calendar dates. Delivery on the estimated day is on time. The
  denominator excludes undelivered orders and the 8 delivered orders with no delivery
  date.
- **Average review score is order-weighted.** Each reviewed order contributes its
  latest review once ([ADR 0011](adr/0011-review-and-outcome-attribution.md)). A review-row average would weight the 547 multi-review orders
  more heavily.
- **Repeat customers need two delivered orders.** Two orders where one was canceled
  don't count. Using per-order `customer_id` would make the rate 0%.
- **Canceled excludes `unavailable`.** "Unavailable" means the product couldn't be
  supplied. Both statuses are excluded from revenue.
- **Seller and category rates** computed on the bridge views attribute each order's
  outcome to every seller or category on it ([ADR 0011](adr/0011-review-and-outcome-attribution.md)).
  Those grouped outcome counts **aren't additive**: summed across sellers or categories
  they exceed the number of unique orders, so overall counts and rates come from `orders`. The
  `sellers` scorecard uses those definitions, and a test checks that its
  `late_delivery_rate` matches.
- **Small samples:** `sellers.has_min_20_delivered_orders` marks the 804 sellers with
  enough history for a fair ranking.

## Terms the catalog does not define

Terms like "best sellers", "top customers" or "growth" have no catalog definition.
Under [ADR 0005](adr/0005-curated-analytics-schema-and-catalog.md) the system states
its assumption and answers, for example "Assuming 'best sellers' means sellers with
the highest total revenue…". Catalog terms such as revenue, late or repeat customer
always use the definitions above, never a model guess.
