-- 006_trade_monthly.sql
-- Grain: product × flow × mois
-- Contenu: poids (t), valeur ; versions courantes uniquement

DROP MATERIALIZED VIEW IF EXISTS gold.trade_monthly;

CREATE MATERIALIZED VIEW gold.trade_monthly AS
SELECT
    COALESCE(tf.product_id, pa.product_id) AS product_id,
    COALESCE(p.product_code, p2.product_code) AS product_code,
    COALESCE(p.canonical_name_fr, p2.canonical_name_fr) AS product_name,
    tf.flow,
    date_trunc('month', tf.period_start)::date AS month,
    round((sum(COALESCE(tf.weight_kg, 0.0)) / 1000.0)::numeric, 3) AS weight_tonnes,
    round(sum(COALESCE(tf.value_mga, 0.0))::numeric, 2) AS value_mga,
    round(sum(COALESCE(tf.value_usd, 0.0))::numeric, 2) AS value_usd,
    count(*)::integer AS n_records
FROM obs.trade_flow tf
LEFT JOIN ref.product p ON tf.product_id = p.product_id
LEFT JOIN meta.source_record sr ON sr.source_record_id = tf.source_record_id
LEFT JOIN LATERAL (
    SELECT min(a.product_id::text)::uuid AS product_id
    FROM ref.product_alias a
    WHERE tf.product_id IS NULL
      AND (a.source_id IS NULL OR a.source_id = sr.source_id)
      AND (a.confidence >= 0.9 OR a.human_reviewed IS TRUE)
      AND (a.alias_display = tf.product_raw
           OR a.alias_norm = lower(trim(tf.product_raw)))
    HAVING count(DISTINCT a.product_id) = 1
) pa ON true
LEFT JOIN ref.product p2 ON pa.product_id = p2.product_id
WHERE tf.superseded_by IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM obs.quarantine_ledger ql 
      WHERE (
          (ql.table_name = 'obs.trade_flow' AND ql.observation_id = tf.observation_id)
          OR (ql.table_name = 'meta.source_record' AND ql.source_record_id = tf.source_record_id)
      )
      AND ql.revoked_at IS NULL
  )
GROUP BY
    COALESCE(tf.product_id, pa.product_id),
    COALESCE(p.product_code, p2.product_code),
    COALESCE(p.canonical_name_fr, p2.canonical_name_fr),
    tf.flow,
    date_trunc('month', tf.period_start)::date
WITH NO DATA;

CREATE INDEX idx_gold_trade_monthly_filter
ON gold.trade_monthly (product_id, flow, month);
