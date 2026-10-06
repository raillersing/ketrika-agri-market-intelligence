"""0001_initial_schema: Initial database schemas for Ketrika Agri Market Intelligence.

Reproduces exact schemas from SPECS.md §8:
- Schemas: meta, ref, obs, ml, ops, dq, gold, auth
- Tables, constraints, foreign keys, indices, PostGIS spatial geometries
- Immutability and append-only triggers for bronze and silver observations
- Roles (ketrika_app, copilot_ro) and least-privilege permissions

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-06 22:36:00
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

    # 2. Schemas
    op.execute("CREATE SCHEMA IF NOT EXISTS meta;")
    op.execute("CREATE SCHEMA IF NOT EXISTS ref;")
    op.execute("CREATE SCHEMA IF NOT EXISTS obs;")
    op.execute("CREATE SCHEMA IF NOT EXISTS ml;")
    op.execute("CREATE SCHEMA IF NOT EXISTS ops;")
    op.execute("CREATE SCHEMA IF NOT EXISTS dq;")
    op.execute("CREATE SCHEMA IF NOT EXISTS gold;")
    op.execute("CREATE SCHEMA IF NOT EXISTS auth;")

    # 3. Roles creation if not already present
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ketrika_app') THEN
                CREATE ROLE ketrika_app WITH LOGIN PASSWORD 'change-me';
            END IF;
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'copilot_ro') THEN
                CREATE ROLE copilot_ro WITH LOGIN PASSWORD 'change-me-ro';
            END IF;
        END
        $$;
        """
    )
    op.execute("ALTER ROLE copilot_ro SET statement_timeout = '5s';")

    # ===================== META =====================
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS meta.source (
            source_id            TEXT PRIMARY KEY,
            spec                 JSONB NOT NULL,
            status               TEXT NOT NULL,
            updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS meta.ingestion_run (
            run_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_id            TEXT NOT NULL REFERENCES meta.source(source_id),
            dagster_run_id       TEXT,
            partition_key        TEXT,
            started_at           TIMESTAMPTZ NOT NULL,
            finished_at          TIMESTAMPTZ,
            status               TEXT NOT NULL,
            n_fetched            INT DEFAULT 0,
            n_new_artifacts      INT DEFAULT 0,
            n_records            INT DEFAULT 0,
            n_rejected           INT DEFAULT 0,
            n_review             INT DEFAULT 0,
            error                TEXT
        );

        CREATE TABLE IF NOT EXISTS meta.source_record (
            source_record_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_id            TEXT NOT NULL REFERENCES meta.source(source_id),
            source_url           TEXT NOT NULL,
            retrieved_via        TEXT NOT NULL DEFAULT 'direct',
            object_key           TEXT NOT NULL,
            content_sha256       TEXT NOT NULL,
            mime_type            TEXT,
            http_status          INT,
            http_etag            TEXT,
            http_last_modified   TEXT,
            published_at         TIMESTAMPTZ,
            fetched_at           TIMESTAMPTZ NOT NULL,
            parser_version       TEXT,
            extraction_status    TEXT NOT NULL DEFAULT 'pending',
            CONSTRAINT uq_source_record_sha UNIQUE (source_id, content_sha256)
        );

        CREATE TABLE IF NOT EXISTS meta.llm_call (
            llm_call_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            provider             TEXT NOT NULL,
            model                TEXT NOT NULL,
            purpose              TEXT NOT NULL,
            prompt_version       TEXT NOT NULL,
            cache_key            TEXT NOT NULL,
            input_tokens         INT,
            output_tokens        INT,
            cost_usd             NUMERIC(10,5),
            source_record_id     UUID REFERENCES meta.source_record(source_record_id),
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            status               TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_llm_call_cache_key ON meta.llm_call (cache_key);
        """
    )

    # ===================== REF =====================
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ref.product (
            product_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            product_code         TEXT UNIQUE NOT NULL,
            canonical_name_fr    TEXT NOT NULL,
            category             TEXT NOT NULL,
            base_unit            TEXT NOT NULL,
            hs6_codes            TEXT[] NOT NULL DEFAULT '{}',
            faostat_item_codes   TEXT[] NOT NULL DEFAULT '{}',
            verified             BOOLEAN NOT NULL DEFAULT false
        );

        CREATE TABLE IF NOT EXISTS ref.product_alias (
            alias_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            alias_norm           TEXT NOT NULL,
            alias_display        TEXT NOT NULL,
            lang                 TEXT NOT NULL,
            product_id           UUID NOT NULL REFERENCES ref.product(product_id),
            source_id            TEXT,
            confidence           NUMERIC(3,2) NOT NULL,
            origin               TEXT NOT NULL,
            human_reviewed       BOOLEAN NOT NULL DEFAULT false
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_product_alias_norm_source
            ON ref.product_alias (alias_norm, COALESCE(source_id, ''));

        CREATE TABLE IF NOT EXISTS ref.unit_conversion (
            unit_code            TEXT NOT NULL,
            product_id           UUID REFERENCES ref.product(product_id),
            base_unit            TEXT NOT NULL,
            factor               NUMERIC(18,6) NOT NULL,
            confidence           NUMERIC(3,2) NOT NULL,
            evidence             TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_unit_conversion_unique
            ON ref.unit_conversion (unit_code, COALESCE(product_id, '00000000-0000-0000-0000-000000000000'::uuid));

        CREATE TABLE IF NOT EXISTS ref.location (
            location_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            admin_level          SMALLINT NOT NULL,
            pcode                TEXT,
            name                 TEXT NOT NULL,
            parent_id            UUID REFERENCES ref.location(location_id),
            boundary_version     TEXT NOT NULL,
            geom                 geometry(MultiPolygon, 4326),
            centroid             geometry(Point, 4326),
            valid_from           DATE,
            valid_to             DATE
        );
        CREATE INDEX IF NOT EXISTS idx_location_geom ON ref.location USING gist (geom);

        CREATE TABLE IF NOT EXISTS ref.location_alias (
            alias_norm           TEXT NOT NULL,
            location_id          UUID NOT NULL REFERENCES ref.location(location_id),
            source_id            TEXT,
            confidence           NUMERIC(3,2) NOT NULL,
            origin               TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_location_alias_norm_source
            ON ref.location_alias (alias_norm, COALESCE(source_id, ''));
        """
    )

    # ===================== OBS (Silver) =====================
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS obs.price_observation (
            observation_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_record_id     UUID NOT NULL REFERENCES meta.source_record(source_record_id),
            natural_key          TEXT NOT NULL,
            product_raw          TEXT NOT NULL,
            product_id           UUID REFERENCES ref.product(product_id),
            variety              TEXT,
            quality_grade        TEXT,
            location_raw         TEXT,
            location_id          UUID REFERENCES ref.location(location_id),
            market_name          TEXT,
            actor_level          TEXT NOT NULL,
            period_start         DATE NOT NULL,
            period_end           DATE NOT NULL,
            published_at         TIMESTAMPTZ,
            ingested_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            price_raw            TEXT NOT NULL,
            price_value          NUMERIC(18,4),
            currency_raw         TEXT NOT NULL DEFAULT 'MGA',
            unit_raw             TEXT NOT NULL,
            package_quantity     NUMERIC(18,4),
            package_unit         TEXT,
            price_mga_per_base   NUMERIC(18,4),
            base_unit            TEXT,
            conversion_status    TEXT NOT NULL,
            observed_or_imputed  TEXT NOT NULL,
            missing_code         TEXT,
            extraction_method    TEXT NOT NULL,
            evidence             JSONB,
            confidence           NUMERIC(3,2) NOT NULL,
            review_status        TEXT NOT NULL DEFAULT 'accepted',
            superseded_by        UUID REFERENCES obs.price_observation(observation_id)
        );
        CREATE INDEX IF NOT EXISTS idx_price_obs_prod_loc_period
            ON obs.price_observation (product_id, location_id, period_start);
        CREATE UNIQUE INDEX IF NOT EXISTS price_obs_current_uk
            ON obs.price_observation (natural_key) WHERE superseded_by IS NULL;

        CREATE TABLE IF NOT EXISTS obs.stock_observation (
            observation_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_record_id     UUID NOT NULL REFERENCES meta.source_record(source_record_id),
            natural_key          TEXT NOT NULL,
            product_raw          TEXT NOT NULL,
            product_id           UUID REFERENCES ref.product(product_id),
            location_raw         TEXT,
            location_id          UUID REFERENCES ref.location(location_id),
            period_start         DATE NOT NULL,
            period_end           DATE NOT NULL,
            published_at         TIMESTAMPTZ,
            ingested_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            quantity_raw         TEXT,
            quantity_value       NUMERIC(18,4),
            unit_raw             TEXT,
            quantity_base        NUMERIC(18,4),
            base_unit            TEXT,
            stock_status         TEXT,
            coverage_days        NUMERIC(8,2),
            extraction_method    TEXT NOT NULL,
            evidence             JSONB,
            confidence           NUMERIC(3,2) NOT NULL,
            review_status        TEXT NOT NULL DEFAULT 'accepted',
            superseded_by        UUID REFERENCES obs.stock_observation(observation_id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS stock_obs_current_uk
            ON obs.stock_observation (natural_key) WHERE superseded_by IS NULL;

        CREATE TABLE IF NOT EXISTS obs.trade_flow (
            observation_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_record_id     UUID NOT NULL REFERENCES meta.source_record(source_record_id),
            natural_key          TEXT NOT NULL,
            flow                 TEXT NOT NULL,
            hs_code              TEXT,
            product_raw          TEXT NOT NULL,
            product_id           UUID REFERENCES ref.product(product_id),
            partner_raw          TEXT,
            partner_iso3         TEXT,
            period_start         DATE NOT NULL,
            period_end           DATE NOT NULL,
            published_at         TIMESTAMPTZ,
            ingested_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            value_raw            TEXT,
            value_mga            NUMERIC(20,2),
            value_usd            NUMERIC(20,2),
            weight_raw           TEXT,
            weight_kg            NUMERIC(20,3),
            extraction_method    TEXT NOT NULL,
            evidence             JSONB,
            confidence           NUMERIC(3,2) NOT NULL,
            review_status        TEXT NOT NULL DEFAULT 'accepted',
            superseded_by        UUID REFERENCES obs.trade_flow(observation_id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS trade_current_uk
            ON obs.trade_flow (natural_key) WHERE superseded_by IS NULL;

        CREATE TABLE IF NOT EXISTS obs.production_observation (
            observation_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_record_id     UUID NOT NULL REFERENCES meta.source_record(source_record_id),
            natural_key          TEXT NOT NULL,
            product_raw          TEXT NOT NULL,
            product_id           UUID REFERENCES ref.product(product_id),
            location_id          UUID REFERENCES ref.location(location_id),
            period_start         DATE NOT NULL,
            period_end           DATE NOT NULL,
            element              TEXT NOT NULL,
            value                NUMERIC(20,4),
            unit_raw             TEXT,
            flag_raw             TEXT,
            published_at         TIMESTAMPTZ,
            ingested_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            observed_or_imputed  TEXT NOT NULL,
            extraction_method    TEXT NOT NULL,
            evidence             JSONB,
            confidence           NUMERIC(3,2) NOT NULL,
            superseded_by        UUID REFERENCES obs.production_observation(observation_id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS prod_current_uk
            ON obs.production_observation (natural_key) WHERE superseded_by IS NULL;

        CREATE TABLE IF NOT EXISTS obs.weather_observation (
            observation_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_record_id     UUID NOT NULL REFERENCES meta.source_record(source_record_id),
            location_id          UUID NOT NULL REFERENCES ref.location(location_id),
            date                 DATE NOT NULL,
            variable             TEXT NOT NULL,
            value                NUMERIC(10,3),
            method               TEXT NOT NULL,
            provider             TEXT NOT NULL,
            ingested_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_weather_obs UNIQUE (provider, location_id, date, variable)
        );

        CREATE TABLE IF NOT EXISTS obs.cpi_observation (
            observation_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_record_id     UUID NOT NULL REFERENCES meta.source_record(source_record_id),
            natural_key          TEXT NOT NULL,
            series_code          TEXT NOT NULL,
            series_label         TEXT NOT NULL,
            geo_scope            TEXT NOT NULL,
            period_start         DATE NOT NULL,
            period_end           DATE NOT NULL,
            index_value          NUMERIC(12,4),
            base_period          TEXT,
            published_at         TIMESTAMPTZ,
            ingested_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            extraction_method    TEXT NOT NULL,
            evidence             JSONB,
            confidence           NUMERIC(3,2) NOT NULL,
            superseded_by        UUID REFERENCES obs.cpi_observation(observation_id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS cpi_current_uk
            ON obs.cpi_observation (natural_key) WHERE superseded_by IS NULL;

        CREATE TABLE IF NOT EXISTS obs.event (
            event_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_record_id     UUID NOT NULL REFERENCES meta.source_record(source_record_id),
            event_type           TEXT NOT NULL,
            title                TEXT NOT NULL,
            summary              TEXT,
            product_ids          UUID[] DEFAULT '{}',
            location_ids         UUID[] DEFAULT '{}',
            event_date           DATE,
            severity             SMALLINT,
            extraction_method    TEXT NOT NULL,
            evidence             JSONB,
            confidence           NUMERIC(3,2) NOT NULL,
            ingested_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    # ===================== ML =====================
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ml.model_run (
            model_run_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task                 TEXT NOT NULL,
            model_name           TEXT NOT NULL,
            model_version        TEXT NOT NULL,
            data_cutoff          DATE NOT NULL,
            trained_at           TIMESTAMPTZ NOT NULL,
            params               JSONB,
            metrics              JSONB
        );

        CREATE TABLE IF NOT EXISTS ml.forecast (
            forecast_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            model_run_id         UUID NOT NULL REFERENCES ml.model_run(model_run_id),
            series_key           TEXT NOT NULL,
            product_id           UUID NOT NULL REFERENCES ref.product(product_id),
            location_id          UUID REFERENCES ref.location(location_id),
            actor_level          TEXT NOT NULL,
            target_period        DATE NOT NULL,
            horizon              SMALLINT NOT NULL,
            p10                  NUMERIC(18,4),
            p50                  NUMERIC(18,4),
            p90                  NUMERIC(18,4),
            generated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    # ===================== OPS & DQ =====================
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ops.review_item (
            review_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            kind                 TEXT NOT NULL,
            source_record_id     UUID REFERENCES meta.source_record(source_record_id),
            payload              JSONB NOT NULL,
            status               TEXT NOT NULL DEFAULT 'open',
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            resolved_at          TIMESTAMPTZ,
            resolved_by          TEXT
        );

        CREATE TABLE IF NOT EXISTS ops.dq_result (
            dq_id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            check_name           TEXT NOT NULL,
            source_id            TEXT,
            asset_key            TEXT,
            passed               BOOLEAN NOT NULL,
            metric               NUMERIC,
            threshold            NUMERIC,
            details              JSONB,
            checked_at           TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE OR REPLACE VIEW dq.dq_result AS SELECT * FROM ops.dq_result;

        CREATE TABLE IF NOT EXISTS ops.alert (
            alert_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            rule_code            TEXT NOT NULL,
            dedupe_key           TEXT NOT NULL UNIQUE,
            severity             TEXT NOT NULL,
            product_id           UUID REFERENCES ref.product(product_id),
            location_id          UUID REFERENCES ref.location(location_id),
            title                TEXT NOT NULL,
            evidence             JSONB NOT NULL,
            state                TEXT NOT NULL DEFAULT 'open',
            first_seen_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_seen_at         TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS ops.bulletin (
            bulletin_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            period_start         DATE NOT NULL,
            period_end           DATE NOT NULL,
            status               TEXT NOT NULL DEFAULT 'draft',
            facts                JSONB NOT NULL,
            html_object_key      TEXT,
            pdf_object_key       TEXT,
            llm_call_id          UUID REFERENCES meta.llm_call(llm_call_id),
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            approved_by          TEXT,
            approved_at          TIMESTAMPTZ
        );
        """
    )

    # ===================== AUTH =====================
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS auth.user_account (
            user_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email                TEXT UNIQUE NOT NULL,
            password_hash        TEXT NOT NULL,
            role                 TEXT NOT NULL,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            disabled             BOOLEAN NOT NULL DEFAULT false
        );

        CREATE TABLE IF NOT EXISTS auth.api_key (
            api_key_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id              UUID NOT NULL REFERENCES auth.user_account(user_id),
            prefix               TEXT NOT NULL,
            key_hash             TEXT NOT NULL,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            revoked_at           TIMESTAMPTZ,
            last_used_at         TIMESTAMPTZ
        );
        """
    )

    # ===================== IMMUTABILITY / APPEND-ONLY TRIGGERS =====================
    # Enforces Bronze immutability and Silver obs append-only rules (SPECS §8.1)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION meta.check_source_record_immutable()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Deletions are forbidden on meta.source_record (Bronze immutability)';
            ELSIF TG_OP = 'UPDATE' THEN
                IF NEW.content_sha256 <> OLD.content_sha256 OR
                   NEW.source_id <> OLD.source_id OR
                   NEW.object_key <> OLD.object_key THEN
                    RAISE EXCEPTION 'Immutable fields cannot be altered on meta.source_record';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_source_record_immutable ON meta.source_record;
        CREATE TRIGGER trg_source_record_immutable
            BEFORE UPDATE OR DELETE ON meta.source_record
            FOR EACH ROW EXECUTE FUNCTION meta.check_source_record_immutable();

        CREATE OR REPLACE FUNCTION obs.check_obs_superseded_only()
        RETURNS TRIGGER AS $$
        DECLARE
            _new_copy RECORD;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Deletions are forbidden on obs tables (append-only architecture)';
            ELSIF TG_OP = 'UPDATE' THEN
                IF OLD.superseded_by IS NOT NULL THEN
                    RAISE EXCEPTION 'Obs record is already superseded and cannot be modified';
                END IF;
                IF NEW.superseded_by IS NULL THEN
                    RAISE EXCEPTION 'Obs tables only permit updating superseded_by column';
                END IF;
                _new_copy := NEW;
                _new_copy.superseded_by := OLD.superseded_by;
                IF (_new_copy IS DISTINCT FROM OLD) THEN
                    RAISE EXCEPTION 'Updates to data fields are forbidden on obs tables; only superseded_by can be updated';
                END IF;
                RETURN NEW;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_price_obs_superseded_only ON obs.price_observation;
        CREATE TRIGGER trg_price_obs_superseded_only
            BEFORE UPDATE OR DELETE ON obs.price_observation
            FOR EACH ROW EXECUTE FUNCTION obs.check_obs_superseded_only();

        DROP TRIGGER IF EXISTS trg_stock_obs_superseded_only ON obs.stock_observation;
        CREATE TRIGGER trg_stock_obs_superseded_only
            BEFORE UPDATE OR DELETE ON obs.stock_observation
            FOR EACH ROW EXECUTE FUNCTION obs.check_obs_superseded_only();

        DROP TRIGGER IF EXISTS trg_trade_flow_superseded_only ON obs.trade_flow;
        CREATE TRIGGER trg_trade_flow_superseded_only
            BEFORE UPDATE OR DELETE ON obs.trade_flow
            FOR EACH ROW EXECUTE FUNCTION obs.check_obs_superseded_only();

        DROP TRIGGER IF EXISTS trg_prod_obs_superseded_only ON obs.production_observation;
        CREATE TRIGGER trg_prod_obs_superseded_only
            BEFORE UPDATE OR DELETE ON obs.production_observation
            FOR EACH ROW EXECUTE FUNCTION obs.check_obs_superseded_only();

        DROP TRIGGER IF EXISTS trg_cpi_obs_superseded_only ON obs.cpi_observation;
        CREATE TRIGGER trg_cpi_obs_superseded_only
            BEFORE UPDATE OR DELETE ON obs.cpi_observation
            FOR EACH ROW EXECUTE FUNCTION obs.check_obs_superseded_only();
        """
    )

    # ===================== ROLES & PRIVILEGES =====================
    # SPECS §8: ketrika_app (R/W meta, ref, obs, ml, ops, auth, dq ; R gold)
    #           copilot_ro (SELECT strictly on gold only, statement_timeout=5s)
    op.execute(
        """
        GRANT USAGE ON SCHEMA meta, ref, obs, ml, ops, dq, gold, auth TO ketrika_app;
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA meta, ref, obs, ml, ops, dq, auth TO ketrika_app;
        GRANT SELECT ON ALL TABLES IN SCHEMA gold TO ketrika_app;
        GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA meta, ref, obs, ml, ops, dq, auth TO ketrika_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA meta, ref, obs, ml, ops, dq, auth GRANT ALL ON TABLES TO ketrika_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO ketrika_app;

        -- Copilot role strictly limited to SELECT on schema gold
        REVOKE ALL ON SCHEMA meta, ref, obs, ml, ops, dq, auth FROM copilot_ro;
        REVOKE ALL ON ALL TABLES IN SCHEMA meta, ref, obs, ml, ops, dq, auth FROM copilot_ro;
        GRANT USAGE ON SCHEMA gold TO copilot_ro;
        GRANT SELECT ON ALL TABLES IN SCHEMA gold TO copilot_ro;
        ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO copilot_ro;
        """
    )


def downgrade() -> None:
    # Drop triggers and functions
    op.execute("DROP TRIGGER IF EXISTS trg_cpi_obs_superseded_only ON obs.cpi_observation;")
    op.execute("DROP TRIGGER IF EXISTS trg_prod_obs_superseded_only ON obs.production_observation;")
    op.execute("DROP TRIGGER IF EXISTS trg_trade_flow_superseded_only ON obs.trade_flow;")
    op.execute("DROP TRIGGER IF EXISTS trg_stock_obs_superseded_only ON obs.stock_observation;")
    op.execute("DROP TRIGGER IF EXISTS trg_price_obs_superseded_only ON obs.price_observation;")
    op.execute("DROP FUNCTION IF EXISTS obs.check_obs_superseded_only();")

    op.execute("DROP TRIGGER IF EXISTS trg_source_record_immutable ON meta.source_record;")
    op.execute("DROP FUNCTION IF EXISTS meta.check_source_record_immutable();")

    # Drop views
    op.execute("DROP VIEW IF EXISTS dq.dq_result;")

    # Drop tables
    op.execute("DROP TABLE IF EXISTS auth.api_key CASCADE;")
    op.execute("DROP TABLE IF EXISTS auth.user_account CASCADE;")
    op.execute("DROP TABLE IF EXISTS ops.bulletin CASCADE;")
    op.execute("DROP TABLE IF EXISTS ops.alert CASCADE;")
    op.execute("DROP TABLE IF EXISTS ops.dq_result CASCADE;")
    op.execute("DROP TABLE IF EXISTS ops.review_item CASCADE;")
    op.execute("DROP TABLE IF EXISTS ml.forecast CASCADE;")
    op.execute("DROP TABLE IF EXISTS ml.model_run CASCADE;")
    op.execute("DROP TABLE IF EXISTS obs.event CASCADE;")
    op.execute("DROP TABLE IF EXISTS obs.cpi_observation CASCADE;")
    op.execute("DROP TABLE IF EXISTS obs.weather_observation CASCADE;")
    op.execute("DROP TABLE IF EXISTS obs.production_observation CASCADE;")
    op.execute("DROP TABLE IF EXISTS obs.trade_flow CASCADE;")
    op.execute("DROP TABLE IF EXISTS obs.stock_observation CASCADE;")
    op.execute("DROP TABLE IF EXISTS obs.price_observation CASCADE;")
    op.execute("DROP TABLE IF EXISTS ref.location_alias CASCADE;")
    op.execute("DROP TABLE IF EXISTS ref.location CASCADE;")
    op.execute("DROP TABLE IF EXISTS ref.unit_conversion CASCADE;")
    op.execute("DROP TABLE IF EXISTS ref.product_alias CASCADE;")
    op.execute("DROP TABLE IF EXISTS ref.product CASCADE;")
    op.execute("DROP TABLE IF EXISTS meta.llm_call CASCADE;")
    op.execute("DROP TABLE IF EXISTS meta.source_record CASCADE;")
    op.execute("DROP TABLE IF EXISTS meta.ingestion_run CASCADE;")
    op.execute("DROP TABLE IF EXISTS meta.source CASCADE;")
