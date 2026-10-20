"""Verifiable harvest window model with dekadal resolution and agroclimatic adjustments (R5.4, ADR-091, SPECS §26-27).

This module produces verifiable agricultural harvest windows:
1. Baseline reproduction of official crop calendar cycles (FAO, MinAE, FOFIFA).
2. Agronomically grounded campaign adjustments under early water stress / rainfall delay.
3. Dekadal temporal resolution (D1: 1-10, D2: 11-20, D3: 21-end), strictly forbidding invented exact-day dates.
4. Independent confrontation against observed physical market arrivals (ODR).
5. Explicit uncertainty disclosure and experimental qualification tagging.
"""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ketrika.connectors.records import StockRecord
from ketrika.core.models.db import StockObservation
from ketrika.geo.contracts import CropCalendarRecord, CropRegime
from ketrika.supply.contracts import QuantityTarget


class ValidationLevel(StrEnum):
    """Validation qualification level of the projected harvest window."""

    BASELINE_REFERENCE = "baseline_reference"
    ADJUSTED_CAMPAIGN_RULE = "adjusted_campaign_rule"
    EXPERIMENTAL_UNVERIFIED = "experimental_unverified"


def get_dekad_bounds(year: int, month: int, dekad: int) -> tuple[date, date]:
    """Return exact (start_date, end_date) for a specific year, month, and dekad (1, 2, or 3)."""
    if dekad not in (1, 2, 3):
        raise ValueError(f"Dekad must be 1, 2, or 3, got {dekad}")
    if not (1 <= month <= 12):
        raise ValueError(f"Month must be between 1 and 12, got {month}")

    _, last_day = calendar.monthrange(year, month)

    if dekad == 1:
        return date(year, month, 1), date(year, month, 10)
    elif dekad == 2:
        return date(year, month, 11), date(year, month, 20)
    else:
        return date(year, month, 21), date(year, month, last_day)


def format_dekad_label(year: int, month: int, dekad: int) -> str:
    """Format standard dekad string identifier (e.g. '2024-05-D2')."""
    return f"{year:04d}-{month:02d}-D{dekad}"


def shift_dekad(year: int, month: int, dekad: int, shift: int) -> tuple[int, int, int]:
    """Translate (year, month, dekad) forward or backward by a number of dekads."""
    total_dekads = (year * 12 + (month - 1)) * 3 + (dekad - 1) + shift
    new_dekad = (total_dekads % 3) + 1
    total_months = total_dekads // 3
    new_month = (total_months % 12) + 1
    new_year = total_months // 12
    return new_year, new_month, new_dekad


class HarvestWindowProjection(BaseModel):
    """Verifiable projected harvest window at dekadal resolution."""

    model_config = ConfigDict(frozen=True)

    zone_code: str
    zone_name: str
    crop: str
    product_code: str
    season_name: str
    crop_cycle: str | None = None
    campaign: str
    crop_regime: str
    window_start_dekad: str
    window_end_dekad: str
    peak_harvest_dekad: str | None = None
    window_start_date: date
    window_end_date: date
    peak_start_date: date | None = None
    peak_end_date: date | None = None
    baseline_harvest_start_month: int
    baseline_harvest_end_month: int
    shift_dekads: int = 0
    shift_reason: str | None = None
    source_reference: str
    validation_level: ValidationLevel
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    uncertainty_note: str


class HarvestConfrontationResult(BaseModel):
    """Independent empirical confrontation of projected harvest window against real market arrivals."""

    model_config = ConfigDict(frozen=True)

    zone_code: str
    product_raw: str
    campaign: str
    window_start_date: date
    window_end_date: date
    total_records_tested: int
    arrivals_within_harvest_window_kg: float
    arrivals_outside_harvest_window_kg: float
    temporal_alignment_ratio: float
    peak_arrival_date: date | None = None
    peak_inside_window: bool
    evaluation_verdict: str
    confrontation_details: str


