"""Add append-only quarantine ledger, enforce anti-self-link guards and auditably repair historical links (ADR-133, AU-08)."""

from pathlib import Path

from alembic import op

revision = "0020_quarantine_ledger_and_anti_self_links"
down_revision = "0019_token_revocation"
branch_labels = None
depends_on = None

VALID_FORM_MISSING_HASHES = (
    "19cf0a8a38f84418a0a5a90f1e3d2d4b40a3ef31422b48e9903b6c23ecca8b44",
    "ebb9dcbf170a407691f6c8ea71cc6407e799c14e9305495e9f8ea09ae380caa0",
    "011658729f1e4a5cb6c48157648faca6cd162a5108174281bd9a46f85a993107",
    "18123df3051c491d8347ae7613b62a30ed90beea399a4c6d94ced20dd6fd1987",
    "4c08e6a9973c4940845f8859f540a32e543c28e8c72046ed8bc2266c9e7d66cf",
    "2bac94cb3c094032bbae3d781d0d6346f635f022bb0740d6860eb392038a7001",
    "4210d593d1ae44abaf1fd7eb59d48026f326dce33e37402283740fe8a1ad4d76",
    "e35057c579994cc6bd7bdb1e09f62123690b609961ae45bf9a530bb3ff1ab985",
    "f685fec9baa54b9baf3286024a275dca8475464a3a9d4fd4ada4cb9dbe061476",
    "8d5097a7c6e84b00810db5e6ef3db9dfeedb9371c1e34b2b99e85045046d9636",
    "8e0632ce459a4387a5b5a56f4ede7d36365ed57778714aaa9a70567c2eb83a5e",
    "fb62260789634f01bf69e16272b16c98eb5b41fc36144b0cbe1fbb545ad0b50e",
    "f80f1a335a674b409a9371389bd397c10be1e6240e414280855b31654311fca1",
    "5a54e9b914fb4a8cb5f5c8a925b7e259979b8dccdce5411e8994edc159022c4f",
    "c49c7c3bfbc1423bbcc0c1896fc0fb914361a3ddb0a74ad7a881a17a1dcbe0e1",
    "e9d1fbb0ccbe4b91abc45cf97cb8ecec2cfcc4a1b55248da938610137445df18",
    "338df25368bd413cb673b543bbae80d79c61c0c5146d47a5b30d08c7ba39b764",
    "5414160c213342a28c1a8642b95f01ed52373549e2f34e89b839a0587e08b1d3",
    "0f903a9b3c2d447d9187d846e1aa716dc3c36fabe19848cab99230a34a9783c3",
    "22ab6c7b058a4d72a8317e136268f23dcb84ddbec6bc4a9582009727eb434219",
    "91d87a36518840a79d098ab298dcd569c3b2ed636b4249d7a7f0e276a4bae147",
    "0f0d651fb26d4483b3b8129737272d07393b5621294c431e899cb4a6b6f02811",
    "a04fb23a127c4e2a98ce084930e67b62b506b5fd122f453898a6d86bf6126626",
    "84b4febdb9f34545b9aac093ffe09017750fa583a9e44563a4ca388890804fc3",
    "c869d8793931468489be017ac2da0b377ead7f74baea485bba93761f9bc342f0",
    "b5191760da66460fbac2149929f4c8aabf63e2ed14794b8aaa680147248f5a9b",
    "cfaedc512a3d4ea9aa008ed8fce67a51438bd391c2894570bfaee595320d3cf3",
    "22f6b56c213a4ea78185e855863c8cf0de2bc6418ef740c9bb33c823638db708",
    "6803c2a5261d4b7898369bfb6d3d7900fefb05f6dc9443d7ac7e49acf713edef",
    "49180dd424fc4f5fb8ffe5bee6e2f8c83c21b581e0a044cc8e8d7080ee53b03d",
    "e53a2a5c765f477c8ebf26ad7648f2a6deee5208840b4dbba3b7429af8406d2f",
    "9c5123dac6e84930a2a734d448d11f59af5c9f761a3a447eb5325f9647af3e04",
    "0a6e71ae14634ea6b47ba50f82d0665f75044d5a9b954a4b9f6c1379df328896",
    "c966798aeead4b2c9a47501aaa685421a9da0c5ff8704f4f8914f7724f475787",
    "cdc07b7090db4d07970568110176cf07553a08201ea64275b8fc0778576e9206",
)


