-- Raw Olist tables: a faithful copy of the source CSVs.
--
-- * Column names match the CSV headers exactly, including the source typos
--   (product_name_lenght, product_description_lenght). They are fixed in the
--   analytics layer, not here.
-- * IDs and zip-code prefixes are text: prefixes carry leading zeros ("01037").
-- * Money is unconstrained numeric so no value is silently rounded on load.
-- * Keys and foreign keys are added after loading (020_raw_constraints.sql).
-- * Nothing in this schema is visible to analytics_reader (ADR 0002, 0005).

CREATE SCHEMA raw;
COMMENT ON SCHEMA raw IS 'Faithful copy of the Olist source CSVs. Not visible to analytics_reader.';

CREATE TABLE raw.customers (
    customer_id              text NOT NULL,
    customer_unique_id       text NOT NULL,
    customer_zip_code_prefix text NOT NULL,
    customer_city            text NOT NULL,
    customer_state           text NOT NULL
);

CREATE TABLE raw.geolocation (
    geolocation_zip_code_prefix text NOT NULL,
    geolocation_lat             double precision NOT NULL,
    geolocation_lng             double precision NOT NULL,
    geolocation_city            text NOT NULL,
    geolocation_state           text NOT NULL
);

CREATE TABLE raw.orders (
    order_id                      text NOT NULL,
    customer_id                   text NOT NULL,
    order_status                  text NOT NULL,
    order_purchase_timestamp      timestamp NOT NULL,
    order_approved_at             timestamp,
    order_delivered_carrier_date  timestamp,
    order_delivered_customer_date timestamp,
    order_estimated_delivery_date timestamp NOT NULL
);

CREATE TABLE raw.order_items (
    order_id            text NOT NULL,
    order_item_id       integer NOT NULL,
    product_id          text NOT NULL,
    seller_id           text NOT NULL,
    shipping_limit_date timestamp NOT NULL,
    price               numeric NOT NULL,
    freight_value       numeric NOT NULL
);

CREATE TABLE raw.order_payments (
    order_id             text NOT NULL,
    payment_sequential   integer NOT NULL,
    payment_type         text NOT NULL,
    payment_installments integer NOT NULL,
    payment_value        numeric NOT NULL
);

CREATE TABLE raw.order_reviews (
    review_id               text NOT NULL,
    order_id                text NOT NULL,
    review_score            integer NOT NULL,
    review_comment_title    text,
    review_comment_message  text,
    review_creation_date    timestamp NOT NULL,
    review_answer_timestamp timestamp NOT NULL
);

CREATE TABLE raw.products (
    product_id                 text NOT NULL,
    product_category_name      text,
    product_name_lenght        integer,
    product_description_lenght integer,
    product_photos_qty         integer,
    product_weight_g           integer,
    product_length_cm          integer,
    product_height_cm          integer,
    product_width_cm           integer
);

CREATE TABLE raw.sellers (
    seller_id              text NOT NULL,
    seller_zip_code_prefix text NOT NULL,
    seller_city            text NOT NULL,
    seller_state           text NOT NULL
);

CREATE TABLE raw.product_category_name_translation (
    product_category_name         text NOT NULL,
    product_category_name_english text NOT NULL
);
