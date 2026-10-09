-- Read-only inventory. Source-ID/URL heuristics flag test evidence, not authenticity.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT source_id, count(*) AS records,
       count(*) FILTER (WHERE source_id ~ '^(dummy_|test_)') AS explicit_test_ids,
       count(*) FILTER (WHERE source_url ~ '^https?://(localhost|127[.]0[.]0[.]1|example[.]com|test[.]url)([:/]|$)') AS test_urls,
       count(*) FILTER (WHERE content_sha256 !~ '^[0-9a-f]{64}$') AS invalid_hashes,
       min(fetched_at) AS first_fetch, max(fetched_at) AS last_fetch
FROM meta.source_record GROUP BY source_id ORDER BY source_id;
SELECT count(*) AS source_records,
       count(*) FILTER (WHERE source_id ~ '^(dummy_|test_)') AS explicit_test_ids,
       count(*) FILTER (WHERE source_url ~ '^https?://(localhost|127[.]0[.]0[.]1|example[.]com|test[.]url)([:/]|$)') AS test_urls,
       count(*) FILTER (WHERE content_sha256 !~ '^[0-9a-f]{64}$') AS invalid_hashes
FROM meta.source_record;
SELECT count(*) AS prices,
       count(*) FILTER (WHERE s.source_record_id IS NULL) AS orphan_prices,
       count(*) FILTER (WHERE s.source_id ~ '^(dummy_|test_)') AS test_source_prices,
       count(*) FILTER (WHERE s.source_url ~ '^https?://(localhost|127[.]0[.]0[.]1|example[.]com|test[.]url)([:/]|$)') AS test_url_prices,
       count(*) FILTER (WHERE p.price_value < 0) AS negative_prices,
       count(*) FILTER (WHERE p.observed_or_imputed NOT IN ('observed','imputed')) AS invalid_value_kind,
       min(p.period_start), max(p.period_end), max(p.ingested_at)
FROM obs.price_observation p LEFT JOIN meta.source_record s USING (source_record_id);
SELECT observed_or_imputed, review_status, count(*) FROM obs.price_observation
GROUP BY observed_or_imputed, review_status ORDER BY observed_or_imputed, review_status;
SELECT 'source_record' AS relation, count(*),
       md5(coalesce(string_agg(source_record_id::text || ':' || content_sha256 || ':' || object_key, ',' ORDER BY source_record_id), '')) AS preservation_digest
FROM meta.source_record
UNION ALL SELECT 'price', count(*),
       md5(coalesce(string_agg(observation_id::text || ':' || to_jsonb(p)::text, ',' ORDER BY observation_id), ''))
FROM obs.price_observation p;
COMMIT;
