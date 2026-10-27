"""Restore the complete quarantine-aware Gold graph without publishing caches (ADR134)."""

from pathlib import Path

from alembic import op

revision = "0021_gold_graph"
down_revision = "0020_quarantine_ledger_and_anti_self_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Restore the complete Gold graph
    definition = (Path(__file__).resolve().parents[1] / "sql/0021_gold_graph.sql").read_text(
        encoding="utf-8"
    )
    if definition.count("WITH NO DATA;") != 14:
        raise RuntimeError("gold_schema_requires_unpopulated_views")
    op.execute(definition)
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA gold TO ketrika_app, copilot_ro")

    # 2. Update functions and triggers to ensure anti-self-link on INSERT and non-revocable historical links
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
                IF NEW.superseded_by IS NOT NULL AND (NEW.superseded_by = OLD.observation_id OR NEW.superseded_by = NEW.observation_id) THEN
                    RAISE EXCEPTION 'Self-supersession is forbidden: superseded_by cannot reference observation itself';
                END IF;
                IF OLD.superseded_by IS NOT NULL AND OLD.superseded_by <> OLD.observation_id THEN
                    RAISE EXCEPTION 'Obs record is already superseded and cannot be modified';
                END IF;
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
                    IF NEW.superseded_by IS NULL THEN
                        RAISE EXCEPTION 'Obs tables only permit updating superseded_by column';
                    END IF;
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


def downgrade() -> None:
    raise RuntimeError("Refusing to restore an incomplete Gold graph")
