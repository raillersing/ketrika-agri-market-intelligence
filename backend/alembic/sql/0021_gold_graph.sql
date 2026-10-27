-- 001_price_obs_current.sql
-- Grain: observation
-- Contenu: Observations courantes, acceptées, converties, avec source_id, priority, observed_or_imputed

DROP MATERIALIZED VIEW IF EXISTS gold.price_obs_current CASCADE;

CREATE MATERIALIZED VIEW gold.price_obs_current AS
SELECT
    po.observation_id,
    sr.source_id,
    COALESCE(s.spec->>'priority', 'P1') AS priority,
    COALESCE(s.spec->>'source_family', sr.source_id) AS source_family,
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
  AND po.price_mga_per_base IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM obs.quarantine_ledger ql
      WHERE (
          (ql.table_name = 'obs.price_observation' AND ql.observation_id = po.observation_id)
          OR (ql.table_name = 'meta.source_record' AND ql.source_record_id = po.source_record_id)
      )
      AND ql.revoked_at IS NULL
  )
WITH NO DATA;

CREATE INDEX idx_gold_price_obs_current_lookup
ON gold.price_obs_current (product_id, location_id, period_start);

CREATE INDEX idx_gold_price_obs_current_source
ON gold.price_obs_current (source_id, month);

-- 002_price_monthly.sql
-- Grain: product × location (niveaux 1 et 2) × actor_level × mois × source
-- Contenu: médiane, min, max, n_obs, part imputée

DROP MATERIALIZED VIEW IF EXISTS gold.price_monthly CASCADE;

CREATE MATERIALIZED VIEW gold.price_monthly AS
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
    source_id,
    source_family,
    priority,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY price_mga_per_base)::numeric(18,2) AS median_price,
    min(price_mga_per_base)::numeric(18,2) AS min_price,
    max(price_mga_per_base)::numeric(18,2) AS max_price,
    (max(price_mga_per_base) - min(price_mga_per_base))::numeric(18,2) AS price_spread,
    stddev_samp(price_mga_per_base)::numeric(18,2) AS stddev_price,
    count(*)::integer AS n_obs,
    round(avg(CASE WHEN observed_or_imputed = 'imputed' THEN 1.0 ELSE 0.0 END)::numeric, 4) AS imputed_share,
    bool_or(observed_or_imputed = 'observed') AS has_observed
FROM gold.price_obs_current
WHERE product_id IS NOT NULL
  AND location_id IS NOT NULL
GROUP BY
    product_id,
    product_code,
    product_name,
    location_id,
    location_pcode,
    location_name,
    admin_level,
    actor_level,
    month,
    source_id,
    source_family,
    priority
WITH NO DATA;

CREATE INDEX idx_gold_price_monthly_filter
ON gold.price_monthly (product_id, location_id, month);

CREATE INDEX idx_gold_price_monthly_source
ON gold.price_monthly (source_id, month);

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

-- 004_price_changes.sql
-- Grain: product × location × actor_level × mois
-- Contenu: variation m/m, sur 3 mois, a/a ; volatilité (MAD/médiane sur 12 mois) ; z-score robuste

DROP MATERIALIZED VIEW IF EXISTS gold.price_changes CASCADE;

CREATE MATERIALIZED VIEW gold.price_changes AS
SELECT
    b.product_id,
    b.product_code,
    b.product_name,
    b.location_id,
    b.location_pcode,
    b.location_name,
    b.admin_level,
    b.actor_level,
    b.month,
    b.chosen_source_id,
    b.median_price,
    CASE
        WHEN p1m.median_price IS NOT NULL AND p1m.median_price > 0
        THEN round(((b.median_price / p1m.median_price) - 1.0)::numeric, 4)
        ELSE NULL
    END AS chg_1m,
    CASE
        WHEN p3m.median_price IS NOT NULL AND p3m.median_price > 0
        THEN round(((b.median_price / p3m.median_price) - 1.0)::numeric, 4)
        ELSE NULL
    END AS chg_3m,
    CASE
        WHEN p12m.median_price IS NOT NULL AND p12m.median_price > 0
        THEN round(((b.median_price / p12m.median_price) - 1.0)::numeric, 4)
        ELSE NULL
    END AS chg_12m,
    m12.med_12,
    dev12.mad_12,
    CASE
        WHEN m12.med_12 IS NOT NULL AND m12.med_12 > 0
        THEN round((COALESCE(dev12.mad_12, 0.0) / m12.med_12)::numeric, 4)
        ELSE NULL
    END AS vol_12,
    CASE
        WHEN dev12.mad_12 IS NOT NULL AND dev12.mad_12 > 0 AND m12.med_12 IS NOT NULL
        THEN round(((b.median_price - m12.med_12) / (1.4826 * dev12.mad_12))::numeric, 4)
        ELSE 0.0
    END AS z_score_robust
