"""Shared SQL corpus for validator tests.

ACCEPTED queries must validate AND execute against the local database
(tests/integration/test_validator_execution.py). REJECTED queries must fail with the
given error code. Several rejected queries are syntactically valid SQL that returns a
wrong business answer; test_validator_execution.py proves the inflation numerically.
"""

from dataclasses import dataclass

from olist_nlsql.sqlsafety import ErrorCode as E


@dataclass(frozen=True)
class Case:
    id: str
    sql: str
    code: E | None = None  # expected error code; None means accepted


ACCEPTED: list[Case] = [
    # --- basics
    Case("simple_select", "SELECT order_id, order_status FROM orders"),
    Case("count", "SELECT COUNT(*) AS orders FROM orders"),
    Case(
        "group_by",
        "SELECT customer_state, COUNT(*) AS orders FROM orders "
        "GROUP BY customer_state ORDER BY orders DESC LIMIT 10",
    ),
    Case(
        "time_filter",
        "SELECT purchase_month, SUM(revenue) AS revenue FROM orders "
        "WHERE purchase_date >= DATE '2017-01-01' AND purchase_date < DATE '2018-09-01' "
        "GROUP BY purchase_month ORDER BY purchase_month",
    ),
    Case(
        "extract_year",
        "SELECT EXTRACT(YEAR FROM purchased_at) AS year, COUNT(*) FROM orders GROUP BY 1",
    ),
    Case(
        "to_char_month",
        "SELECT TO_CHAR(purchase_month, 'YYYY-MM') AS month, COUNT(*) FROM orders "
        "GROUP BY 1 ORDER BY 1",
    ),
    Case(
        "predicates",
        "SELECT COUNT(*) FROM orders WHERE customer_state IN ('SP', 'RJ') "
        "AND purchase_date BETWEEN '2017-01-01' AND '2017-12-31' "
        "AND customer_city LIKE 'sao%' AND review_score IS NOT NULL",
    ),
    Case(
        "interval_arithmetic",
        "SELECT COUNT(*) FROM orders "
        "WHERE delivered_to_customer_at > estimated_delivery_date + INTERVAL '7 days'",
    ),
    Case(
        "case_cast_coalesce",
        "SELECT CASE WHEN delivery_days > 20 THEN 'slow' ELSE 'fast' END AS speed, COUNT(*), "
        "ROUND(AVG(COALESCE(review_score, 0))::numeric, 2) AS avg_score "
        "FROM orders WHERE is_delivered GROUP BY 1",
    ),
    Case(
        "median",
        "SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY delivery_days) AS median_days "
        "FROM orders",
    ),
    Case(
        "string_functions",
        "SELECT INITCAP(REPLACE(product_category, '_', ' ')) AS category, COUNT(*) "
        "FROM order_items GROUP BY 1",
    ),
    Case("select_distinct", "SELECT DISTINCT payment_type FROM order_payments"),
    Case(
        "payments_by_type",
        "SELECT payment_type, COUNT(DISTINCT order_id) AS orders, SUM(payment_value) AS paid "
        "FROM order_payments GROUP BY payment_type",
    ),
    Case(
        "limit_offset",
        "SELECT order_id, revenue FROM orders ORDER BY revenue DESC NULLS LAST LIMIT 10 OFFSET 5",
    ),
    # --- formatting variants
    Case(
        "comments_and_casing",
        "-- top states\nselect CUSTOMER_STATE, count(*) /* orders */ from ORDERS "
        "group by customer_state",
    ),
    Case(
        "quoted_identifiers",
        'SELECT "order_status", COUNT(*) FROM "analytics"."orders" GROUP BY "order_status"',
    ),
    Case("parenthesised", "(SELECT COUNT(*) FROM orders)"),
    # --- approved joins
    Case(
        "join_aggregate_many_side",
        "SELECT i.product_category, SUM(i.revenue) AS revenue FROM orders o "
        "JOIN order_items i ON o.order_id = i.order_id WHERE o.is_delivered "
        "GROUP BY i.product_category",
    ),
    Case(
        "join_using",
        "SELECT i.product_category, COUNT(*) AS items FROM orders "
        "JOIN order_items i USING (order_id) WHERE orders.customer_state = 'SP' GROUP BY 1",
    ),
    Case(
        "join_many_to_one",
        "SELECT o.customer_state, SUM(i.price) AS item_value FROM order_items i "
        "JOIN orders o ON o.order_id = i.order_id GROUP BY 1",
    ),
    Case(
        "join_products_count_items",
        "SELECT p.photo_count, COUNT(*) AS items FROM order_items i "
        "JOIN products p ON p.product_id = i.product_id GROUP BY 1",
    ),
    Case(
        "join_composite_key",
        "SELECT s.seller_state, SUM(i.freight_value) AS freight FROM order_sellers s "
        "JOIN order_items i ON s.order_id = i.order_id AND s.seller_id = i.seller_id GROUP BY 1",
    ),
    Case(
        "join_with_filter_in_on",
        "SELECT COUNT(i.order_item_id) FROM orders o "
        "LEFT JOIN order_items i ON o.order_id = i.order_id AND i.price > 100",
    ),
    Case(
        "min_max_after_fanout",
        "SELECT MAX(o.purchased_at) AS last_toy_order FROM orders o "
        "JOIN order_items i ON o.order_id = i.order_id WHERE i.product_category = 'toys'",
    ),
    Case(
        "count_distinct_after_fanout",
        "SELECT COUNT(DISTINCT o.order_id) FROM orders o "
        "JOIN order_items i ON o.order_id = i.order_id WHERE i.product_category = 'health_beauty'",
    ),
    # --- CTEs, subqueries, safe pre-aggregation
    Case(
        "cte",
        "WITH monthly AS (SELECT purchase_month, SUM(revenue) AS revenue FROM orders "
        "GROUP BY purchase_month) SELECT purchase_month, revenue FROM monthly "
        "ORDER BY revenue DESC LIMIT 3",
    ),
    Case(
        "nested_subquery",
        "SELECT AVG(x.items) AS avg_items FROM "
        "(SELECT order_id, COUNT(*) AS items FROM order_items GROUP BY order_id) x",
    ),
    Case(
        "preaggregate_items_then_join",
        "SELECT o.customer_state, SUM(o.revenue) AS revenue, SUM(x.items) AS items "
        "FROM orders o JOIN (SELECT order_id, COUNT(*) AS items FROM order_items "
        "GROUP BY order_id) x ON x.order_id = o.order_id GROUP BY 1",
    ),
    Case(
        "preaggregate_payments_cte",
        "WITH p AS (SELECT order_id, SUM(payment_value) AS paid FROM order_payments "
        "GROUP BY order_id) SELECT SUM(o.revenue) AS revenue, SUM(p.paid) AS paid "
        "FROM orders o LEFT JOIN p ON p.order_id = o.order_id",
    ),
    Case(
        "identity_join_per_customer",
        "SELECT c.orders_placed, COUNT(*) AS orders FROM orders o "
        "JOIN (SELECT customer_unique_id, COUNT(*) AS orders_placed FROM orders "
        "GROUP BY customer_unique_id) c ON c.customer_unique_id = o.customer_unique_id "
        "GROUP BY 1",
    ),
    Case(
        "exists",
        "SELECT COUNT(*) FROM orders o WHERE EXISTS (SELECT 1 FROM order_items i "
        "WHERE i.order_id = o.order_id AND i.product_category = 'toys')",
    ),
    Case(
        "not_exists",
        "SELECT COUNT(*) FROM orders o WHERE NOT EXISTS "
        "(SELECT 1 FROM order_payments p WHERE p.order_id = o.order_id)",
    ),
    Case(
        "in_subquery",
        "SELECT AVG(review_score) FROM orders "
        "WHERE order_id IN (SELECT order_id FROM order_items WHERE price > 500)",
    ),
    Case(
        "correlated_scalar_subquery",
        "SELECT o.order_id, (SELECT COUNT(*) FROM order_items i WHERE i.order_id = o.order_id) "
        "AS items FROM orders o ORDER BY items DESC LIMIT 5",
    ),
    Case(
        "cross_join_single_row_share",
        "WITH t AS (SELECT SUM(revenue) AS total FROM orders) SELECT o.customer_state, "
        "ROUND(SUM(o.revenue) / MAX(t.total), 4) AS share FROM orders o CROSS JOIN t "
        "GROUP BY o.customer_state",
    ),
    Case(
        "union_all",
        "SELECT 'delivered' AS kind, COUNT(*) AS orders FROM orders WHERE is_delivered "
        "UNION ALL SELECT 'canceled', COUNT(*) FROM orders WHERE is_canceled",
    ),
    # --- windows
    Case(
        "running_total",
        "SELECT purchase_month, SUM(revenue) AS revenue, "
        "SUM(SUM(revenue)) OVER (ORDER BY purchase_month) AS running_revenue "
        "FROM orders GROUP BY purchase_month",
    ),
    Case(
        "rank_categories",
        "SELECT product_category, revenue, RANK() OVER (ORDER BY revenue DESC) AS rnk FROM "
        "(SELECT product_category, SUM(revenue) AS revenue FROM order_items "
        "GROUP BY product_category) c",
    ),
    # --- bridge relations (ADR 0011)
    Case(
        "bridge_grouped_by_seller",
        "SELECT seller_id, AVG(review_score) AS avg_score, COUNT(*) FILTER (WHERE is_late) "
        "AS late_orders FROM order_sellers GROUP BY seller_id HAVING COUNT(*) >= 20 "
        "ORDER BY avg_score DESC LIMIT 10",
    ),
    Case(
        "bridge_late_rate_by_category",
        "SELECT product_category, (COUNT(*) FILTER (WHERE is_late))::numeric / "
        "NULLIF(COUNT(is_late), 0) AS late_rate FROM order_categories GROUP BY product_category",
    ),
    Case(
        "bridge_money_is_additive",
        "SELECT SUM(revenue) FROM order_categories WHERE product_category = 'bed_bath_table'",
    ),
    # --- literal and syntax edge cases (regenerated SQL must mean the same to PostgreSQL)
    Case(
        "e_string_escaped_quote",
        r"SELECT order_id FROM orders WHERE order_id = E'\' OR true --'",
    ),
    Case(
        "standard_string_backslash",
        r"SELECT order_id FROM orders WHERE order_id = 'a\' OR order_id = 'b'",
    ),
    Case("dollar_quoted_string", "SELECT $$abc$$ AS a"),
    Case(
        "tautology_is_just_a_filter",
        "SELECT order_id FROM orders WHERE order_id = 'x' OR 1 = 1 --",
    ),
    Case(
        "parenthesised_join_condition",
        "SELECT COUNT(*) FROM orders o JOIN order_items i ON (o.order_id = i.order_id)",
    ),
    Case(
        "chained_ctes",
        "WITH a AS (SELECT order_id, revenue FROM orders), "
        "b AS (SELECT order_id FROM a WHERE revenue > 100) SELECT COUNT(*) FROM b",
    ),
    Case(
        "any_subquery",
        "SELECT COUNT(*) FROM orders WHERE order_id = ANY (SELECT order_id FROM order_items)",
    ),
    Case(
        "bridge_count_distinct_orders",
        "SELECT seller_state, COUNT(DISTINCT order_id) AS orders FROM order_sellers "
        "GROUP BY seller_state",
    ),
]


