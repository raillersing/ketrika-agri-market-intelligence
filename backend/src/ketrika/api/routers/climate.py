"""Agroclimate, weather forecast and crop calendar API router (SPECS §19, §26, ADR-087, R4.11)."""

from __future__ import annotations

import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from ketrika.api.gold_availability import require_gold_view
from ketrika.api.schemas import (
    ClimateAnomalyDetailItem,
    ClimateEventItem,
    ClimateForecastItem,
    ClimateSummaryResponse,
    CropCalendarItem,
    FacultativeSourceStatus,
)
from ketrika.core.db import get_db
from ketrika.core.models.db import Location, WeatherForecast
from ketrika.geo.calendar import detect_phenological_stage
from ketrika.geo.contracts import CropCalendarRecord, load_crop_calendar
from ketrika.gold.compatibility import is_gold_view_populated

router = APIRouter(prefix="/v1/climate", tags=["climate"])

# Mapping administrative regions/districts to production agro-climatic basins
PCODE_TO_BASIN: dict[str, str] = {
    "MDG11": "ZONE_CENTRE",
    "MDG12": "ZONE_CENTRE",
    "MDG13": "ZONE_CENTRE",
    "MDG31": "ZONE_EST",
    "MDG32": "ZONE_ALAOTRA",
    "MDG33": "ZONE_EST",
    "MDG41": "ZONE_BOENY",
    "MDG51": "ZONE_SUD",
    "MDG52": "ZONE_SUD",
    "MDG53": "ZONE_SUD",
}


FACULTATIVE_SOURCES: list[FacultativeSourceStatus] = [
    FacultativeSourceStatus(
        source_id="firms_mdg",
        source_name="NASA FIRMS (Détection thermique & feux)",
        status="unavailable",
        reason="Source facultative non intégrée (clé d'accès NASA LANCE optionnelle). Aucun faux zéro fabriqué.",
        data_available=False,
    ),
    FacultativeSourceStatus(
        source_id="glofas_mdg",
        source_name="Copernicus GloFAS (Débit & inondations)",
        status="unavailable",
        reason="Source facultative non configurée (modélisation hydrologique globale optionnelle).",
        data_available=False,
    ),
    FacultativeSourceStatus(
        source_id="copernicus_ndvi",
        source_name="Copernicus Sentinel-2 NDVI (Biomasse)",
        status="unavailable",
        reason="Source facultative non configurée (télédétection haute résolution optionnelle).",
        data_available=False,
    ),
]


def _get_facultative_sources() -> list[FacultativeSourceStatus]:
    """Return explicit transparent status for unintegrated optional environmental sources (ADR-087)."""
    return list(FACULTATIVE_SOURCES)


def _observed_sources(session: Session, location: Location, month: str) -> str | None:
    """Resolve actual monthly observation parents, without inferring a provider."""
    rows = session.execute(
        text("""
            SELECT DISTINCT sr.source_id
            FROM obs.weather_observation wo
            JOIN meta.source_record sr USING (source_record_id)
            WHERE wo.location_id = :location_id
              AND date_trunc('month', wo.date)::date = CAST(:month AS date)
              AND wo.superseded_by IS NULL
            ORDER BY sr.source_id
        """),
        {"location_id": location.location_id, "month": month},
    ).fetchall()
    return ", ".join(str(row[0]) for row in rows) or None


