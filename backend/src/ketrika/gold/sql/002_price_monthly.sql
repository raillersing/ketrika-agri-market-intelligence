-- 002_price_monthly.sql
-- Grain: product × location (niveaux 1 et 2) × actor_level × mois × source
-- Contenu: médiane, min, max, n_obs, part imputée

DROP MATERIALIZED VIEW IF EXISTS gold.price_monthly CASCADE;

CREATE MATERIALIZED VIEW gold.price_monthly AS
SELECT
    product_id,
    product_code,
    product_name,
    location_id,
    location_pcode,
    location_name,
    admin_level,
    actor_level,
    month,
    source_id,
    priority,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY price_mga_per_base)::numeric(18,2) AS median_price,
    min(price_mga_per_base)::numeric(18,2) AS min_price,
    max(price_mga_per_base)::numeric(18,2) AS max_price,
    count(*)::integer AS n_obs,
    round(avg(CASE WHEN observed_or_imputed = 'imputed' THEN 1.0 ELSE 0.0 END)::numeric, 4) AS imputed_share,
    bool_or(observed_or_imputed = 'observed') AS has_observed
FROM gold.price_obs_current
WHERE product_id IS NOT NULL
  AND location_id IS NOT NULL
GROUP BY
    product_id,
    product_code,
    product_name,
    location_id,
    location_pcode,
    location_name,
    admin_level,
    actor_level,
    month,
    source_id,
    priority;

CREATE INDEX idx_gold_price_monthly_filter
ON gold.price_monthly (product_id, location_id, month);

CREATE INDEX idx_gold_price_monthly_source
ON gold.price_monthly (source_id, month);
