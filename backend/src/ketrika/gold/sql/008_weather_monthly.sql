-- 008_weather_monthly.sql
-- Grain: district × mois
-- Contenu: précipitations totales, anomalie % vs climatologie 1991–2020, températures moyennes

DROP MATERIALIZED VIEW IF EXISTS gold.weather_monthly CASCADE;

CREATE MATERIALIZED VIEW gold.weather_monthly AS
WITH monthly_aggregates AS (
    SELECT
        wo.location_id,
        loc.pcode AS location_pcode,
        loc.name AS location_name,
        date_trunc('month', wo.date)::date AS month,
        EXTRACT(MONTH FROM wo.date)::integer AS cal_month,
        round(sum(CASE WHEN wo.variable = 'precip_mm' THEN COALESCE(wo.value, 0.0) ELSE 0.0 END)::numeric, 2) AS precip_total_mm,
        round(avg(CASE WHEN wo.variable = 't2m_max_c' THEN wo.value END)::numeric, 2) AS t2m_max_avg_c,
        round(avg(CASE WHEN wo.variable = 't2m_min_c' THEN wo.value END)::numeric, 2) AS t2m_min_avg_c,
        round(avg(CASE WHEN wo.variable = 'rh2m_pct' THEN wo.value END)::numeric, 2) AS rh2m_avg_pct
    FROM obs.weather_observation wo
    LEFT JOIN ref.location loc ON wo.location_id = loc.location_id
    WHERE to_jsonb(wo)->>'superseded_by' IS NULL
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
        ELSE 0.0
    END AS rain_anom_pct,
    round(
        avg(
            CASE
                WHEN wc.baseline_precip_mm > 0
                THEN (wc.precip_total_mm - wc.baseline_precip_mm) / wc.baseline_precip_mm
                ELSE 0.0
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
