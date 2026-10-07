-- 007_import_dependency.sql
-- Grain: product × année
-- Contenu: imports / (production + imports − exports), avec production FAOSTAT et commerce Douanes ou FAOSTAT

DROP MATERIALIZED VIEW IF EXISTS gold.import_dependency CASCADE;

CREATE MATERIALIZED VIEW gold.import_dependency AS
WITH yearly_production AS (
    SELECT
        po.product_id,
        p.product_code,
        p.canonical_name_fr AS product_name,
        EXTRACT(YEAR FROM po.period_start)::integer AS year,
        sum(COALESCE(po.value, 0.0))::numeric(18,2) AS production_tonnes
    FROM obs.production_observation po
    LEFT JOIN ref.product p ON po.product_id = p.product_id
    WHERE po.superseded_by IS NULL
      AND po.element = 'production_t'
    GROUP BY po.product_id, p.product_code, p.canonical_name_fr, EXTRACT(YEAR FROM po.period_start)
),
yearly_trade AS (
    SELECT
        tf.product_id,
        p.product_code,
        p.canonical_name_fr AS product_name,
        EXTRACT(YEAR FROM tf.period_start)::integer AS year,
        sum(CASE WHEN tf.flow = 'import' THEN COALESCE(tf.weight_kg, 0.0) / 1000.0 ELSE 0.0 END)::numeric(18,2) AS import_tonnes,
        sum(CASE WHEN tf.flow = 'export' THEN COALESCE(tf.weight_kg, 0.0) / 1000.0 ELSE 0.0 END)::numeric(18,2) AS export_tonnes
    FROM obs.trade_flow tf
    LEFT JOIN ref.product p ON tf.product_id = p.product_id
    WHERE tf.superseded_by IS NULL
    GROUP BY tf.product_id, p.product_code, p.canonical_name_fr, EXTRACT(YEAR FROM tf.period_start)
),
combined_keys AS (
    SELECT product_id, product_code, product_name, year FROM yearly_production
    UNION
    SELECT product_id, product_code, product_name, year FROM yearly_trade
)
SELECT
    ck.product_id,
    ck.product_code,
    ck.product_name,
    ck.year,
    COALESCE(yp.production_tonnes, 0.0) AS production_tonnes,
    COALESCE(yt.import_tonnes, 0.0) AS import_tonnes,
    COALESCE(yt.export_tonnes, 0.0) AS export_tonnes,
    (COALESCE(yp.production_tonnes, 0.0) + COALESCE(yt.import_tonnes, 0.0) - COALESCE(yt.export_tonnes, 0.0))::numeric(18,2) AS net_availability_tonnes,
    CASE
        WHEN (COALESCE(yp.production_tonnes, 0.0) + COALESCE(yt.import_tonnes, 0.0) - COALESCE(yt.export_tonnes, 0.0)) > 0
        THEN round(
            (COALESCE(yt.import_tonnes, 0.0) /
            (COALESCE(yp.production_tonnes, 0.0) + COALESCE(yt.import_tonnes, 0.0) - COALESCE(yt.export_tonnes, 0.0)))::numeric,
            4
        )
        ELSE NULL
    END AS import_dependency_ratio
FROM combined_keys ck
LEFT JOIN yearly_production yp ON ck.product_id = yp.product_id AND ck.year = yp.year
LEFT JOIN yearly_trade yt ON ck.product_id = yt.product_id AND ck.year = yt.year;

CREATE INDEX idx_gold_import_dependency_filter
ON gold.import_dependency (product_id, year);
