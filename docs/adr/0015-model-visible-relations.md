# 0015. The model sees fact views and product attributes; lifetime summaries are hidden

- Status: Accepted
- Date: 2026-09-24

## Context

The analytics schema has eight views ([data-model.md](../data-model.md)). Three of them
are lifetime summaries: `customers`, `sellers`, and the sales columns of `products`.
Their totals and rates are computed over all time, so a question like "top sellers by
revenue in 2018" gives a wrong answer if the model reads `sellers.total_revenue`. No
date filter can reach inside a precomputed total. Every extra relation also widens the
choices the model has to make.

## Decision

The **LLM-visible** relation set (catalog `exposed: true`) is the smallest set that
answers business questions correctly at any time grain:

| Relation | Visible | Why |
|---|---|---|
| `orders` | yes | Order grain: counts, status, delivery, reviews, money |
| `order_items` | yes | Item grain: products, units, category/seller revenue |
| `order_sellers` | yes | Seller outcomes over time |
| `order_categories` | yes | Category outcomes over time |
| `order_payments` | yes | Payment methods and installments |
| `products` | yes, attributes only | Weight, size, photos. `units_sold`, `order_count` and `total_revenue` are hidden columns. |
| `customers` | **no** | Lifetime summary. Use `orders` grouped by `customer_unique_id`. |
| `sellers` | **no** | Lifetime scorecard. Use `order_sellers` grouped by `seller_id`. |

- Hidden views and columns are **not deleted**. They stay documented in the catalog,
  covered by the drift test, and used in database tests.
- The validator rejects them with `UNAPPROVED_RELATION` or `UNAPPROVED_COLUMN`, and the
  message names the alternative.
- Metrics may only reference visible relations:
  - `customer_count` is `COUNT(DISTINCT customer_unique_id)` on `orders`.
  - `repeat_customer_rate` is a catalog query over `orders`.

## Consequences

- Every visible number respects the question's date filter.
- Per-customer and per-seller questions need a GROUP BY, or a grouped subquery, over
  the fact views. The validator accepts those patterns, and the benchmark will show
  whether the model finds them reliably.
- Seller-ranking guidance, such as a minimum of 20 delivered orders, now has to be
  expressed as `HAVING COUNT(*) FILTER (WHERE is_delivered) >= 20` over
  `order_sellers`, not as the hidden `has_min_20_delivered_orders` flag.
- We can revisit this with evidence. If benchmark failures trace to missing summaries,
  a date-aware design, such as parameterised aggregation, would be needed rather than
  simply exposing the lifetime views.
