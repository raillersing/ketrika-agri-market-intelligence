BEGIN READ ONLY;
SET LOCAL statement_timeout = '15s';
SELECT p.product_code,p.canonical_name_fr,p.verified,count(o.observation_id) AS current_price_rows,min(o.period_start) AS first_period,max(o.period_end) AS last_period FROM ref.product p LEFT JOIN obs.price_observation o ON o.product_id=p.product_id AND o.superseded_by IS NULL GROUP BY p.product_id,p.product_code,p.canonical_name_fr,p.verified ORDER BY p.product_code;
SELECT actor_level,observed_or_imputed,count(*) AS current_price_rows,min(period_start),max(period_end) FROM obs.price_observation WHERE superseded_by IS NULL GROUP BY actor_level,observed_or_imputed ORDER BY actor_level,observed_or_imputed;
SELECT 'cpi' AS kind,count(*) AS current_rows,min(period_start),max(period_end) FROM obs.cpi_observation WHERE superseded_by IS NULL UNION ALL SELECT 'macro',count(*),min(period_start),max(period_end) FROM obs.macro_observation WHERE superseded_by IS NULL;
SELECT indicator_code,review_status,observed_or_imputed,count(*) FROM obs.macro_observation WHERE superseded_by IS NULL GROUP BY indicator_code,review_status,observed_or_imputed ORDER BY indicator_code;
SELECT schemaname,matviewname,ispopulated FROM pg_matviews WHERE schemaname='gold' AND (matviewname LIKE '%economic%' OR matviewname LIKE '%price%') ORDER BY matviewname;
COMMIT;
