-- 011_source_health.sql
-- Grain: source
-- Contenu: dernier run, statut, fraîcheur vs SLA, n_records sur 30 j, taux de parse, éléments de revue ouverts

DROP MATERIALIZED VIEW IF EXISTS gold.source_health CASCADE;

CREATE MATERIALIZED VIEW gold.source_health AS
WITH latest_run AS (
    SELECT
        ir.source_id,
        ir.run_id,
        ir.started_at,
        ir.finished_at,
        ir.status AS latest_run_status,
        ir.n_fetched,
        ir.n_records,
        ir.n_rejected,
        ir.n_review,
        ROW_NUMBER() OVER (PARTITION BY ir.source_id ORDER BY ir.started_at DESC) AS rn
    FROM meta.ingestion_run ir
),
all_time_records AS (
    SELECT
        sr.source_id,
        max(sr.fetched_at) AS last_fetched_at,
        count(CASE WHEN sr.fetched_at >= (now() - interval '30 days') THEN 1 END)::integer AS n_records_30d,
        round(
            (count(CASE WHEN sr.extraction_status = 'parsed' THEN 1 END)::numeric /
            NULLIF(count(*), 0)::numeric)::numeric,
            4
        ) AS parse_success_rate
    FROM meta.source_record sr
    GROUP BY sr.source_id
),
open_reviews AS (
    SELECT
        sr.source_id,
        count(ri.review_id)::integer AS open_review_items
    FROM ops.review_item ri
    JOIN meta.source_record sr ON ri.source_record_id = sr.source_record_id
    WHERE ri.status = 'open'
    GROUP BY sr.source_id
)
SELECT
    s.source_id,
    s.status AS source_status,
    s.spec->>'name' AS source_name,
    COALESCE(s.spec->>'priority', 'P1') AS priority,
    (s.spec->>'freshness_sla_days')::integer AS freshness_sla_days,
    lr.latest_run_status,
    lr.started_at AS last_run_started_at,
    lr.finished_at AS last_run_finished_at,
    COALESCE(atr.n_records_30d, 0) AS n_records_30d,
    atr.last_fetched_at,
    EXTRACT(DAY FROM (now() - atr.last_fetched_at))::integer AS freshness_days,
    CASE
        WHEN s.spec->>'freshness_sla_days' IS NOT NULL AND atr.last_fetched_at IS NOT NULL
        THEN (EXTRACT(DAY FROM (now() - atr.last_fetched_at)) > (s.spec->>'freshness_sla_days')::integer)
        WHEN atr.last_fetched_at IS NULL THEN true
        ELSE false
    END AS is_stale,
    COALESCE(atr.parse_success_rate, 1.0) AS parse_success_rate,
    COALESCE(rev.open_review_items, 0) AS open_review_items
FROM meta.source s
LEFT JOIN latest_run lr ON s.source_id = lr.source_id AND lr.rn = 1
LEFT JOIN all_time_records atr ON s.source_id = atr.source_id
LEFT JOIN open_reviews rev ON s.source_id = rev.source_id
WITH NO DATA;

CREATE INDEX idx_gold_source_health_source
ON gold.source_health (source_id);
