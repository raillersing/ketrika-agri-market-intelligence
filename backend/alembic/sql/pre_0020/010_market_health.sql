-- 010_market_health.sql
-- Grain: product × région × mois
-- Contenu: composantes + score (SPECS §16)

DROP MATERIALIZED VIEW IF EXISTS gold.market_health CASCADE;

CREATE MATERIALIZED VIEW gold.market_health AS
WITH price_comp AS (
    SELECT
        pc.product_id,
        pc.product_code,
        pc.product_name,
        pc.location_id,
        pc.location_pcode,
        pc.location_name,
        pc.month,
        pc.vol_12,
        CASE
            WHEN pc.vol_12 IS NOT NULL
            THEN round((100.0 * (1.0 - LEAST(pc.vol_12 / 0.30, 1.0)))::numeric, 2)
            ELSE NULL
        END AS score_stability,
        CASE
            WHEN pc.chg_12m IS NOT NULL
            THEN round(
                (100.0 * (1.0 - LEAST(GREATEST(pc.chg_12m, 0.0) / 0.40, 1.0)))::numeric,
                2
            )
            ELSE NULL
        END AS score_affordability
    FROM gold.price_changes pc
    WHERE pc.admin_level <= 2
),
stock_comp AS (
    SELECT
        sl.product_id,
        sl.location_id,
        sl.stock_status,
        CASE
            WHEN sl.stock_status = 'sufficient' THEN 100.0
            WHEN sl.stock_status = 'tight' THEN 50.0
            WHEN sl.stock_status = 'shortage' THEN 0.0
            ELSE NULL
        END::numeric(5,2) AS score_availability
    FROM gold.stock_latest sl
),
weather_comp AS (
    SELECT
        wm.location_id,
        wm.month,
        wm.rain_anom_3m,
        CASE
            WHEN wm.rain_anom_3m IS NOT NULL
            THEN round(
                (100.0 * (1.0 - LEAST(GREATEST(-wm.rain_anom_3m, 0.0) / 0.50, 1.0)))::numeric,
                2
            )
            ELSE NULL
        END AS score_climate
    FROM gold.weather_monthly wm
),
combined AS (
    SELECT
        p.product_id,
        p.product_code,
        p.product_name,
        p.location_id,
        p.location_pcode,
        p.location_name,
        p.month,
        p.score_stability,
        p.score_affordability,
        s.score_availability,
        w.score_climate,
        -- Calculate present weights
        (
            (CASE WHEN p.score_stability IS NOT NULL THEN 0.30 ELSE 0.0 END) +
            (CASE WHEN p.score_affordability IS NOT NULL THEN 0.25 ELSE 0.0 END) +
            (CASE WHEN s.score_availability IS NOT NULL THEN 0.25 ELSE 0.0 END) +
            (CASE WHEN w.score_climate IS NOT NULL THEN 0.20 ELSE 0.0 END)
        )::numeric(4,2) AS coverage,
        -- Weighted sum of available components
        (
            (CASE WHEN p.score_stability IS NOT NULL THEN p.score_stability * 0.30 ELSE 0.0 END) +
            (CASE WHEN p.score_affordability IS NOT NULL THEN p.score_affordability * 0.25 ELSE 0.0 END) +
            (CASE WHEN s.score_availability IS NOT NULL THEN s.score_availability * 0.25 ELSE 0.0 END) +
            (CASE WHEN w.score_climate IS NOT NULL THEN w.score_climate * 0.20 ELSE 0.0 END)
        )::numeric(8,2) AS weighted_sum
    FROM price_comp p
    LEFT JOIN stock_comp s ON p.product_id = s.product_id AND p.location_id = s.location_id
    LEFT JOIN weather_comp w ON p.location_id = w.location_id AND p.month = w.month
)
SELECT
    product_id,
    product_code,
    product_name,
    location_id,
    location_pcode,
    location_name,
    month,
    score_stability,
    score_affordability,
    score_availability,
    score_climate,
    coverage,
    CASE
        WHEN coverage >= 0.50 AND coverage > 0
        THEN round((weighted_sum / coverage)::numeric, 2)
        ELSE NULL
    END AS market_health_score
FROM combined
WITH NO DATA;

CREATE INDEX idx_gold_market_health_filter
ON gold.market_health (product_id, location_id, month);
