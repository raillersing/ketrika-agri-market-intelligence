-- 009_cpi_food.sql
-- Grain: série × mois
-- Contenu: indices et variations

DROP MATERIALIZED VIEW IF EXISTS gold.cpi_food CASCADE;

CREATE MATERIALIZED VIEW gold.cpi_food AS
WITH ordered_cpi AS (
    SELECT
        co.observation_id,
        co.series_code,
        co.series_label,
        co.geo_scope,
        date_trunc('month', co.period_start)::date AS month,
        co.index_value,
        co.base_period,
        LAG(co.index_value, 1) OVER (
            PARTITION BY co.series_code, co.geo_scope
            ORDER BY co.period_start
        ) AS prev_index_1m,
        LAG(co.index_value, 12) OVER (
            PARTITION BY co.series_code, co.geo_scope
            ORDER BY co.period_start
        ) AS prev_index_12m
    FROM obs.cpi_observation co
    WHERE co.superseded_by IS NULL
)
SELECT
    series_code,
    series_label,
    geo_scope,
    month,
    index_value,
    base_period,
    CASE
        WHEN prev_index_1m IS NOT NULL AND prev_index_1m > 0
        THEN round(((index_value / prev_index_1m) - 1.0)::numeric, 4)
        ELSE NULL
    END AS chg_1m,
    CASE
        WHEN prev_index_12m IS NOT NULL AND prev_index_12m > 0
        THEN round(((index_value / prev_index_12m) - 1.0)::numeric, 4)
        ELSE NULL
    END AS chg_12m
FROM ordered_cpi
WITH NO DATA;

CREATE INDEX idx_gold_cpi_food_filter
ON gold.cpi_food (series_code, month);