@router.get("/summary", response_model=ClimateSummaryResponse)
def get_climate_summary(
    location: str = Query("MDG11", description="District or Region P-code (e.g. MDG11)"),
    month: datetime.date | None = Query(
        None, description="Reference month (YYYY-MM-01), defaults to latest available"
    ),
    session: Session = Depends(get_db),
) -> ClimateSummaryResponse:
    """Consolidated agroclimate summary by zone explaining observed, forecasted and phenological states."""
    # 1. Resolve Location
    loc_record = (
        session.query(Location)
        .filter(or_(Location.pcode == location, Location.name == location))
        .first()
    )
    if loc_record is None:
        raise HTTPException(404, "Zone inconnue : aucune substitution géographique.")
    loc_name = loc_record.name
    loc_pcode = loc_record.pcode or location

    # 2. Reference Month
    if month is not None and month.day != 1:
        raise HTTPException(422, "month doit être le premier jour du mois.")
    now = datetime.datetime.now(datetime.UTC)
    ref_month_str = (month or now.date().replace(day=1)).isoformat()
    ref_month_int = int(ref_month_str.split("-")[1])

    # 3. Query Observed Weather & Anomaly
    obs_row = None
    if is_gold_view_populated(session, "weather_monthly"):
        obs_sql = """
            SELECT
                month::text AS month,
                precip_total_mm::float,
                (rain_anom_pct * 100.0)::float AS precip_anomaly_pct,
                ((t2m_max_avg_c + t2m_min_avg_c) / 2.0)::float AS t2m_mean
            FROM gold.weather_monthly
            WHERE (location_pcode = :loc OR location_id::text = :loc)
              AND (CAST(:requested_month AS date) IS NULL OR month = CAST(:requested_month AS date))
            ORDER BY month DESC
            LIMIT 1;
        """
        obs_row = session.execute(
            text(obs_sql), {"loc": loc_pcode, "requested_month": month}
        ).fetchone()

    obs_precip: float | None = None
    precip_anom_pct: float | None = None
    risk_level: str | None = None
    t2m_mean: float | None = None

    if obs_row:
        ref_month_str = str(obs_row[0])
        ref_month_int = int(ref_month_str.split("-")[1])
        obs_precip = float(obs_row[1]) if obs_row[1] is not None else None
        precip_anom_pct = float(obs_row[2]) if obs_row[2] is not None else None
        t2m_mean = float(obs_row[3]) if obs_row[3] is not None else None
        # Available-history anomalies are not a qualified hydrological risk baseline.

    # 4. Query Weather Forecast (obs.weather_forecast)
    fc_sql = """
        SELECT
            wf.forecast_id::text,
            wf.model_name,
            wf.issued_at::text,
            wf.predicted_value::float,
            wf.predicted_p10::float,
            wf.predicted_p90::float,
            wf.horizon_hours
        FROM obs.weather_forecast wf
        JOIN ref.location loc ON wf.location_id = loc.location_id
        WHERE (loc.pcode = :loc OR loc.name = :loc)
          AND wf.variable = 'precip_mm' AND wf.unit = 'mm'
          AND wf.horizon_hours = 72 AND wf.issued_at <= :now
          AND wf.superseded_by IS NULL
          AND wf.valid_from <= :now AND wf.valid_to > :now
        ORDER BY wf.issued_at DESC, wf.horizon_hours ASC
        LIMIT 1;
    """
    fc_row = None
    if ref_month_str == now.date().replace(day=1).isoformat():
        fc_row = session.execute(text(fc_sql), {"loc": loc_pcode, "now": now}).fetchone()

    fc_val: float | None = None
    fc_p10: float | None = None
    fc_p90: float | None = None
    fc_model: str | None = None
    fc_issued: str | None = None

    if fc_row:
        fc_model = fc_row[1]
        fc_issued = fc_row[2]
        fc_val = float(fc_row[3]) if fc_row[3] is not None else None
        fc_p10 = float(fc_row[4]) if fc_row[4] is not None else None
        fc_p90 = float(fc_row[5]) if fc_row[5] is not None else None

    # 5. Active Crop Calendars for this Basin
    target_basin = PCODE_TO_BASIN.get(loc_pcode)
    all_calendars = load_crop_calendar()
    active_basin_cycles: list[CropCalendarItem] = []

    for r in all_calendars:
        if r.zone_code == target_basin and r.is_active and r.superseded_by is None:
            stage = detect_phenological_stage(r, ref_month_int)
            active_basin_cycles.append(
                CropCalendarItem(
                    zone_code=r.zone_code,
                    zone_name=r.zone_name,
                    crop=r.crop,
                    product_code=r.product_code,
                    crop_cycle=r.crop_cycle,
                    season_name=r.season_name,
                    crop_regime=str(r.crop_regime),
                    calendar_version=r.calendar_version,
                    calendar_type=str(r.calendar_type),
                    campaign=r.campaign,
                    variety=r.variety,
                    current_phenological_stage=stage,
                    planting_months=r.planting_months,
                    harvest_months=r.harvest_months,
                    peak_harvest_month=r.peak_harvest_month,
                    water_sensitivity_profile=r.water_sensitivity_profile,
                    market_links=[link.model_dump() for link in r.market_links],
                    source_reference=r.source_reference,
                    verified=r.verified,
                    eligible_for_alerts=r.eligible_for_alerts,
                )
            )

    # 6. Events & Food Security Outlooks
    events_sql = """
        SELECT
            ev.event_id::text,
            COALESCE(sr.source_id, 'fewsnet_mdg') AS source_id,
            COALESCE(loc.pcode, 'MDG') AS location_pcode,
            COALESCE(loc.name, 'Madagascar National') AS location_name,
            ev.event_type,
            COALESCE(ev.severity::text, 'warning') AS severity,
            ev.title,
            COALESCE(ev.summary, '') AS description,
            COALESCE(ev.evidence->>'published_at', ev.event_date::text, ev.ingested_at::text) AS published_at,
            COALESCE((ev.evidence->>'is_projected')::boolean, FALSE) AS is_projected,
            (ev.evidence->>'ipc_phase')::int AS ipc_phase,
            COALESCE(ev.evidence->>'source_reference', sr.source_id, 'FEWS NET') AS source_reference
        FROM obs.event ev
        LEFT JOIN meta.source_record sr ON ev.source_record_id = sr.source_record_id
        LEFT JOIN ref.location loc ON loc.location_id = ANY(ev.location_ids)
        WHERE (loc.pcode = :loc OR loc.pcode IS NULL OR loc.pcode = 'MDG')
        ORDER BY ev.ingested_at DESC
        LIMIT 5;
    """
    event_rows = session.execute(text(events_sql), {"loc": loc_pcode}).fetchall()
    events_list: list[ClimateEventItem] = []

    for er in event_rows:
        events_list.append(
            ClimateEventItem(
                event_id=str(er[0]),
                source_id=str(er[1]),
                location_pcode=str(er[2]),
                location_name=str(er[3]),
                event_type=str(er[4]),
                severity=str(er[5]),
                title=str(er[6]),
                description=str(er[7]),
                published_at=str(er[8]),
                is_projected=bool(er[9]),
                ipc_phase=int(er[10]) if er[10] is not None else None,
                source_reference=str(er[11]),
            )
        )

    return ClimateSummaryResponse(
        location_pcode=loc_pcode,
        location_name=loc_name,
        current_month=ref_month_str,
        observed_precipitation_mm=obs_precip,
        precipitation_anomaly_pct=precip_anom_pct,
        precipitation_risk_level=risk_level,
        aggregation_method="zonal_mean (administratif sans masque agricole vérifié)",
        cropland_mask_applied=False,
        observed_source=_observed_sources(session, loc_record, ref_month_str) if obs_row else None,
        temperature_mean_c=t2m_mean,
        forecast_next_72h_precip_mm=fc_val,
        forecast_p10_mm=fc_p10,
        forecast_p90_mm=fc_p90,
        forecast_model=fc_model,
        forecast_issued_at=fc_issued,
        forecast_value_kind="projected",
        active_crop_cycles=active_basin_cycles,
        events_and_outlooks=events_list,
        facultative_sources=_get_facultative_sources(),
    )


