-- 009_cpi_food.sql
-- Grain: série × mois
-- Contenu: indices et variations

DROP MATERIALIZED VIEW IF EXISTS gold.cpi_food CASCADE;

CREATE MATERIALIZED VIEW gold.cpi_food AS
WITH current_cpi AS (
    SELECT
        co.observation_id,
        co.series_code,
        co.series_label,
        co.geo_scope,
        date_trunc('month', co.period_start)::date AS month,
        co.index_value,
        co.base_period
    FROM obs.cpi_observation co
    WHERE co.superseded_by IS NULL
      AND NOT EXISTS (
          SELECT 1 FROM obs.quarantine_ledger ql 
          WHERE (
              (ql.table_name = 'obs.cpi_observation' AND ql.observation_id = co.observation_id)
              OR (ql.table_name = 'meta.source_record' AND ql.source_record_id = co.source_record_id)
          )
          AND ql.revoked_at IS NULL
      )
)
SELECT
    c.series_code,
    c.series_label,
    c.geo_scope,
    c.month,
    c.index_value,
    c.base_period,
    CASE
        WHEN p1m.index_value IS NOT NULL AND p1m.index_value > 0
        THEN round(((c.index_value / p1m.index_value) - 1.0)::numeric, 4)
        ELSE NULL
    END AS chg_1m,
    CASE
        WHEN p12m.index_value IS NOT NULL AND p12m.index_value > 0
        THEN round(((c.index_value / p12m.index_value) - 1.0)::numeric, 4)
        ELSE NULL
    END AS chg_12m
FROM current_cpi c
LEFT JOIN current_cpi p1m ON (
    p1m.series_code = c.series_code
    AND p1m.geo_scope = c.geo_scope
    AND p1m.month = (c.month - INTERVAL '1 month')::date
)
LEFT JOIN current_cpi p12m ON (
    p12m.series_code = c.series_code
    AND p12m.geo_scope = c.geo_scope
    AND p12m.month = (c.month - INTERVAL '12 months')::date
)
WITH NO DATA;

CREATE INDEX idx_gold_cpi_food_filter
ON gold.cpi_food (series_code, month);
