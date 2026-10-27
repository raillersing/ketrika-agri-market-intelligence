-- 013_market_coverage.sql
-- Grain: product × location × actor_level × month
-- Contenu: Matrice de couverture avec n_obs, sources, familles de sources, granularité admin_level, âge en jours et part imputée.

DROP MATERIALIZED VIEW IF EXISTS gold.market_coverage CASCADE;

CREATE MATERIALIZED VIEW gold.market_coverage AS
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
    count(DISTINCT source_id)::integer AS n_sources,
    count(DISTINCT source_family)::integer AS n_families,
    string_agg(DISTINCT source_id, ', ' ORDER BY source_id) AS sources,
    string_agg(DISTINCT source_family, ', ' ORDER BY source_family) AS source_families,
    sum(n_obs)::integer AS n_obs,
    round(avg(imputed_share)::numeric, 4) AS imputed_share,
    bool_or(has_observed) AS has_observed,
    CASE
        WHEN bool_or(has_observed) THEN 'observed'
        ELSE 'imputed'
    END AS observed_or_imputed,
    min(min_price)::numeric(18,2) AS min_price,
    max(max_price)::numeric(18,2) AS max_price,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY median_price)::numeric(18,2) AS median_price,
    (CURRENT_DATE - month)::integer AS age_days
FROM gold.price_monthly
GROUP BY
    product_id,
    product_code,
    product_name,
    location_id,
    location_pcode,
    location_name,
    admin_level,
    actor_level,
    month
WITH NO DATA;

CREATE INDEX idx_gold_market_coverage_lookup
ON gold.market_coverage (product_code, location_pcode, month);

CREATE INDEX idx_gold_market_coverage_location
ON gold.market_coverage (location_pcode, admin_level);
