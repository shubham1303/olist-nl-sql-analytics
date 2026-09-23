# 0011. Latest review per order; full outcome attribution in seller/category views

- Status: Accepted
- Date: 2026-09-23

## Context

- 547 orders have 2–3 review records, and in 202 of them the scores disagree.
- 1,278 orders have items from more than one seller, and many orders span several
  categories.
- Delivery and review outcomes belong to the whole order, not to an item, a seller or a
  category.

## Decision

1. **One review per order.** Where an order has several review records, the order's
   review is the **most recently answered** one. Ties are broken by creation date, then
   `review_id`, so the choice is deterministic. `review_count` still exposes how many
   records existed.
2. **Full attribution in bridge views.** In `order_sellers` and `order_categories`:
   - Each order's delivery and review outcome (`delivery_status`, `is_late`,
     `delivery_days`, `delivery_delay_days`, `has_review`, `review_score`) is
     attributed **in full** to every participating seller or category.
   - Money columns cover only that seller's or category's own items.
3. **Grouped outcome counts aren't additive.** Late orders counted per seller or per
   category, summed across all sellers or categories, exceed the number of unique late
   orders. This is documented in the catalog caveats and in
   [data-model.md](../data-model.md). Overall outcome counts and rates come from
   `orders`.

## Consequences

- "Late delivery rate by seller" and "average review by category" have one defined
  answer, and each order counts once per seller or category.
- Summing a per-seller outcome back up to a total is wrong. The model has to query
  `orders` for totals, and the catalog says so explicitly.
- The average review score is order-weighted. A review-row average would weight the
  547 multi-review orders more heavily, and isn't offered.
- `order_seller_count` and `order_category_count` let analyses spot or exclude
  multi-seller and multi-category orders.
