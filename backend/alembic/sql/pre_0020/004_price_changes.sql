-- 004_price_changes.sql
-- Grain: product × location × actor_level × mois
-- Contenu: variation m/m, sur 3 mois, a/a ; volatilité (MAD/médiane sur 12 mois) ; z-score robuste

DROP MATERIALIZED VIEW IF EXISTS gold.price_changes CASCADE;

CREATE MATERIALIZED VIEW gold.price_changes AS
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
    CASE
        WHEN p1m.median_price IS NOT NULL AND p1m.median_price > 0
        THEN round(((b.median_price / p1m.median_price) - 1.0)::numeric, 4)
        ELSE NULL
    END AS chg_1m,
    CASE
        WHEN p3m.median_price IS NOT NULL AND p3m.median_price > 0
        THEN round(((b.median_price / p3m.median_price) - 1.0)::numeric, 4)
        ELSE NULL
    END AS chg_3m,
    CASE
        WHEN p12m.median_price IS NOT NULL AND p12m.median_price > 0
        THEN round(((b.median_price / p12m.median_price) - 1.0)::numeric, 4)
        ELSE NULL
    END AS chg_12m,
    m12.med_12,
    dev12.mad_12,
    CASE
        WHEN m12.med_12 IS NOT NULL AND m12.med_12 > 0
        THEN round((COALESCE(dev12.mad_12, 0.0) / m12.med_12)::numeric, 4)
        ELSE NULL
    END AS vol_12,
    CASE
        WHEN dev12.mad_12 IS NOT NULL AND dev12.mad_12 > 0 AND m12.med_12 IS NOT NULL
        THEN round(((b.median_price - m12.med_12) / (1.4826 * dev12.mad_12))::numeric, 4)
        ELSE 0.0
    END AS z_score_robust
FROM gold.price_monthly_best b
LEFT JOIN gold.price_monthly_best p1m ON (
    p1m.product_id = b.product_id
    AND p1m.location_id = b.location_id
    AND p1m.actor_level = b.actor_level
    AND p1m.month = (b.month - INTERVAL '1 month')::date
)
LEFT JOIN gold.price_monthly_best p3m ON (
    p3m.product_id = b.product_id
    AND p3m.location_id = b.location_id
    AND p3m.actor_level = b.actor_level
    AND p3m.month = (b.month - INTERVAL '3 months')::date
)
LEFT JOIN gold.price_monthly_best p12m ON (
    p12m.product_id = b.product_id
    AND p12m.location_id = b.location_id
    AND p12m.actor_level = b.actor_level
    AND p12m.month = (b.month - INTERVAL '12 months')::date
)
LEFT JOIN LATERAL (
    SELECT
        percentile_cont(0.5) WITHIN GROUP (ORDER BY p12.median_price)::numeric(18,2) AS med_12
    FROM gold.price_monthly_best p12
    WHERE p12.product_id = b.product_id
      AND p12.location_id = b.location_id
      AND p12.actor_level = b.actor_level
      AND p12.month <= b.month
      AND p12.month >= (b.month - INTERVAL '11 months')::date
) m12 ON true
LEFT JOIN LATERAL (
    SELECT
        percentile_cont(0.5) WITHIN GROUP (ORDER BY abs(p12.median_price - m12.med_12))::numeric(18,2) AS mad_12
    FROM gold.price_monthly_best p12
    WHERE p12.product_id = b.product_id
      AND p12.location_id = b.location_id
      AND p12.actor_level = b.actor_level
      AND p12.month <= b.month
      AND p12.month >= (b.month - INTERVAL '11 months')::date
) dev12 ON true
WITH NO DATA;

CREATE INDEX idx_gold_price_changes_filter
ON gold.price_changes (product_id, location_id, month);
