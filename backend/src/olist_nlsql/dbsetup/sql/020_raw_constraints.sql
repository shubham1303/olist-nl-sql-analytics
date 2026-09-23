-- Keys, relationships and indexes, added after the bulk load.
--
-- These encode source assumptions that were verified against the data; a load
-- that violates one fails loudly. Deliberately NOT declared:
-- * customers.customer_unique_id is not unique (one person, many customer_ids).
-- * order_reviews.review_id is not unique; (review_id, order_id) is.
-- * order_reviews.order_id is not unique (some orders have several reviews).
-- * products.product_category_name -> translation: 13 products in 2 categories
--   have no translation row, so no foreign key.
-- * geolocation has no key: it contains exact duplicate rows.

ALTER TABLE raw.customers      ADD PRIMARY KEY (customer_id);
ALTER TABLE raw.orders         ADD PRIMARY KEY (order_id);
ALTER TABLE raw.order_items    ADD PRIMARY KEY (order_id, order_item_id);
ALTER TABLE raw.order_payments ADD PRIMARY KEY (order_id, payment_sequential);
ALTER TABLE raw.order_reviews  ADD CONSTRAINT order_reviews_review_order_key UNIQUE (review_id, order_id);
ALTER TABLE raw.products       ADD PRIMARY KEY (product_id);
ALTER TABLE raw.sellers        ADD PRIMARY KEY (seller_id);
ALTER TABLE raw.product_category_name_translation ADD PRIMARY KEY (product_category_name);

ALTER TABLE raw.orders
    ADD FOREIGN KEY (customer_id) REFERENCES raw.customers (customer_id);
ALTER TABLE raw.order_items
    ADD FOREIGN KEY (order_id)   REFERENCES raw.orders (order_id),
    ADD FOREIGN KEY (product_id) REFERENCES raw.products (product_id),
    ADD FOREIGN KEY (seller_id)  REFERENCES raw.sellers (seller_id);
ALTER TABLE raw.order_payments
    ADD FOREIGN KEY (order_id) REFERENCES raw.orders (order_id);
ALTER TABLE raw.order_reviews
    ADD FOREIGN KEY (order_id) REFERENCES raw.orders (order_id);

CREATE INDEX ON raw.customers (customer_unique_id);
CREATE INDEX ON raw.order_items (product_id);
CREATE INDEX ON raw.order_items (seller_id);
CREATE INDEX ON raw.order_reviews (order_id);
CREATE INDEX ON raw.orders (order_purchase_timestamp);
