-- Curated analytics layer (ADR 0005). The only schema analytics_reader can read.
--
-- Grain rule: items, payments and reviews are each reduced to the target grain
-- BEFORE they are joined, so no view multiplies another fact. Every view states
-- its grain; tests assert the grain key is unique and that money totals agree
-- across views.
--
-- Revenue (canonical): sum of item price, excluding freight, for orders whose
-- status is not 'canceled' or 'unavailable' and that have at least one item.
-- The `revenue` column is NULL outside that population, so SUM(revenue) and
-- AVG(revenue) are correct without extra filters. See docs/metrics.md.
--
-- Dependency order: analytics_internal.product_category_map -> orders ->
-- products -> order_items, order_sellers, order_categories, order_payments ->
-- customers, sellers.

CREATE SCHEMA analytics_internal;
COMMENT ON SCHEMA analytics_internal IS
    'Building blocks for analytics views. Not visible to analytics_reader.';

CREATE SCHEMA analytics;
COMMENT ON SCHEMA analytics IS
    'Curated business views over the Olist dataset. The only schema the NL-to-SQL model sees.';

-- ---------------------------------------------------------------------------
-- Category mapping. Grain: one row per Portuguese category name in products.
-- Olist's translation table is used as-is, except for three project entries:
--   * casa_conforto: corrects the source typo 'home_confort' -> 'home_comfort'
--     (its sibling is 'home_comfort_2').
--   * pc_gamer, portateis_cozinha_e_preparadores_de_alimentos: missing from the
--     source translation table (13 products). Named to match existing Olist
--     conventions (cf. portateis_casa_forno_e_cafe -> small_appliances_home_oven_and_coffee).
-- Products with no category map to 'uncategorized' (handled in the views).
-- ---------------------------------------------------------------------------
CREATE VIEW analytics_internal.product_category_map AS
WITH project_translation (product_category_name, product_category_name_english) AS (
    VALUES
        ('casa_conforto', 'home_comfort'),
        ('pc_gamer', 'pc_gamer'),
        ('portateis_cozinha_e_preparadores_de_alimentos',
         'small_appliances_kitchen_and_food_preparers')
),
categories AS (
    SELECT DISTINCT product_category_name
    FROM raw.products
    WHERE product_category_name IS NOT NULL
)
SELECT
    c.product_category_name,
    COALESCE(pt.product_category_name_english,
             ot.product_category_name_english,
             c.product_category_name) AS product_category,
    CASE
        WHEN pt.product_category_name IS NOT NULL THEN 'project'
        WHEN ot.product_category_name IS NOT NULL THEN 'olist'
        ELSE 'untranslated'
    END AS translation_source
FROM categories AS c
LEFT JOIN project_translation AS pt USING (product_category_name)
LEFT JOIN raw.product_category_name_translation AS ot USING (product_category_name);