FROM gold.price_monthly_best b
LEFT JOIN gold.price_monthly_best p1m ON (
    p1m.product_id = b.product_id
    AND p1m.location_id = b.location_id
    AND p1m.actor_level = b.actor_level
    AND p1m.month = (b.month - INTERVAL '1 month')::date
)
LEFT JOIN gold.price_monthly_best p3m ON (
    p3m.product_id = b.product_id
    AND p3m.location_id = b.location_id
    AND p3m.actor_level = b.actor_level
    AND p3m.month = (b.month - INTERVAL '3 months')::date
)
LEFT JOIN gold.price_monthly_best p12m ON (
    p12m.product_id = b.product_id
    AND p12m.location_id = b.location_id
    AND p12m.actor_level = b.actor_level
    AND p12m.month = (b.month - INTERVAL '12 months')::date
)
LEFT JOIN LATERAL (
    SELECT
        percentile_cont(0.5) WITHIN GROUP (ORDER BY p12.median_price)::numeric(18,2) AS med_12
    FROM gold.price_monthly_best p12
    WHERE p12.product_id = b.product_id
      AND p12.location_id = b.location_id
      AND p12.actor_level = b.actor_level
      AND p12.month <= b.month
      AND p12.month >= (b.month - INTERVAL '11 months')::date
) m12 ON true
LEFT JOIN LATERAL (
    SELECT
        percentile_cont(0.5) WITHIN GROUP (ORDER BY abs(p12.median_price - m12.med_12))::numeric(18,2) AS mad_12
    FROM gold.price_monthly_best p12
    WHERE p12.product_id = b.product_id
      AND p12.location_id = b.location_id
      AND p12.actor_level = b.actor_level
      AND p12.month <= b.month
      AND p12.month >= (b.month - INTERVAL '11 months')::date
) dev12 ON true
WITH NO DATA;

CREATE INDEX idx_gold_price_changes_filter
ON gold.price_changes (product_id, location_id, month);

-- 005_stock_latest.sql
-- Grain: product × location
-- Contenu: dernier statut, tendance sur 3 observations

DROP MATERIALIZED VIEW IF EXISTS gold.stock_latest CASCADE;

CREATE MATERIALIZED VIEW gold.stock_latest AS
WITH ranked_stocks AS (
    SELECT
        so.observation_id,
        so.product_id,
        p.product_code,
        p.canonical_name_fr AS product_name,
        so.location_id,
        loc.pcode AS location_pcode,
        loc.name AS location_name,
        loc.admin_level,
        so.period_start,
        so.period_end,
        so.published_at,
        so.quantity_raw,
        so.quantity_value,
        so.unit_raw,
        so.quantity_base,
        so.base_unit,
        so.stock_status,
        so.coverage_days,
        ROW_NUMBER() OVER (
            PARTITION BY so.product_id, so.location_id
            ORDER BY so.period_end DESC, so.published_at DESC NULLS LAST, so.ingested_at DESC
        ) AS rn,
        LAG(so.coverage_days, 1) OVER (
            PARTITION BY so.product_id, so.location_id
            ORDER BY so.period_end ASC, so.published_at ASC NULLS LAST, so.ingested_at ASC
        ) AS prev_coverage_days
    FROM obs.stock_observation so
    LEFT JOIN ref.product p ON so.product_id = p.product_id
    LEFT JOIN ref.location loc ON so.location_id = loc.location_id
    WHERE so.superseded_by IS NULL
      AND so.product_id IS NOT NULL
      AND so.location_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM obs.quarantine_ledger ql
          WHERE (
              (ql.table_name = 'obs.stock_observation' AND ql.observation_id = so.observation_id)
              OR (ql.table_name = 'meta.source_record' AND ql.source_record_id = so.source_record_id)
          )
          AND ql.revoked_at IS NULL
      )
)
SELECT
    product_id,
    product_code,
    product_name,
    location_id,
    location_pcode,
    location_name,
    admin_level,
    period_start,
    period_end,
    published_at,
    quantity_base,
    base_unit,
    stock_status,
    coverage_days,
    CASE
        WHEN prev_coverage_days IS NULL THEN 'stable'
        WHEN coverage_days > prev_coverage_days THEN 'improving'
        WHEN coverage_days < prev_coverage_days THEN 'declining'
        ELSE 'stable'
    END AS trend