@router.get("/anomalies", response_model=list[ClimateAnomalyDetailItem])
def get_climate_anomalies(
    location: str | None = Query(None, description="District or Region P-code"),
    from_date: datetime.date | None = Query(None, alias="from"),
    to_date: datetime.date | None = Query(None, alias="to"),
    variable: Literal["precip_mm", "t2m_c"] = Query("precip_mm"),
    session: Session = Depends(get_db),
) -> list[ClimateAnomalyDetailItem]:
    """Retrieve detailed climate anomalies with baseline reference and categorical risk."""
    if from_date and to_date and from_date > to_date:
        raise HTTPException(422, "La date de début dépasse la date de fin.")
    require_gold_view(session, "weather_monthly")
    sql = """
        SELECT
            location_pcode,
            location_name,
            month::text AS month,
            precip_total_mm::float,
            (rain_anom_pct * 100.0)::float AS precip_anomaly_pct,
                ((t2m_max_avg_c + t2m_min_avg_c) / 2.0)::float AS t2m_mean,
                baseline_precip_mm::float,
                (SELECT array_agg(DISTINCT sr.source_id)
                 FROM obs.weather_observation wo
                 JOIN meta.source_record sr USING (source_record_id)
                 WHERE wo.location_id = weather_monthly.location_id
                   AND date_trunc('month', wo.date)::date = weather_monthly.month
                   AND wo.superseded_by IS NULL) AS observed_sources
        FROM gold.weather_monthly
        WHERE 1=1
    """
    params: dict[str, Any] = {}
    if location:
        sql += " AND (location_pcode = :loc OR location_id::text = :loc)"
        params["loc"] = location
    if from_date:
        sql += " AND month >= CAST(:from_date AS date)"
        params["from_date"] = from_date
    if to_date:
        sql += " AND month <= CAST(:to_date AS date)"
        params["to_date"] = to_date

    sql += " ORDER BY month ASC, location_pcode;"
    rows = session.execute(text(sql), params).fetchall()

    results: list[ClimateAnomalyDetailItem] = []
    for r in rows:
        loc_code = str(r[0])
        loc_label = str(r[1])
        m = str(r[2])
        observed = r[3] if variable == "precip_mm" else r[5]
        if observed is None:
            continue
        anom_pct = float(r[4]) if variable == "precip_mm" and r[4] is not None else None

        results.append(
            ClimateAnomalyDetailItem(
                location_pcode=loc_code,
                location_name=loc_label,
                month=m,
                variable=variable,
                observed_value=float(observed),
                baseline_mean=float(r[6]) if variable == "precip_mm" and r[6] is not None else None,
                baseline_years=None,
                anomaly_pct=anom_pct,
                risk_level=None,
                status="available_history_reference"
                if variable == "precip_mm"
                else "baseline_unavailable",
                aggregation_method="zonal_mean",
                cropland_mask_applied=False,
                sources=list(r[7] or []),
                value_kind="observed",
            )
        )
    return results