REJECTED: list[Case] = [
    # --- parse and statement shape
    Case("parse_typo", "SELEC order_id FROM orders", E.PARSE_ERROR),
    Case("parse_incomplete", "SELECT order_id FROM orders WHERE", E.PARSE_ERROR),
    Case("parse_unterminated", "SELECT 'oops FROM orders", E.PARSE_ERROR),
    Case("empty", "   ", E.PARSE_ERROR),
    Case("two_selects", "SELECT 1; SELECT 2", E.MULTIPLE_STATEMENTS),
    Case(
        "select_then_drop", "SELECT order_id FROM orders; DROP TABLE orders", E.MULTIPLE_STATEMENTS
    ),
    Case("select_then_delete", "SELECT 1;DELETE FROM orders", E.MULTIPLE_STATEMENTS),
    # --- writes, DDL, privileges, session and transaction control
    Case("insert", "INSERT INTO orders (order_id) VALUES ('x')", E.WRITE_OPERATION),
    Case("update", "UPDATE orders SET revenue = 0", E.WRITE_OPERATION),
    Case("delete", "DELETE FROM orders", E.WRITE_OPERATION),
    Case(
        "merge",
        "MERGE INTO orders o USING orders s ON o.order_id = s.order_id WHEN MATCHED THEN DELETE",
        E.WRITE_OPERATION,
    ),
    Case("drop", "DROP VIEW analytics.orders", E.WRITE_OPERATION),
    Case("alter", "ALTER VIEW analytics.orders RENAME TO o", E.WRITE_OPERATION),
    Case("create", "CREATE TABLE t (x int)", E.WRITE_OPERATION),
    Case("create_as", "CREATE TEMP TABLE t AS SELECT order_id FROM orders", E.WRITE_OPERATION),
    Case("truncate", "TRUNCATE orders", E.WRITE_OPERATION),
    Case("copy", "COPY orders TO '/tmp/orders.csv'", E.WRITE_OPERATION),
    Case("grant", "GRANT SELECT ON analytics.orders TO PUBLIC", E.WRITE_OPERATION),
    Case("revoke", "REVOKE SELECT ON analytics.orders FROM PUBLIC", E.WRITE_OPERATION),
    Case("call", "CALL do_something()", E.WRITE_OPERATION),
    Case("do_block", "DO $$ BEGIN PERFORM 1; END $$", E.WRITE_OPERATION),
    Case("begin", "BEGIN", E.WRITE_OPERATION),
    Case("commit", "COMMIT", E.WRITE_OPERATION),
    Case("rollback", "ROLLBACK", E.WRITE_OPERATION),
    Case("set", "SET statement_timeout = 0", E.WRITE_OPERATION),
    Case("lock", "LOCK TABLE orders", E.WRITE_OPERATION),
    Case("select_into", "SELECT order_id INTO copied FROM orders", E.WRITE_OPERATION),
    Case("for_update", "SELECT order_id FROM orders FOR UPDATE", E.WRITE_OPERATION),
    Case(
        "data_modifying_cte",
        "WITH gone AS (DELETE FROM orders RETURNING order_id) SELECT COUNT(*) FROM gone",
        E.WRITE_OPERATION,
    ),
    Case("explain", "EXPLAIN SELECT order_id FROM orders", E.UNSUPPORTED_CONSTRUCT),
    # --- SELECT *
    Case("star", "SELECT * FROM orders", E.SELECT_STAR),
    Case("qualified_star", "SELECT o.* FROM orders o", E.SELECT_STAR),
    Case("star_in_cte", "WITH x AS (SELECT * FROM orders) SELECT order_id FROM x", E.SELECT_STAR),
    # --- schemas and relations
    Case("raw_schema", "SELECT order_id FROM raw.orders", E.UNAPPROVED_SCHEMA),
    Case("pg_catalog", "SELECT tablename FROM pg_catalog.pg_tables", E.UNAPPROVED_SCHEMA),
    Case(
        "information_schema",
        "SELECT table_name FROM information_schema.tables",
        E.UNAPPROVED_SCHEMA,
    ),
    Case(
        "internal_schema",
        "SELECT product_category FROM analytics_internal.product_category_map",
        E.UNAPPROVED_SCHEMA,
    ),
    Case("three_part_name", "SELECT order_id FROM olist.analytics.orders", E.UNAPPROVED_SCHEMA),
    Case(
        "raw_in_subquery",
        "SELECT order_id FROM orders WHERE order_id IN (SELECT order_id FROM raw.order_items)",
        E.UNAPPROVED_SCHEMA,
    ),
    Case(
        "raw_in_cte",
        "WITH r AS (SELECT order_id FROM raw.orders) SELECT order_id FROM r",
        E.UNAPPROVED_SCHEMA,
    ),
    Case(
        "schema_function", "SELECT pg_catalog.lower(order_status) FROM orders", E.UNAPPROVED_SCHEMA
    ),
    Case("hidden_customers", "SELECT COUNT(*) FROM customers", E.UNAPPROVED_RELATION),
    Case("hidden_sellers", "SELECT seller_id, total_revenue FROM sellers", E.UNAPPROVED_RELATION),
    Case("unknown_relation", "SELECT zip FROM geolocation", E.UNAPPROVED_RELATION),
    Case("system_view", "SELECT usename FROM pg_user", E.UNAPPROVED_RELATION),
    Case("quoted_wrong_case", 'SELECT order_id FROM "Orders"', E.UNAPPROVED_RELATION),
    # --- columns
    Case("raw_customer_id", "SELECT customer_id FROM orders", E.UNAPPROVED_COLUMN),
    Case(
        "hidden_lifetime_column",
        "SELECT product_id, total_revenue FROM products",
        E.UNAPPROVED_COLUMN,
    ),
    Case("unknown_column", "SELECT o.nope FROM orders o", E.UNAPPROVED_COLUMN),
    Case("system_column", "SELECT ctid FROM orders", E.UNAPPROVED_COLUMN),
    Case("column_in_where", "SELECT order_id FROM orders WHERE secret_flag", E.UNAPPROVED_COLUMN),
    Case(
        "ambiguous_column",
        "SELECT order_id FROM orders o JOIN order_items i ON o.order_id = i.order_id",
        E.AMBIGUOUS_COLUMN,
    ),
    # --- functions and casts
    Case("pg_sleep", "SELECT pg_sleep(20)", E.UNAPPROVED_FUNCTION),
    Case(
        "pg_sleep_in_where",
        "SELECT order_id FROM orders WHERE pg_sleep(1) IS NOT NULL",
        E.UNAPPROVED_FUNCTION,
    ),
    Case("read_file", "SELECT pg_read_file('/etc/passwd')", E.UNAPPROVED_FUNCTION),
    Case("set_config", "SELECT set_config('statement_timeout', '0', false)", E.UNAPPROVED_FUNCTION),
    Case("current_setting", "SELECT current_setting('search_path')", E.UNAPPROVED_FUNCTION),
    Case("version", "SELECT version()", E.UNAPPROVED_FUNCTION),
    Case(
        "now",
        "SELECT COUNT(*) FROM orders WHERE purchased_at > NOW() - INTERVAL '30 days'",
        E.UNAPPROVED_FUNCTION,
    ),
    Case(
        "current_date",
        "SELECT COUNT(*) FROM orders WHERE purchase_date = CURRENT_DATE",
        E.UNAPPROVED_FUNCTION,
    ),
    Case("string_agg", "SELECT STRING_AGG(order_id, ',') FROM orders", E.UNAPPROVED_FUNCTION),
    Case("udf", "SELECT my_function(order_id) FROM orders", E.UNAPPROVED_FUNCTION),
    Case("regclass_cast", "SELECT 'raw.orders'::regclass", E.UNAPPROVED_FUNCTION),
    Case(
        "regex_operator", "SELECT COUNT(*) FROM orders WHERE order_id ~ '^a'", E.UNAPPROVED_FUNCTION
    ),
    # --- unsupported constructs
    Case(
        "recursive_cte",
        "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r) SELECT n FROM r",
        E.UNSUPPORTED_CONSTRUCT,
    ),
    Case(
        "lateral",
        "SELECT o.order_id, x.n FROM orders o, LATERAL (SELECT COUNT(*) AS n FROM order_items i WHERE i.order_id = o.order_id) x",
        E.UNSUPPORTED_CONSTRUCT,
    ),
    Case("values", "SELECT v.x FROM (VALUES (1)) AS v(x)", E.UNSUPPORTED_CONSTRUCT),
    Case("table_function", "SELECT g FROM generate_series(1, 3) AS g", E.UNSUPPORTED_CONSTRUCT),
    Case(
        "tablesample",
        "SELECT order_id FROM orders TABLESAMPLE SYSTEM (10)",
        E.UNSUPPORTED_CONSTRUCT,
    ),
    Case(
        "fetch_first",
        "SELECT order_id FROM orders FETCH FIRST 5 ROWS ONLY",
        E.UNSUPPORTED_CONSTRUCT,
    ),
    Case(
        "distinct_on",
        "SELECT DISTINCT ON (customer_state) customer_state, order_id FROM orders",
        E.UNSUPPORTED_CONSTRUCT,
    ),
    Case(
        "rollup",
        "SELECT customer_state, COUNT(*) FROM orders GROUP BY ROLLUP (customer_state)",
        E.UNSUPPORTED_CONSTRUCT,
    ),
    Case(
        "intersect",
        "SELECT order_id FROM orders INTERSECT SELECT order_id FROM order_items",
        E.UNSUPPORTED_CONSTRUCT,
    ),
    Case(
        "except",
        "SELECT order_id FROM orders EXCEPT SELECT order_id FROM order_payments",
        E.UNSUPPORTED_CONSTRUCT,
    ),
    Case(
        "natural_join",
        "SELECT o.order_id FROM orders o NATURAL JOIN order_items i",
        E.UNSUPPORTED_CONSTRUCT,
    ),
    Case(
        "right_join",
        "SELECT o.order_id FROM orders o RIGHT JOIN order_items i ON o.order_id = i.order_id",
        E.UNSUPPORTED_CONSTRUCT,
    ),
    Case(
        "full_join",
        "SELECT o.order_id FROM orders o FULL JOIN order_items i ON o.order_id = i.order_id",
        E.UNSUPPORTED_CONSTRUCT,
    ),
    Case("parameter", "SELECT order_id FROM orders WHERE order_id = $1", E.UNSUPPORTED_CONSTRUCT),
    Case(
        "cte_shadows_relation",
        "WITH orders AS (SELECT order_id, price FROM order_items) SELECT SUM(price) FROM orders",
        E.UNSUPPORTED_CONSTRUCT,
    ),
    Case("subquery_limit", "SELECT order_id FROM orders LIMIT (SELECT 5)", E.UNSUPPORTED_CONSTRUCT),
    Case(
        "subquery_in_on",
        "SELECT o.order_id FROM orders o JOIN order_items i ON o.order_id = i.order_id AND i.price > (SELECT 1)",
        E.UNSUPPORTED_CONSTRUCT,
    ),
    # --- join paths
    Case(
        "wrong_join_key",
        "SELECT o.order_id FROM orders o JOIN order_items i ON o.order_id = i.product_id",
        E.INVALID_JOIN_PATH,
    ),
    Case(
        "non_key_join",
        "SELECT COUNT(*) FROM orders o JOIN order_items i ON o.customer_state = i.customer_state",
        E.INVALID_JOIN_PATH,
    ),
    Case(
        "cross_join",
        "SELECT o.order_id FROM orders o CROSS JOIN order_items i",
        E.INVALID_JOIN_PATH,
    ),
    Case(
        "comma_join",
        "SELECT o.order_id FROM orders o, order_items i WHERE o.order_id = i.order_id",
        E.INVALID_JOIN_PATH,
    ),
    Case(
        "join_on_true",
        "SELECT o.order_id FROM orders o JOIN order_items i ON true",
        E.INVALID_JOIN_PATH,
    ),
    Case(
        "join_on_one_equals_one",
        "SELECT o.order_id FROM orders o JOIN order_items i ON 1 = 1",
        E.INVALID_JOIN_PATH,
    ),
    Case(
        "join_on_self_equality",
        "SELECT o.order_id FROM orders o JOIN order_items i ON o.order_id = o.order_id",
        E.INVALID_JOIN_PATH,
    ),
    Case(
        "join_or_bypass",
        "SELECT COUNT(*) FROM orders o JOIN order_items i ON o.order_id = i.order_id OR 1 = 1",
        E.INVALID_JOIN_PATH,
    ),
    Case(
        "join_inequality",
        "SELECT COUNT(*) FROM orders o JOIN order_items i ON o.order_id <> i.order_id",
        E.INVALID_JOIN_PATH,
    ),
    Case(
        "join_function_on_key",
        "SELECT COUNT(*) FROM orders o JOIN order_items i ON LOWER(o.order_id) = i.order_id",
        E.INVALID_JOIN_PATH,
    ),
    Case(
        "join_computed_key",
        "SELECT COUNT(*) FROM orders o JOIN (SELECT UPPER(order_id) AS order_id FROM order_items) i ON o.order_id = i.order_id",
        E.INVALID_JOIN_PATH,
    ),
    Case(
        "items_payments_many_to_many",
        "SELECT SUM(i.price) FROM order_items i JOIN order_payments p ON i.order_id = p.order_id",
        E.INVALID_JOIN_PATH,
    ),
    Case(
        "sellers_categories_many_to_many",
        "SELECT COUNT(*) FROM order_sellers s JOIN order_categories c ON s.order_id = c.order_id",
        E.INVALID_JOIN_PATH,
    ),
    Case(
        "partial_composite_key",
        "SELECT SUM(i.price) FROM order_items i JOIN order_sellers s ON i.order_id = s.order_id",
        E.INVALID_JOIN_PATH,
    ),
    Case(
        "unrelated_relations",
        "SELECT COUNT(*) FROM orders o JOIN products p ON o.order_id = p.product_id",
        E.INVALID_JOIN_PATH,
    ),
    # --- fan-out: syntactically valid SQL with inflated answers
    Case(
        "fanout_revenue_items",
        "SELECT SUM(o.revenue) FROM analytics.orders o JOIN analytics.order_items i ON o.order_id = i.order_id",
        E.FANOUT_RISK,
    ),
    Case(
        "fanout_revenue_payments",
        "SELECT SUM(o.revenue) FROM orders o JOIN order_payments p ON o.order_id = p.order_id",
        E.FANOUT_RISK,
    ),
    Case(
        "fanout_revenue_by_category_via_items",
        "SELECT i.product_category, SUM(o.revenue) FROM orders o JOIN order_items i ON o.order_id = i.order_id GROUP BY 1",
        E.FANOUT_RISK,
    ),
    Case(
        "fanout_reviews_items",
        "SELECT AVG(o.review_score) FROM orders o JOIN order_items i ON o.order_id = i.order_id",
        E.FANOUT_RISK,
    ),
    Case(
        "fanout_review_count_items",
        "SELECT COUNT(o.review_score) FROM orders o JOIN order_items i ON o.order_id = i.order_id",
        E.FANOUT_RISK,
    ),
    Case(
        "fanout_items_times_payments",
        "SELECT SUM(i.price), SUM(p.payment_value) FROM orders o JOIN order_items i ON o.order_id = i.order_id JOIN order_payments p ON o.order_id = p.order_id",
        E.FANOUT_RISK,
    ),
    Case(
        "fanout_freight_sellers",
        "SELECT SUM(o.freight_total) FROM orders o JOIN order_sellers s ON o.order_id = s.order_id",
        E.FANOUT_RISK,
    ),
    Case(
        "fanout_delivery_days_categories",
        "SELECT AVG(o.delivery_days) FROM orders o JOIN order_categories c ON o.order_id = c.order_id",
        E.FANOUT_RISK,
    ),
    Case(
        "fanout_sum_distinct_is_not_a_fix",
        "SELECT SUM(DISTINCT o.revenue) FROM orders o JOIN order_items i ON o.order_id = i.order_id",
        E.FANOUT_RISK,
    ),
    Case(
        "fanout_product_attribute",
        "SELECT i.product_category, AVG(p.weight_g) FROM order_items i JOIN products p ON i.product_id = p.product_id GROUP BY 1",
        E.FANOUT_RISK,
    ),
    Case(
        "fanout_window",
        "SELECT SUM(o.revenue) OVER () FROM orders o JOIN order_items i ON o.order_id = i.order_id",
        E.FANOUT_RISK,
    ),
    Case(
        "fanout_median",
        "SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY o.delivery_days) FROM orders o JOIN order_items i ON o.order_id = i.order_id",
        E.FANOUT_RISK,
    ),
    Case(
        "fanout_cross_join_total",
        "WITH t AS (SELECT SUM(revenue) AS total FROM orders) SELECT SUM(t.total) FROM orders o CROSS JOIN t",
        E.FANOUT_RISK,
    ),
    Case(
        "fanout_inside_cte",
        "WITH x AS (SELECT o.revenue FROM orders o JOIN order_items i ON o.order_id = i.order_id) SELECT SUM(revenue) FROM x",
        E.FANOUT_RISK,
    ),
    Case(
        "fanout_inside_derived_table",
        "SELECT SUM(x.rev) FROM (SELECT o.revenue AS rev FROM orders o JOIN order_items i ON o.order_id = i.order_id) x",
        E.FANOUT_RISK,
    ),
    Case(
        "fanout_inside_where_subquery",
        "SELECT COUNT(*) FROM orders WHERE revenue > (SELECT AVG(o.revenue) FROM orders o JOIN order_items i ON o.order_id = i.order_id)",
        E.FANOUT_RISK,
    ),
    # --- bridge attribution (ADR 0011)
    Case(
        "bridge_avg_review_ungrouped", "SELECT AVG(review_score) FROM order_sellers", E.FANOUT_RISK
    ),
    Case(
        "bridge_late_count_ungrouped",
        "SELECT COUNT(*) FILTER (WHERE is_late) FROM order_categories",
        E.FANOUT_RISK,
    ),
    Case(
        "bridge_grouped_by_other_column",
        "SELECT seller_state, AVG(review_score) FROM order_sellers GROUP BY seller_state",
        E.FANOUT_RISK,
    ),
    Case(
        "bridge_orders_by_state",
        "SELECT customer_state, COUNT(*) FROM order_sellers GROUP BY customer_state",
        E.FANOUT_RISK,
    ),
    Case(
        "bridge_joined_to_orders",
        "SELECT AVG(s.review_score) FROM order_sellers s JOIN orders o ON o.order_id = s.order_id",
        E.FANOUT_RISK,
    ),
    # --- bypass attempts
    Case(
        "raw_scalar_subquery",
        "SELECT (SELECT order_id FROM raw.orders LIMIT 1) AS x",
        E.UNAPPROVED_SCHEMA,
    ),
    Case(
        "union_system_view",
        "SELECT order_status FROM orders UNION SELECT usename FROM pg_user",
        E.UNAPPROVED_RELATION,
    ),
    Case("current_user", "SELECT current_user", E.UNAPPROVED_FUNCTION),
    Case(
        "sleep_in_order_by",
        "SELECT order_id FROM orders ORDER BY pg_sleep(1)",
        E.UNAPPROVED_FUNCTION,
    ),
    Case(
        "sleep_in_having",
        "SELECT customer_state FROM orders GROUP BY customer_state HAVING pg_sleep(1) IS NOT NULL",
        E.UNAPPROVED_FUNCTION,
    ),
    Case(
        "sleep_in_join_on",
        "SELECT COUNT(*) FROM orders o JOIN order_items i ON o.order_id = i.order_id AND pg_sleep(1) IS NULL",
        E.UNAPPROVED_FUNCTION,
    ),
    Case(
        "unicode_escaped_identifier",
        r'SELECT U&"\006f\0072\0064\0065\0072\005f\0069\0064" FROM orders',
        E.UNAPPROVED_COLUMN,
    ),
    Case("collate", 'SELECT order_id COLLATE "C" FROM orders', E.UNAPPROVED_FUNCTION),
    Case(
        "array_literal",
        "SELECT COUNT(*) FROM orders WHERE order_id LIKE ANY (ARRAY['a%'])",
        E.UNAPPROVED_FUNCTION,
    ),
    # sqlglot regenerates this as an unterminated string; the round-trip check refuses it.
    Case("e_string_double_backslash", r"SELECT E'\\' AS backslash", E.UNSUPPORTED_CONSTRUCT),
    Case(
        "same_many_side_twice",
        "SELECT o.order_id FROM orders o JOIN order_items i ON o.order_id = i.order_id JOIN order_items j ON j.order_id = o.order_id",
        E.FANOUT_RISK,
    ),
    Case(
        "many_to_many_inside_in_subquery",
        "SELECT order_id FROM orders o WHERE o.order_id IN (SELECT i.order_id FROM order_items i JOIN order_payments p ON p.order_id = i.order_id)",
        E.INVALID_JOIN_PATH,
    ),
    # --- limits
    Case("limit_too_high", "SELECT order_id FROM orders LIMIT 5000", E.RESULT_LIMIT_EXCEEDED),
    Case("limit_just_over", "SELECT order_id FROM orders LIMIT 1001", E.RESULT_LIMIT_EXCEEDED),
    Case("limit_expression", "SELECT order_id FROM orders LIMIT 1 + 1", E.UNSUPPORTED_CONSTRUCT),
]

# Rejected by the validator AND by the database role on its own (validator bypassed):
# test_validator_execution.py runs these directly as analytics_reader.
DATABASE_BLOCKED = [
    "insert", "update", "delete", "drop", "alter", "create", "create_as", "truncate",
    "grant", "revoke", "select_into", "for_update", "data_modifying_cte",
    "raw_schema", "internal_schema", "raw_in_subquery", "read_file", "copy",
]  # fmt: skip
