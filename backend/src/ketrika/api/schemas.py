"""Pydantic request and response schemas for Ketrika API (SPECS §19)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ValueKind = Literal["observed", "imputed", "forecast", "composite"]


# ===================== AUTH =====================


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


class LocationItem(BaseModel):
    """Geographic reference entity."""

    location_id: uuid.UUID
    admin_level: int
    pcode: str | None = None
    name: str
    parent_pcode: str | None = None
    boundary_version: str
    aliases: list[str] = Field(default_factory=list)


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
    precip_total_mm: float
    precip_anomaly_pct: float | None = None
    t2m_mean: float | None = None
    value_kind: ValueKind = "observed"
    sources: list[str] = Field(default_factory=list)


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
    """Price forecast horizons and quantiles."""

    product_code: str
    location_pcode: str
    horizon: int
    target_period: str
    p10: float
    p50: float
    p90: float
    model_name: str
    value_kind: ValueKind = "forecast"


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