@router.get("/forecasts", response_model=list[ClimateForecastItem])
def get_climate_forecasts(
    location: str | None = Query(None, description="District or Region P-code"),
    model: str | None = Query(
        None, description="Numerical weather prediction model e.g. ecmwf_ifs"
    ),
    variable: str | None = Query(None, description="Weather variable e.g. precip_mm"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db),
) -> list[ClimateForecastItem]:
    """Retrieve archived numerical weather forecasts (obs.weather_forecast, ADR-084)."""
    query = session.query(WeatherForecast, Location).join(
        Location, WeatherForecast.location_id == Location.location_id
    )

    if location:
        query = query.filter(or_(Location.pcode == location, Location.name == location))
    if model:
        query = query.filter(WeatherForecast.model_name == model)
    if variable:
        query = query.filter(WeatherForecast.variable == variable)

    records = query.order_by(WeatherForecast.issued_at.desc()).offset(offset).limit(limit).all()

    items: list[ClimateForecastItem] = []
    for wf, loc in records:
        items.append(
            ClimateForecastItem(
                forecast_id=str(wf.forecast_id),
                location_pcode=str(loc.pcode or "MDG"),
                location_name=str(loc.name or "Madagascar"),
                issued_at=wf.issued_at.isoformat(),
                valid_from=wf.valid_from.isoformat(),
                valid_to=wf.valid_to.isoformat(),
                horizon_hours=wf.horizon_hours,
                variable=wf.variable,
                model_name=wf.model_name,
                predicted_value=float(wf.predicted_value)
                if wf.predicted_value is not None
                else None,
                predicted_p10=float(wf.predicted_p10) if wf.predicted_p10 is not None else None,
                predicted_p90=float(wf.predicted_p90) if wf.predicted_p90 is not None else None,
                unit=wf.unit,
                method=wf.method,
                spatial_resolution=wf.spatial_resolution,
                value_kind="projected",
                source="ecmwf_open",
            )
        )
    return items


