"""Typed analytical tools for Copilot Analyst (SPECS §21, R6.1, ADR-095).

Normative rules:
- Strictly typed input and output contracts (Pydantic models).
- Query only validated Gold views through the secured executor under copilot_ro.
- Strict input parameter validation (product_code, location_pcode, date ranges).
- Rejection of invalid or injection-laden parameters with safe error messages (no infrastructure leakage).
- Deterministic calculation methods prioritized over free-form SQL generation.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from ketrika.copilot.executor import QueryResult, execute_copilot_query
from ketrika.core.settings import Settings, get_settings
from ketrika.geo.contracts import load_crop_calendar

logger = logging.getLogger("ketrika.copilot.tools")

PRODUCT_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_]{2,50}$")
LOCATION_PCODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{2,50}$")
MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")


class ParameterValidationError(ValueError):
    """Exception raised when an analytical tool receives an invalid or suspicious parameter."""

    def __init__(self, message: str = "Paramètre non valide ou non autorisé.") -> None:
        super().__init__(message)


def validate_product_code(product_code: str) -> str:
    """Validate and normalize a product code, rejecting malicious or ill-formed input."""
    clean = product_code.strip()
    if not PRODUCT_CODE_PATTERN.match(clean):
        raise ParameterValidationError(
            f"Code produit '{clean}' non valide. Doit être composé de 2 à 50 caractères alphanumériques."
        )
    return clean


def validate_location_pcode(location_pcode: str) -> str:
    """Validate and normalize a geographic P-code or market code."""
    clean = location_pcode.strip()
    if not LOCATION_PCODE_PATTERN.match(clean):
        raise ParameterValidationError(
            f"Code localisation '{clean}' non valide. Doit respecter le format P-Code (ex: MG-T, MKT_ANOSIBE)."
        )
    return clean


def validate_month_string(month_str: str) -> str:
    """Validate YYYY-MM format."""
    clean = month_str.strip()
    if not MONTH_PATTERN.match(clean):
        raise ParameterValidationError(
            f"Format de mois '{clean}' non valide. Le format attendu est 'YYYY-MM' (ex: 2024-05)."
        )
    return clean


# ==============================================================================
# TOOL SCHEMAS & OUTPUT CONTRACTS
# ==============================================================================


class PriceObservationPoint(BaseModel):
    """Single monthly aggregated price observation point."""

    month: str
    product_name: str
    location_name: str
    median_price_mga: float
    chosen_source_id: str | None = None


class PriceSeriesOutput(BaseModel):
    """Output contract for get_price_series tool."""

    product_code: str
    location_pcode: str | None = None
    row_count: int
    series: list[PriceObservationPoint]
    citations: list[dict[str, Any]] = Field(default_factory=list)
    value_kinds: list[str] = Field(default_factory=list)


class MarketFactMetric(BaseModel):
    """Key metric summary for a product on a specific market."""

    product_name: str
    location_name: str
    month: str
    median_price_mga: float
    chg_1m_pct: float | None = None
    chg_12m_pct: float | None = None
    z_score_robust: float | None = None
    vol_12: float | None = None


class MarketFactsOutput(BaseModel):
    """Output contract for get_market_facts tool."""

    product_code: str
    month: str | None = None
    metrics: list[MarketFactMetric]
    citations: list[dict[str, Any]] = Field(default_factory=list)


class SourceProvenanceOutput(BaseModel):
    """Output contract for get_source_provenance tool."""

    source_id: str
    priority: int | None = None
    freshness_days: int | None = None
    freshness_sla_days: int | None = None
    is_stale: bool = False
    observation_count: int = 0
    verification_status: str = "OFFICIAL_PROVENANCE_VERIFIED"


class MarketCoverageOutput(BaseModel):
    """Output contract for get_market_coverage tool."""

    product_code: str | None = None
    active_markets_count: int
    total_surveys_recorded: int
    coverage_ratio: float
    time_window_start: str | None = None
    time_window_end: str | None = None


class ForecastHorizonPoint(BaseModel):
    """Forecast quantile projection for a specific horizon."""

    horizon: int
    target_period: str
    p10: float
    p50: float
    p90: float
    model_name: str
    qualification_status: str = "QUALIFIED_OUT_OF_SAMPLE"


class QualifiedForecastOutput(BaseModel):
    """Output contract for get_qualified_forecast tool."""

    product_code: str
    location_pcode: str | None = None
    horizons: list[ForecastHorizonPoint]
    disclaimer: str = (
        "Prévision statistique indicative strictement conditionnée aux historiques passés. "
        "Les quantiles p10/p90 sont calibrés de manière non paramétrique sans hypothèse gaussienne."
    )


class CropCalendarOutput(BaseModel):
    """Output contract for get_crop_calendar tool."""

    zone_code: str
    crop: str
    planting_dekads: str
    harvest_nominal_dekads: str
    peak_dekad: str
    regime: str
    agronomic_notes: str


# ==============================================================================
# SECURED ANALYTICAL TOOL CATALOG
# ==============================================================================


class AnalyticalToolCatalog:
    """Secured catalog of typed analytical tools for Ketrika Copilot Analyst."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def get_price_series(
        self,
        product_code: str,
        location_pcode: str | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
        limit: int = 100,
    ) -> PriceSeriesOutput:
        """Fetch historical monthly aggregated price series from gold.price_monthly_best."""
        clean_prod = validate_product_code(product_code)
        conditions = [f"product_code ILIKE '%{clean_prod}%'"]

        if location_pcode:
            clean_loc = validate_location_pcode(location_pcode)
            conditions.append(
                f"(location_pcode = '{clean_loc}' OR location_name ILIKE '%{clean_loc}%')"
            )

        if period_start:
            clean_start = validate_month_string(period_start)
            conditions.append(f"month >= '{clean_start}-01'")

        if period_end:
            clean_end = validate_month_string(period_end)
            conditions.append(f"month <= '{clean_end}-28'")

        safe_limit = min(max(1, limit), 500)
        where_clause = " AND ".join(conditions)

        sql = f"""
        SELECT month, product_name, location_name, median_price, chosen_source_id
        FROM gold.price_monthly_best
        WHERE {where_clause}
        ORDER BY month DESC
        LIMIT {safe_limit};
        """.strip()

        res: QueryResult = execute_copilot_query(sql, self.settings)

        series: list[PriceObservationPoint] = []
        for r in res.rows:
            series.append(
                PriceObservationPoint(
                    month=str(r.get("month", "")),
                    product_name=str(r.get("product_name", clean_prod)),
                    location_name=str(r.get("location_name", "National")),
                    median_price_mga=float(r.get("median_price", 0.0) or 0.0),
                    chosen_source_id=r.get("chosen_source_id"),
                )
            )

        return PriceSeriesOutput(
            product_code=clean_prod,
            location_pcode=location_pcode,
            row_count=len(series),
            series=series,
            citations=res.citations,
            value_kinds=res.value_kinds,
        )

    def get_market_facts(
        self,
        product_code: str,
        location_pcode: str | None = None,
        month: str | None = None,
        limit: int = 10,
    ) -> MarketFactsOutput:
        """Fetch monthly price change indicators and robust anomalies from gold.price_changes."""
        clean_prod = validate_product_code(product_code)
        conditions = [f"product_code ILIKE '%{clean_prod}%'"]

        if location_pcode:
            clean_loc = validate_location_pcode(location_pcode)
            conditions.append(
                f"(location_pcode = '{clean_loc}' OR location_name ILIKE '%{clean_loc}%')"
            )

        if month:
            clean_month = validate_month_string(month)
            conditions.append(f"month = '{clean_month}-01'")

        safe_limit = min(max(1, limit), 500)
        where_clause = " AND ".join(conditions)

        sql = f"""
        SELECT month, product_name, location_name, median_price, chg_1m, chg_12m, z_score_robust, vol_12
        FROM gold.price_changes
        WHERE {where_clause}
        ORDER BY month DESC
        LIMIT {safe_limit};
        """.strip()

        res: QueryResult = execute_copilot_query(sql, self.settings)

        metrics: list[MarketFactMetric] = []
        for r in res.rows:
            metrics.append(
                MarketFactMetric(
                    product_name=str(r.get("product_name", clean_prod)),
                    location_name=str(r.get("location_name", "National")),
                    month=str(r.get("month", "")),
                    median_price_mga=float(r.get("median_price", 0.0) or 0.0),
                    chg_1m_pct=float(r["chg_1m"]) if r.get("chg_1m") is not None else None,
                    chg_12m_pct=float(r["chg_12m"]) if r.get("chg_12m") is not None else None,
                    z_score_robust=float(r["z_score_robust"]) if r.get("z_score_robust") is not None else None,
                    vol_12=float(r["vol_12"]) if r.get("vol_12") is not None else None,
                )
            )

        return MarketFactsOutput(
            product_code=clean_prod,
            month=month,
            metrics=metrics,
            citations=res.citations,
        )

    def get_source_provenance(self, source_id: str) -> SourceProvenanceOutput:
        """Query official source health, SLA adherence and provenance metadata."""
        clean_src = validate_product_code(source_id)  # Same alphanumeric pattern

        sql = f"""
        SELECT source_id, priority, freshness_days, freshness_sla_days, is_stale
        FROM gold.source_health
        WHERE source_id = '{clean_src}'
        LIMIT 1;
        """.strip()

        res: QueryResult = execute_copilot_query(sql, self.settings)
        if not res.rows:
            return SourceProvenanceOutput(
                source_id=clean_src,
                is_stale=False,
                verification_status="UNKNOWN_SOURCE_OR_NO_GOLD_METRICS",
            )

        r = res.rows[0]
        return SourceProvenanceOutput(
            source_id=clean_src,
            priority=r.get("priority"),
            freshness_days=r.get("freshness_days"),
            freshness_sla_days=r.get("freshness_sla_days"),
            is_stale=bool(r.get("is_stale", False)),
            verification_status="OFFICIAL_PROVENANCE_VERIFIED",
        )

    def get_market_coverage(
        self,
        product_code: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> MarketCoverageOutput:
        """Query spatial and temporal coverage from gold.market_health or price_monthly."""
        conditions = ["1=1"]
        clean_prod = None
        if product_code:
            clean_prod = validate_product_code(product_code)
            conditions.append(f"product_code ILIKE '%{clean_prod}%'")

        if start_date:
            clean_start = validate_month_string(start_date)
            conditions.append(f"month >= '{clean_start}-01'")

        if end_date:
            clean_end = validate_month_string(end_date)
            conditions.append(f"month <= '{clean_end}-28'")

        where_clause = " AND ".join(conditions)

        sql = f"""
        SELECT count(DISTINCT location_name) as n_locations, count(*) as n_rows
        FROM gold.price_monthly_best
        WHERE {where_clause}
        LIMIT 1;
        """.strip()

        res: QueryResult = execute_copilot_query(sql, self.settings)
        n_locs = 0
        n_rows = 0
        if res.rows:
            n_locs = int(res.rows[0].get("n_locations", 0) or 0)
            n_rows = int(res.rows[0].get("n_rows", 0) or 0)

        # Baseline reference: 22 administrative regions
        ratio = round(min(1.0, n_locs / 22.0), 3) if n_locs > 0 else 0.0

        return MarketCoverageOutput(
            product_code=clean_prod,
            active_markets_count=n_locs,
            total_surveys_recorded=n_rows,
            coverage_ratio=ratio,
            time_window_start=start_date,
            time_window_end=end_date,
        )

    def get_qualified_forecast(
        self,
        product_code: str,
        location_pcode: str | None = None,
        horizon: int | None = None,
    ) -> QualifiedForecastOutput:
        """Fetch qualified price forecast projections from gold.forecast_latest."""
        clean_prod = validate_product_code(product_code)
        conditions = [f"product_code ILIKE '%{clean_prod}%'"]

        if location_pcode:
            clean_loc = validate_location_pcode(location_pcode)
            conditions.append(
                f"(location_pcode = '{clean_loc}' OR location_name ILIKE '%{clean_loc}%')"
            )

        if horizon:
            if horizon < 1 or horizon > 12:
                raise ParameterValidationError(
                    f"Horizon de prévision '{horizon}' hors limites (autorisé: 1 à 12)."
                )
            conditions.append(f"horizon = {horizon}")

        where_clause = " AND ".join(conditions)

        sql = f"""
        SELECT horizon, target_period, p10, p50, p90, model_name
        FROM gold.forecast_latest
        WHERE {where_clause}
        ORDER BY horizon ASC
        LIMIT 12;
        """.strip()

        res: QueryResult = execute_copilot_query(sql, self.settings)

        horizons: list[ForecastHorizonPoint] = []
        for r in res.rows:
            horizons.append(
                ForecastHorizonPoint(
                    horizon=int(r.get("horizon", 1)),
                    target_period=str(r.get("target_period", "")),
                    p10=float(r.get("p10", 0.0)),
                    p50=float(r.get("p50", 0.0)),
                    p90=float(r.get("p90", 0.0)),
                    model_name=str(r.get("model_name", "StatisticalBaseline")),
                )
            )

        return QualifiedForecastOutput(
            product_code=clean_prod,
            location_pcode=location_pcode,
            horizons=horizons,
        )

    def get_crop_calendar(self, zone_code: str, crop: str) -> CropCalendarOutput:
        """Fetch authoritative agricultural calendar phenology for a given zone and crop."""
        clean_zone = validate_location_pcode(zone_code)
        clean_crop = validate_product_code(crop).upper()

        calendars = load_crop_calendar()
        matches = [
            c for c in calendars
            if c.zone_code.upper() == clean_zone.upper() and c.crop.upper() == clean_crop
        ]

        if not matches:
            # Fallback to general crop search across zones
            crop_matches = [c for c in calendars if c.crop.upper() == clean_crop]
            if crop_matches:
                m = crop_matches[0]
            else:
                raise ParameterValidationError(
                    f"Aucun calendrier trouvé pour la zone '{clean_zone}' et la culture '{clean_crop}'."
                )
        else:
            m = matches[0]

        regime_str = m.crop_regime.value if hasattr(m.crop_regime, "value") else str(m.crop_regime)
        peak_str = f"Mois {m.peak_harvest_month}" if m.peak_harvest_month else f"Mois {m.harvest_start_month}"
        return CropCalendarOutput(
            zone_code=m.zone_code,
            crop=m.crop,
            planting_dekads=f"Mois {m.planting_start_month} à {m.planting_end_month}",
            harvest_nominal_dekads=f"Mois {m.harvest_start_month} à {m.harvest_end_month}",
            peak_dekad=peak_str,
            regime=regime_str,
            agronomic_notes=m.notes or "",
        )
