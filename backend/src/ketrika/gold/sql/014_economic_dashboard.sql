-- 014_economic_dashboard.sql
-- Grain: indicator_code × geo_scope × period_month
-- Contenu: tableau de bord économique consolidé par dimension autonome, avec variations calendaires exactes et traçabilité (R2.8, ADR-070)

DROP MATERIALIZED VIEW IF EXISTS gold.economic_dashboard CASCADE;

CREATE MATERIALIZED VIEW gold.economic_dashboard AS
WITH current_macro AS (
    SELECT
        m.indicator_code,
        m.indicator_name,
        CASE
            WHEN m.indicator_code LIKE 'EXCHANGE_RATE_%' OR m.indicator_code LIKE 'FX_%' OR m.indicator_code LIKE 'MONEY_SUPPLY_%' THEN 'exchange_rate'
            WHEN m.indicator_code LIKE 'FUEL_%' OR m.indicator_code LIKE 'ELECTRICITY_%' THEN 'fuel_energy'
            WHEN m.indicator_code LIKE 'RICE_IMPORT_%' OR m.indicator_code LIKE 'TRADE_%' THEN 'external_trade'
            WHEN m.indicator_code LIKE 'CPI_%' THEN 'inflation'
            ELSE 'real_activity'
        END AS dimension,
        m.geo_scope,
        m.frequency,
        m.unit,
        m.base_period,
        date_trunc('month', m.period_start)::date AS period_month,
        m.period_start,
        m.period_end,
        m.value,
        m.observed_or_imputed,
        sr.source_id,
        COALESCE(s.spec->>'source_family', sr.source_id) AS source_family
    FROM obs.macro_observation m
    JOIN meta.source_record sr ON m.source_record_id = sr.source_record_id
    LEFT JOIN meta.source s ON sr.source_id = s.source_id
    WHERE m.superseded_by IS NULL
)
SELECT
    cm.indicator_code,
    cm.indicator_name,
    cm.dimension,
    cm.geo_scope,
    cm.frequency,
    cm.unit,
    cm.base_period,
    cm.period_month,
    cm.period_start,
    cm.period_end,
    cm.value AS current_value,
    cm.observed_or_imputed,
    cm.source_id,
    cm.source_family,
    -- Variation calendaire sur 1 mois (rejet strict si rupture de base indiciaire)
    CASE
        WHEN p1m.value IS NOT NULL AND p1m.value > 0 AND (cm.base_period IS NOT DISTINCT FROM p1m.base_period)
        THEN round(((cm.value / p1m.value) - 1.0)::numeric, 4)
        ELSE NULL
    END AS chg_1m,
    -- Variation calendaire sur 12 mois (rejet strict si rupture de base indiciaire)
    CASE
        WHEN p12m.value IS NOT NULL AND p12m.value > 0 AND (cm.base_period IS NOT DISTINCT FROM p12m.base_period)
        THEN round(((cm.value / p12m.value) - 1.0)::numeric, 4)
        ELSE NULL
    END AS chg_12m
FROM current_macro cm
LEFT JOIN current_macro p1m ON (
    p1m.indicator_code = cm.indicator_code
    AND p1m.geo_scope = cm.geo_scope
    AND p1m.period_month = (cm.period_month - INTERVAL '1 month')::date
)
LEFT JOIN current_macro p12m ON (
    p12m.indicator_code = cm.indicator_code
    AND p12m.geo_scope = cm.geo_scope
    AND p12m.period_month = (cm.period_month - INTERVAL '12 months')::date
)
WITH NO DATA;

CREATE INDEX idx_gold_economic_dashboard_filter
ON gold.economic_dashboard (indicator_code, geo_scope, period_month);

CREATE INDEX idx_gold_economic_dashboard_dimension
ON gold.economic_dashboard (dimension, period_month);