FROM ranked_stocks
WHERE rn = 1
WITH NO DATA;

CREATE INDEX idx_gold_stock_latest_lookup
ON gold.stock_latest (product_id, location_id);

-- 006_trade_monthly.sql
-- Grain: product × flow × mois
-- Contenu: poids (t), valeur ; versions courantes uniquement

DROP MATERIALIZED VIEW IF EXISTS gold.trade_monthly CASCADE;

CREATE MATERIALIZED VIEW gold.trade_monthly AS
SELECT
    tf.product_id,
    p.product_code,
    p.canonical_name_fr AS product_name,
    tf.flow,
    date_trunc('month', tf.period_start)::date AS month,
    round((sum(COALESCE(tf.weight_kg, 0.0)) / 1000.0)::numeric, 3) AS weight_tonnes,
    round(sum(COALESCE(tf.value_mga, 0.0))::numeric, 2) AS value_mga,
    round(sum(COALESCE(tf.value_usd, 0.0))::numeric, 2) AS value_usd,
    count(*)::integer AS n_records
FROM obs.trade_flow tf
LEFT JOIN ref.product p ON tf.product_id = p.product_id
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
    tf.product_id,
    p.product_code,
    p.canonical_name_fr,
    tf.flow,
    date_trunc('month', tf.period_start)::date
WITH NO DATA;

CREATE INDEX idx_gold_trade_monthly_filter
ON gold.trade_monthly (product_id, flow, month);

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
      AND NOT EXISTS (
          SELECT 1 FROM obs.quarantine_ledger ql
          WHERE (
              (ql.table_name = 'obs.production_observation' AND ql.observation_id = po.observation_id)
              OR (ql.table_name = 'meta.source_record' AND ql.source_record_id = po.source_record_id)
          )
          AND ql.revoked_at IS NULL
      )
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
      AND NOT EXISTS (
          SELECT 1 FROM obs.quarantine_ledger ql
          WHERE (
              (ql.table_name = 'obs.trade_flow' AND ql.observation_id = tf.observation_id)
              OR (ql.table_name = 'meta.source_record' AND ql.source_record_id = tf.source_record_id)
          )
          AND ql.revoked_at IS NULL
      )
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
LEFT JOIN yearly_trade yt ON ck.product_id = yt.product_id AND ck.year = yt.year
WITH NO DATA;

CREATE INDEX idx_gold_import_dependency_filter
ON gold.import_dependency (product_id, year);

-- 008_weather_monthly.sql
-- Grain: district × mois
-- Contenu: precipitation and temperature; baseline uses available calendar-month history, not a qualified 1991-2020 normal

DROP MATERIALIZED VIEW IF EXISTS gold.weather_monthly CASCADE;

