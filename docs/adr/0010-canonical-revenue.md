# 0010. Canonical revenue is merchandise revenue

- Status: Accepted
- Date: 2026-09-23

## Context

Olist records money four ways: item price, freight per item, their sum, and payment
records. Payments include installment interest and vouchers. Business users say
"revenue" or "sales" without saying which of these they mean. If the model picked one
each time, the same question could get different answers.

## Decision

**Revenue**, the `revenue` metric and column, means **merchandise revenue**:
- It's the sum of item price, excluding freight.
- It covers only **eligible orders**: status is neither `canceled` nor `unavailable`,
  and the order has at least one item. `is_revenue_order` flags these orders.

How the `revenue` column behaves:
- It is NULL outside the eligible population, so `SUM(revenue)` and `AVG(revenue)` are
  correct without an extra filter.
- It appears at every fact grain: `orders`, `order_items`, `order_sellers` and
  `order_categories`.

The other three money measures stay **separate metrics**. They use the same
eligible-order population and are never substituted for revenue:

| Metric | Meaning |
|---|---|
| `freight_value` | Freight charged on items |
| `total_order_value` | Item price + freight |
| `payment_value` | Sum of payment records |

Technical documentation uses the term "merchandise revenue". The metric keeps the
short name `revenue` and lists "merchandise revenue" as an alias.

## Consequences

- Revenue adds up the same way at every grain: by product, category, seller or
  customer, it sums to the total, R$13,494,400.74. Tests assert this across all seven
  views that carry it, and against an independent recomputation from the CSVs.
- Revenue includes eligible orders that haven't been delivered yet (shipped, invoiced,
  processing, approved). Delivered-only revenue needs `WHERE is_delivered`.
- Revenue can't reconcile to cash received. That's `payment_value`, which differs by
  interest and vouchers on 303 orders.
- `SUM(revenue) / COUNT(*)` understates average order value. `AVG(revenue)` is the
  correct form, and the evaluation will show whether the model follows the catalog.
