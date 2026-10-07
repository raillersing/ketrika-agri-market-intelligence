-- 001_price_obs_current.sql
-- Grain: observation
-- Contenu: Observations courantes, acceptées, converties, avec source_id, priority, observed_or_imputed

DROP MATERIALIZED VIEW IF EXISTS gold.price_obs_current CASCADE;

CREATE MATERIALIZED VIEW gold.price_obs_current AS
SELECT
    po.observation_id,
    sr.source_id,
    COALESCE(s.spec->>'priority', 'P1') AS priority,
    po.source_record_id,
    po.natural_key,
    po.product_id,
    p.product_code,
    p.canonical_name_fr AS product_name,
    po.product_raw,
    po.variety,
    po.quality_grade,
    po.location_id,
    loc.pcode AS location_pcode,
    loc.name AS location_name,
    loc.admin_level,
    po.location_raw,
    po.market_name,
    po.actor_level,
    po.period_start,
    po.period_end,
    date_trunc('month', po.period_start)::date AS month,
    po.published_at,
    po.price_raw,
    po.price_value,
    po.currency_raw,
    po.unit_raw,
    po.price_mga_per_base,
    po.base_unit,
    po.conversion_status,
    po.observed_or_imputed,
    po.missing_code,
    po.extraction_method,
    po.confidence,
    po.evidence,
    po.ingested_at
FROM obs.price_observation po
JOIN meta.source_record sr ON po.source_record_id = sr.source_record_id
LEFT JOIN meta.source s ON sr.source_id = s.source_id
LEFT JOIN ref.product p ON po.product_id = p.product_id
LEFT JOIN ref.location loc ON po.location_id = loc.location_id
WHERE po.superseded_by IS NULL
  AND po.review_status = 'accepted'
  AND po.price_mga_per_base IS NOT NULL;

CREATE INDEX idx_gold_price_obs_current_lookup
ON gold.price_obs_current (product_id, location_id, period_start);

CREATE INDEX idx_gold_price_obs_current_source
ON gold.price_obs_current (source_id, month);