-- ---------------------------------------------------------------------------
-- analytics.orders. Grain: one row per order (order_id).
-- ---------------------------------------------------------------------------
CREATE VIEW analytics.orders AS
WITH items AS (
    SELECT
        order_id,
        count(*)::integer                   AS item_count,
        count(DISTINCT product_id)::integer AS product_count,
        count(DISTINCT seller_id)::integer  AS seller_count,
        sum(price)                          AS item_price_total,
        sum(freight_value)                  AS freight_total
    FROM raw.order_items
    GROUP BY order_id
),
payments AS (
    SELECT
        order_id,
        count(*)::integer         AS payment_count,
        sum(payment_value)        AS payment_total,
        max(payment_installments) AS max_installments,
        -- Deterministic: the method carrying the most value, then the first used.
        (array_agg(payment_type ORDER BY payment_value DESC, payment_sequential))[1]
            AS primary_payment_type
    FROM raw.order_payments
    GROUP BY order_id
),
review_counts AS (
    SELECT order_id, count(*)::integer AS review_count
    FROM raw.order_reviews
    GROUP BY order_id
),
latest_review AS (
    -- One review per order: the most recently answered, ties broken deterministically.
    SELECT DISTINCT ON (order_id)
        order_id,
        review_score,
        review_creation_date,
        review_answer_timestamp,
        NULLIF(btrim(review_comment_message), '') IS NOT NULL AS has_comment
    FROM raw.order_reviews
    ORDER BY order_id, review_answer_timestamp DESC, review_creation_date DESC, review_id DESC
),
base AS (
    SELECT
        o.*,
        c.customer_unique_id,
        c.customer_city,
        c.customer_state,
        o.order_status = 'delivered' AS is_delivered,
        o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL
            AS is_delivery_comparable
    FROM raw.orders AS o
    JOIN raw.customers AS c USING (customer_id)
)
SELECT
    b.order_id,
    b.customer_unique_id,
    b.customer_city,
    b.customer_state,
    b.order_status,
    b.is_delivered,
    b.order_status = 'canceled' AS is_canceled,
    (b.order_status NOT IN ('canceled', 'unavailable') AND i.order_id IS NOT NULL)
        AS is_revenue_order,
    b.order_purchase_timestamp                                AS purchased_at,
    b.order_purchase_timestamp::date                          AS purchase_date,
    date_trunc('month', b.order_purchase_timestamp)::date     AS purchase_month,
    b.order_approved_at                                       AS approved_at,
    b.order_delivered_carrier_date                            AS delivered_to_carrier_at,
    b.order_delivered_customer_date                           AS delivered_to_customer_at,
    b.order_estimated_delivery_date::date                     AS estimated_delivery_date,
    CASE
        WHEN NOT b.is_delivered THEN 'not_delivered'
        WHEN NOT b.is_delivery_comparable THEN 'missing_delivery_date'
        WHEN b.order_delivered_customer_date::date < b.order_estimated_delivery_date::date
            THEN 'early'
        WHEN b.order_delivered_customer_date::date = b.order_estimated_delivery_date::date
            THEN 'on_time'
        ELSE 'late'
    END AS delivery_status,
    CASE WHEN b.is_delivery_comparable THEN
        b.order_delivered_customer_date::date > b.order_estimated_delivery_date::date
    END AS is_late,
    CASE WHEN b.is_delivery_comparable THEN
        b.order_delivered_customer_date::date - b.order_estimated_delivery_date::date
    END AS delivery_delay_days,
    CASE WHEN b.is_delivery_comparable THEN
        round(extract(epoch FROM b.order_delivered_customer_date - b.order_purchase_timestamp)
              / 86400, 2)
    END AS delivery_days,
    COALESCE(i.item_count, 0)                         AS item_count,
    COALESCE(i.product_count, 0)                      AS product_count,
    COALESCE(i.seller_count, 0)                       AS seller_count,
    COALESCE(i.item_price_total, 0)                   AS item_price_total,
    COALESCE(i.freight_total, 0)                      AS freight_total,
    COALESCE(i.item_price_total + i.freight_total, 0) AS order_total_value,
    CASE WHEN b.order_status NOT IN ('canceled', 'unavailable') THEN i.item_price_total END
        AS revenue,
    COALESCE(p.payment_count, 0) AS payment_count,
    p.payment_total,
    p.max_installments,
    p.primary_payment_type,
    COALESCE(rc.review_count, 0)   AS review_count,
    lr.order_id IS NOT NULL        AS has_review,
    lr.review_score,
    COALESCE(lr.has_comment, false) AS review_has_comment,
    lr.review_creation_date::date  AS review_created_date,
    lr.review_answer_timestamp     AS review_answered_at
FROM base AS b
LEFT JOIN items AS i USING (order_id)
LEFT JOIN payments AS p USING (order_id)
LEFT JOIN review_counts AS rc USING (order_id)
LEFT JOIN latest_review AS lr USING (order_id);

-- ---------------------------------------------------------------------------
-- analytics.products. Grain: one row per product (product_id).
-- Lifetime sales totals use the revenue population.
-- ---------------------------------------------------------------------------
CREATE VIEW analytics.products AS
WITH sales AS (
    SELECT
        i.product_id,
        count(*)::integer                   AS units_sold,
        count(DISTINCT i.order_id)::integer AS order_count,
        sum(i.price)                        AS total_revenue
    FROM raw.order_items AS i
    JOIN analytics.orders AS o USING (order_id)
    WHERE o.is_revenue_order
    GROUP BY i.product_id
)
SELECT
    p.product_id,
    COALESCE(m.product_category, 'uncategorized')      AS product_category,
    COALESCE(m.translation_source, 'uncategorized')    AS category_translation_source,
    p.product_name_lenght        AS product_name_length,
    p.product_description_lenght AS product_description_length,
    p.product_photos_qty         AS photo_count,
    p.product_weight_g           AS weight_g,
    p.product_length_cm          AS length_cm,
    p.product_height_cm          AS height_cm,
    p.product_width_cm           AS width_cm,
    COALESCE(s.units_sold, 0)    AS units_sold,
    COALESCE(s.order_count, 0)   AS order_count,
    COALESCE(s.total_revenue, 0) AS total_revenue
