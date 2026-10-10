-- 003_price_monthly_best.sql
-- Grain: product × location × actor_level × mois
-- Contenu: Valeur retenue selon la priorité : P0 observé > P1 observé > P1 imputé > autres.
-- Colonne chosen_source_id

DROP MATERIALIZED VIEW IF EXISTS gold.price_monthly_best CASCADE;

CREATE MATERIALIZED VIEW gold.price_monthly_best AS
WITH ranked_prices AS (
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
        source_id AS chosen_source_id,
        priority,
        median_price,
        min_price,
        max_price,
        n_obs,
        imputed_share,
        CASE
            WHEN has_observed THEN 'observed'
            ELSE 'imputed'
        END AS observed_or_imputed,
        ROW_NUMBER() OVER (
            PARTITION BY product_id, location_id, actor_level, month
            ORDER BY
                CASE
                    WHEN priority = 'P0' AND has_observed THEN 1
                    WHEN priority = 'P1' AND has_observed THEN 2
                    WHEN priority = 'P0' AND NOT has_observed THEN 3
                    WHEN priority = 'P1' AND NOT has_observed THEN 4
                    WHEN priority = 'P2' AND has_observed THEN 5
                    WHEN priority = 'P2' AND NOT has_observed THEN 6
                    ELSE 7
                END ASC,
                n_obs DESC,
                source_id ASC
        ) AS rank_priority
    FROM gold.price_monthly
)
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
    chosen_source_id,
    priority,
    median_price,
    min_price,
    max_price,
    n_obs,
    imputed_share,
    observed_or_imputed
FROM ranked_prices
WHERE rank_priority = 1
WITH NO DATA;

CREATE UNIQUE INDEX idx_gold_price_monthly_best_pk
ON gold.price_monthly_best (product_id, location_id, actor_level, month);

CREATE INDEX idx_gold_price_monthly_best_source
ON gold.price_monthly_best (chosen_source_id, month);