def upgrade() -> None:
    # Fresh Alembic installations start with VARCHAR(32); retain this published ID.
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)")
    # 1. Create obs.quarantine_ledger
    op.execute("""
        CREATE TABLE IF NOT EXISTS obs.quarantine_ledger (
            quarantine_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            table_name VARCHAR(64) NOT NULL,
            observation_id UUID NOT NULL,
            source_record_id UUID REFERENCES meta.source_record(source_record_id),
            reason_code VARCHAR(64) NOT NULL,
            details JSONB NOT NULL DEFAULT '{}'::jsonb,
            operator VARCHAR(128) NOT NULL DEFAULT CURRENT_USER,
            quarantined_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
            revoked_at TIMESTAMPTZ,
            revocation_reason TEXT
        );

        CREATE UNIQUE INDEX IF NOT EXISTS uq_quarantine_active_entity
        ON obs.quarantine_ledger (table_name, observation_id)
        WHERE revoked_at IS NULL;

        CREATE INDEX IF NOT EXISTS idx_quarantine_reason
        ON obs.quarantine_ledger (reason_code);

        CREATE INDEX IF NOT EXISTS idx_quarantine_source_record
        ON obs.quarantine_ledger (source_record_id);

        CREATE INDEX IF NOT EXISTS idx_quarantine_entity
        ON obs.quarantine_ledger (table_name, observation_id);

        GRANT SELECT, INSERT, UPDATE ON obs.quarantine_ledger TO ketrika_app;
        GRANT SELECT ON obs.quarantine_ledger TO copilot_ro;
    """)

    # 2. Append-only trigger on obs.quarantine_ledger (prevent deletion, prohibit revocation of historical self-links)
    op.execute("""
        CREATE OR REPLACE FUNCTION obs.check_quarantine_ledger_append_only()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Deletions are forbidden on obs.quarantine_ledger (append-only architecture)';
            ELSIF TG_OP = 'UPDATE' THEN
                IF OLD.reason_code = 'HISTORICAL_SELF_LINK' THEN
                    RAISE EXCEPTION 'Quarantine for historical self-links is permanent and cannot be revoked';
                END IF;
                IF OLD.revoked_at IS NOT NULL THEN
                    RAISE EXCEPTION 'Quarantine record is already revoked and cannot be modified';
                END IF;
                IF NEW.revoked_at IS NULL THEN
                    RAISE EXCEPTION 'Quarantine ledger only permits updating revoked_at and revocation_reason';
                END IF;
                IF NEW.quarantine_id <> OLD.quarantine_id
                   OR NEW.table_name <> OLD.table_name
                   OR NEW.observation_id <> OLD.observation_id
                   OR NEW.source_record_id IS DISTINCT FROM OLD.source_record_id
                   OR NEW.reason_code <> OLD.reason_code
                   OR NEW.details IS DISTINCT FROM OLD.details
                   OR NEW.operator <> OLD.operator
                   OR NEW.quarantined_at <> OLD.quarantined_at THEN
                    RAISE EXCEPTION 'Updates to data fields are forbidden on obs.quarantine_ledger; only revoked_at and revocation_reason can be set';
                END IF;
                RETURN NEW;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_quarantine_ledger_append_only ON obs.quarantine_ledger;
        CREATE TRIGGER trg_quarantine_ledger_append_only
            BEFORE UPDATE OR DELETE ON obs.quarantine_ledger
            FOR EACH ROW EXECUTE FUNCTION obs.check_quarantine_ledger_append_only();
    """)

    # 3. Update obs.check_obs_superseded_only() with anti-self-link guard on INSERT and UPDATE
    op.execute("""
        CREATE OR REPLACE FUNCTION obs.check_obs_superseded_only()
        RETURNS TRIGGER AS $$
        DECLARE
            _new_copy RECORD;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.superseded_by IS NOT NULL AND NEW.superseded_by = NEW.observation_id THEN
                    RAISE EXCEPTION 'Self-supersession is forbidden: superseded_by cannot reference observation itself';
                END IF;
                RETURN NEW;
            ELSIF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Deletions are forbidden on obs tables (append-only architecture)';
            ELSIF TG_OP = 'UPDATE' THEN
                -- 1. Anti-self-supersession guard:
                IF NEW.superseded_by IS NOT NULL AND (NEW.superseded_by = OLD.observation_id OR NEW.superseded_by = NEW.observation_id) THEN
                    RAISE EXCEPTION 'Self-supersession is forbidden: superseded_by cannot reference observation itself';
                END IF;

                -- 2. If record was already legitimately superseded by another record:
                IF OLD.superseded_by IS NOT NULL AND OLD.superseded_by <> OLD.observation_id THEN
                    RAISE EXCEPTION 'Obs record is already superseded and cannot be modified';
                END IF;

                -- 3. If record had a historical self-link being repaired under quarantine:
                IF OLD.superseded_by IS NOT NULL AND OLD.superseded_by = OLD.observation_id THEN
                    IF NEW.superseded_by IS NOT NULL THEN
                        RAISE EXCEPTION 'Historical self-linked record can only be cleared to NULL under quarantine';
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM obs.quarantine_ledger q
                        WHERE q.table_name = TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME
                          AND q.observation_id = OLD.observation_id
                          AND q.revoked_at IS NULL
                    ) THEN
                        RAISE EXCEPTION 'Historical self-link cannot be cleared without an active quarantine ledger record';
                    END IF;
                ELSE
                    -- Normal supersession: superseded_by was NULL and must now be non-NULL
                    IF NEW.superseded_by IS NULL THEN
                        RAISE EXCEPTION 'Obs tables only permit updating superseded_by column';
                    END IF;
                END IF;

                -- 4. Check that no data fields were modified
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

        -- Recreate triggers on all observation tables to intercept INSERT, UPDATE and DELETE
        DROP TRIGGER IF EXISTS trg_price_obs_superseded_only ON obs.price_observation;
        CREATE TRIGGER trg_price_obs_superseded_only
            BEFORE INSERT OR UPDATE OR DELETE ON obs.price_observation
            FOR EACH ROW EXECUTE FUNCTION obs.check_obs_superseded_only();

        DROP TRIGGER IF EXISTS trg_stock_obs_superseded_only ON obs.stock_observation;
        CREATE TRIGGER trg_stock_obs_superseded_only
            BEFORE INSERT OR UPDATE OR DELETE ON obs.stock_observation
            FOR EACH ROW EXECUTE FUNCTION obs.check_obs_superseded_only();

        DROP TRIGGER IF EXISTS trg_trade_flow_superseded_only ON obs.trade_flow;
        CREATE TRIGGER trg_trade_flow_superseded_only
            BEFORE INSERT OR UPDATE OR DELETE ON obs.trade_flow
            FOR EACH ROW EXECUTE FUNCTION obs.check_obs_superseded_only();

        DROP TRIGGER IF EXISTS trg_prod_obs_superseded_only ON obs.production_observation;
        CREATE TRIGGER trg_prod_obs_superseded_only
            BEFORE INSERT OR UPDATE OR DELETE ON obs.production_observation
            FOR EACH ROW EXECUTE FUNCTION obs.check_obs_superseded_only();

        DROP TRIGGER IF EXISTS trg_cpi_obs_superseded_only ON obs.cpi_observation;
        CREATE TRIGGER trg_cpi_obs_superseded_only
            BEFORE INSERT OR UPDATE OR DELETE ON obs.cpi_observation
            FOR EACH ROW EXECUTE FUNCTION obs.check_obs_superseded_only();

        DROP TRIGGER IF EXISTS trg_weather_obs_superseded_only ON obs.weather_observation;
        CREATE TRIGGER trg_weather_obs_superseded_only
            BEFORE INSERT OR UPDATE OR DELETE ON obs.weather_observation
            FOR EACH ROW EXECUTE FUNCTION obs.check_obs_superseded_only();

        DROP TRIGGER IF EXISTS trg_macro_obs_superseded_only ON obs.macro_observation;
        CREATE TRIGGER trg_macro_obs_superseded_only
            BEFORE INSERT OR UPDATE OR DELETE ON obs.macro_observation
            FOR EACH ROW EXECUTE FUNCTION obs.check_obs_superseded_only();
    """)

    # 4. Ingest unverified Bronze SourceRecords into quarantine (B-R085 targeted: 129 non-sha256 + 35 valid missing)
    hashes_in_list = ", ".join(f"'{h}'" for h in VALID_FORM_MISSING_HASHES)
    op.execute(f"""
        INSERT INTO obs.quarantine_ledger (
            table_name,
            observation_id,
            source_record_id,
            reason_code,
            details,
            operator,
            quarantined_at
        )
        SELECT
            'meta.source_record',
            sr.source_record_id,
            sr.source_record_id,
            'MISSING_BRONZE_OBJECT',
            jsonb_build_object(
                'source_id', sr.source_id,
                'object_key', sr.object_key,
                'content_sha256', sr.content_sha256
            ),
            'migration_0020_quarantine',
            now()
        FROM meta.source_record sr
        WHERE sr.content_sha256 !~ '^[0-9a-f]{{64}}$'
           OR sr.content_sha256 IN ({hashes_in_list})
        ON CONFLICT DO NOTHING;
    """)

    # 5. Ingest historical self-links into quarantine and clear superseded_by under quarantine guard
    # price_observation
    op.execute("""
        INSERT INTO obs.quarantine_ledger (
            table_name,
            observation_id,
            source_record_id,
            reason_code,
            details,
            operator,
            quarantined_at
        )
        SELECT
            'obs.price_observation',
            po.observation_id,
            po.source_record_id,
            'HISTORICAL_SELF_LINK',
            jsonb_build_object(
                'natural_key', po.natural_key,
                'product_raw', po.product_raw,
                'location_raw', po.location_raw,
                'period_start', po.period_start,
                'period_end', po.period_end,
                'source_id', sr.source_id,
                'historical_superseded_by', po.superseded_by
            ),
            'migration_0020_quarantine',
            now()
        FROM obs.price_observation po
        JOIN meta.source_record sr ON po.source_record_id = sr.source_record_id
        WHERE po.superseded_by = po.observation_id
        ON CONFLICT DO NOTHING;

        UPDATE obs.price_observation
        SET superseded_by = NULL
        WHERE superseded_by = observation_id;
    """)

    # cpi_observation
    op.execute("""
        INSERT INTO obs.quarantine_ledger (
            table_name,
            observation_id,
            source_record_id,
            reason_code,
            details,
            operator,
            quarantined_at
        )
        SELECT
            'obs.cpi_observation',
            co.observation_id,
            co.source_record_id,
            'HISTORICAL_SELF_LINK',
            jsonb_build_object(
                'series_code', co.series_code,
                'period_start', co.period_start,
                'historical_superseded_by', co.superseded_by
            ),
            'migration_0020_quarantine',
            now()
        FROM obs.cpi_observation co
        WHERE co.superseded_by = co.observation_id
        ON CONFLICT DO NOTHING;

        UPDATE obs.cpi_observation
        SET superseded_by = NULL
        WHERE superseded_by = observation_id;
    """)

    # weather_observation
    op.execute("""
        INSERT INTO obs.quarantine_ledger (
            table_name,
            observation_id,
            source_record_id,
            reason_code,
            details,
            operator,
            quarantined_at
        )
        SELECT
            'obs.weather_observation',
            wo.observation_id,
            wo.source_record_id,
            'HISTORICAL_SELF_LINK',
            jsonb_build_object(
                'variable', wo.variable,
                'obs_date', wo.date,
                'historical_superseded_by', wo.superseded_by
            ),
            'migration_0020_quarantine',
            now()
        FROM obs.weather_observation wo
        WHERE wo.superseded_by = wo.observation_id
        ON CONFLICT DO NOTHING;

        UPDATE obs.weather_observation
        SET superseded_by = NULL
        WHERE superseded_by = observation_id;
    """)

    # production_observation
    op.execute("""
        INSERT INTO obs.quarantine_ledger (
            table_name,
            observation_id,
            source_record_id,
            reason_code,
            details,
            operator,
            quarantined_at
        )
        SELECT
            'obs.production_observation',
            pro.observation_id,
            pro.source_record_id,
            'HISTORICAL_SELF_LINK',
            jsonb_build_object(
                'product_raw', pro.product_raw,
                'element', pro.element,
                'period_start', pro.period_start,
                'historical_superseded_by', pro.superseded_by
            ),
            'migration_0020_quarantine',
            now()
        FROM obs.production_observation pro
        WHERE pro.superseded_by = pro.observation_id
        ON CONFLICT DO NOTHING;

        UPDATE obs.production_observation
        SET superseded_by = NULL
        WHERE superseded_by = observation_id;
    """)

    # trade_flow
    op.execute("""
        INSERT INTO obs.quarantine_ledger (
            table_name,
            observation_id,
            source_record_id,
            reason_code,
            details,
            operator,
            quarantined_at
        )
        SELECT
            'obs.trade_flow',
            tf.observation_id,
            tf.source_record_id,
            'HISTORICAL_SELF_LINK',
            jsonb_build_object(
                'flow', tf.flow,
                'period_start', tf.period_start,
                'historical_superseded_by', tf.superseded_by
            ),
            'migration_0020_quarantine',
            now()
        FROM obs.trade_flow tf
        WHERE tf.superseded_by = tf.observation_id
        ON CONFLICT DO NOTHING;

        UPDATE obs.trade_flow
        SET superseded_by = NULL
        WHERE superseded_by = observation_id;
    """)

    # stock_observation
    op.execute("""
        INSERT INTO obs.quarantine_ledger (
            table_name,
            observation_id,
            source_record_id,
            reason_code,
            details,
            operator,
            quarantined_at
        )
        SELECT
            'obs.stock_observation',
            so.observation_id,
            so.source_record_id,
            'HISTORICAL_SELF_LINK',
            jsonb_build_object(
                'stock_status', so.stock_status,
                'period_start', so.period_start,
                'historical_superseded_by', so.superseded_by
            ),
            'migration_0020_quarantine',
            now()
        FROM obs.stock_observation so
        WHERE so.superseded_by = so.observation_id
        ON CONFLICT DO NOTHING;

        UPDATE obs.stock_observation
        SET superseded_by = NULL
        WHERE superseded_by = observation_id;
    """)

    # 6. Ingest unprovenanced active observations into quarantine (SPECS §4, ADR-017, ADR-133)
    op.execute("""
        INSERT INTO obs.quarantine_ledger (
            table_name,
            observation_id,
            source_record_id,
            reason_code,
            details,
            operator,
            quarantined_at
        )
        SELECT
            'obs.price_observation',
            po.observation_id,
            po.source_record_id,
            'MISSING_PROVENANCE_PROOF',
            jsonb_build_object(
                'natural_key', po.natural_key,
                'product_raw', po.product_raw,
                'location_raw', po.location_raw,
                'period_start', po.period_start,
                'period_end', po.period_end,
                'source_id', sr.source_id
            ),
            'migration_0020_quarantine',
            now()
        FROM obs.price_observation po
        JOIN meta.source_record sr ON po.source_record_id = sr.source_record_id
        WHERE po.superseded_by IS NULL
          AND (po.evidence IS NULL OR po.evidence->'provenance' IS NULL)
        ON CONFLICT DO NOTHING;
    """)

    # 7. Redefine Gold materialized views with quarantine filtering
    gold_dir = Path(__file__).resolve().parent.parent.parent / "src" / "ketrika" / "gold" / "sql"
    if not gold_dir.exists():
        gold_dir = Path("/app/src/ketrika/gold/sql")

    views_to_refresh = (
        "001_price_obs_current.sql",
        "002_price_monthly.sql",
        "003_price_monthly_best.sql",
        "004_price_changes.sql",
        "010_market_health.sql",
        "005_stock_latest.sql",
        "006_trade_monthly.sql",
        "007_import_dependency.sql",
        "008_weather_monthly.sql",
        "009_cpi_food.sql",
    )
    for v in views_to_refresh:
        sql = (gold_dir / v).read_text(encoding="utf-8")
        op.execute(sql)

    op.execute("""
        GRANT USAGE ON SCHEMA gold TO ketrika_app, copilot_ro;
        GRANT SELECT ON ALL TABLES IN SCHEMA gold TO ketrika_app, copilot_ro;
        ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO ketrika_app, copilot_ro;
    """)


def downgrade() -> None:
    raise RuntimeError("Refusing to rollback audit quarantine ledger and anti-self-link guards")