FROM raw.products AS p
LEFT JOIN analytics_internal.product_category_map AS m USING (product_category_name)
LEFT JOIN sales AS s USING (product_id);

-- ---------------------------------------------------------------------------
-- analytics.order_items. Grain: one row per order item (order_id, order_item_id).
-- Carries order context for filtering, but NOT order outcomes (delivery,
-- review): those would be weighted by item count. Use order_categories or
-- order_sellers for outcomes by category or seller.
-- ---------------------------------------------------------------------------
CREATE VIEW analytics.order_items AS
SELECT
    i.order_id,
    i.order_item_id,
    i.product_id,
    COALESCE(m.product_category, 'uncategorized') AS product_category,
    i.seller_id,
    s.seller_city,
    s.seller_state,
    i.shipping_limit_date                 AS shipping_limit_at,
    i.price,
    i.freight_value,
    i.price + i.freight_value             AS item_total_value,
    CASE WHEN o.is_revenue_order THEN i.price END AS revenue,
    o.order_status,
    o.is_delivered,
    o.is_canceled,
    o.is_revenue_order,
    o.purchased_at,
    o.purchase_date,
    o.purchase_month,
    o.customer_unique_id,
    o.customer_state
FROM raw.order_items AS i
JOIN analytics.orders AS o USING (order_id)
JOIN raw.products AS p USING (product_id)
LEFT JOIN analytics_internal.product_category_map AS m USING (product_category_name)
JOIN raw.sellers AS s USING (seller_id);

-- ---------------------------------------------------------------------------
-- analytics.order_sellers. Grain: one row per (order_id, seller_id).
-- Money is limited to that seller's items; order outcomes (delivery, review)
-- are attributed in full to every seller on the order.
-- ---------------------------------------------------------------------------
CREATE VIEW analytics.order_sellers AS
WITH seller_items AS (
    SELECT
        order_id,
        seller_id,
        count(*)::integer  AS item_count,
        sum(price)         AS item_price_total,
        sum(freight_value) AS freight_total
    FROM raw.order_items
    GROUP BY order_id, seller_id
)
SELECT
    si.order_id,
    si.seller_id,
    s.seller_city,
    s.seller_state,
    si.item_count,
    si.item_price_total,
    si.freight_total,
    CASE WHEN o.is_revenue_order THEN si.item_price_total END AS revenue,
    o.seller_count AS order_seller_count,
    o.order_status,
    o.is_delivered,
    o.is_canceled,
    o.is_revenue_order,
    o.purchased_at,
    o.purchase_date,
    o.purchase_month,
    o.customer_unique_id,
    o.customer_state,
    o.delivery_status,
    o.is_late,
    o.delivery_days,
    o.delivery_delay_days,
    o.has_review,
    o.review_score
FROM seller_items AS si
JOIN raw.sellers AS s USING (seller_id)
JOIN analytics.orders AS o USING (order_id);

-- ---------------------------------------------------------------------------
-- analytics.order_categories. Grain: one row per (order_id, product_category).
-- Money is limited to that category's items; order outcomes are attributed in
-- full to every category on the order.
-- ---------------------------------------------------------------------------
CREATE VIEW analytics.order_categories AS
WITH category_items AS (
    SELECT
        i.order_id,
        COALESCE(m.product_category, 'uncategorized') AS product_category,
        count(*)::integer    AS item_count,
        sum(i.price)         AS item_price_total,
        sum(i.freight_value) AS freight_total
    FROM raw.order_items AS i
    JOIN raw.products AS p USING (product_id)
    LEFT JOIN analytics_internal.product_category_map AS m USING (product_category_name)
    GROUP BY 1, 2
)
SELECT
    ci.order_id,
    ci.product_category,
    ci.item_count,
    ci.item_price_total,
    ci.freight_total,
    CASE WHEN o.is_revenue_order THEN ci.item_price_total END AS revenue,
    (count(*) OVER (PARTITION BY ci.order_id))::integer AS order_category_count,
    o.order_status,
    o.is_delivered,
    o.is_canceled,
    o.is_revenue_order,
    o.purchased_at,
    o.purchase_date,
    o.purchase_month,
    o.customer_unique_id,
    o.customer_state,
    o.delivery_status,
    o.is_late,
    o.delivery_days,
    o.delivery_delay_days,
    o.has_review,
    o.review_score
