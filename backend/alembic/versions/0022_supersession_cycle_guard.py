"""Reject cyclic observation revisions, including concurrent writes (ADR140)."""

from alembic import op

revision = "0022_supersession_cycle_guard"
down_revision = "0021_gold_graph"
branch_labels = None
depends_on = None

TABLES = (
    "price_observation",
    "stock_observation",
    "trade_flow",
    "production_observation",
    "cpi_observation",
    "weather_observation",
    "macro_observation",
)


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION obs.check_supersession_acyclic()
        RETURNS TRIGGER AS $$
        DECLARE
            target UUID := NEW.superseded_by;
            visited UUID[] := ARRAY[NEW.observation_id];
        BEGIN
            IF TG_OP = 'UPDATE'
               AND OLD.superseded_by = OLD.observation_id
               AND NEW.superseded_by IS NULL THEN
                IF NOT EXISTS (
                    SELECT 1 FROM obs.quarantine_ledger q
                    WHERE q.table_name = TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME
                      AND q.observation_id = OLD.observation_id
                      AND q.source_record_id IS NOT DISTINCT FROM OLD.source_record_id
                      AND q.reason_code = 'HISTORICAL_SELF_LINK'
                      AND q.revoked_at IS NULL
                ) THEN
                    RAISE EXCEPTION 'Historical repair requires matching permanent quarantine'
                        USING ERRCODE = '23514';
                END IF;
            END IF;
            WHILE target IS NOT NULL LOOP
                IF target = ANY(visited) THEN
                    RAISE EXCEPTION 'Supersession cycle is forbidden'
                        USING ERRCODE = '23514';
                END IF;
                visited := array_append(visited, target);
                EXECUTE format(
                    'SELECT superseded_by FROM %I.%I WHERE observation_id = $1 FOR UPDATE',
                    TG_TABLE_SCHEMA, TG_TABLE_NAME
                ) INTO target USING target;
            END LOOP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    for table in TABLES:
        op.execute(f"""
            CREATE TRIGGER trg_zz_obs_supersession_cycle
                BEFORE INSERT OR UPDATE ON obs.{table}
                FOR EACH ROW EXECUTE FUNCTION obs.check_supersession_acyclic();
        """)


def downgrade() -> None:
    raise RuntimeError("Refusing to remove observation cycle protection")
