-- 005_stock_latest.sql
-- Grain: product × location
-- Contenu: dernier statut, tendance sur 3 observations

DROP MATERIALIZED VIEW IF EXISTS gold.stock_latest CASCADE;

CREATE MATERIALIZED VIEW gold.stock_latest AS
WITH ranked_stocks AS (
    SELECT
        so.observation_id,
        so.product_id,
        p.product_code,
        p.canonical_name_fr AS product_name,
        so.location_id,
        loc.pcode AS location_pcode,
        loc.name AS location_name,
        loc.admin_level,
        so.period_start,
        so.period_end,
        so.published_at,
        so.quantity_raw,
        so.quantity_value,
        so.unit_raw,
        so.quantity_base,
        so.base_unit,
        so.stock_status,
        so.coverage_days,
        ROW_NUMBER() OVER (
            PARTITION BY so.product_id, so.location_id
            ORDER BY so.period_end DESC, so.published_at DESC NULLS LAST, so.ingested_at DESC
        ) AS rn,
        LAG(so.coverage_days, 1) OVER (
            PARTITION BY so.product_id, so.location_id
            ORDER BY so.period_end ASC, so.published_at ASC NULLS LAST, so.ingested_at ASC
        ) AS prev_coverage_days
    FROM obs.stock_observation so
    LEFT JOIN ref.product p ON so.product_id = p.product_id
    LEFT JOIN ref.location loc ON so.location_id = loc.location_id
    WHERE so.superseded_by IS NULL
      AND so.product_id IS NOT NULL
      AND so.location_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM obs.quarantine_ledger ql 
          WHERE (
              (ql.table_name = 'obs.stock_observation' AND ql.observation_id = so.observation_id)
              OR (ql.table_name = 'meta.source_record' AND ql.source_record_id = so.source_record_id)
          )
          AND ql.revoked_at IS NULL
      )
)
SELECT
    product_id,
    product_code,
    product_name,
    location_id,
    location_pcode,
    location_name,
    admin_level,
    period_start,
    period_end,
    published_at,
    quantity_base,
    base_unit,
    stock_status,
    coverage_days,
    CASE
        WHEN prev_coverage_days IS NULL THEN 'stable'
        WHEN coverage_days > prev_coverage_days THEN 'improving'
        WHEN coverage_days < prev_coverage_days THEN 'declining'
        ELSE 'stable'
    END AS trend
FROM ranked_stocks
WHERE rn = 1
WITH NO DATA;

CREATE INDEX idx_gold_stock_latest_lookup
ON gold.stock_latest (product_id, location_id);
