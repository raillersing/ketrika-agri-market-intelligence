"""Typed observation record definitions for Ketrika connectors (SPECS §9)."""

from __future__ import annotations

import datetime as dt
from datetime import date, datetime
from typing import ClassVar

from pydantic import Field

from ketrika.connectors.base import RecordBase


class PriceRecord(RecordBase):
    """Normalized price observation record (matching obs.price_observation)."""

    natural_key_fields: ClassVar[tuple[str, ...]] = (
        "product_raw",
        "location_raw",
        "actor_level",
        "period_start",
        "period_end",
    )

    product_raw: str
    location_raw: str | None = None
    variety: str | None = None
    actor_level: str = "retail"  # retail | wholesale | farmgate | producer
    period_start: date
    period_end: date
    price_raw: str
    price_value: float | None = None
    unit_raw: str
    currency_raw: str = "MGA"
    observed_or_imputed: str = "observed"  # observed | imputed
    value_kind: str = "point"  # point | min | max | avg
    missing_code: str | None = None  # ND | NA | None
    published_at: datetime | None = None

    def compute_natural_key(self, source_id: str) -> str:
        from ketrika.normalize.price_identity import PriceIdentity

        return PriceIdentity(
            source_id,
            self.product_raw,
            self.variety,
            self.location_raw,
            self.actor_level,
            self.period_start,
            self.period_end,
            self.value_kind,
            self.unit_raw,
            self.currency_raw,
            self.observed_or_imputed,
        ).natural_key


class StockRecord(RecordBase):
    """Normalized stock level record (matching obs.stock_observation)."""

    natural_key_fields: ClassVar[tuple[str, ...]] = (
        "product_raw",
        "location_raw",
        "period_start",
        "period_end",
    )

    product_raw: str
    location_raw: str | None = None
    period_start: date
    period_end: date
    quantity_raw: str | None = None
    quantity_value: float | None = None
    unit_raw: str | None = None
    stock_status: str | None = None  # sufficient | tight | shortage | unknown
    coverage_days: float | None = None
    published_at: datetime | None = None


class TradeFlowRecord(RecordBase):
    """Normalized trade import/export flow record (matching obs.trade_flow)."""

    natural_key_fields: ClassVar[tuple[str, ...]] = (
        "flow",
        "product_raw",
        "partner_raw",
        "period_start",
        "period_end",
    )

    flow: str  # import | export
    product_raw: str
    hs_code: str | None = None
    partner_raw: str | None = None
    partner_iso3: str | None = None
    period_start: date
    period_end: date
    value_raw: str | None = None
    value_mga: float | None = None
    value_usd: float | None = None
    weight_raw: str | None = None
    weight_kg: float | None = None
    published_at: datetime | None = None


class ProductionRecord(RecordBase):
    """Normalized agricultural production record (matching obs.production_observation)."""

    natural_key_fields: ClassVar[tuple[str, ...]] = (
        "product_raw",
        "location_raw",
        "element",
        "period_start",
        "period_end",
    )

    product_raw: str
    location_raw: str | None = None
    period_start: date
    period_end: date
    element: str  # area_harvested_ha | production_t | yield_kg_ha | food_supply_kcal
    value_raw: str | None = None
    value: float | None = None
    unit_raw: str | None = None
    flag_raw: str | None = None
    observed_or_imputed: str = "observed"
    published_at: datetime | None = None


class WeatherRecord(RecordBase):
    """Normalized climate/weather record (matching obs.weather_observation)."""

    natural_key_fields: ClassVar[tuple[str, ...]] = (
        "location_raw",
        "date",
        "variable",
        "provider",
    )

    location_raw: str
    date: date
    variable: str  # precip_mm | t2m_max_c | t2m_min_c | rh2m_pct
    value: float
    value_raw: str | None = None
    method: str = "point_centroid"  # point_centroid | zonal_mean
    provider: str = "nasa_power"  # nasa_power | chirps

    # Provide period_start and period_end defaulting to date
    period_start: dt.date = Field(default_factory=dt.date.today)
    period_end: dt.date = Field(default_factory=dt.date.today)

    def model_post_init(self, __context: object) -> None:
        """Align period_start and period_end with date."""
        self.period_start = self.date
        self.period_end = self.date


class CpiRecord(RecordBase):
    """Normalized consumer price index record (matching obs.cpi_observation)."""

    natural_key_fields: ClassVar[tuple[str, ...]] = (
        "series_code",
        "geo_scope",
        "period_start",
        "period_end",
    )

    series_code: str
    series_label: str
    geo_scope: str = "national"  # national | urbain | rural | <city>
    period_start: date
    period_end: date
    index_value_raw: str
    index_value: float | None = None
    base_period: str | None = None
    published_at: datetime | None = None


class EventRecord(RecordBase):
    """Normalized market/policy event record (matching obs.event)."""

    natural_key_fields: ClassVar[tuple[str, ...]] = (
        "event_type",
        "title",
        "event_date",
    )

    event_type: str  # regulatory | climate | market_disruption | policy | other
    title: str
    summary: str | None = None
    event_date: date | None = None
    severity: int | None = None  # 1..5

    period_start: date = Field(default_factory=lambda: date.today())
    period_end: date = Field(default_factory=lambda: date.today())

    def model_post_init(self, __context: object) -> None:
        """Align period_start and period_end with event_date if set."""
        if self.event_date is not None:
            self.period_start = self.event_date
            self.period_end = self.event_date


class MacroRecord(RecordBase):
    """Normalized macroeconomic observation record (matching obs.macro_observation)."""

    natural_key_fields: ClassVar[tuple[str, ...]] = (
        "indicator_code",
        "geo_scope",
        "frequency",
        "vintage",
        "period_start",
        "period_end",
    )

    indicator_code: str
    indicator_name: str
    frequency: str = "monthly"  # daily | monthly | quarterly | annual | adhoc
    unit: str  # MGA | USD | pct | index | ratio
    geo_scope: str = "national"  # national | <pcode>
    period_start: date
    period_end: date
    value_raw: str | None = None
    value: float | None = None
    base_period: str | None = None
    vintage: str = "final"  # preliminary | provisional | revised | final
    observed_or_imputed: str = "observed"  # observed | imputed | estimated
    first_available_at: datetime | None = None
    published_at: datetime | None = None

