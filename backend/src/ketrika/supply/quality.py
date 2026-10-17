"""Quality control, coverage matrices, and temporal non-double-counting for market supply (R5.3, ADR-090, SPECS §27).

This module enforces strict metrological data quality checks on agricultural quantities and market supplies:
1. Strict distinction between spot readings and cumulative periods, flows and inventories.
2. Verified physical unit conversions (refusal of unproven packaging variations).
3. Market x Period matrix construction detecting surveyed vs unmonitored days.
4. Core rule: ABSENCE OF SURVEY != ZERO ARRIVAL (missing data must never be imputed as 0.0 kg).
5. Sampling coverage quantification (ratio of monitored days, measured vs declared shares) without unweighted extrapolation.
6. Detection and prevention of temporal double-counting (daily cumulation subsumed in monthly total).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

from ketrika.connectors.records import StockRecord
from ketrika.core.models.db import StockObservation
from ketrika.supply.contracts import (
    QuantityMeasurementMode,
    QuantityTarget,
    QuantityUnit,
    convert_quantity_to_kg,
)


class ObservationPresence(StrEnum):
    """Presence status of an observation on a given market day."""

    OBSERVED_ARRIVAL = "observed_arrival"
    ZERO_ARRIVAL_VERIFIED = "zero_arrival_verified"
    MISSING_SURVEY = "missing_survey"


class MarketPeriodCell(BaseModel):
    """State of a specific market x product on a calendar date."""

    model_config = ConfigDict(frozen=True)

    calendar_date: date
    market_code: str
    product_raw: str
    target: str
    presence: ObservationPresence
    quantity_kg: float | None = None
    measurement_mode: str | None = None
    raw_unit: str | None = None
    raw_quantity: str | None = None

    @property
    def is_missing(self) -> bool:
        """Return True if survey was not conducted on this day."""
        return self.presence == ObservationPresence.MISSING_SURVEY

    @property
    def is_zero(self) -> bool:
        """Return True if survey verified zero arrivals (measured or officially declared zero)."""
        return self.presence == ObservationPresence.ZERO_ARRIVAL_VERIFIED


class MarketCoverageStats(BaseModel):
    """Sampling coverage metrics for a market, product and target over an interval."""

    model_config = ConfigDict(frozen=True)

    market_code: str
    product_raw: str
    target: str
    start_date: date
    end_date: date
    total_calendar_days: int
    surveyed_days: int
    unmonitored_days: int
    sampling_coverage_rate: float
    total_observed_quantity_kg: float
    measured_scale_count: int
    declared_trader_count: int
    estimated_survey_count: int
    certified_measurement_ratio: float


class TemporalDoubleCountViolation(BaseModel):
    """Detection of temporal overlapping records creating double counting hazard."""

    model_config = ConfigDict(frozen=True)

    market_code: str
    product_raw: str
    target: str
    parent_period: tuple[date, date]
    parent_quantity_kg: float
    child_periods: list[tuple[date, date]]
    child_sum_quantity_kg: float
    violation_type: str
    details: str


class UnitConversionAudit(BaseModel):
    """Verification of physical unit conversion against standardized metric factors."""

    model_config = ConfigDict(frozen=True)

    product_raw: str
    unit_raw: str
    quantity_raw: str | float
    converted_kg: float
    expected_kg: float
    is_valid: bool
    discrepancy_reason: str | None = None


class SupplyDataQualityReport(BaseModel):
    """Comprehensive data quality report for market supply and quantities."""

    model_config = ConfigDict(frozen=True)

    is_valid: bool
    total_records_analyzed: int
    markets_analyzed: list[str]
    coverage_by_market: list[MarketCoverageStats]
    double_counting_violations: list[TemporalDoubleCountViolation]
    conversion_audit_issues: list[UnitConversionAudit]
    unmonitored_days_detected: bool
    missing_vs_zero_strictly_respected: bool


class SupplyQualityChecker:
    """Rigorous metrological inspector for market supply and agricultural quantities."""

    @staticmethod
    def _extract_record_attrs(record: StockRecord | StockObservation) -> dict[str, Any]:
        """Extract standardized attributes from either Pydantic StockRecord or DB StockObservation."""
        if isinstance(record, StockRecord):
            return {
                "target": record.target or QuantityTarget.STOCK_INVENTORY.value,
                "measurement_mode": record.measurement_mode or QuantityMeasurementMode.DECLARED_TRADER.value,
                "market_code": record.market_code or "UNKNOWN_MARKET",
                "product_raw": record.product_raw,
                "period_start": record.period_start,
                "period_end": record.period_end,
                "quantity_value": record.quantity_value,
                "quantity_raw": record.quantity_raw,
                "unit_raw": record.unit_raw,
            }
        # StockObservation
        return {
            "target": getattr(record, "target", None) or QuantityTarget.STOCK_INVENTORY.value,
            "measurement_mode": getattr(record, "measurement_mode", None) or QuantityMeasurementMode.DECLARED_TRADER.value,
            "market_code": getattr(record, "market_code", None) or "UNKNOWN_MARKET",
            "product_raw": record.product_raw,
            "period_start": record.period_start,
            "period_end": record.period_end,
            "quantity_value": float(record.quantity_value) if record.quantity_value is not None else None,
            "quantity_raw": record.quantity_raw,
            "unit_raw": record.unit_raw,
        }

    def build_market_period_matrix(
        self,
        records: Sequence[StockRecord | StockObservation],
        start_date: date,
        end_date: date,
        target: str = QuantityTarget.INFLOW_ARRIVAL.value,
    ) -> dict[tuple[str, str, date], MarketPeriodCell]:
        """Build explicit market x product x calendar date matrix.

        Distinguishes observed presence, verified zero arrivals, and unmonitored days.
        Crucial principle: missing surveys are NOT populated as zero kg.
        """
        if end_date < start_date:
            raise ValueError("end_date cannot be earlier than start_date")

        # Map existing observations by (market_code, product_raw, date)
        observations_map: dict[tuple[str, str, date], list[dict[str, Any]]] = {}
        all_markets: set[str] = set()
        all_products: set[str] = set()

        for rec in records:
            attrs = self._extract_record_attrs(rec)
            if attrs["target"] != target:
                continue
            m_code = attrs["market_code"]
            prod = attrs["product_raw"]
            all_markets.add(m_code)
            all_products.add(prod)

            # Expand multi-day periods or spot days
            cur = attrs["period_start"]
            p_end = attrs["period_end"]
            while cur <= p_end:
                if start_date <= cur <= end_date:
                    key = (m_code, prod, cur)
                    if key not in observations_map:
                        observations_map[key] = []
                    observations_map[key].append(attrs)
                cur += timedelta(days=1)

        matrix: dict[tuple[str, str, date], MarketPeriodCell] = {}
        delta_days = (end_date - start_date).days + 1

        for m_code in sorted(all_markets):
            for prod in sorted(all_products):
                for d_offset in range(delta_days):
                    current_day = start_date + timedelta(days=d_offset)
                    cell_key = (m_code, prod, current_day)

                    if cell_key in observations_map:
                        obs_list = observations_map[cell_key]
                        # Take the primary observation
                        primary = obs_list[0]
                        q_val = primary["quantity_value"]

                        if q_val is not None and q_val == 0.0:
                            presence = ObservationPresence.ZERO_ARRIVAL_VERIFIED
                        else:
                            presence = ObservationPresence.OBSERVED_ARRIVAL

                        matrix[cell_key] = MarketPeriodCell(
                            calendar_date=current_day,
                            market_code=m_code,
                            product_raw=prod,
                            target=target,
                            presence=presence,
                            quantity_kg=q_val,
                            measurement_mode=primary["measurement_mode"],
                            raw_unit=primary["unit_raw"],
                            raw_quantity=str(primary["quantity_raw"]) if primary["quantity_raw"] is not None else None,
                        )
                    else:
                        # Non-enquêté: absence de relevé != zéro
                        matrix[cell_key] = MarketPeriodCell(
                            calendar_date=current_day,
                            market_code=m_code,
                            product_raw=prod,
                            target=target,
                            presence=ObservationPresence.MISSING_SURVEY,
                            quantity_kg=None,  # STRICT: never 0.0
                            measurement_mode=None,
                            raw_unit=None,
                            raw_quantity=None,
                        )

        return matrix

    def detect_temporal_overlap_double_counting(
        self,
        records: Sequence[StockRecord | StockObservation],
    ) -> list[TemporalDoubleCountViolation]:
        """Detect temporal double counting hazards where an aggregate period overlaps finer records."""
        violations: list[TemporalDoubleCountViolation] = []

        # Group by (market_code, product_raw, target)
        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for rec in records:
            attrs = self._extract_record_attrs(rec)
            key = (attrs["market_code"], attrs["product_raw"], attrs["target"])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(attrs)

        for (m_code, prod, target), rec_list in grouped.items():
            # For cumulative targets (flows), check if a longer period subsumes shorter periods
            if target not in (QuantityTarget.INFLOW_ARRIVAL.value, QuantityTarget.HARVEST_VOLUME.value):
                continue

            for parent in rec_list:
                p_start = parent["period_start"]
                p_end = parent["period_end"]
                p_duration = (p_end - p_start).days

                if p_duration <= 0:
                    continue  # Spot observation cannot subsume others

                children: list[dict[str, Any]] = []
                for other in rec_list:
                    if other is parent:
                        continue
                    o_start = other["period_start"]
                    o_end = other["period_end"]

                    # Check if other is strictly contained or overlapping within parent
                    if (
                        p_start <= o_start <= p_end
                        and p_start <= o_end <= p_end
                        and (o_end - o_start).days < p_duration
                    ):
                        children.append(other)

                if children:
                    p_qty = parent["quantity_value"] or 0.0
                    c_sum = sum(c["quantity_value"] or 0.0 for c in children)
                    child_periods = [(c["period_start"], c["period_end"]) for c in children]

                    violations.append(
                        TemporalDoubleCountViolation(
                            market_code=m_code,
                            product_raw=prod,
                            target=target,
                            parent_period=(p_start, p_end),
                            parent_quantity_kg=p_qty,
                            child_periods=child_periods,
                            child_sum_quantity_kg=c_sum,
                            violation_type="subsumed_interval_double_count",
                            details=(
                                f"Aggregate period {p_start} to {p_end} ({p_qty:,.1f} kg) overlaps with "
                                f"{len(children)} finer observation(s) summing {c_sum:,.1f} kg. "
                                f"Summing both would cause destructive double counting."
                            ),
                        )
                    )

        return violations

    def calculate_market_coverage(
        self,
        records: Sequence[StockRecord | StockObservation],
        start_date: date,
        end_date: date,
        target: str = QuantityTarget.INFLOW_ARRIVAL.value,
    ) -> list[MarketCoverageStats]:
        """Compute sampling coverage metrics per market and product over the calendar interval."""
        matrix = self.build_market_period_matrix(records, start_date, end_date, target=target)
        if not matrix:
            return []

        # Group cells by (market_code, product_raw)
        grouped: dict[tuple[str, str], list[MarketPeriodCell]] = {}
        for (m_code, prod, _), cell in matrix.items():
            k = (m_code, prod)
            if k not in grouped:
                grouped[k] = []
            grouped[k].append(cell)

        stats_list: list[MarketCoverageStats] = []
        for (m_code, prod), cells in grouped.items():
            total_days = len(cells)
            surveyed_cells = [c for c in cells if not c.is_missing]
            surveyed_count = len(surveyed_cells)
            unmonitored_count = total_days - surveyed_count
            coverage_rate = (surveyed_count / total_days) if total_days > 0 else 0.0

            total_qty = sum(c.quantity_kg or 0.0 for c in surveyed_cells)

            measured_scale = sum(
                1 for c in surveyed_cells if c.measurement_mode == QuantityMeasurementMode.MEASURED_SCALE.value
            )
            declared_trader = sum(
                1 for c in surveyed_cells if c.measurement_mode == QuantityMeasurementMode.DECLARED_TRADER.value
            )
            estimated_survey = sum(
                1 for c in surveyed_cells if c.measurement_mode == QuantityMeasurementMode.ESTIMATED_SURVEY.value
            )

            cert_ratio = (measured_scale / surveyed_count) if surveyed_count > 0 else 0.0

            stats_list.append(
                MarketCoverageStats(
                    market_code=m_code,
                    product_raw=prod,
                    target=target,
                    start_date=start_date,
                    end_date=end_date,
                    total_calendar_days=total_days,
                    surveyed_days=surveyed_count,
                    unmonitored_days=unmonitored_count,
                    sampling_coverage_rate=round(coverage_rate, 4),
                    total_observed_quantity_kg=round(total_qty, 2),
                    measured_scale_count=measured_scale,
                    declared_trader_count=declared_trader,
                    estimated_survey_count=estimated_survey,
                    certified_measurement_ratio=round(cert_ratio, 4),
                )
            )

        return stats_list

    def audit_unit_conversions(
        self,
        records: Sequence[StockRecord | StockObservation],
    ) -> list[UnitConversionAudit]:
        """Verify that converted kilogram values exactly match standardized physical factors."""
        audits: list[UnitConversionAudit] = []

        for rec in records:
            attrs = self._extract_record_attrs(rec)
            raw_unit_str = attrs["unit_raw"]
            raw_qty_val = attrs["quantity_raw"]
            actual_kg = attrs["quantity_value"]
            prod = attrs["product_raw"]

            if not raw_unit_str or raw_qty_val is None or actual_kg is None:
                continue

            try:
                numeric_raw = float(str(raw_qty_val).replace(" ", "").replace(",", "."))
            except ValueError:
                audits.append(
                    UnitConversionAudit(
                        product_raw=prod,
                        unit_raw=str(raw_unit_str),
                        quantity_raw=str(raw_qty_val),
                        converted_kg=float(actual_kg),
                        expected_kg=0.0,
                        is_valid=False,
                        discrepancy_reason="Unparseable raw numeric quantity",
                    )
                )
                continue

            # Attempt standard conversion
            try:
                standard_unit = QuantityUnit(raw_unit_str.lower().strip())
                expected_kg = convert_quantity_to_kg(numeric_raw, standard_unit, prod)
                diff = abs(actual_kg - expected_kg)
                is_valid = diff <= 1e-2

                audits.append(
                    UnitConversionAudit(
                        product_raw=prod,
                        unit_raw=raw_unit_str,
                        quantity_raw=numeric_raw,
                        converted_kg=actual_kg,
                        expected_kg=expected_kg,
                        is_valid=is_valid,
                        discrepancy_reason=None if is_valid else f"Discrepancy of {diff:.2f} kg from standard factor",
                    )
                )
            except ValueError:
                # Unrecognized local packaging
                audits.append(
                    UnitConversionAudit(
                        product_raw=prod,
                        unit_raw=raw_unit_str,
                        quantity_raw=numeric_raw,
                        converted_kg=actual_kg,
                        expected_kg=actual_kg,
                        is_valid=False,
                        discrepancy_reason=f"Unrecognized local unit '{raw_unit_str}' without proven conversion factor",
                    )
                )

        return audits

    def run_full_quality_audit(
        self,
        records: Sequence[StockRecord | StockObservation],
        start_date: date,
        end_date: date,
        target: str = QuantityTarget.INFLOW_ARRIVAL.value,
    ) -> SupplyDataQualityReport:
        """Run complete metrological quality audit on supply records."""
        coverage_stats = self.calculate_market_coverage(records, start_date, end_date, target=target)
        double_counts = self.detect_temporal_overlap_double_counting(records)
        conversion_audits = self.audit_unit_conversions(records)

        unmonitored_detected = any(s.unmonitored_days > 0 for s in coverage_stats)
        invalid_conversions = [c for c in conversion_audits if not c.is_valid]

        # Check missing vs zero respect: verify that no unmonitored day has quantity_kg == 0.0
        matrix = self.build_market_period_matrix(records, start_date, end_date, target=target)
        missing_vs_zero_respected = all(
            cell.quantity_kg is None for cell in matrix.values() if cell.is_missing
        )

        is_valid = (len(double_counts) == 0) and (len(invalid_conversions) == 0) and missing_vs_zero_respected

        markets = sorted({s.market_code for s in coverage_stats})

        return SupplyDataQualityReport(
            is_valid=is_valid,
            total_records_analyzed=len(records),
            markets_analyzed=markets,
            coverage_by_market=coverage_stats,
            double_counting_violations=double_counts,
            conversion_audit_issues=invalid_conversions,
            unmonitored_days_detected=unmonitored_detected,
            missing_vs_zero_strictly_respected=missing_vs_zero_respected,
        )