CREATE MATERIALIZED VIEW gold.weather_monthly AS
WITH monthly_aggregates AS (
    SELECT
        wo.location_id,
        loc.pcode AS location_pcode,
        loc.name AS location_name,
        date_trunc('month', wo.date)::date AS month,
        EXTRACT(MONTH FROM wo.date)::integer AS cal_month,
        round(sum(CASE WHEN wo.variable = 'precip_mm' THEN wo.value ELSE NULL END)::numeric, 2) AS precip_total_mm,
        round(avg(CASE WHEN wo.variable = 't2m_max_c' THEN wo.value END)::numeric, 2) AS t2m_max_avg_c,
        round(avg(CASE WHEN wo.variable = 't2m_min_c' THEN wo.value END)::numeric, 2) AS t2m_min_avg_c,
        round(avg(CASE WHEN wo.variable = 'rh2m_pct' THEN wo.value END)::numeric, 2) AS rh2m_avg_pct
    FROM obs.weather_observation wo
    LEFT JOIN ref.location loc ON wo.location_id = loc.location_id
    WHERE to_jsonb(wo)->>'superseded_by' IS NULL
      AND NOT EXISTS (
          SELECT 1 FROM obs.quarantine_ledger ql
          WHERE (
              (ql.table_name = 'obs.weather_observation' AND ql.observation_id = wo.observation_id)
              OR (ql.table_name = 'meta.source_record' AND ql.source_record_id = wo.source_record_id)
          )
          AND ql.revoked_at IS NULL
      )
    GROUP BY
        wo.location_id,
        loc.pcode,
        loc.name,
        date_trunc('month', wo.date)::date,
        EXTRACT(MONTH FROM wo.date)
),
with_climatology AS (
    SELECT
        ma.*,
        avg(ma.precip_total_mm) OVER (
            PARTITION BY ma.location_id, ma.cal_month
        )::numeric(10,2) AS baseline_precip_mm
    FROM monthly_aggregates ma
)
SELECT
    wc.location_id,
    wc.location_pcode,
    wc.location_name,
    wc.month,
    wc.precip_total_mm,
    wc.baseline_precip_mm,
    wc.t2m_max_avg_c,
    wc.t2m_min_avg_c,
    wc.rh2m_avg_pct,
    CASE
        WHEN wc.baseline_precip_mm > 0
        THEN round(((wc.precip_total_mm - wc.baseline_precip_mm) / wc.baseline_precip_mm)::numeric, 4)
        ELSE NULL
    END AS rain_anom_pct,
    round(
        avg(
            CASE
                WHEN wc.baseline_precip_mm > 0
                THEN (wc.precip_total_mm - wc.baseline_precip_mm) / wc.baseline_precip_mm
                ELSE NULL
            END
        ) OVER (
            PARTITION BY wc.location_id
            ORDER BY wc.month
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        )::numeric,
        4
    ) AS rain_anom_3m
FROM with_climatology wc
WITH NO DATA;

CREATE INDEX idx_gold_weather_monthly_filter
ON gold.weather_monthly (location_id, month);

-- 009_cpi_food.sql
-- Grain: série × mois
-- Contenu: indices et variations

DROP MATERIALIZED VIEW IF EXISTS gold.cpi_food CASCADE;

CREATE MATERIALIZED VIEW gold.cpi_food AS
WITH current_cpi AS (
    SELECT
        co.observation_id,
        co.series_code,
        co.series_label,
        co.geo_scope,
        date_trunc('month', co.period_start)::date AS month,
        co.index_value,
        co.base_period
    FROM obs.cpi_observation co
    WHERE co.superseded_by IS NULL
      AND NOT EXISTS (
          SELECT 1 FROM obs.quarantine_ledger ql
          WHERE (
              (ql.table_name = 'obs.cpi_observation' AND ql.observation_id = co.observation_id)
              OR (ql.table_name = 'meta.source_record' AND ql.source_record_id = co.source_record_id)
          )
          AND ql.revoked_at IS NULL
      )
)
SELECT
    c.series_code,
    c.series_label,
    c.geo_scope,
    c.month,
    c.index_value,
    c.base_period,
    CASE
        WHEN p1m.index_value IS NOT NULL AND p1m.index_value > 0
        THEN round(((c.index_value / p1m.index_value) - 1.0)::numeric, 4)
        ELSE NULL
    END AS chg_1m,
    CASE
        WHEN p12m.index_value IS NOT NULL AND p12m.index_value > 0
        THEN round(((c.index_value / p12m.index_value) - 1.0)::numeric, 4)
        ELSE NULL
    END AS chg_12m
FROM current_cpi c
LEFT JOIN current_cpi p1m ON (
    p1m.series_code = c.series_code
    AND p1m.geo_scope = c.geo_scope
    AND p1m.month = (c.month - INTERVAL '1 month')::date
)
LEFT JOIN current_cpi p12m ON (
    p12m.series_code = c.series_code
    AND p12m.geo_scope = c.geo_scope
    AND p12m.month = (c.month - INTERVAL '12 months')::date
)
WITH NO DATA;

