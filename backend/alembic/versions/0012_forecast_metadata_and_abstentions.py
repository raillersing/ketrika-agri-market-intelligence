"""Formalize price forecasting publication, metadata, and abstentions (ADR-078, SPECS §17, R3.7).

Revision ID: 0012_forecast_metadata_and_abstentions
Revises: 0011_macro_observation_and_time_contracts
"""

from alembic import op

revision: str = "0012_forecast_metadata_and_abstentions"
down_revision: str = "0011_macro_observation_and_time_contracts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE ml.forecast
      ADD COLUMN IF NOT EXISTS model_requested TEXT,
      ADD COLUMN IF NOT EXISTS model_effective TEXT,
      ADD COLUMN IF NOT EXISTS is_baseline BOOLEAN NOT NULL DEFAULT FALSE,
      ADD COLUMN IF NOT EXISTS is_calibrated BOOLEAN NOT NULL DEFAULT FALSE,
      ADD COLUMN IF NOT EXISTS calibration_sample_size INTEGER NOT NULL DEFAULT 0,
      ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'nominal',
      ADD COLUMN IF NOT EXISTS fallback_reason TEXT,
      ADD COLUMN IF NOT EXISTS currency TEXT NOT NULL DEFAULT 'MGA',
      ADD COLUMN IF NOT EXISTS unit TEXT NOT NULL DEFAULT 'kg',
      ADD COLUMN IF NOT EXISTS interval_width NUMERIC(18, 4),
      ADD COLUMN IF NOT EXISTS coverage_rate_80 NUMERIC(6, 4);

    -- Update materialized view gold.forecast_latest
    DROP MATERIALIZED VIEW IF EXISTS gold.forecast_latest CASCADE;

    CREATE MATERIALIZED VIEW gold.forecast_latest AS
    WITH latest_runs AS (
        SELECT
            f.forecast_id,
            f.series_key,
            f.product_id,
            p.product_code,
            p.canonical_name_fr AS product_name,
            f.location_id,
            loc.pcode AS location_pcode,
            loc.name AS location_name,
            f.actor_level,
            f.target_period,
            f.horizon,
            f.p10,
            f.p50,
            f.p90,
            f.model_requested,
            COALESCE(f.model_effective, mr.model_name) AS model_effective,
            f.is_baseline,
            f.is_calibrated,
            f.calibration_sample_size,
            f.status,
            f.fallback_reason,
            f.currency,
            f.unit,
            f.interval_width,
            f.coverage_rate_80,
            f.generated_at,
            mr.model_run_id,
            mr.model_name,
            mr.model_version,
            mr.data_cutoff,
            mr.trained_at,
            mr.params->>'dataset_fingerprint' AS dataset_fingerprint,
            mr.params->>'cohort' AS cohort,
            ROW_NUMBER() OVER (
                PARTITION BY f.series_key, f.horizon, f.target_period
                ORDER BY mr.trained_at DESC, f.generated_at DESC
            ) AS rn
        FROM ml.forecast f
        JOIN ml.model_run mr ON f.model_run_id = mr.model_run_id
        LEFT JOIN ref.product p ON f.product_id = p.product_id
        LEFT JOIN ref.location loc ON f.location_id = loc.location_id
    )
    SELECT
        forecast_id,
        model_run_id,
        series_key,
        product_id,
        product_code,
        product_name,
        location_id,
        location_pcode,
        location_name,
        actor_level,
        target_period,
        horizon,
        p10,
        p50,
        p90,
        model_requested,
        model_effective,
        is_baseline,
        is_calibrated,
        calibration_sample_size,
        status,
        fallback_reason,
        currency,
        unit,
        interval_width,
        coverage_rate_80,
        model_name,
        model_version,
        data_cutoff,
        trained_at,
        generated_at,
        dataset_fingerprint,
        cohort
    FROM latest_runs
    WHERE rn = 1
    WITH NO DATA;

    CREATE INDEX idx_gold_forecast_latest_series
    ON gold.forecast_latest (series_key, target_period);

    GRANT SELECT ON gold.forecast_latest TO ketrika_app;
    GRANT SELECT ON gold.forecast_latest TO copilot_ro;
    """)


def downgrade() -> None:
    op.execute("""
    DROP MATERIALIZED VIEW IF EXISTS gold.forecast_latest CASCADE;

    CREATE MATERIALIZED VIEW gold.forecast_latest AS
    WITH latest_runs AS (
        SELECT
            f.forecast_id,
            f.series_key,
            f.product_id,
            p.product_code,
            p.canonical_name_fr AS product_name,
            f.location_id,
            loc.pcode AS location_pcode,
            loc.name AS location_name,
            f.actor_level,
            f.target_period,
            f.horizon,
            f.p10,
            f.p50,
            f.p90,
            f.generated_at,
            mr.model_run_id,
            mr.model_name,
            mr.model_version,
            mr.data_cutoff,
            mr.trained_at,
            ROW_NUMBER() OVER (
                PARTITION BY f.series_key, f.horizon, f.target_period
                ORDER BY mr.trained_at DESC, f.generated_at DESC
            ) AS rn
        FROM ml.forecast f
        JOIN ml.model_run mr ON f.model_run_id = mr.model_run_id
        LEFT JOIN ref.product p ON f.product_id = p.product_id
        LEFT JOIN ref.location loc ON f.location_id = loc.location_id
    )
    SELECT
        forecast_id,
        model_run_id,
        series_key,
        product_id,
        product_code,
        product_name,
        location_id,
        location_pcode,
        location_name,
        actor_level,
        target_period,
        horizon,
        p10,
        p50,
        p90,
        model_name,
        model_version,
        data_cutoff,
        trained_at,
        generated_at
    FROM latest_runs
    WHERE rn = 1
    WITH NO DATA;

    CREATE INDEX idx_gold_forecast_latest_series
    ON gold.forecast_latest (series_key, target_period);

    ALTER TABLE ml.forecast
      DROP COLUMN IF EXISTS model_requested,
      DROP COLUMN IF EXISTS model_effective,
      DROP COLUMN IF EXISTS is_baseline,
      DROP COLUMN IF EXISTS is_calibrated,
      DROP COLUMN IF EXISTS calibration_sample_size,
      DROP COLUMN IF EXISTS status,
      DROP COLUMN IF EXISTS fallback_reason,
      DROP COLUMN IF EXISTS currency,
      DROP COLUMN IF EXISTS unit,
      DROP COLUMN IF EXISTS interval_width,
      DROP COLUMN IF EXISTS coverage_rate_80;
    """)
