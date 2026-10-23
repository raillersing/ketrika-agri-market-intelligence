-- Read-only audit of the active baseline; never a repair or rebuild script.
BEGIN READ ONLY;
SELECT count(*) AS price_rows,
       count(*) FILTER (WHERE superseded_by = observation_id) AS self_supersessions,
       min(period_start) AS first_period, max(period_start) AS last_period
FROM obs.price_observation;
SELECT sr.source_id, po.observed_or_imputed, count(*) AS total,
       count(*) FILTER (WHERE po.superseded_by IS NULL) AS current_rows
FROM obs.price_observation po
JOIN meta.source_record sr USING (source_record_id)
GROUP BY sr.source_id, po.observed_or_imputed
ORDER BY sr.source_id, po.observed_or_imputed;
COMMIT;