FROM category_items AS ci
JOIN analytics.orders AS o USING (order_id);

-- ---------------------------------------------------------------------------
-- analytics.order_payments. Grain: one row per payment record
-- (order_id, payment_sequential).
-- ---------------------------------------------------------------------------
CREATE VIEW analytics.order_payments AS
SELECT
    p.order_id,
    p.payment_sequential,
    p.payment_type,
    p.payment_installments,
    p.payment_value,
    o.order_status,
    o.is_revenue_order,
    o.purchased_at,
    o.purchase_date,
    o.purchase_month,
    o.customer_unique_id,
    o.customer_state
FROM raw.order_payments AS p
JOIN analytics.orders AS o USING (order_id);

-- ---------------------------------------------------------------------------
-- analytics.customers. Grain: one row per real customer (customer_unique_id).
-- Location is taken from the customer's most recent order.
-- ---------------------------------------------------------------------------
CREATE VIEW analytics.customers AS
WITH per_customer AS (
    SELECT
        customer_unique_id,
        count(*)::integer                                   AS order_count,
        (count(*) FILTER (WHERE is_delivered))::integer     AS delivered_order_count,
        (count(*) FILTER (WHERE is_revenue_order))::integer AS revenue_order_count,
        COALESCE(sum(revenue), 0)                           AS total_revenue,
        min(purchased_at)                                   AS first_order_at,
        max(purchased_at)                                   AS last_order_at
    FROM analytics.orders
    GROUP BY customer_unique_id
),
latest_location AS (
    SELECT DISTINCT ON (customer_unique_id)
        customer_unique_id, customer_city, customer_state
    FROM analytics.orders
    ORDER BY customer_unique_id, purchased_at DESC, order_id DESC
)
SELECT
    pc.customer_unique_id,
    ll.customer_city,
    ll.customer_state,
    pc.order_count,
    pc.delivered_order_count,
    pc.revenue_order_count,
    pc.total_revenue,
    pc.first_order_at,
    pc.last_order_at,
    pc.delivered_order_count >= 2 AS is_repeat_customer
FROM per_customer AS pc
JOIN latest_location AS ll USING (customer_unique_id);

-- ---------------------------------------------------------------------------
-- analytics.sellers. Grain: one row per seller (seller_id).
-- Lifetime scorecard built from order_sellers, using the same metric
-- definitions as the catalog.
-- ---------------------------------------------------------------------------
CREATE VIEW analytics.sellers AS
SELECT
    s.seller_id,
    s.seller_city,
    s.seller_state,
    count(os.order_id)::integer                                   AS order_count,
    (count(*) FILTER (WHERE os.is_delivered))::integer            AS delivered_order_count,
    COALESCE(sum(os.item_count) FILTER (WHERE os.is_revenue_order), 0)::integer
        AS units_sold,
    COALESCE(sum(os.revenue), 0)                                  AS total_revenue,
    count(os.is_late)::integer                                    AS comparable_delivery_count,
    (count(*) FILTER (WHERE os.is_late))::integer                 AS late_delivery_count,
    (count(*) FILTER (WHERE os.is_late))::numeric / NULLIF(count(os.is_late), 0)
        AS late_delivery_rate,
    avg(os.delivery_days)                                         AS average_delivery_days,
    count(os.review_score)::integer                               AS reviewed_order_count,
    avg(os.review_score)                                          AS average_review_score,
    min(os.purchased_at)                                          AS first_order_at,
    max(os.purchased_at)                                          AS last_order_at,
    (count(*) FILTER (WHERE os.is_delivered)) >= 20               AS has_min_20_delivered_orders
FROM raw.sellers AS s
LEFT JOIN analytics.order_sellers AS os USING (seller_id)
GROUP BY s.seller_id, s.seller_city, s.seller_state;
