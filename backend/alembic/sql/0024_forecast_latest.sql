-- 012_forecast_latest.sql
-- Grain: série × horizon
-- Contenu: dernier model_run pour chaque série avec métadonnées conformes (ADR-078)

DROP MATERIALIZED VIEW IF EXISTS gold.forecast_latest;

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
    WHERE NOT EXISTS (
        SELECT 1 FROM obs.quarantine_ledger ql
        WHERE ql.table_name = 'ml.forecast'
          AND ql.observation_id = f.forecast_id
          AND ql.revoked_at IS NULL
    )
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
