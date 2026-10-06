-- ==============================================================================
-- Ketrika Agri Market Intelligence - Database Initialization Script
-- Executed on first startup in docker-entrypoint-initdb.d
-- ==============================================================================

-- 1. Create Dagster database and role
CREATE ROLE dagster WITH LOGIN PASSWORD 'change-me';
CREATE DATABASE dagster OWNER dagster;
GRANT ALL PRIVILEGES ON DATABASE dagster TO dagster;

-- 2. Setup in primary database (ketrika)
-- Note: PostgreSQL connects initially to POSTGRES_DB (ketrika)

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "unaccent";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- 3. Create Schemas
CREATE SCHEMA IF NOT EXISTS meta;
CREATE SCHEMA IF NOT EXISTS ref;
CREATE SCHEMA IF NOT EXISTS obs;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS dq;

-- 4. Application Role (ketrika_app)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ketrika_app') THEN
        CREATE ROLE ketrika_app WITH LOGIN PASSWORD 'change-me';
    END IF;
END
$$;

GRANT ALL PRIVILEGES ON SCHEMA meta, ref, obs, gold, dq TO ketrika;
GRANT ALL PRIVILEGES ON SCHEMA meta, ref, obs, gold, dq TO ketrika_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA meta, ref, obs, gold, dq GRANT ALL ON TABLES TO ketrika;
ALTER DEFAULT PRIVILEGES IN SCHEMA meta, ref, obs, gold, dq GRANT ALL ON TABLES TO ketrika_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA meta, ref, obs, gold, dq GRANT ALL ON SEQUENCES TO ketrika;
ALTER DEFAULT PRIVILEGES IN SCHEMA meta, ref, obs, gold, dq GRANT ALL ON SEQUENCES TO ketrika_app;

-- 5. Copilot Read-Only Role (copilot_ro)
-- SPECS §10.1 & §21: strictly limited to SELECT on schema gold only
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'copilot_ro') THEN
        CREATE ROLE copilot_ro WITH LOGIN PASSWORD 'change-me-ro';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA gold TO copilot_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO copilot_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO copilot_ro;

-- Revoke create or alter on public
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
