-- 004_price_changes.sql
-- Grain: product × location × actor_level × mois
-- Contenu: variation m/m, sur 3 mois, a/a ; volatilité (MAD/médiane sur 12 mois) ; z-score robuste

DROP MATERIALIZED VIEW IF EXISTS gold.price_changes CASCADE;

CREATE MATERIALIZED VIEW gold.price_changes AS
WITH lagged_prices AS (
    SELECT
        b.product_id,
        b.product_code,
        b.product_name,
        b.location_id,
        b.location_pcode,
        b.location_name,
        b.admin_level,
        b.actor_level,
        b.month,
        b.chosen_source_id,
        b.median_price,
        LAG(b.median_price, 1) OVER (
            PARTITION BY b.product_id, b.location_id, b.actor_level
            ORDER BY b.month
        ) AS price_prev_1m,
        LAG(b.median_price, 3) OVER (
            PARTITION BY b.product_id, b.location_id, b.actor_level
            ORDER BY b.month
        ) AS price_prev_3m,
        LAG(b.median_price, 12) OVER (
            PARTITION BY b.product_id, b.location_id, b.actor_level
            ORDER BY b.month
        ) AS price_prev_12m
    FROM gold.price_monthly_best b
)
SELECT
    lp.product_id,
    lp.product_code,
    lp.product_name,
    lp.location_id,
    lp.location_pcode,
    lp.location_name,
    lp.admin_level,
    lp.actor_level,
    lp.month,
    lp.chosen_source_id,
    lp.median_price,
    CASE
        WHEN lp.price_prev_1m IS NOT NULL AND lp.price_prev_1m > 0
        THEN round(((lp.median_price / lp.price_prev_1m) - 1.0)::numeric, 4)
        ELSE NULL
    END AS chg_1m,
    CASE
        WHEN lp.price_prev_3m IS NOT NULL AND lp.price_prev_3m > 0
        THEN round(((lp.median_price / lp.price_prev_3m) - 1.0)::numeric, 4)
        ELSE NULL
    END AS chg_3m,
    CASE
        WHEN lp.price_prev_12m IS NOT NULL AND lp.price_prev_12m > 0
        THEN round(((lp.median_price / lp.price_prev_12m) - 1.0)::numeric, 4)
        ELSE NULL
    END AS chg_12m,
    m12.med_12,
    dev12.mad_12,
    CASE
        WHEN m12.med_12 IS NOT NULL AND m12.med_12 > 0
        THEN round((COALESCE(dev12.mad_12, 0.0) / m12.med_12)::numeric, 4)
        ELSE 0.0
    END AS vol_12,
    CASE
        WHEN dev12.mad_12 IS NOT NULL AND dev12.mad_12 > 0
        THEN round(((lp.median_price - m12.med_12) / (1.4826 * dev12.mad_12))::numeric, 4)
        ELSE 0.0
    END AS z_score_robust
FROM lagged_prices lp
LEFT JOIN LATERAL (
    SELECT
        percentile_cont(0.5) WITHIN GROUP (ORDER BY p12.median_price)::numeric(18,2) AS med_12
    FROM gold.price_monthly_best p12
    WHERE p12.product_id = lp.product_id
      AND p12.location_id = lp.location_id
      AND p12.actor_level = lp.actor_level
      AND p12.month <= lp.month
      AND p12.month >= (lp.month - INTERVAL '11 months')::date
) m12 ON true
LEFT JOIN LATERAL (
    SELECT
        percentile_cont(0.5) WITHIN GROUP (ORDER BY abs(p12.median_price - m12.med_12))::numeric(18,2) AS mad_12
    FROM gold.price_monthly_best p12
    WHERE p12.product_id = lp.product_id
      AND p12.location_id = lp.location_id
      AND p12.actor_level = lp.actor_level
      AND p12.month <= lp.month
      AND p12.month >= (lp.month - INTERVAL '11 months')::date
) dev12 ON true;

CREATE INDEX idx_gold_price_changes_filter
ON gold.price_changes (product_id, location_id, month);
