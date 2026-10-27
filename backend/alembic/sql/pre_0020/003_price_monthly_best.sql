-- 003_price_monthly_best.sql
-- Grain: product × location × actor_level × mois
-- Contenu: Valeur retenue selon la priorité : P0 observé > P1 observé > P1 imputé > autres.
-- Colonne chosen_source_id

DROP MATERIALIZED VIEW IF EXISTS gold.price_monthly_best CASCADE;

CREATE MATERIALIZED VIEW gold.price_monthly_best AS
WITH group_stats AS (
    SELECT
        product_id,
        location_id,
        actor_level,
        month,
        count(DISTINCT source_id)::integer AS n_sources,
        count(DISTINCT source_family)::integer AS n_families,
        min(min_price)::numeric(18,2) AS group_min_price,
        max(max_price)::numeric(18,2) AS group_max_price,
        (max(max_price) - min(min_price))::numeric(18,2) AS group_spread,
        CASE
            WHEN count(DISTINCT source_id) > 1
                 AND min(min_price) > 0
                 AND (max(max_price) / min(min_price)) >= 1.25
            THEN true
            ELSE false
        END AS has_conflict
    FROM gold.price_monthly
    GROUP BY product_id, location_id, actor_level, month
),
ranked_prices AS (
    SELECT
        pm.product_id,
        pm.product_code,
        pm.product_name,
        pm.location_id,
        pm.location_pcode,
        pm.location_name,
        pm.admin_level,
        pm.actor_level,
        pm.month,
        pm.source_id AS chosen_source_id,
        pm.source_family AS chosen_source_family,
        pm.priority,
        pm.median_price,
        pm.min_price,
        pm.max_price,
        pm.n_obs,
        pm.imputed_share,
        CASE
            WHEN pm.has_observed THEN 'observed'
            ELSE 'imputed'
        END AS observed_or_imputed,
        ROW_NUMBER() OVER (
            PARTITION BY pm.product_id, pm.location_id, pm.actor_level, pm.month
            ORDER BY
                CASE
                    WHEN pm.priority = 'P0' AND pm.has_observed THEN 1
                    WHEN pm.priority = 'P1' AND pm.has_observed THEN 2
                    WHEN pm.priority = 'P0' AND NOT pm.has_observed THEN 3
                    WHEN pm.priority = 'P1' AND NOT pm.has_observed THEN 4
                    WHEN pm.priority = 'P2' AND pm.has_observed THEN 5
                    WHEN pm.priority = 'P2' AND NOT pm.has_observed THEN 6
                    ELSE 7
                END ASC,
                pm.n_obs DESC,
                pm.source_id ASC
        ) AS rank_priority
    FROM gold.price_monthly pm
)
SELECT
    rp.product_id,
    rp.product_code,
    rp.product_name,
    rp.location_id,
    rp.location_pcode,
    rp.location_name,
    rp.admin_level,
    rp.actor_level,
    rp.month,
    rp.chosen_source_id,
    rp.chosen_source_family,
    rp.priority,
    rp.median_price,
    rp.min_price,
    rp.max_price,
    rp.n_obs,
    rp.imputed_share,
    rp.observed_or_imputed,
    gs.n_sources,
    gs.n_families,
    gs.has_conflict,
    gs.group_spread
FROM ranked_prices rp
JOIN group_stats gs ON (
    rp.product_id = gs.product_id
    AND rp.location_id = gs.location_id
    AND rp.actor_level = gs.actor_level
    AND rp.month = gs.month
)
WHERE rp.rank_priority = 1
WITH NO DATA;

CREATE UNIQUE INDEX idx_gold_price_monthly_best_pk
ON gold.price_monthly_best (product_id, location_id, actor_level, month);

CREATE INDEX idx_gold_price_monthly_best_source
ON gold.price_monthly_best (chosen_source_id, month);