CREATE INDEX idx_gold_cpi_food_filter
ON gold.cpi_food (series_code, month);

-- 010_market_health.sql
-- Grain: product × région × mois
-- Contenu: composantes + score (SPECS §16)

DROP MATERIALIZED VIEW IF EXISTS gold.market_health CASCADE;

CREATE MATERIALIZED VIEW gold.market_health AS
WITH price_comp AS (
    SELECT
        pc.product_id,
        pc.product_code,
        pc.product_name,
        pc.location_id,
        pc.location_pcode,
        pc.location_name,
        pc.month,
        pc.vol_12,
        CASE
            WHEN pc.vol_12 IS NOT NULL
            THEN round((100.0 * (1.0 - LEAST(pc.vol_12 / 0.30, 1.0)))::numeric, 2)
            ELSE NULL
        END AS score_stability,
        CASE
            WHEN pc.chg_12m IS NOT NULL
            THEN round(
                (100.0 * (1.0 - LEAST(GREATEST(pc.chg_12m, 0.0) / 0.40, 1.0)))::numeric,
                2
            )
            ELSE NULL
        END AS score_affordability
    FROM gold.price_changes pc
    WHERE pc.admin_level <= 2
),
stock_comp AS (
    SELECT
        sl.product_id,
        sl.location_id,
        sl.stock_status,
        CASE
            WHEN sl.stock_status = 'sufficient' THEN 100.0
            WHEN sl.stock_status = 'tight' THEN 50.0
            WHEN sl.stock_status = 'shortage' THEN 0.0
            ELSE NULL
        END::numeric(5,2) AS score_availability
    FROM gold.stock_latest sl
),
weather_comp AS (
    SELECT
        wm.location_id,
        wm.month,
        wm.rain_anom_3m,
        CASE
            WHEN wm.rain_anom_3m IS NOT NULL
            THEN round(
                (100.0 * (1.0 - LEAST(GREATEST(-wm.rain_anom_3m, 0.0) / 0.50, 1.0)))::numeric,
                2
            )
            ELSE NULL
        END AS score_climate
    FROM gold.weather_monthly wm
),
combined AS (
    SELECT
        p.product_id,
        p.product_code,
        p.product_name,
        p.location_id,
        p.location_pcode,
        p.location_name,
        p.month,
        p.score_stability,
        p.score_affordability,
        s.score_availability,
        w.score_climate,
        -- Calculate present weights
        (
            (CASE WHEN p.score_stability IS NOT NULL THEN 0.30 ELSE 0.0 END) +
            (CASE WHEN p.score_affordability IS NOT NULL THEN 0.25 ELSE 0.0 END) +
            (CASE WHEN s.score_availability IS NOT NULL THEN 0.25 ELSE 0.0 END) +
            (CASE WHEN w.score_climate IS NOT NULL THEN 0.20 ELSE 0.0 END)
        )::numeric(4,2) AS coverage,
        -- Weighted sum of available components
        (
            (CASE WHEN p.score_stability IS NOT NULL THEN p.score_stability * 0.30 ELSE 0.0 END) +
            (CASE WHEN p.score_affordability IS NOT NULL THEN p.score_affordability * 0.25 ELSE 0.0 END) +
            (CASE WHEN s.score_availability IS NOT NULL THEN s.score_availability * 0.25 ELSE 0.0 END) +
            (CASE WHEN w.score_climate IS NOT NULL THEN w.score_climate * 0.20 ELSE 0.0 END)
        )::numeric(8,2) AS weighted_sum
    FROM price_comp p
    LEFT JOIN stock_comp s ON p.product_id = s.product_id AND p.location_id = s.location_id
    LEFT JOIN weather_comp w ON p.location_id = w.location_id AND p.month = w.month
)
SELECT
    product_id,
    product_code,
    product_name,
    location_id,
    location_pcode,
    location_name,
    month,
    score_stability,
    score_affordability,
    score_availability,
    score_climate,
    coverage,
    CASE
        WHEN coverage >= 0.50 AND coverage > 0
        THEN round((weighted_sum / coverage)::numeric, 2)
        ELSE NULL
    END AS market_health_score
FROM combined
WITH NO DATA;

CREATE INDEX idx_gold_market_health_filter
ON gold.market_health (product_id, location_id, month);

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

