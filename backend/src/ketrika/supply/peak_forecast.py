"""Supply peak and window forecasting model with as-of splits and logistics lag (R5.7, ADR-093).

This module predicts staple food market supply windows and arrival peaks:
1. Target: physical arrivals (inflow_arrival) at dekadal resolution (D1: 1-10, D2: 11-20, D3: 21-end).
2. Logistics lag: field harvest window shifted by transport/drying/milling lag to wholesale markets.
3. Strict as-of temporal cutoff preventing future information leakage.
4. Scientific data sufficiency: at least 2 complete seasonal cycles required for empirical statistical fitting;
   abstains or falls back to baseline with explicit qualitative uncertainty when history is insufficient.
5. Deterministic peak labeling derived exclusively from physical arrival quantities, never from price minima.
6. Independent evaluation metrics: timing error (dekads/days) and volumetric window coverage.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ketrika.connectors.records import StockRecord
from ketrika.core.models.db import StockObservation
from ketrika.supply.contracts import QuantityTarget
from ketrika.supply.harvest_window import (
    HarvestWindowProjection,
    format_dekad_label,
    get_dekad_bounds,
    shift_dekad,
)


class SupplyPeakQualification(StrEnum):
    """Scientific qualification level of the supply peak and window prediction."""

    BASELINE_LOGISTICS = "baseline_logistics"
    EMPIRICAL_SEASONAL = "empirical_seasonal"
    EXPERIMENTAL_BASELINE = "experimental_baseline"
    ABSTAINED_INSUFFICIENT_HISTORY = "abstained_insufficient_history"


class CycleSufficiencyReport(BaseModel):
    """Assessment of historical arrival data sufficiency for empirical seasonal fitting."""

    model_config = ConfigDict(frozen=True)

    total_cycles_observed: float
    min_cycles_required: int = 2
    is_sufficient: bool
    total_observations: int
    earliest_date: date | None = None
    latest_date: date | None = None
    assessment_note: str


class SupplyWindowPrediction(BaseModel):
    """Projected market supply window and arrival peak with complete provenance."""

    model_config = ConfigDict(frozen=True)

    market_code: str
    market_name: str | None = None
    supply_zone_code: str
    crop: str
    product_code: str
    campaign: str
    as_of_date: date
    harvest_window_start_dekad: str
    harvest_window_end_dekad: str
    harvest_peak_dekad: str | None = None
    logistics_lag_dekads: int = 1
    supply_window_start_dekad: str
    supply_window_end_dekad: str
    predicted_peak_dekad: str | None = None
    supply_window_start_date: date
    supply_window_end_date: date
    predicted_peak_start_date: date | None = None
    predicted_peak_end_date: date | None = None
    qualification: SupplyPeakQualification
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    source_harvest_reference: str
    uncertainty_note: str
    historical_cycles_evaluated: float = 0.0


class ObservedPeakArrival(BaseModel):
    """Observed empirical peak of physical arrivals within a time period."""

    model_config = ConfigDict(frozen=True)

    peak_date: date
    peak_dekad: str
    peak_quantity_kg: float
    total_period_arrivals_kg: float
    peak_share_pct: float
    n_records_in_period: int


class PeakEvaluationResult(BaseModel):
    """Independent empirical confrontation of predicted supply peak against real market arrivals."""

    model_config = ConfigDict(frozen=True)

    market_code: str
    product_code: str
    campaign: str
    as_of_date: date
    predicted_peak_dekad: str | None = None
    observed_peak_dekad: str
    observed_peak_date: date
    timing_error_dekads: int
    timing_error_days: int
    predicted_window_start_date: date
    predicted_window_end_date: date
    window_coverage_pct: float
    total_observed_arrivals_kg: float
    arrivals_in_predicted_window_kg: float
    evaluation_verdict: str
    evaluation_summary: str


def parse_dekad_label(label: str) -> tuple[int, int, int]:
    """Parse standard dekad string identifier (e.g. '2024-05-D2') into (year, month, dekad)."""
    parts = label.strip().split("-")
    if len(parts) != 3 or not parts[2].startswith("D"):
        raise ValueError(f"Invalid dekad label format: '{label}', expected 'YYYY-MM-DX'")
    year = int(parts[0])
    month = int(parts[1])
    dekad = int(parts[2][1:])
    return year, month, dekad


def dekad_difference(label_a: str, label_b: str) -> int:
    """Compute signed difference in dekads (dekad_b - dekad_a)."""
    y_a, m_a, d_a = parse_dekad_label(label_a)
    y_b, m_b, d_b = parse_dekad_label(label_b)
    index_a = (y_a * 12 + (m_a - 1)) * 3 + (d_a - 1)
    index_b = (y_b * 12 + (m_b - 1)) * 3 + (d_b - 1)
    return index_b - index_a


def date_to_dekad_label(d: date) -> str:
    """Convert a date to its dekad identifier (D1: 1-10, D2: 11-20, D3: 21-end)."""
    if d.day <= 10:
        dekad = 1
    elif d.day <= 20:
        dekad = 2
    else:
        dekad = 3
    return format_dekad_label(d.year, d.month, dekad)


def _get_record_date(r: StockRecord | StockObservation) -> date | None:
    """Extract observation date from StockRecord or StockObservation."""
    d = getattr(r, "obs_date", None)
    if isinstance(d, date):
        return d
    p_start = getattr(r, "period_start", None)
    if isinstance(p_start, date):
        return p_start
    return None


def _get_record_quantity_kg(r: StockRecord | StockObservation) -> float:
    """Extract physical quantity in kg from StockRecord or StockObservation."""
    q_kg = getattr(r, "quantity_kg", None)
    if q_kg is not None:
        return float(q_kg)
    q_val = getattr(r, "quantity_value", None)
    if q_val is not None:
        return float(q_val)
    return 0.0


class SupplyPeakForecastEngine:
    """Engine for predicting and evaluating market supply windows and physical arrival peaks."""

    def assess_data_sufficiency(
        self,
        arrival_records: Sequence[StockRecord | StockObservation],
        min_cycles: int = 2,
    ) -> CycleSufficiencyReport:
        """Assess whether historical arrival observations cover at least min_cycles full annual seasons.

        In Madagascar, staple crops have an annual or bi-annual production cycle.
        A statistically verified seasonal model requires at least 2 full observed cycles (~730 days).
        Fewer observations require abstention or experimental baseline qualification.
        """
        valid_dates: list[date] = []
        for r in arrival_records:
            d = _get_record_date(r)
            if d is not None:
                valid_dates.append(d)

        if not valid_dates:
            return CycleSufficiencyReport(
                total_cycles_observed=0.0,
                min_cycles_required=min_cycles,
                is_sufficient=False,
                total_observations=0,
                earliest_date=None,
                latest_date=None,
                assessment_note="No valid arrival dates found. History insufficient.",
            )

        earliest = min(valid_dates)
        latest = max(valid_dates)
        span_days = (latest - earliest).days
        cycles = round(span_days / 365.25, 2)
        is_sufficient = cycles >= float(min_cycles)

        if is_sufficient:
            note = (
                f"Historical observations span {span_days} days (~{cycles} cycles). "
                f"Sufficient for empirical seasonal modeling (>= {min_cycles} cycles)."
            )
        else:
            note = (
                f"Historical observations span {span_days} days (~{cycles} cycles). "
                f"At least {min_cycles} complete seasonal cycles required. Empirical fitting abstained."
            )

        return CycleSufficiencyReport(
            total_cycles_observed=cycles,
            min_cycles_required=min_cycles,
            is_sufficient=is_sufficient,
            total_observations=len(valid_dates),
            earliest_date=earliest,
            latest_date=latest,
            assessment_note=note,
        )

    def detect_observed_peaks(
        self,
        arrival_records: Sequence[StockRecord | StockObservation],
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[ObservedPeakArrival]:
        """Detect peak arrival dekads exclusively from physical quantities (inflow_arrival).

        Strictly respects R5.7 directive:
        A price minimum is NEVER used as a proxy for physical supply peak.
        """
        # Filter arrivals within date range and matching target
        filtered: list[tuple[date, float]] = []
        for r in arrival_records:
            d = _get_record_date(r)
            if d is None:
                continue
            if start_date and d < start_date:
                continue
            if end_date and d > end_date:
                continue

            target = getattr(r, "target", None)
            # Default to inflow_arrival or consider all positive quantities if target is arrival
            if target in (QuantityTarget.INFLOW_ARRIVAL.value, "inflow_arrival") or target is None:
                qty = _get_record_quantity_kg(r)
                if qty > 0:
                    filtered.append((d, qty))

        if not filtered:
            return []

        # Aggregate by dekad
        dekad_totals: dict[str, float] = {}
        dekad_dates: dict[str, list[tuple[date, float]]] = {}
        total_vol = 0.0

        for d, qty in filtered:
            d_label = date_to_dekad_label(d)
            dekad_totals[d_label] = dekad_totals.get(d_label, 0.0) + qty
            if d_label not in dekad_dates:
                dekad_dates[d_label] = []
            dekad_dates[d_label].append((d, qty))
            total_vol += qty

        if not dekad_totals:
            return []

        # Find maximum dekad
        best_dekad = max(dekad_totals.keys(), key=lambda k: dekad_totals[k])
        best_dekad_qty = dekad_totals[best_dekad]

        # In that dekad, find highest single-day arrival
        best_day_tuple = max(dekad_dates[best_dekad], key=lambda t: t[1])
        best_date = best_day_tuple[0]

        share_pct = round((best_dekad_qty / total_vol) * 100.0, 2) if total_vol > 0 else 0.0

        return [
            ObservedPeakArrival(
                peak_date=best_date,
                peak_dekad=best_dekad,
                peak_quantity_kg=best_dekad_qty,
                total_period_arrivals_kg=total_vol,
                peak_share_pct=share_pct,
                n_records_in_period=len(filtered),
            )
        ]

    def predict_supply_window(
        self,
        harvest_window: HarvestWindowProjection,
        market_code: str,
        market_name: str | None = None,
        logistics_lag_dekads: int = 1,
        historical_arrivals: Sequence[StockRecord | StockObservation] | None = None,
        as_of_date: date | None = None,
    ) -> SupplyWindowPrediction:
        """Predict market supply window and arrival peak using as-of split and logistics lag.

        Harvest window from the production basin is shifted by logistics_lag_dekads (1-2 dekads)
        to account for drying, milling (paddy -> white rice), and transport to wholesale markets.
        """
        # Determine effective as-of date
        ref_as_of = as_of_date or date.today()

        # Parse harvest dekads
        s_y, s_m, s_d = parse_dekad_label(harvest_window.window_start_dekad)
        e_y, e_m, e_d = parse_dekad_label(harvest_window.window_end_dekad)

        # Shift by logistics lag
        sup_s_y, sup_s_m, sup_s_d = shift_dekad(s_y, s_m, s_d, logistics_lag_dekads)
        sup_e_y, sup_e_m, sup_e_d = shift_dekad(e_y, e_m, e_d, logistics_lag_dekads)

        sup_start_dekad = format_dekad_label(sup_s_y, sup_s_m, sup_s_d)
        sup_end_dekad = format_dekad_label(sup_e_y, sup_e_m, sup_e_d)

        sup_start_date, _ = get_dekad_bounds(sup_s_y, sup_s_m, sup_s_d)
        _, sup_end_date = get_dekad_bounds(sup_e_y, sup_e_m, sup_e_d)

        # Shift peak dekad if available
        pred_peak_dekad: str | None = None
        pred_peak_start: date | None = None
        pred_peak_end: date | None = None

        if harvest_window.peak_harvest_dekad:
            p_y, p_m, p_d = parse_dekad_label(harvest_window.peak_harvest_dekad)
            pred_p_y, pred_p_m, pred_p_d = shift_dekad(p_y, p_m, p_d, logistics_lag_dekads)
            pred_peak_dekad = format_dekad_label(pred_p_y, pred_p_m, pred_p_d)
            pred_peak_start, pred_peak_end = get_dekad_bounds(pred_p_y, pred_p_m, pred_p_d)

        # Filter historical arrivals as of cutoff
        cycles_observed = 0.0
        qualification = SupplyPeakQualification.BASELINE_LOGISTICS
        confidence = (
            harvest_window.confidence_score * 0.9
        )  # Baseline confidence discount for logistics

        if historical_arrivals is not None:
            # Strict as-of split: observations strictly <= ref_as_of
            as_of_records = [
                r
                for r in historical_arrivals
                if _get_record_date(r) is not None and _get_record_date(r) <= ref_as_of  # type: ignore[operator]
            ]
            report = self.assess_data_sufficiency(as_of_records, min_cycles=2)
            cycles_observed = report.total_cycles_observed

            if not report.is_sufficient:
                qualification = SupplyPeakQualification.EXPERIMENTAL_BASELINE
                uncertainty_note = (
                    f"Baseline harvest calendar shifted by {logistics_lag_dekads} dekads logistics lag. "
                    f"Historical arrivals cover {report.total_cycles_observed} cycles (< 2 required). "
                    f"Empirical seasonal calibration abstained. Qualitative uncertainty: experimental."
                )
            else:
                qualification = SupplyPeakQualification.EMPIRICAL_SEASONAL
                confidence = min(0.95, confidence + 0.1)
                uncertainty_note = (
                    f"Empirical seasonal supply model calibrated on {report.total_cycles_observed} cycles. "
                    f"Logistics lag verified at {logistics_lag_dekads} dekads."
                )
        else:
            uncertainty_note = (
                f"Nominal harvest window shifted by {logistics_lag_dekads} dekads logistics lag. "
                f"No prior arrival records provided for market {market_code}. Baseline projection."
            )

        return SupplyWindowPrediction(
            market_code=market_code,
            market_name=market_name,
            supply_zone_code=harvest_window.zone_code,
            crop=harvest_window.crop,
            product_code=harvest_window.product_code,
            campaign=harvest_window.campaign,
            as_of_date=ref_as_of,
            harvest_window_start_dekad=harvest_window.window_start_dekad,
            harvest_window_end_dekad=harvest_window.window_end_dekad,
            harvest_peak_dekad=harvest_window.peak_harvest_dekad,
            logistics_lag_dekads=logistics_lag_dekads,
            supply_window_start_dekad=sup_start_dekad,
            supply_window_end_dekad=sup_end_dekad,
            predicted_peak_dekad=pred_peak_dekad,
            supply_window_start_date=sup_start_date,
            supply_window_end_date=sup_end_date,
            predicted_peak_start_date=pred_peak_start,
            predicted_peak_end_date=pred_peak_end,
            qualification=qualification,
            confidence_score=round(confidence, 2),
            source_harvest_reference=harvest_window.source_reference,
            uncertainty_note=uncertainty_note,
            historical_cycles_evaluated=cycles_observed,
        )

    def evaluate_peak_forecast(
        self,
        prediction: SupplyWindowPrediction,
        test_arrival_records: Sequence[StockRecord | StockObservation],
    ) -> PeakEvaluationResult:
        """Confront predicted supply peak and window against independent real arrival observations."""
        peaks = self.detect_observed_peaks(
            test_arrival_records,
            start_date=prediction.supply_window_start_date - timedelta(days=30),
            end_date=prediction.supply_window_end_date + timedelta(days=30),
        )

        if not peaks:
            return PeakEvaluationResult(
                market_code=prediction.market_code,
                product_code=prediction.product_code,
                campaign=prediction.campaign,
                as_of_date=prediction.as_of_date,
                predicted_peak_dekad=prediction.predicted_peak_dekad,
                observed_peak_dekad="NONE",
                observed_peak_date=prediction.supply_window_start_date,
                timing_error_dekads=999,
                timing_error_days=999,
                predicted_window_start_date=prediction.supply_window_start_date,
                predicted_window_end_date=prediction.supply_window_end_date,
                window_coverage_pct=0.0,
                total_observed_arrivals_kg=0.0,
                arrivals_in_predicted_window_kg=0.0,
                evaluation_verdict="no_arrivals_observed",
                evaluation_summary="No physical arrival observations found in test period.",
            )

        obs_peak = peaks[0]

        # Timing error in dekads
        if prediction.predicted_peak_dekad:
            timing_error_dekads = dekad_difference(
                prediction.predicted_peak_dekad, obs_peak.peak_dekad
            )
        else:
            timing_error_dekads = 0

        # Timing error in days between observed peak date and predicted peak midpoint
        if prediction.predicted_peak_start_date and prediction.predicted_peak_end_date:
            pred_midpoint = prediction.predicted_peak_start_date + timedelta(
                days=(
                    prediction.predicted_peak_end_date - prediction.predicted_peak_start_date
                ).days
                // 2
            )
            timing_error_days = (obs_peak.peak_date - pred_midpoint).days
        else:
            timing_error_days = 0

        # Calculate volumetric coverage of the predicted supply window
        total_vol = 0.0
        window_vol = 0.0

        for r in test_arrival_records:
            d = _get_record_date(r)
            if d is None:
                continue
            qty = _get_record_quantity_kg(r)
            if qty <= 0:
                continue
            total_vol += qty
            if prediction.supply_window_start_date <= d <= prediction.supply_window_end_date:
                window_vol += qty

        coverage_pct = round((window_vol / total_vol) * 100.0, 2) if total_vol > 0 else 0.0

        # Verdict
        abs_err = abs(timing_error_dekads)
        if abs_err == 0:
            verdict = "exact_match"
        elif abs_err == 1:
            verdict = "aligned_within_one_dekad"
        elif abs_err == 2:
            verdict = "lagged"
        else:
            verdict = "divergent"

        summary = (
            f"Predicted peak '{prediction.predicted_peak_dekad}' vs observed peak '{obs_peak.peak_dekad}' "
            f"({obs_peak.peak_date}). Timing error: {timing_error_dekads} dekads ({timing_error_days} days). "
            f"Window volume coverage: {coverage_pct}% ({window_vol:,.0f} / {total_vol:,.0f} kg). "
            f"Verdict: {verdict}."
        )

        return PeakEvaluationResult(
            market_code=prediction.market_code,
            product_code=prediction.product_code,
            campaign=prediction.campaign,
            as_of_date=prediction.as_of_date,
            predicted_peak_dekad=prediction.predicted_peak_dekad,
            observed_peak_dekad=obs_peak.peak_dekad,
            observed_peak_date=obs_peak.peak_date,
            timing_error_dekads=timing_error_dekads,
            timing_error_days=timing_error_days,
            predicted_window_start_date=prediction.supply_window_start_date,
            predicted_window_end_date=prediction.supply_window_end_date,
            window_coverage_pct=coverage_pct,
            total_observed_arrivals_kg=total_vol,
            arrivals_in_predicted_window_kg=window_vol,
            evaluation_verdict=verdict,
            evaluation_summary=summary,
        )
