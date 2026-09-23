-- Privileges for analytics_reader (ADR 0002). Runs as olist_owner after the
-- views are (re)created. The reader gets USAGE on analytics and SELECT on its
-- views, and nothing else: no raw schema, no writes, no DDL.

REVOKE ALL ON SCHEMA raw FROM PUBLIC;
REVOKE ALL ON SCHEMA analytics_internal FROM PUBLIC;
REVOKE ALL ON SCHEMA analytics FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA raw FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA analytics_internal FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA analytics FROM PUBLIC;

GRANT USAGE ON SCHEMA analytics TO analytics_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO analytics_reader;
