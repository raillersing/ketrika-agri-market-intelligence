"""SQLAlchemy 2.0 declarative ORM models matching SPECS.md §8."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    BOOLEAN,
    DATE,
    INTEGER,
    NUMERIC,
    SMALLINT,
    TEXT,
    ForeignKey,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""

    pass


# ===================== META SCHEMA =====================


class Source(Base):
    """Registered data source metadata."""

    __tablename__ = "source"
    __table_args__ = {"schema": "meta"}

    source_id: Mapped[str] = mapped_column(TEXT, primary_key=True)
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(TEXT, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    ingestion_runs: Mapped[list["IngestionRun"]] = relationship(back_populates="source")
    source_records: Mapped[list["SourceRecord"]] = relationship(back_populates="source")


class IngestionRun(Base):
    """Execution run of an ingestion pipeline."""

    __tablename__ = "ingestion_run"
    __table_args__ = {"schema": "meta"}

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[str] = mapped_column(
        TEXT, ForeignKey("meta.source.source_id"), nullable=False
    )
    dagster_run_id: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    partition_key: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(TEXT, nullable=False)
    n_fetched: Mapped[int] = mapped_column(INTEGER, default=0)
    n_new_artifacts: Mapped[int] = mapped_column(INTEGER, default=0)
    n_records: Mapped[int] = mapped_column(INTEGER, default=0)
    n_rejected: Mapped[int] = mapped_column(INTEGER, default=0)
    n_review: Mapped[int] = mapped_column(INTEGER, default=0)
    error: Mapped[str | None] = mapped_column(TEXT, nullable=True)

    source: Mapped[Source] = relationship(back_populates="ingestion_runs")


class SourceRecord(Base):
    """Bronze raw artifact descriptor with SHA-256 provenance."""

    __tablename__ = "source_record"
    __table_args__ = {"schema": "meta"}

    source_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[str] = mapped_column(
        TEXT, ForeignKey("meta.source.source_id"), nullable=False
    )
    source_url: Mapped[str] = mapped_column(TEXT, nullable=False)
    retrieved_via: Mapped[str] = mapped_column(TEXT, nullable=False, default="direct")
    object_key: Mapped[str] = mapped_column(TEXT, nullable=False)
    content_sha256: Mapped[str] = mapped_column(TEXT, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    http_status: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    http_etag: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    http_last_modified: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(nullable=False)
    parser_version: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    extraction_status: Mapped[str] = mapped_column(TEXT, nullable=False, default="pending")

    source: Mapped[Source] = relationship(back_populates="source_records")
    price_observations: Mapped[list["PriceObservation"]] = relationship(
        back_populates="source_record"
    )


class LlmCall(Base):
    """Trace of an LLM invocation for provenance, audit and budget tracking."""

    __tablename__ = "llm_call"
    __table_args__ = (
        Index("idx_llm_call_cache_key", "cache_key"),
        {"schema": "meta"},
    )

    llm_call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider: Mapped[str] = mapped_column(TEXT, nullable=False)
    model: Mapped[str] = mapped_column(TEXT, nullable=False)
    purpose: Mapped[str] = mapped_column(TEXT, nullable=False)
    prompt_version: Mapped[str] = mapped_column(TEXT, nullable=False)
    cache_key: Mapped[str] = mapped_column(TEXT, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(INTEGER, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(NUMERIC(10, 5), nullable=True)
    source_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.source_record.source_record_id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    status: Mapped[str] = mapped_column(TEXT, nullable=False)


# ===================== REF SCHEMA =====================


class Product(Base):
    """Canonical food and agricultural commodity."""

    __tablename__ = "product"
    __table_args__ = {"schema": "ref"}

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_code: Mapped[str] = mapped_column(TEXT, unique=True, nullable=False)
    canonical_name_fr: Mapped[str] = mapped_column(TEXT, nullable=False)
    category: Mapped[str] = mapped_column(TEXT, nullable=False)
    base_unit: Mapped[str] = mapped_column(TEXT, nullable=False)
    hs6_codes: Mapped[list[str]] = mapped_column(ARRAY(TEXT), default=list)
    faostat_item_codes: Mapped[list[str]] = mapped_column(ARRAY(TEXT), default=list)
    verified: Mapped[bool] = mapped_column(BOOLEAN, default=False)

    aliases: Mapped[list["ProductAlias"]] = relationship(back_populates="product")


class ProductAlias(Base):
    """Product alias mapped to canonical product."""

    __tablename__ = "product_alias"
    __table_args__ = {"schema": "ref"}

    alias_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    alias_norm: Mapped[str] = mapped_column(TEXT, nullable=False)
    alias_display: Mapped[str] = mapped_column(TEXT, nullable=False)
    lang: Mapped[str] = mapped_column(TEXT, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ref.product.product_id"), nullable=False
    )
    source_id: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    confidence: Mapped[float] = mapped_column(NUMERIC(3, 2), nullable=False)
    origin: Mapped[str] = mapped_column(TEXT, nullable=False)
    human_reviewed: Mapped[bool] = mapped_column(BOOLEAN, default=False)

    product: Mapped[Product] = relationship(back_populates="aliases")


class UnitConversion(Base):
    """Unit conversion factor to canonical base unit."""

    __tablename__ = "unit_conversion"
    __table_args__ = {"schema": "ref"}

    unit_code: Mapped[str] = mapped_column(TEXT, primary_key=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ref.product.product_id"),
        primary_key=True,
        nullable=True,
    )
    base_unit: Mapped[str] = mapped_column(TEXT, nullable=False)
    factor: Mapped[float] = mapped_column(NUMERIC(18, 6), nullable=False)
    confidence: Mapped[float] = mapped_column(NUMERIC(3, 2), nullable=False)
    evidence: Mapped[str | None] = mapped_column(TEXT, nullable=True)


class Location(Base):
    """Geographical entity (admin0 to admin3, or market level 9)."""

    __tablename__ = "location"
    __table_args__ = {"schema": "ref"}

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    admin_level: Mapped[int] = mapped_column(SMALLINT, nullable=False)
    pcode: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    name: Mapped[str] = mapped_column(TEXT, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ref.location.location_id"), nullable=True
    )
    boundary_version: Mapped[str] = mapped_column(TEXT, nullable=False)
    valid_from: Mapped[date | None] = mapped_column(DATE, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(DATE, nullable=True)

    aliases: Mapped[list["LocationAlias"]] = relationship(back_populates="location")


class LocationAlias(Base):
    """Location name alias mapped to reference location."""

    __tablename__ = "location_alias"
    __table_args__ = {"schema": "ref"}

    alias_norm: Mapped[str] = mapped_column(TEXT, primary_key=True)
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ref.location.location_id"), nullable=False
    )
    source_id: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    confidence: Mapped[float] = mapped_column(NUMERIC(3, 2), nullable=False)
    origin: Mapped[str] = mapped_column(TEXT, nullable=False)

    location: Mapped[Location] = relationship(back_populates="aliases")


class CropCalendar(Base):
    """Crop calendar defining planting, growing and harvest windows by product and location."""

    __tablename__ = "crop_calendar"
    __table_args__ = (
        Index(
            "uq_crop_calendar_active",
            "product_id",
            "location_id",
            "season_name",
            "crop_regime",
            unique=True,
            postgresql_where=text("is_active = TRUE"),
        ),
        {"schema": "ref"},
    )

    calendar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ref.product.product_id"), nullable=False
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ref.location.location_id"), nullable=False
    )
    season_name: Mapped[str] = mapped_column(TEXT, nullable=False)
    crop_regime: Mapped[str] = mapped_column(TEXT, nullable=False)
    calendar_version: Mapped[str] = mapped_column(TEXT, nullable=False, default="v1.0")
    calendar_type: Mapped[str] = mapped_column(TEXT, nullable=False, default="traditional_baseline")
    campaign: Mapped[str] = mapped_column(TEXT, nullable=False, default="baseline_permanent")
    variety: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    planting_start_month: Mapped[int] = mapped_column(SMALLINT, nullable=False)
    planting_end_month: Mapped[int] = mapped_column(SMALLINT, nullable=False)
    growing_start_month: Mapped[int] = mapped_column(SMALLINT, nullable=False)
    growing_end_month: Mapped[int] = mapped_column(SMALLINT, nullable=False)
    harvest_start_month: Mapped[int] = mapped_column(SMALLINT, nullable=False)
    harvest_end_month: Mapped[int] = mapped_column(SMALLINT, nullable=False)
    peak_harvest_month: Mapped[int | None] = mapped_column(SMALLINT, nullable=True)
    water_sensitivity_profile: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    source_reference: Mapped[str] = mapped_column(TEXT, nullable=False)
    verified: Mapped[bool] = mapped_column(BOOLEAN, default=True)
    eligible_for_alerts: Mapped[bool] = mapped_column(BOOLEAN, default=True)
    is_active: Mapped[bool] = mapped_column(BOOLEAN, default=True)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ref.crop_calendar.calendar_id"), nullable=True
    )
    basin_code: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    market_links: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    product: Mapped[Product] = relationship()
    location: Mapped[Location] = relationship()


# ===================== OBS SCHEMA (Silver) =====================


class PriceObservation(Base):
    """Harmonized price observation (Silver layer)."""

    __tablename__ = "price_observation"
    __table_args__ = (
        Index("idx_price_obs_prod_loc_period", "product_id", "location_id", "period_start"),
        {"schema": "obs"},
    )

    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.source_record.source_record_id"),
        nullable=False,
    )
    natural_key: Mapped[str] = mapped_column(TEXT, nullable=False)
    product_raw: Mapped[str] = mapped_column(TEXT, nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ref.product.product_id"), nullable=True
    )
    variety: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    quality_grade: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    location_raw: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ref.location.location_id"), nullable=True
    )
    market_name: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    actor_level: Mapped[str] = mapped_column(TEXT, nullable=False)
    period_start: Mapped[date] = mapped_column(DATE, nullable=False)
    period_end: Mapped[date] = mapped_column(DATE, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    price_raw: Mapped[str] = mapped_column(TEXT, nullable=False)
    price_value: Mapped[float | None] = mapped_column(NUMERIC(18, 4), nullable=True)
    currency_raw: Mapped[str] = mapped_column(TEXT, nullable=False, default="MGA")
    unit_raw: Mapped[str] = mapped_column(TEXT, nullable=False)
    package_quantity: Mapped[float | None] = mapped_column(NUMERIC(18, 4), nullable=True)
    package_unit: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    price_mga_per_base: Mapped[float | None] = mapped_column(NUMERIC(18, 4), nullable=True)
    base_unit: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    conversion_status: Mapped[str] = mapped_column(TEXT, nullable=False)
    observed_or_imputed: Mapped[str] = mapped_column(TEXT, nullable=False)
    missing_code: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    extraction_method: Mapped[str] = mapped_column(TEXT, nullable=False)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float] = mapped_column(NUMERIC(3, 2), nullable=False)
    review_status: Mapped[str] = mapped_column(TEXT, nullable=False, default="accepted")
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("obs.price_observation.observation_id"),
        nullable=True,
    )

    source_record: Mapped[SourceRecord] = relationship(back_populates="price_observations")
    product: Mapped[Product | None] = relationship()
    location: Mapped[Location | None] = relationship()


class StockObservation(Base):
    """Harmonized commodity stock observation (Silver layer)."""

    __tablename__ = "stock_observation"
    __table_args__ = {"schema": "obs"}

    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.source_record.source_record_id"),
        nullable=False,
    )
    natural_key: Mapped[str] = mapped_column(TEXT, nullable=False)
    product_raw: Mapped[str] = mapped_column(TEXT, nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ref.product.product_id"), nullable=True
    )
    location_raw: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ref.location.location_id"), nullable=True
    )
    period_start: Mapped[date] = mapped_column(DATE, nullable=False)
    period_end: Mapped[date] = mapped_column(DATE, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    quantity_raw: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    quantity_value: Mapped[float | None] = mapped_column(NUMERIC(18, 4), nullable=True)
    unit_raw: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    quantity_base: Mapped[float | None] = mapped_column(NUMERIC(18, 4), nullable=True)
    base_unit: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    stock_status: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    coverage_days: Mapped[float | None] = mapped_column(NUMERIC(8, 2), nullable=True)
    target: Mapped[str] = mapped_column(TEXT, nullable=False, server_default="stock_inventory")
    measurement_mode: Mapped[str] = mapped_column(
        TEXT, nullable=False, server_default="declared_trader"
    )
    market_type: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    market_code: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    extraction_method: Mapped[str] = mapped_column(TEXT, nullable=False)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float] = mapped_column(NUMERIC(3, 2), nullable=False)
    review_status: Mapped[str] = mapped_column(TEXT, nullable=False, default="accepted")
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("obs.stock_observation.observation_id"),
        nullable=True,
    )


class TradeFlow(Base):
    """Harmonized international trade flow observation (import/export)."""

    __tablename__ = "trade_flow"
    __table_args__ = {"schema": "obs"}

    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.source_record.source_record_id"),
        nullable=False,
    )
    natural_key: Mapped[str] = mapped_column(TEXT, nullable=False)
    flow: Mapped[str] = mapped_column(TEXT, nullable=False)
    hs_code: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    product_raw: Mapped[str] = mapped_column(TEXT, nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ref.product.product_id"), nullable=True
    )
    partner_raw: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    partner_iso3: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    period_start: Mapped[date] = mapped_column(DATE, nullable=False)
    period_end: Mapped[date] = mapped_column(DATE, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    value_raw: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    value_mga: Mapped[float | None] = mapped_column(NUMERIC(20, 2), nullable=True)
    value_usd: Mapped[float | None] = mapped_column(NUMERIC(20, 2), nullable=True)
    weight_raw: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(NUMERIC(20, 3), nullable=True)
    extraction_method: Mapped[str] = mapped_column(TEXT, nullable=False)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float] = mapped_column(NUMERIC(3, 2), nullable=False)
    review_status: Mapped[str] = mapped_column(TEXT, nullable=False, default="accepted")
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obs.trade_flow.observation_id"), nullable=True
    )


class ProductionObservation(Base):
    """Harmonized agricultural production observation."""

    __tablename__ = "production_observation"
    __table_args__ = {"schema": "obs"}

    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.source_record.source_record_id"),
        nullable=False,
    )
    natural_key: Mapped[str] = mapped_column(TEXT, nullable=False)
    product_raw: Mapped[str] = mapped_column(TEXT, nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ref.product.product_id"), nullable=True
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ref.location.location_id"), nullable=True
    )
    period_start: Mapped[date] = mapped_column(DATE, nullable=False)
    period_end: Mapped[date] = mapped_column(DATE, nullable=False)
    element: Mapped[str] = mapped_column(TEXT, nullable=False)
    value: Mapped[float | None] = mapped_column(NUMERIC(20, 4), nullable=True)
    value_raw: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    unit_raw: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    flag_raw: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    observed_or_imputed: Mapped[str] = mapped_column(TEXT, nullable=False)
    extraction_method: Mapped[str] = mapped_column(TEXT, nullable=False)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float] = mapped_column(NUMERIC(3, 2), nullable=False)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("obs.production_observation.observation_id"),
        nullable=True,
    )


class WeatherObservation(Base):
    """Daily agro-meteorological point/zonal observation."""

    __tablename__ = "weather_observation"
    __table_args__ = {"schema": "obs"}

    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.source_record.source_record_id"),
        nullable=False,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ref.location.location_id"), nullable=False
    )
    date: Mapped[date] = mapped_column(DATE, nullable=False)
    variable: Mapped[str] = mapped_column(TEXT, nullable=False)
    value: Mapped[float | None] = mapped_column(NUMERIC(10, 3), nullable=True)
    method: Mapped[str] = mapped_column(TEXT, nullable=False)
    provider: Mapped[str] = mapped_column(TEXT, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    location_raw: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    value_raw: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    stage: Mapped[str] = mapped_column(TEXT, nullable=False, server_default="final")
    spatial_resolution: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    coverage_ratio: Mapped[float | None] = mapped_column(NUMERIC(5, 4), nullable=True)
    raster_source_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meta.source_record.source_record_id"), nullable=True
    )
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("obs.weather_observation.observation_id", deferrable=True, initially="DEFERRED"),
        nullable=True,
    )

    location: Mapped[Location] = relationship()
    source_record: Mapped[SourceRecord] = relationship(foreign_keys=[source_record_id])


class WeatherForecast(Base):
    """Numerical agro-meteorological weather forecast."""

    __tablename__ = "weather_forecast"
    __table_args__ = {"schema": "obs"}

    forecast_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.source_record.source_record_id"),
        nullable=False,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ref.location.location_id"), nullable=False
    )
    issued_at: Mapped[datetime] = mapped_column(nullable=False)
    valid_from: Mapped[datetime] = mapped_column(nullable=False)
    valid_to: Mapped[datetime] = mapped_column(nullable=False)
    horizon_hours: Mapped[int] = mapped_column(INTEGER, nullable=False)
    variable: Mapped[str] = mapped_column(TEXT, nullable=False)
    model_name: Mapped[str] = mapped_column(TEXT, nullable=False)
    predicted_value: Mapped[float | None] = mapped_column(NUMERIC(10, 3), nullable=True)
    predicted_p10: Mapped[float | None] = mapped_column(NUMERIC(10, 3), nullable=True)
    predicted_p90: Mapped[float | None] = mapped_column(NUMERIC(10, 3), nullable=True)
    method: Mapped[str] = mapped_column(TEXT, nullable=False)
    spatial_resolution: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    unit: Mapped[str] = mapped_column(TEXT, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("obs.weather_forecast.forecast_id", deferrable=True, initially="DEFERRED"),
        nullable=True,
    )

    location: Mapped[Location] = relationship()
    source_record: Mapped[SourceRecord] = relationship(foreign_keys=[source_record_id])


class CpiObservation(Base):
    """Harmonized consumer price index (NIPC) observation."""

    __tablename__ = "cpi_observation"
    __table_args__ = {"schema": "obs"}

    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.source_record.source_record_id"),
        nullable=False,
    )
    natural_key: Mapped[str] = mapped_column(TEXT, nullable=False)
    series_code: Mapped[str] = mapped_column(TEXT, nullable=False)
    series_label: Mapped[str] = mapped_column(TEXT, nullable=False)
    geo_scope: Mapped[str] = mapped_column(TEXT, nullable=False)
    period_start: Mapped[date] = mapped_column(DATE, nullable=False)
    period_end: Mapped[date] = mapped_column(DATE, nullable=False)
    index_value: Mapped[float | None] = mapped_column(NUMERIC(12, 4), nullable=True)
    base_period: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    extraction_method: Mapped[str] = mapped_column(TEXT, nullable=False)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float] = mapped_column(NUMERIC(3, 2), nullable=False)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("obs.cpi_observation.observation_id"),
        nullable=True,
    )


class Event(Base):
    """Contextual regulatory, policy or market shock event."""

    __tablename__ = "event"
    __table_args__ = {"schema": "obs"}

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.source_record.source_record_id"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(TEXT, nullable=False)
    title: Mapped[str] = mapped_column(TEXT, nullable=False)
    summary: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    product_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    location_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    event_date: Mapped[date | None] = mapped_column(DATE, nullable=True)
    severity: Mapped[int | None] = mapped_column(SMALLINT, nullable=True)
    extraction_method: Mapped[str] = mapped_column(TEXT, nullable=False)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float] = mapped_column(NUMERIC(3, 2), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))


class MacroObservation(Base):
    """Harmonized macroeconomic indicator observation (Silver layer, ADR-069)."""

    __tablename__ = "macro_observation"
    __table_args__ = (
        Index("idx_macro_obs_ind_geo_period", "indicator_code", "geo_scope", "period_start"),
        {"schema": "obs"},
    )

    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.source_record.source_record_id"),
        nullable=False,
    )
    natural_key: Mapped[str] = mapped_column(TEXT, nullable=False)
    indicator_code: Mapped[str] = mapped_column(TEXT, nullable=False)
    indicator_name: Mapped[str] = mapped_column(TEXT, nullable=False)
    frequency: Mapped[str] = mapped_column(TEXT, nullable=False)
    unit: Mapped[str] = mapped_column(TEXT, nullable=False)
    base_period: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    geo_scope: Mapped[str] = mapped_column(TEXT, nullable=False, default="national")
    period_start: Mapped[date] = mapped_column(DATE, nullable=False)
    period_end: Mapped[date] = mapped_column(DATE, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    first_available_at: Mapped[datetime] = mapped_column(nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    vintage: Mapped[str] = mapped_column(TEXT, nullable=False, default="final")
    value: Mapped[float | None] = mapped_column(NUMERIC(20, 4), nullable=True)
    value_raw: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    observed_or_imputed: Mapped[str] = mapped_column(TEXT, nullable=False, default="observed")
    extraction_method: Mapped[str] = mapped_column(TEXT, nullable=False)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float] = mapped_column(NUMERIC(3, 2), nullable=False)
    review_status: Mapped[str] = mapped_column(TEXT, nullable=False, default="accepted")
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("obs.macro_observation.observation_id"),
        nullable=True,
    )


# ===================== ML SCHEMA =====================


class ModelRun(Base):
    """Forecasting or anomaly model training and backtest run."""

    __tablename__ = "model_run"
    __table_args__ = {"schema": "ml"}

    model_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task: Mapped[str] = mapped_column(TEXT, nullable=False)
    model_name: Mapped[str] = mapped_column(TEXT, nullable=False)
    model_version: Mapped[str] = mapped_column(TEXT, nullable=False)
    data_cutoff: Mapped[date] = mapped_column(DATE, nullable=False)
    trained_at: Mapped[datetime] = mapped_column(nullable=False)
    params: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    forecasts: Mapped[list["Forecast"]] = relationship(back_populates="model_run")


class Forecast(Base):
    """Price prediction quantile (p10, p50, p90)."""

    __tablename__ = "forecast"
    __table_args__ = {"schema": "ml"}

    forecast_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    model_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ml.model_run.model_run_id"), nullable=False
    )
    series_key: Mapped[str] = mapped_column(TEXT, nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ref.product.product_id"), nullable=False
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ref.location.location_id"), nullable=True
    )
    actor_level: Mapped[str] = mapped_column(TEXT, nullable=False)
    target_period: Mapped[date] = mapped_column(DATE, nullable=False)
    horizon: Mapped[int] = mapped_column(SMALLINT, nullable=False)
    p10: Mapped[float | None] = mapped_column(NUMERIC(18, 4), nullable=True)
    p50: Mapped[float | None] = mapped_column(NUMERIC(18, 4), nullable=True)
    p90: Mapped[float | None] = mapped_column(NUMERIC(18, 4), nullable=True)
    model_requested: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    model_effective: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    is_baseline: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_calibrated: Mapped[bool] = mapped_column(nullable=False, default=False)
    calibration_sample_size: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[str] = mapped_column(TEXT, nullable=False, default="nominal")
    fallback_reason: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    currency: Mapped[str] = mapped_column(TEXT, nullable=False, default="MGA")
    unit: Mapped[str] = mapped_column(TEXT, nullable=False, default="kg")
    interval_width: Mapped[float | None] = mapped_column(NUMERIC(18, 4), nullable=True)
    coverage_rate_80: Mapped[float | None] = mapped_column(NUMERIC(6, 4), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    model_run: Mapped[ModelRun] = relationship(back_populates="forecasts")
    evaluations: Mapped[list["ForecastEvaluation"]] = relationship(back_populates="forecast")


class ForecastEvaluation(Base):
    """Matured and as-of forecast evaluation record (ADR-079, SPECS §17.4, R3.8)."""

    __tablename__ = "forecast_evaluation"
    __table_args__ = {"schema": "ml"}

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    forecast_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ml.forecast.forecast_id"), nullable=False
    )
    model_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ml.model_run.model_run_id"), nullable=False
    )
    series_key: Mapped[str] = mapped_column(TEXT, nullable=False)
    product_code: Mapped[str] = mapped_column(TEXT, nullable=False)
    location_pcode: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    actor_level: Mapped[str] = mapped_column(TEXT, nullable=False)
    target_period: Mapped[date] = mapped_column(DATE, nullable=False)
    horizon: Mapped[int] = mapped_column(SMALLINT, nullable=False)
    evaluation_kind: Mapped[str] = mapped_column(
        TEXT, nullable=False
    )  # as_of_holdout | matured_actual | prospective_pending
    model_name: Mapped[str] = mapped_column(TEXT, nullable=False)
    is_baseline: Mapped[bool] = mapped_column(nullable=False, default=False)
    predicted_p50: Mapped[float | None] = mapped_column(NUMERIC(18, 4), nullable=True)
    predicted_p10: Mapped[float | None] = mapped_column(NUMERIC(18, 4), nullable=True)
    predicted_p90: Mapped[float | None] = mapped_column(NUMERIC(18, 4), nullable=True)
    actual_price: Mapped[float | None] = mapped_column(NUMERIC(18, 4), nullable=True)
    actual_observation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obs.price_observation.observation_id"), nullable=True
    )
    absolute_error: Mapped[float | None] = mapped_column(NUMERIC(18, 4), nullable=True)
    percentage_error: Mapped[float | None] = mapped_column(NUMERIC(8, 4), nullable=True)
    is_covered_80: Mapped[bool | None] = mapped_column(nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    forecast: Mapped[Forecast] = relationship(back_populates="evaluations")
    model_run: Mapped[ModelRun] = relationship()


# ===================== OPS SCHEMA =====================


class ReviewItem(Base):
    """Human review queue item for ambiguities, conflicts or missing references."""

    __tablename__ = "review_item"
    __table_args__ = {"schema": "ops"}

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kind: Mapped[str] = mapped_column(TEXT, nullable=False)
    source_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta.source_record.source_record_id"),
        nullable=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(TEXT, nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(TEXT, nullable=True)


class DqResult(Base):
    """Data quality test execution result."""

    __tablename__ = "dq_result"
    __table_args__ = {"schema": "ops"}

    dq_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    check_name: Mapped[str] = mapped_column(TEXT, nullable=False)
    source_id: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    asset_key: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    passed: Mapped[bool] = mapped_column(BOOLEAN, nullable=False)
    metric: Mapped[float | None] = mapped_column(NUMERIC, nullable=True)
    threshold: Mapped[float | None] = mapped_column(NUMERIC, nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))


class Alert(Base):
    """Generated market intelligence alert (spike, shortage, anomaly)."""

    __tablename__ = "alert"
    __table_args__ = {"schema": "ops"}

    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rule_code: Mapped[str] = mapped_column(TEXT, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(TEXT, unique=True, nullable=False)
    severity: Mapped[str] = mapped_column(TEXT, nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ref.product.product_id"), nullable=True
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ref.location.location_id"), nullable=True
    )
    title: Mapped[str] = mapped_column(TEXT, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    state: Mapped[str] = mapped_column(TEXT, nullable=False, default="open")
    first_seen_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    last_seen_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))


class Bulletin(Base):
    """Weekly automated PPN market bulletin."""

    __tablename__ = "bulletin"
    __table_args__ = {"schema": "ops"}

    bulletin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    period_start: Mapped[date] = mapped_column(DATE, nullable=False)
    period_end: Mapped[date] = mapped_column(DATE, nullable=False)
    status: Mapped[str] = mapped_column(TEXT, nullable=False, default="draft")
    facts: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    html_object_key: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    pdf_object_key: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    llm_call_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meta.llm_call.llm_call_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    approved_by: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)


# ===================== AUTH SCHEMA =====================


class UserAccount(Base):
    """Platform user account."""

    __tablename__ = "user_account"
    __table_args__ = {"schema": "auth"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(TEXT, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(TEXT, nullable=False)
    role: Mapped[str] = mapped_column(TEXT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    disabled: Mapped[bool] = mapped_column(BOOLEAN, default=False)

    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user")


class ApiKey(Base):
    """API key for programmatic authentication."""

    __tablename__ = "api_key"
    __table_args__ = {"schema": "auth"}

    api_key_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth.user_account.user_id"), nullable=False
    )
    prefix: Mapped[str] = mapped_column(TEXT, nullable=False)
    key_hash: Mapped[str] = mapped_column(TEXT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(nullable=True)

    user: Mapped[UserAccount] = relationship(back_populates="api_keys")
