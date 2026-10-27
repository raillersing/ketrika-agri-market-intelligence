"""Add weather proof and append-only revisions without rewriting observations.

Revision ID: 0003_weather_provenance
Revises: 0002_gold_views
"""

from pathlib import Path

from sqlalchemy import text

from alembic import op

revision = "0003_weather_provenance"
down_revision = "0002_gold_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE obs.weather_observation
          ADD COLUMN location_raw TEXT,
          ADD COLUMN value_raw TEXT,
          ADD COLUMN evidence JSONB,
          ADD COLUMN extraction_method TEXT,
          ADD COLUMN superseded_by UUID REFERENCES obs.weather_observation(observation_id)
              DEFERRABLE INITIALLY DEFERRED;
        ALTER TABLE obs.weather_observation DROP CONSTRAINT uq_weather_obs;
        CREATE UNIQUE INDEX weather_current_uk ON obs.weather_observation
          (provider, location_id, date, variable) WHERE superseded_by IS NULL;
        CREATE TRIGGER trg_weather_obs_superseded_only
          BEFORE UPDATE OR DELETE ON obs.weather_observation
          FOR EACH ROW EXECUTE FUNCTION obs.check_obs_superseded_only();
    """)
    alembic_sql = Path(__file__).resolve().parents[1] / "sql"
    sql_dir = Path(__file__).resolve().parents[2] / "src/ketrika/gold/sql"
    weather_file = (
        alembic_sql / "008_weather_monthly_pre_0020.sql"
        if (alembic_sql / "008_weather_monthly_pre_0020.sql").is_file()
        else sql_dir / "008_weather_monthly.sql"
    )
    op.execute(weather_file.read_text(encoding="utf-8"))
    op.execute((sql_dir / "010_market_health.sql").read_text(encoding="utf-8"))
    op.execute(
        "GRANT SELECT ON gold.weather_monthly, gold.market_health TO ketrika_app, copilot_ro"
    )


def downgrade() -> None:
    populated = op.get_bind().scalar(
        text("""
        SELECT EXISTS(SELECT 1 FROM obs.weather_observation WHERE
          location_raw IS NOT NULL OR value_raw IS NOT NULL OR evidence IS NOT NULL
          OR extraction_method IS NOT NULL OR superseded_by IS NOT NULL)
    """)
    )
    if populated:
        raise RuntimeError(
            "Weather provenance downgrade refused: it would discard evidence/history"
        )
    op.execute("""
        DROP TRIGGER trg_weather_obs_superseded_only ON obs.weather_observation;
        DROP INDEX obs.weather_current_uk;
        ALTER TABLE obs.weather_observation
          DROP COLUMN location_raw,
          DROP COLUMN value_raw,
          DROP COLUMN evidence,
          DROP COLUMN extraction_method,
          DROP COLUMN superseded_by;
        ALTER TABLE obs.weather_observation ADD CONSTRAINT uq_weather_obs
          UNIQUE (provider, location_id, date, variable);
    """)