-- 012_forecast_latest.sql
-- Grain: série × horizon
-- Contenu: dernier model_run pour chaque série avec métadonnées conformes (ADR-078)

DROP MATERIALIZED VIEW IF EXISTS gold.forecast_latest CASCADE;

CREATE MATERIALIZED VIEW gold.forecast_latest AS
WITH latest_runs AS (
    SELECT
        f.forecast_id,
        f.series_key,
        f.product_id,
        p.product_code,
        p.canonical_name_fr AS product_name,
        f.location_id,
        loc.pcode AS location_pcode,
        loc.name AS location_name,
        f.actor_level,
        f.target_period,
        f.horizon,
        f.p10,
        f.p50,
        f.p90,
        f.model_requested,
        COALESCE(f.model_effective, mr.model_name) AS model_effective,
        f.is_baseline,
        f.is_calibrated,
        f.calibration_sample_size,
        f.status,
        f.fallback_reason,
        f.currency,
        f.unit,
        f.interval_width,
        f.coverage_rate_80,
        f.generated_at,
        mr.model_run_id,
        mr.model_name,
        mr.model_version,
        mr.data_cutoff,
        mr.trained_at,
        mr.params->>'dataset_fingerprint' AS dataset_fingerprint,
        mr.params->>'cohort' AS cohort,
        ROW_NUMBER() OVER (
            PARTITION BY f.series_key, f.horizon, f.target_period
            ORDER BY mr.trained_at DESC, f.generated_at DESC
        ) AS rn
    FROM ml.forecast f
    JOIN ml.model_run mr ON f.model_run_id = mr.model_run_id
    LEFT JOIN ref.product p ON f.product_id = p.product_id
    LEFT JOIN ref.location loc ON f.location_id = loc.location_id
)
SELECT
    forecast_id,
    model_run_id,
    series_key,
    product_id,
    product_code,
    product_name,
    location_id,
    location_pcode,
    location_name,
    actor_level,
    target_period,
    horizon,
    p10,
    p50,
    p90,
    model_requested,
    model_effective,
    is_baseline,
    is_calibrated,
    calibration_sample_size,
    status,
    fallback_reason,
    currency,
    unit,
    interval_width,
    coverage_rate_80,
    model_name,
    model_version,
    data_cutoff,
    trained_at,
    generated_at,
    dataset_fingerprint,
    cohort
FROM latest_runs
WHERE rn = 1
WITH NO DATA;

CREATE INDEX idx_gold_forecast_latest_series
ON gold.forecast_latest (series_key, target_period);

-- 013_market_coverage.sql
-- Grain: product × location × actor_level × month
-- Contenu: Matrice de couverture avec n_obs, sources, familles de sources, granularité admin_level, âge en jours et part imputée.

DROP MATERIALIZED VIEW IF EXISTS gold.market_coverage CASCADE;

CREATE MATERIALIZED VIEW gold.market_coverage AS
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
    count(DISTINCT source_id)::integer AS n_sources,
    count(DISTINCT source_family)::integer AS n_families,
    string_agg(DISTINCT source_id, ', ' ORDER BY source_id) AS sources,
    string_agg(DISTINCT source_family, ', ' ORDER BY source_family) AS source_families,
    sum(n_obs)::integer AS n_obs,
    round(avg(imputed_share)::numeric, 4) AS imputed_share,
    bool_or(has_observed) AS has_observed,
    CASE
        WHEN bool_or(has_observed) THEN 'observed'
        ELSE 'imputed'
    END AS observed_or_imputed,
    min(min_price)::numeric(18,2) AS min_price,
    max(max_price)::numeric(18,2) AS max_price,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY median_price)::numeric(18,2) AS median_price,
    (CURRENT_DATE - month)::integer AS age_days
FROM gold.price_monthly
GROUP BY
    product_id,
    product_code,
    product_name,
    location_id,
    location_pcode,
    location_name,
    admin_level,
    actor_level,
    month
WITH NO DATA;

CREATE INDEX idx_gold_market_coverage_lookup
ON gold.market_coverage (product_code, location_pcode, month);

CREATE INDEX idx_gold_market_coverage_location
ON gold.market_coverage (location_pcode, admin_level);

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
