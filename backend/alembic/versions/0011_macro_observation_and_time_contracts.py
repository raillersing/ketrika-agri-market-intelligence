"""Formalize time, origin, and macroeconomic contracts (ADR-069, SPECS §8, R2.1).

Revision ID: 0011_macro_observation_and_time_contracts
Revises: 0010_http_policy_budget
"""

from alembic import op

revision: str = "0011_macro_observation_and_time_contracts"
down_revision: str = "0010_http_policy_budget"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)")
    op.execute("""
    CREATE TABLE obs.macro_observation (
      observation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      source_record_id UUID NOT NULL REFERENCES meta.source_record(source_record_id),
      natural_key TEXT NOT NULL,
      indicator_code TEXT NOT NULL,
      indicator_name TEXT NOT NULL,
      frequency TEXT NOT NULL,
      unit TEXT NOT NULL,
      base_period TEXT,
      geo_scope TEXT NOT NULL DEFAULT 'national',
      period_start DATE NOT NULL,
      period_end DATE NOT NULL,
      published_at TIMESTAMPTZ,
      first_available_at TIMESTAMPTZ NOT NULL,
      ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      vintage TEXT NOT NULL DEFAULT 'final',
      value NUMERIC(20,4),
      value_raw TEXT,
      observed_or_imputed TEXT NOT NULL DEFAULT 'observed',
      extraction_method TEXT NOT NULL,
      evidence JSONB,
      confidence NUMERIC(3,2) NOT NULL,
      review_status TEXT NOT NULL DEFAULT 'accepted',
      superseded_by UUID REFERENCES obs.macro_observation(observation_id)
    );

    CREATE UNIQUE INDEX macro_obs_current_uk ON obs.macro_observation (natural_key)
      WHERE superseded_by IS NULL;

    CREATE INDEX idx_macro_obs_ind_geo_period ON obs.macro_observation
      (indicator_code, geo_scope, period_start);

    DROP TRIGGER IF EXISTS trg_macro_obs_superseded_only ON obs.macro_observation;
    CREATE TRIGGER trg_macro_obs_superseded_only
      BEFORE UPDATE OR DELETE ON obs.macro_observation
      FOR EACH ROW EXECUTE FUNCTION obs.check_obs_superseded_only();

    GRANT ALL PRIVILEGES ON obs.macro_observation TO ketrika_app;
    GRANT SELECT ON obs.macro_observation TO copilot_ro;
    """)


def downgrade() -> None:
    op.execute("""
    DROP TRIGGER IF EXISTS trg_macro_obs_superseded_only ON obs.macro_observation;
    DROP INDEX IF EXISTS obs.macro_obs_current_uk;
    DROP INDEX IF EXISTS obs.idx_macro_obs_ind_geo_period;
    DROP TABLE IF EXISTS obs.macro_observation CASCADE;
    """)