class HarvestWindowModel:
    """Scientific harvest window projection engine with agroclimatic adjustment rules."""

    def project_baseline_window(
        self,
        record: CropCalendarRecord,
        year: int,
    ) -> HarvestWindowProjection:
        """Project nominal baseline harvest window directly from official crop calendar taxonomy."""
        start_m = record.harvest_start_month
        end_m = record.harvest_end_month

        # Target harvest calendar year
        h_start_year = year
        h_end_year = year if end_m >= start_m else year + 1

        w_start_date, _ = get_dekad_bounds(h_start_year, start_m, 1)
        _, w_end_date = get_dekad_bounds(h_end_year, end_m, 3)

        w_start_dekad = format_dekad_label(h_start_year, start_m, 1)
        w_end_dekad = format_dekad_label(h_end_year, end_m, 3)

        peak_dekad: str | None = None
        p_start_date: date | None = None
        p_end_date: date | None = None

        if record.peak_harvest_month is not None:
            p_m = record.peak_harvest_month
            p_year = h_start_year if p_m >= start_m else h_end_year
            peak_dekad = format_dekad_label(p_year, p_m, 2)
            p_start_date, _ = get_dekad_bounds(p_year, p_m, 1)
            _, p_end_date = get_dekad_bounds(p_year, p_m, 3)

        # Planting campaign year (previous year if planting started after harvest month in calendar order)
        p_start_year = year - 1 if record.planting_start_month > start_m else year

        return HarvestWindowProjection(
            zone_code=record.zone_code,
            zone_name=record.zone_name,
            crop=record.crop,
            product_code=record.product_code,
            season_name=record.season_name,
            crop_cycle=record.crop_cycle,
            campaign=f"campaign_{p_start_year}_{year}",
            crop_regime=str(record.crop_regime),
            window_start_dekad=w_start_dekad,
            window_end_dekad=w_end_dekad,
            peak_harvest_dekad=peak_dekad,
            window_start_date=w_start_date,
            window_end_date=w_end_date,
            peak_start_date=p_start_date,
            peak_end_date=p_end_date,
            baseline_harvest_start_month=start_m,
            baseline_harvest_end_month=end_m,
            shift_dekads=0,
            shift_reason=None,
            source_reference=record.source_reference,
            validation_level=ValidationLevel.BASELINE_REFERENCE,
            confidence_score=0.90,
            uncertainty_note=(
                "Baseline harvest window derived directly from official institutional calendar "
                "without seasonal climate anomalies adjustment."
            ),
        )

    def project_adjusted_window(
        self,
        record: CropCalendarRecord,
        year: int,
        rainfall_early_anomaly_pct: float | None = None,
        is_drought_scenario: bool = False,
    ) -> HarvestWindowProjection:
        """Project agronomically adjusted harvest window under campaign hydrological conditions."""
        # 1. Start from baseline
        base = self.project_baseline_window(record, year)

        # 2. Check if irrigation buffers rainfall variations
        is_fully_irrigated = record.crop_regime == CropRegime.IRRIGATED

        shift = 0
        shift_reason: str | None = None
        validation_level = ValidationLevel.BASELINE_REFERENCE
        confidence = 0.90

        if is_drought_scenario:
            # Explicit dry scenario simulation
            shift = 2  # 2 dekads (~20 days delay in planting and vegetative maturity)
            shift_reason = "Simulated severe drought scenario: late planting delay of 2 dekads"
            validation_level = ValidationLevel.ADJUSTED_CAMPAIGN_RULE
            confidence = 0.75
        elif rainfall_early_anomaly_pct is not None:
            if is_fully_irrigated and rainfall_early_anomaly_pct > -40.0:
                # Controlled irrigation perimeter (e.g. Lac Alaotra PC15) resists moderate deficits
                shift = 0
                shift_reason = "Irrigated regime with hydraulic control buffers rainfall deficit"
                validation_level = ValidationLevel.BASELINE_REFERENCE
                confidence = 0.85
            elif rainfall_early_anomaly_pct <= -30.0:
                shift = 2  # 2 dekads delay
                shift_reason = f"Severe early rainfall deficit ({rainfall_early_anomaly_pct:+.1f}%) delayed planting"
                validation_level = ValidationLevel.ADJUSTED_CAMPAIGN_RULE
                confidence = 0.80
            elif rainfall_early_anomaly_pct <= -15.0:
                shift = 1  # 1 dekad delay
                shift_reason = f"Moderate early rainfall deficit ({rainfall_early_anomaly_pct:+.1f}%) delayed planting"
                validation_level = ValidationLevel.ADJUSTED_CAMPAIGN_RULE
                confidence = 0.82

        if shift == 0:
            if shift_reason is not None:
                # Return copy with the explicit agroclimatic buffer reason documented
                return HarvestWindowProjection(
                    zone_code=base.zone_code,
                    zone_name=base.zone_name,
                    crop=base.crop,
                    product_code=base.product_code,
                    season_name=base.season_name,
                    crop_cycle=base.crop_cycle,
                    campaign=base.campaign,
                    crop_regime=base.crop_regime,
                    window_start_dekad=base.window_start_dekad,
                    window_end_dekad=base.window_end_dekad,
                    peak_harvest_dekad=base.peak_harvest_dekad,
                    window_start_date=base.window_start_date,
                    window_end_date=base.window_end_date,
                    peak_start_date=base.peak_start_date,
                    peak_end_date=base.peak_end_date,
                    baseline_harvest_start_month=base.baseline_harvest_start_month,
                    baseline_harvest_end_month=base.baseline_harvest_end_month,
                    shift_dekads=0,
                    shift_reason=shift_reason,
                    source_reference=base.source_reference,
                    validation_level=validation_level,
                    confidence_score=confidence,
                    uncertainty_note=f"Irrigation buffered early rainfall deficit: {shift_reason}.",
                )
            return base

        # 3. Apply dekadal shift to harvest start, end and peak
        # Parse start and end dekad components
        s_y, s_m, s_d = (
            int(base.window_start_dekad[:4]),
            int(base.window_start_dekad[5:7]),
            int(base.window_start_dekad[9]),
        )
        e_y, e_m, e_d = (
            int(base.window_end_dekad[:4]),
            int(base.window_end_dekad[5:7]),
            int(base.window_end_dekad[9]),
        )

        ns_y, ns_m, ns_d = shift_dekad(s_y, s_m, s_d, shift)
        ne_y, ne_m, ne_d = shift_dekad(e_y, e_m, e_d, shift)

        nw_start_date, _ = get_dekad_bounds(ns_y, ns_m, ns_d)
        _, nw_end_date = get_dekad_bounds(ne_y, ne_m, ne_d)

        new_peak_dekad: str | None = None
        new_p_start: date | None = None
        new_p_end: date | None = None

        if base.peak_harvest_dekad is not None:
            p_y, p_m, p_d = (
                int(base.peak_harvest_dekad[:4]),
                int(base.peak_harvest_dekad[5:7]),
                int(base.peak_harvest_dekad[9]),
            )
            np_y, np_m, np_d = shift_dekad(p_y, p_m, p_d, shift)
            new_peak_dekad = format_dekad_label(np_y, np_m, np_d)
            new_p_start, _ = get_dekad_bounds(np_y, np_m, 1)
            _, new_p_end = get_dekad_bounds(np_y, np_m, 3)

        return HarvestWindowProjection(
            zone_code=record.zone_code,
            zone_name=record.zone_name,
            crop=record.crop,
            product_code=record.product_code,
            season_name=record.season_name,
            crop_cycle=record.crop_cycle,
            campaign=f"campaign_{year}_{year + 1}",
            crop_regime=str(record.crop_regime),
            window_start_dekad=format_dekad_label(ns_y, ns_m, ns_d),
            window_end_dekad=format_dekad_label(ne_y, ne_m, ne_d),
            peak_harvest_dekad=new_peak_dekad,
            window_start_date=nw_start_date,
            window_end_date=nw_end_date,
            peak_start_date=new_p_start,
            peak_end_date=new_p_end,
            baseline_harvest_start_month=base.baseline_harvest_start_month,
            baseline_harvest_end_month=base.baseline_harvest_end_month,
            shift_dekads=shift,
            shift_reason=shift_reason,
            source_reference=record.source_reference,
            validation_level=validation_level,
            confidence_score=confidence,
            uncertainty_note=(
                f"Agronomically shifted by {shift} dekad(s) due to agroclimatic condition: {shift_reason}. "
                "Experimental model qualification; in situ phenological validation required."
            ),
        )

    def evaluate_against_market_arrivals(
        self,
        harvest_window: HarvestWindowProjection,
        arrival_records: Sequence[StockRecord | StockObservation],
        market_code: str | None = None,
    ) -> HarvestConfrontationResult:
        """Confront projected harvest window against authentic empirical market arrival records."""
        # Standardize and filter records by product and target
        matching: list[dict[str, Any]] = []
        for rec in arrival_records:
            if isinstance(rec, StockRecord):
                target = rec.target or QuantityTarget.STOCK_INVENTORY.value
                m_code = rec.market_code or "UNKNOWN"
                prod = rec.product_raw
                p_start = rec.period_start
                p_end = rec.period_end
                q_val = rec.quantity_value or 0.0
            else:
                target = getattr(rec, "target", None) or QuantityTarget.STOCK_INVENTORY.value
                m_code = getattr(rec, "market_code", None) or "UNKNOWN"
                prod = rec.product_raw
                p_start = rec.period_start
                p_end = rec.period_end
                q_val = float(rec.quantity_value) if rec.quantity_value is not None else 0.0

            if target != QuantityTarget.INFLOW_ARRIVAL.value:
                continue
            if market_code and m_code != market_code:
                continue

            # Compare product compatibility (e.g. RICE_PADDY matches rice_vary_gasy or rice_paddy)
            crop_lower = harvest_window.crop.lower()
            prod_lower = prod.lower()
            if (
                crop_lower not in prod_lower
                and harvest_window.product_code.lower() not in prod_lower
            ):
                continue

            matching.append(
                {
                    "period_start": p_start,
                    "period_end": p_end,
                    "quantity_kg": q_val,
                }
            )

        if not matching:
            return HarvestConfrontationResult(
                zone_code=harvest_window.zone_code,
                product_raw=harvest_window.crop,
                campaign=harvest_window.campaign,
                window_start_date=harvest_window.window_start_date,
                window_end_date=harvest_window.window_end_date,
                total_records_tested=0,
                arrivals_within_harvest_window_kg=0.0,
                arrivals_outside_harvest_window_kg=0.0,
                temporal_alignment_ratio=0.0,
                peak_arrival_date=None,
                peak_inside_window=False,
                evaluation_verdict="unverified_sparse_data",
                confrontation_details="No matching inflow arrival records found for independent confrontation.",
            )

        w_start = harvest_window.window_start_date
        w_end = harvest_window.window_end_date

        within_kg = 0.0
        outside_kg = 0.0
        max_qty = -1.0
        peak_date: date | None = None

        for item in matching:
            q = item["quantity_kg"]
            p_s = item["period_start"]
            p_e = item["period_end"]

            # Check overlap with window
            if p_s <= w_end and p_e >= w_start:
                within_kg += q
            else:
                outside_kg += q

            if q > max_qty:
                max_qty = q
                peak_date = p_s

        total_kg = within_kg + outside_kg
        ratio = (within_kg / total_kg) if total_kg > 0 else 0.0
        peak_inside = (w_start <= peak_date <= w_end) if peak_date else False

        if ratio >= 0.70 and peak_inside:
            verdict = "consistent"
        elif ratio >= 0.40:
            verdict = "partially_aligned"
        else:
            verdict = "shifted"

        return HarvestConfrontationResult(
            zone_code=harvest_window.zone_code,
            product_raw=harvest_window.crop,
            campaign=harvest_window.campaign,
            window_start_date=w_start,
            window_end_date=w_end,
            total_records_tested=len(matching),
            arrivals_within_harvest_window_kg=round(within_kg, 2),
            arrivals_outside_harvest_window_kg=round(outside_kg, 2),
            temporal_alignment_ratio=round(ratio, 4),
            peak_arrival_date=peak_date,
            peak_inside_window=peak_inside,
            evaluation_verdict=verdict,
            confrontation_details=(
                f"Confronted against {len(matching)} market arrival observations: "
                f"{within_kg:,.1f} kg ({ratio * 100:.1f}%) occurred within the projected window. "
                f"Peak arrival observed on {peak_date} (inside_window={peak_inside})."
            ),
        )
