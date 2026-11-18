"""Pydantic request and response schemas for Ketrika API (SPECS §19)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ValueKind = Literal["observed", "imputed", "forecast", "projected", "composite"]


# ===================== AUTH =====================


class CollectionInput(BaseModel):
    request_id: uuid.UUID
    source_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,99}$")


class LoginRequest(BaseModel):
    """User credentials for session authentication."""

    email: str
    password: str


class UserSummary(BaseModel):
    """User account summary."""

    user_id: uuid.UUID
    email: str
    role: str
    disabled: bool = False


class LoginResponse(BaseModel):
    """Successful login response."""

    token: str
    token_type: str = "bearer"
    user: UserSummary


class ApiKeyCreateRequest(BaseModel):
    """Create programmatic API key request."""

    name: str = "Default API Key"


class ApiKeyResponse(BaseModel):
    """API key response (raw_key provided only at creation)."""

    api_key_id: uuid.UUID
    prefix: str
    raw_key: str | None = None
    created_at: datetime
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None


# ===================== PRODUCTS & LOCATIONS =====================


class ProductItem(BaseModel):
    """PPN Reference Product."""

    product_id: uuid.UUID
    product_code: str
    canonical_name_fr: str
    category: str
    base_unit: str
    hs6_codes: list[str] = Field(default_factory=list)
    faostat_item_codes: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)


class ProductCreateRequest(BaseModel):
    """Payload to create a new canonical product and its aliases."""

    product_code: str = Field(
        ...,
        pattern=r"^[A-Z0-9_]{3,32}$",
        description="Canonical uppercase product identifier (e.g. ONION_RED, VANILLA)",
    )
    canonical_name_fr: str = Field(
        ..., min_length=2, max_length=120, description="Nom officiel en français"
    )
    category: str = Field(
        "other",
        description="Catégorie (cereal, root_tuber, pulse, pulse_oilseed, oil, sugar, flour, spice, vegetable, fruit, cash_crop, other)",
    )
    base_unit: str = Field("kg", description="Unité de mesure de base (kg, l, t)")
    hs6_codes: list[str] = Field(
        default_factory=list, description="Codes du Système Harmonisé à 6 chiffres (ex: 090500)"
    )
    faostat_item_codes: list[str] = Field(default_factory=list, description="Identifiants FAOSTAT")
    aliases: list[str] = Field(
        default_factory=list,
        description="Synonymes et libellés bruts pour la détection automatique",
    )
    notes: str = Field(default="", description="Notes ou spécifications botaniques/commerciales")


class ObservationItemInput(BaseModel):
    """Input observation item with verified provenance metadata."""

    date: str = Field(..., description="Date de relevé (YYYY-MM-DD ou YYYY-MM)")
    location_pcode: str = Field(
        "MDG", description="Code géographique P-code (ex: MDG, MDG11, MDG12)"
    )
    actor_level: str = Field(
        "retail", description="Stade de vente (retail, wholesale, producer, farmgate)"
    )
    price: float = Field(..., gt=0, description="Prix unitaire observé")
    currency: str = Field("MGA", description="Devise (MGA, EUR, USD)")
    unit: str = Field("kg", description="Unité de mesure (kg, l, etc.)")
    source_name: str = Field(
        "Relevé direct / Saisie utilisateur", description="Référence ou nom de la source"
    )


class ObservationBatchCreateRequest(BaseModel):
    """Batch observation payload conforming to 100% Bronze provenance (ADR-165)."""

    observations: list[ObservationItemInput] = Field(..., min_length=1)
    notes: str = Field(default="", description="Contexte de la collecte ou de l'import")


class ObservationBatchCreateResponse(BaseModel):
    """Outcome of observation batch ingestion."""

    product_code: str
    observations_created: int
    bronze_content_hash: str
    source_record_id: uuid.UUID
    recomputed_gold_views: list[str]


class LocationItem(BaseModel):
    """Geographic reference entity."""

    location_id: uuid.UUID
    admin_level: int
    pcode: str | None = None
    name: str
    parent_pcode: str | None = None
    boundary_version: str
    aliases: list[str] = Field(default_factory=list)


class LocationResolutionResult(BaseModel):
    """Result of geographic location resolution."""

    raw_query: str
    resolved: bool
    pcode: str | None = None
    name: str | None = None
    admin_level: int | None = None
    confidence: float = 0.0
    match_type: str | None = None
    note: str | None = None


class UnresolvedLocationItem(BaseModel):
    """Pending location item awaiting human review (Gate H5)."""

    location_raw: str
    observation_count: int
    source_id: str | None = None
    suggested_pcode: str | None = None
    suggested_name: str | None = None
    suggested_confidence: float = 0.0
    review_status: str = "pending"
    human_reviewed: bool = False


# ===================== PRICES =====================


class PriceSeriesItem(BaseModel):
    """Aggregated price observation item from gold.price_monthly(_best)."""

    product_code: str
    location_pcode: str | None = None
    location_name: str | None = None
    actor_level: str
    month: str
    median_price: float
    min_price: float | None = None
    max_price: float | None = None
    currency: str = "MGA"
    unit: str = "kg"
    value_kind: ValueKind = "observed"
    sources: list[str] = Field(default_factory=list)
    n_obs: int = 1
    imputed_share: float | None = 0.0


class PriceLatestItem(BaseModel):
    """Latest price per location for geospatial map visualization."""

    product_code: str
    location_pcode: str
    location_name: str
    month: str
    median_price: float
    currency: str = "MGA"
    unit: str = "kg"
    value_kind: ValueKind = "observed"
    sources: list[str] = Field(default_factory=list)


class ObservationDetailResponse(BaseModel):
    """Complete observation provenance and raw audit trail (SPECS §19)."""

    observation_id: uuid.UUID
    source_id: str
    source_url: str
    parser_version: str
    price_raw: str
    price_value: float | None = None
    price_mga_per_base: float | None = None
    currency_raw: str
    unit_raw: str
    base_unit: str
    actor_level: str
    period_start: str
    period_end: str
    observed_or_imputed: str
    value_kind: ValueKind = "observed"
    extraction_method: str
    confidence: float
    evidence: dict[str, Any] = Field(default_factory=dict)
    bronze_presigned_url: str


# ===================== STOCKS & TRADE =====================


class StockItem(BaseModel):
    """Latest stock status item."""

    product_code: str
    location_pcode: str
    location_name: str | None = None
    stock_status: str
    coverage_days: float | None = None
    trend_3obs: str | None = None
    value_kind: ValueKind = "observed"
    sources: list[str] = Field(default_factory=list)


class TradeItem(BaseModel):
    """International trade flow item."""

    product_code: str
    flow: str
    month: str
    weight_tons: float
    value_mga: float | None = None
    value_usd: float | None = None
    value_kind: ValueKind = "observed"
    sources: list[str] = Field(default_factory=list)


# ===================== WEATHER & KPIS =====================


class WeatherAnomalyItem(BaseModel):
    """Monthly weather observation and anomaly."""

    district_pcode: str
    district_name: str
    month: str
    precip_total_mm: float | None
    precip_anomaly_pct: float | None = None
    t2m_mean: float | None = None
    value_kind: ValueKind = "observed"
    sources: list[str] = Field(default_factory=list)


class ClimateForecastItem(BaseModel):
    """Archived numerical weather forecast item (obs.weather_forecast, ADR-084, ADR-087)."""

    forecast_id: str
    location_pcode: str
    location_name: str
    issued_at: str
    valid_from: str
    valid_to: str
    horizon_hours: int
    variable: str
    model_name: str
    predicted_value: float | None = None
    predicted_p10: float | None = None
    predicted_p90: float | None = None
    unit: str
    method: str
    spatial_resolution: str | None = None
    value_kind: ValueKind = "projected"
    source: str = "ecmwf_open"


class CropCalendarItem(BaseModel):
    """Crop calendar phenological cycle and trade corridors (ADR-086, ADR-087)."""

    zone_code: str
    zone_name: str
    crop: str
    product_code: str
    crop_cycle: str | None = None
    season_name: str
    crop_regime: str
    calendar_version: str = "v1.0"
    calendar_type: str = "traditional_baseline"
    campaign: str = "baseline_permanent"
    variety: str | None = None
    current_phenological_stage: str | None = None
    planting_months: list[int] = Field(default_factory=list)
    harvest_months: list[int] = Field(default_factory=list)
    peak_harvest_month: int | None = None
    water_sensitivity_profile: dict[str, str] = Field(default_factory=dict)
    market_links: list[dict[str, Any]] = Field(default_factory=list)
    source_reference: str
    verified: bool = True
    eligible_for_alerts: bool = True


class ClimateEventItem(BaseModel):
    """Food security outlook and environmental event item (obs.event, ADR-083, ADR-087)."""

    event_id: str
    source_id: str
    location_pcode: str
    location_name: str
    event_type: str
    severity: str
    title: str
    description: str
    published_at: str
    is_projected: bool = False
    ipc_phase: int | None = None
    source_reference: str


class FacultativeSourceStatus(BaseModel):
    """Status descriptor for facultative environmental sources (ADR-087)."""

    source_id: str
    source_name: str
    status: str = "unavailable"
    reason: str
    data_available: bool = False


class ClimateAnomalyDetailItem(BaseModel):
    """Detailed climate anomaly measurement (ADR-085, ADR-087)."""

    location_pcode: str
    location_name: str
    month: str
    variable: str
    observed_value: float
    baseline_mean: float | None = None
    baseline_years: int | None = None
    anomaly_delta: float | None = None
    anomaly_pct: float | None = None
    standardized_zscore: float | None = None
    risk_level: str | None = None
    status: str = "computed"
    aggregation_method: str = "zonal_mean"
    cropland_mask_applied: bool = False
    sources: list[str] = Field(default_factory=list)
    value_kind: ValueKind = "observed"


class ClimateSummaryResponse(BaseModel):
    """Consolidated agroclimate summary for decision-support (ADR-087, R4.11)."""

    location_pcode: str
    location_name: str
    current_month: str
    observed_precipitation_mm: float | None = None
    precipitation_anomaly_pct: float | None = None
    precipitation_risk_level: str | None = None
    aggregation_method: str = "zonal_mean"
    cropland_mask_applied: bool = False
    observed_source: str | None = None
    temperature_mean_c: float | None = None
    forecast_next_72h_precip_mm: float | None = None
    forecast_p10_mm: float | None = None
    forecast_p90_mm: float | None = None
    forecast_model: str | None = None
    forecast_issued_at: str | None = None
    forecast_value_kind: ValueKind = "projected"
    active_crop_cycles: list[CropCalendarItem] = Field(default_factory=list)
    events_and_outlooks: list[ClimateEventItem] = Field(default_factory=list)
    facultative_sources: list[FacultativeSourceStatus] = Field(default_factory=list)


class MarketHealthItem(BaseModel):
    """Composite Market Health Score item."""

    product_code: str
    region_pcode: str
    region_name: str
    month: str
    price_stability_score: float | None = None
    affordability_score: float | None = None
    availability_score: float | None = None
    climate_risk_score: float | None = None
    coverage: float
    composite_score: float | None = None
    value_kind: ValueKind = "composite"
    components_present: list[str] = Field(default_factory=list)


class ForecastItem(BaseModel):
    """Price forecast horizons, quantiles, and conformal metadata (SPECS §17, §19, ADR-078)."""

    forecast_id: uuid.UUID | None = None
    model_run_id: uuid.UUID | None = None
    series_key: str | None = None
    product_code: str
    product_name: str | None = None
    location_pcode: str
    location_name: str | None = None
    actor_level: str = "retail"
    horizon: int
    target_period: str
    p10: float | None = None
    p50: float
    p90: float | None = None
    model_requested: str | None = None
    model_effective: str = "NaiveLast"
    model_name: str = "NaiveLast"
    is_baseline: bool = False
    is_calibrated: bool = False
    calibration_sample_size: int = 0
    status: str = "nominal"
    fallback_reason: str | None = None
    currency: str = "MGA"
    unit: str = "kg"
    interval_width: float | None = None
    coverage_rate_80: float | None = None
    data_cutoff: str | None = None
    dataset_fingerprint: str | None = None
    cohort: str | None = None
    value_kind: ValueKind = "forecast"


class ModelRunSummaryItem(BaseModel):
    """Forecasting model run summary (C4 audit trail)."""

    model_run_id: uuid.UUID
    task: str
    model_name: str
    model_version: str
    data_cutoff: str
    trained_at: datetime
    dataset_fingerprint: str | None = None
    cohort: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)


class ModelRunDetailResponse(BaseModel):
    """Detailed model run information including forecasts and metrics decomposition."""

    run: ModelRunSummaryItem
    forecasts: list[ForecastItem] = Field(default_factory=list)


class ForecastAbstentionItem(BaseModel):
    """Documented series abstention or exclusion with normative reasons."""

    series_key: str
    product_code: str
    location_pcode: str
    actor_level: str
    reason: str
    points_count: int = 0


class PerformanceMetricsSummary(BaseModel):
    """Statistical summary metrics for evaluated forecasts (SPECS §17.4, ADR-079)."""

    wape: float | None = None
    mae: float | None = None
    smape: float | None = None
    coverage_80: float | None = None
    coverage_ci_95: list[float] | None = None
    mean_interval_width: float | None = None
    sample_size: int = 0


class ForecastEvaluationItem(BaseModel):
    """Individual forecast evaluation record against actual ground truth."""

    evaluation_id: uuid.UUID | None = None
    forecast_id: uuid.UUID
    model_run_id: uuid.UUID
    series_key: str
    product_code: str
    location_pcode: str | None = None
    actor_level: str
    target_period: str
    horizon: int
    evaluation_kind: str  # as_of_holdout | matured_actual | prospective_pending
    model_name: str
    is_baseline: bool = False
    predicted_p50: float | None = None
    predicted_p10: float | None = None
    predicted_p90: float | None = None
    actual_price: float | None = None
    actual_observation_id: uuid.UUID | None = None
    absolute_error: float | None = None
    percentage_error: float | None = None
    is_covered_80: bool | None = None
    evaluated_at: str | None = None


class ForecastPerformanceResponse(BaseModel):
    """Multidimensional forecast performance report (ADR-079, R3.8)."""

    summary: PerformanceMetricsSummary
    by_product: dict[str, PerformanceMetricsSummary] = Field(default_factory=dict)
    by_location: dict[str, PerformanceMetricsSummary] = Field(default_factory=dict)
    by_horizon: dict[str, PerformanceMetricsSummary] = Field(default_factory=dict)
    by_seasonality: dict[str, PerformanceMetricsSummary] = Field(default_factory=dict)
    evaluations: list[ForecastEvaluationItem] = Field(default_factory=list)
    total_evaluations: int = 0


class ModelExtrapolationTrajectory(BaseModel):
    """Multi-model comparative forecast trajectory."""

    model_name: str
    is_baseline: bool
    predictions: list[float]
    p10: list[float] | None = None
    p90: list[float] | None = None
    historical_wape: float | None = None
    historical_mae: float | None = None


class MultiModelExtrapolationResponse(BaseModel):
    """Multi-model comparative extrapolations response."""

    product_code: str
    product_name: str | None = None
    location_pcode: str
    location_name: str | None = None
    unit: str
    currency: str
    data_cutoff: str
    last_observed_price: float
    horizons: list[int]
    target_periods: list[str]
    winning_model: str | None = None
    models: dict[str, ModelExtrapolationTrajectory] = Field(default_factory=dict)


# ===================== OPS & ALERTS =====================


class AlertItem(BaseModel):
    """Market Intelligence Alert item."""

    alert_id: uuid.UUID
    rule_code: str
    dedupe_key: str
    severity: str
    product_code: str | None = None
    location_pcode: str | None = None
    title: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    state: str
    first_seen_at: datetime
    last_seen_at: datetime


class AlertPatchRequest(BaseModel):
    """Alert state update request."""

    state: Literal["open", "acknowledged", "resolved"]


class BulletinItem(BaseModel):
    """Automated market intelligence bulletin."""

    bulletin_id: uuid.UUID
    period_start: str
    period_end: str
    status: str
    facts: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    approved_at: datetime | None = None
    approved_by: str | None = None


class SourceItem(BaseModel):
    """Data source registry item with DataOps health indicators."""

    source_id: str
    name: str
    priority: str
    status: str
    freshness_sla_days: int | None = None
    freshness_days: int | None = None
    is_stale: bool | None = None
    latest_run_status: str | None = None
    last_run_started_at: datetime | None = None
    diagnostic_status: str | None = None
    diagnostic_code: str | None = None
    diagnostic_message: str | None = None


class SourceHealthItem(BaseModel):
    """DataOps source health item."""

    source_id: str
    source_name: str | None = None
    priority: str
    freshness_sla_days: int | None = None
    freshness_days: int | None = None
    is_stale: bool
    latest_run_status: str | None = None
    last_run_started_at: datetime | None = None
    n_records_30d: int = 0
    parse_success_rate: float = 1.0
    open_review_items: int = 0
    diagnostic_status: str | None = None
    diagnostic_code: str | None = None
    diagnostic_message: str | None = None


class SourceRunItem(BaseModel):
    """Actual ingestion history, not a cache-recalculation receipt."""

    run_id: str
    source_id: str
    source_name: str | None = None
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    n_records: int | None = None
    n_fetched: int | None = None
    error: str | None = None
    diagnostic_status: str | None = None
    diagnostic_code: str | None = None
    diagnostic_message: str | None = None


class SourceRefreshResponse(BaseModel):
    """A guarded cache recalculation never claims new collection or freshness."""

    success: bool
    action: Literal["recompute"] = "recompute"
    collection_performed: Literal[False] = False
    new_records_count: Literal[0] = 0
    message: str
    views_refreshed: list[str] = Field(default_factory=list)
    refreshed_at: datetime


class GoldDomainRefreshResponse(BaseModel):
    """Response of a domain-isolated or multi-domain Gold refresh (IA-DATA-06)."""

    status: str
    domains_succeeded: list[str] = Field(default_factory=list)
    domains_failed: list[str] = Field(default_factory=list)
    domain_errors: dict[str, str] = Field(default_factory=dict)
    views_refreshed: list[str] = Field(default_factory=list)
    count: int = 0
    refreshed_at: datetime


class ReviewItemOut(BaseModel):
    """Review queue item."""

    review_id: uuid.UUID
    kind: str
    source_record_id: uuid.UUID | None = None
    payload: dict[str, Any]
    status: str
    created_at: datetime
    resolved_at: datetime | None = None
    resolved_by: str | None = None


class ReviewResolveRequest(BaseModel):
    """Review item resolution request."""

    status: Literal["approved", "rejected", "created_alias"]
    resolution_note: str | None = None
    alias_created: str | None = None


# ===================== MACROECONOMIC (ADR-069) =====================


class MacroItem(BaseModel):
    """Macroeconomic observation item (SPECS §19, ADR-069)."""

    observation_id: uuid.UUID
    indicator_code: str
    indicator_name: str
    geo_scope: str
    frequency: str
    unit: str
    base_period: str | None = None
    period_start: str
    period_end: str
    vintage: str
    value: float | None = None
    value_raw: str | None = None
    observed_or_imputed: str
    first_available_at: datetime
    published_at: datetime | None = None
    sources: list[str] = Field(default_factory=list)


# ===================== MARKET COVERAGE & PILOT (R2.4) =====================


class MarketCoverageItem(BaseModel):
    """Market coverage matrix cell (SPECS §19, R2.4)."""

    product_code: str
    product_name: str
    location_pcode: str | None = None
    location_name: str | None = None
    admin_level: int | None = None
    actor_level: str
    month: str
    n_sources: int
    n_families: int
    sources: str
    source_families: str
    n_obs: int
    imputed_share: float
    has_observed: bool
    observed_or_imputed: str
    min_price: float | None = None
    max_price: float | None = None
    median_price: float | None = None
    age_days: int


class SeriesCoverageSummaryItem(BaseModel):
    """Independent series coverage and gap evaluation."""

    product_code: str
    location_pcode: str
    location_name: str | None = None
    actor_level: str
    admin_level: int | None = None
    start_month: str | None = None
    end_month: str | None = None
    expected_months: int
    observed_months: int
    missing_months: int
    coverage_ratio: float
    missing_months_list: list[str] = Field(default_factory=list)
    source_families: list[str] = Field(default_factory=list)
    is_pilot_candidate: bool


class PilotProductItem(BaseModel):
    """Pilot product definition."""

    product_code: str
    canonical_name_fr: str
    role: str
    category: str
    base_unit: str
    justification: str


class PilotLocationItem(BaseModel):
    """Pilot location definition."""

    pcode: str
    name: str
    admin_level: int
    economic_role: str
    justification: str


class ImpossibleCapabilityItem(BaseModel):
    """Explicitly documented impossible capability."""

    capability: str
    status: str
    scope: list[str]
    reason: str


class PilotConfigResponse(BaseModel):
    """Pilot configuration with products, locations, complementarity and impossible capabilities."""

    pilot_id: str
    version: str
    title: str
    description: str
    products: list[PilotProductItem]
    locations: list[PilotLocationItem]
    complementarity_rationale: str
    impossible_capabilities: list[ImpossibleCapabilityItem]
    authenticity_status: str
    authentic_sources_found: list[str]
    authentic_observations_count: int
    synthetic_observations_count: int


class EconomicMetricCardItem(BaseModel):
    """Specification of an economic metric card (ADR-070)."""

    metric_id: str
    dimension: str
    title: str
    definition: str
    formula: str
    unit: str
    frequency: str
    geo_scope: str
    primary_source: str
    source_family: str
    publication_lag_days: int
    limitations: str


class IndicatorObservationOut(BaseModel):
    """Observation item for an economic indicator."""

    indicator_code: str
    dimension: str
    title: str
    unit: str
    frequency: str
    geo_scope: str
    period_month: str
    current_value: float | None = None
    base_period: str | None = None
    chg_1m: float | None = None
    chg_12m: float | None = None
    null_reason: str | None = None
    source_id: str | None = None
    source_family: str | None = None
    is_administered: bool = False


class DimensionSummaryOut(BaseModel):
    """Summary of an economic dimension."""

    dimension: str
    completeness: str  # complete, partial, no_data
    indicators: list[IndicatorObservationOut] = Field(default_factory=list)


class EconomicDashboardOut(BaseModel):
    """Consolidated response for the interpretable economic dashboard."""

    overall_status: str  # complete, partial, no_data
    period_month: str
    dimensions: dict[str, DimensionSummaryOut]
    metric_catalog: dict[str, EconomicMetricCardItem]


class PilotEconomicContextOut(BaseModel):
    """Articulation between macro indicators and the rice pilot (R2.8)."""

    pilot_id: str
    target_month: str
    fx_usd_mga: float | None = None
    fuel_diesel_ceiling_mga: float | None = None
    rice_import_unit_cost_mga_per_kg: float | None = None
    cpi_food_chg_12m_pct: float | None = None
    local_rice_market_price_mga_per_kg: float | None = None
    local_rice_price_chg_12m_pct: float | None = None
    distinctness_audit: dict[str, Any] = Field(default_factory=dict)
    status: str