@router.get("/calendars", response_model=list[CropCalendarItem])
def get_crop_calendars(
    zone_code: str | None = Query(None, description="Basin code e.g. ZONE_ALAOTRA"),
    product: str | None = Query(None, description="Product code e.g. RICE_PADDY"),
    month: int | None = Query(
        None, ge=1, le=12, description="Month for active stage detection (1-12)"
    ),
) -> list[CropCalendarItem]:
    """Retrieve verified crop calendars, active phenological phases and trade corridors (ADR-086)."""
    records: list[CropCalendarRecord] = load_crop_calendar()
    eval_month = month or datetime.date.today().month

    items: list[CropCalendarItem] = []
    for r in records:
        if zone_code and r.zone_code != zone_code:
            continue
        if product and r.product_code != product:
            continue

        stage = detect_phenological_stage(r, eval_month)
        items.append(
            CropCalendarItem(
                zone_code=r.zone_code,
                zone_name=r.zone_name,
                crop=r.crop,
                product_code=r.product_code,
                crop_cycle=r.crop_cycle,
                season_name=r.season_name,
                crop_regime=str(r.crop_regime),
                calendar_version=r.calendar_version,
                calendar_type=str(r.calendar_type),
                campaign=r.campaign,
                variety=r.variety,
                current_phenological_stage=stage,
                planting_months=r.planting_months,
                harvest_months=r.harvest_months,
                peak_harvest_month=r.peak_harvest_month,
                water_sensitivity_profile=r.water_sensitivity_profile,
                market_links=[link.model_dump() for link in r.market_links],
                source_reference=r.source_reference,
                verified=r.verified,
                eligible_for_alerts=r.eligible_for_alerts,
            )
        )
    return items


@router.get("/events", response_model=list[ClimateEventItem])
def get_climate_events(
    location: str | None = Query(None, description="District or Region P-code"),
    limit: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_db),
) -> list[ClimateEventItem]:
    """Retrieve food security outlooks and agroclimatic events (FEWS NET / IPC, obs.event)."""
    sql = """
        SELECT
            ev.event_id::text,
            COALESCE(sr.source_id, 'fewsnet_mdg') AS source_id,
            COALESCE(loc.pcode, 'MDG') AS location_pcode,
            COALESCE(loc.name, 'Madagascar National') AS location_name,
            ev.event_type,
            COALESCE(ev.severity::text, 'warning') AS severity,
            ev.title,
            COALESCE(ev.summary, '') AS description,
            COALESCE(ev.evidence->>'published_at', ev.event_date::text, ev.ingested_at::text) AS published_at,
            COALESCE((ev.evidence->>'is_projected')::boolean, FALSE) AS is_projected,
            (ev.evidence->>'ipc_phase')::int AS ipc_phase,
            COALESCE(ev.evidence->>'source_reference', sr.source_id, 'FEWS NET') AS source_reference
        FROM obs.event ev
        LEFT JOIN meta.source_record sr ON ev.source_record_id = sr.source_record_id
        LEFT JOIN ref.location loc ON loc.location_id = ANY(ev.location_ids)
        WHERE 1=1
    """
    params: dict[str, Any] = {"limit": limit}
    if location:
        sql += " AND (loc.pcode = :loc OR loc.name = :loc OR loc.pcode IS NULL)"
        params["loc"] = location
    sql += " ORDER BY ev.ingested_at DESC LIMIT :limit;"

    rows = session.execute(text(sql), params).fetchall()

    items: list[ClimateEventItem] = []
    for er in rows:
        items.append(
            ClimateEventItem(
                event_id=str(er[0]),
                source_id=str(er[1]),
                location_pcode=str(er[2]),
                location_name=str(er[3]),
                event_type=str(er[4]),
                severity=str(er[5]),
                title=str(er[6]),
                description=str(er[7]),
                published_at=str(er[8]),
                is_projected=bool(er[9]),
                ipc_phase=int(er[10]) if er[10] is not None else None,
                source_reference=str(er[11]),
            )
        )
    return items


@router.get("/facultative-status", response_model=list[FacultativeSourceStatus])
def get_facultative_sources_status() -> list[FacultativeSourceStatus]:
    """Report transparent status for optional environmental sources (FIRMS, GloFAS, NDVI)."""
    return _get_facultative_sources()
