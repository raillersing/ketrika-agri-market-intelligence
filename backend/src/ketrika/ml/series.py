"""Series extraction, regular calendar reconstruction, and eligibility filtering for price forecasting (SPECS §17, ADR-004, ADR-073, R3.1)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.core.logging import get_logger

logger = get_logger(__name__)

# Normative constants per SPECS §17 & ADR-073
MIN_TOTAL_POINTS: int = 36
MIN_RECENT_POINTS: int = 12
RECENCY_WINDOW_MONTHS: int = 24
ALLOWED_ADMIN_LEVELS: tuple[int, ...] = (0, 1)  # 0: national, 1: regional (ADR-004)
ALLOWED_ACTOR_LEVELS: tuple[str, ...] = ("retail", "wholesale", "producer", "farmgate", "unknown")
EXCLUDED_ACTOR_LEVELS: tuple[str, ...] = ("official_ppn", "administered")
DEFAULT_QUALITY_GRADE: str = "standard"
DEFAULT_UNIT: str = "kg"


def build_series_key(
    product_code: str,
    quality_grade: str = DEFAULT_QUALITY_GRADE,
    actor_level: str = "retail",
    location_pcode: str = "MG",
    unit: str = DEFAULT_UNIT,
) -> str:
    """Build canonical 5-component series key: product_code|quality_grade|actor_level|location_pcode|unit."""
    return f"{product_code}|{quality_grade}|{actor_level}|{location_pcode}|{unit}"


def parse_series_key(key: str) -> dict[str, str]:
    """Parse series key supporting both canonical 5-part and legacy 3-part formats."""
    parts = key.split("|")
    if len(parts) == 5:
        return {
            "product_code": parts[0],
            "quality_grade": parts[1],
            "actor_level": parts[2],
            "location_pcode": parts[3],
            "unit": parts[4],
        }
    elif len(parts) == 3:
        # Legacy format: product_code|location_pcode|actor_level
        return {
            "product_code": parts[0],
            "quality_grade": DEFAULT_QUALITY_GRADE,
            "actor_level": parts[2],
            "location_pcode": parts[1],
            "unit": DEFAULT_UNIT,
        }
    else:
        raise ValueError(f"Invalid series_key format: {key}")


def shift_months(base: date, months_offset: int) -> date:
    """Shift a date by a given number of months, returning 1st of resulting month."""
    total_months = base.year * 12 + (base.month - 1) + months_offset
    new_year = total_months // 12
    new_month = (total_months % 12) + 1
    return date(new_year, new_month, 1)


def generate_monthly_calendar(start_month: date, end_month: date) -> list[date]:
    """Generate a strictly continuous monthly calendar from start_month to end_month (inclusive)."""
    cur = date(start_month.year, start_month.month, 1)
    end = date(end_month.year, end_month.month, 1)
    months: list[date] = []
    while cur <= end:
        months.append(cur)
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return months


@dataclass(frozen=True)
class PricePoint:
    """Price observation or calendar gap point."""

    month: date
    price: float | None  # None indicates calendar gap / hole
    observed_or_imputed: str | None = "observed"  # "observed" | "imputed" | None (for gap)
    source_id: str | None = None
    source_family: str | None = None

    @property
    def is_observed(self) -> bool:
        return self.price is not None and self.price > 0 and self.observed_or_imputed == "observed"

    @property
    def is_valid(self) -> bool:
        return self.price is not None and self.price > 0


@dataclass
class ExcludedSeries:
    """Detailed record of an excluded price series with specific rejection reasons."""

    series_key: str
    product_code: str
    location_pcode: str
    actor_level: str
    admin_level: int | None
    quality_grade: str
    unit: str
    total_valid_points: int
    recent_points_24m: int
    reasons: list[str]


@dataclass
class EligibleSeries:
    """Statistically qualified price series on a regular calendar grid with explicit gaps."""

    series_key: str
    product_id: uuid.UUID
    product_code: str
    product_name: str
    location_id: uuid.UUID
    location_pcode: str
    location_name: str
    actor_level: str
    admin_level: int
    quality_grade: str = DEFAULT_QUALITY_GRADE
    unit: str = DEFAULT_UNIT
    cohort: str = "observed"  # "observed" (100% observed) | "mixed" (contains imputed)
    grid: list[PricePoint] = field(
        default_factory=list
    )  # Complete regular monthly grid (start to cutoff)
    total_valid_points: int = 0
    recent_points_24m: int = 0
    imputed_points_count: int = 0
    coverage_ratio: float = 0.0
    can_backtest_6_windows: bool = False
    can_calibrate_conformal: bool = False

    @property
    def points(self) -> list[PricePoint]:
        """Return non-null price points for backwards compatibility with legacy callers."""
        return [pt for pt in self.grid if pt.price is not None and pt.price > 0]

    @property
    def observed_points(self) -> list[PricePoint]:
        """Return strictly observed ground-truth price points."""
        return [pt for pt in self.grid if pt.is_observed]

    def to_numpy_array(self, fill_strategy: str = "none") -> np.ndarray:
        """Convert regular monthly grid to numpy array.

        fill_strategy:
          - 'none': preserves holes as np.nan (anti-compression)
          - 'forward_fill': propagates last observed price into holes
          - 'linear': linearly interpolates gaps between observations
        """
        raw = np.array(
            [pt.price if pt.price is not None and pt.price > 0 else np.nan for pt in self.grid],
            dtype=float,
        )
        if fill_strategy == "none":
            return raw
        elif fill_strategy == "forward_fill":
            filled = raw.copy()
            last_valid = np.nan
            for i in range(len(filled)):
                if not np.isnan(filled[i]):
                    last_valid = filled[i]
                elif not np.isnan(last_valid):
                    filled[i] = last_valid
            return filled
        elif fill_strategy == "linear":
            nans = np.isnan(raw)
            if not np.any(nans) or np.all(nans):
                return raw
            x = np.arange(len(raw))
            valid_x = x[~nans]
            valid_y = raw[~nans]
            interp_vals = np.interp(x, valid_x, valid_y)
            return np.asarray(interp_vals, dtype=float)
        else:
            raise ValueError(f"Unknown fill_strategy: {fill_strategy}")


@dataclass
class SeriesEligibilityReport:
    """Exhaustive audit report of series eligibility evaluation."""

    data_cutoff: date
    total_series_evaluated: int
    eligible_count: int
    excluded_count: int
    eligible_series: list[EligibleSeries]
    excluded_series: list[ExcludedSeries]
    summary_reasons: dict[str, int]


def evaluate_series_eligibility_records(
    records: list[dict[str, Any]],
    data_cutoff: date,
    min_total_points: int = MIN_TOTAL_POINTS,
    min_recent_points: int = MIN_RECENT_POINTS,
    recency_window_months: int = RECENCY_WINDOW_MONTHS,
    allowed_admin_levels: tuple[int, ...] = ALLOWED_ADMIN_LEVELS,
    allowed_actor_levels: tuple[str, ...] = ALLOWED_ACTOR_LEVELS,
    require_observed_only: bool = False,
) -> SeriesEligibilityReport:
    """Pure in-memory evaluator for series eligibility and calendar reconstruction."""
    cutoff_month = date(data_cutoff.year, data_cutoff.month, 1)
    recency_start = shift_months(cutoff_month, -(recency_window_months - 1))

    # Group records by (product_code, quality_grade, actor_level, location_pcode, unit)
    grouped: dict[str, dict[str, Any]] = {}
    for r in records:
        r_month = r["month"]
        if isinstance(r_month, str):
            r_month = date.fromisoformat(r_month)
        r_month = date(r_month.year, r_month.month, 1)

        # Strictly anti-leakage filter
        if r_month > cutoff_month:
            continue

        p_code = str(r["product_code"])
        quality = str(r.get("quality_grade") or DEFAULT_QUALITY_GRADE)
        actor = str(r["actor_level"])
        loc_pcode = str(r["location_pcode"])
        unit = str(r.get("unit") or DEFAULT_UNIT)

        series_key = build_series_key(
            product_code=p_code,
            quality_grade=quality,
            actor_level=actor,
            location_pcode=loc_pcode,
            unit=unit,
        )

        if series_key not in grouped:
            grouped[series_key] = {
                "series_key": series_key,
                "product_id": r.get("product_id") or uuid.UUID(int=0),
                "product_code": p_code,
                "product_name": str(r.get("product_name") or p_code),
                "quality_grade": quality,
                "location_id": r.get("location_id") or uuid.UUID(int=0),
                "location_pcode": loc_pcode,
                "location_name": str(r.get("location_name") or loc_pcode),
                "admin_level": r.get("admin_level"),
                "actor_level": actor,
                "unit": unit,
                "obs_by_month": {},
            }

        price_val = r.get("median_price")
        if price_val is not None:
            price_val = float(price_val)
            if price_val > 0:
                grouped[series_key]["obs_by_month"][r_month] = {
                    "price": price_val,
                    "observed_or_imputed": r.get("observed_or_imputed", "observed"),
                    "source_id": r.get("chosen_source_id") or r.get("source_id"),
                    "source_family": r.get("chosen_source_family") or r.get("source_family"),
                }

    eligible_series: list[EligibleSeries] = []
    excluded_series: list[ExcludedSeries] = []
    summary_reasons: dict[str, int] = {}

    def add_reason(reasons_list: list[str], reason: str, reason_key: str) -> None:
        reasons_list.append(reason)
        summary_reasons[reason_key] = summary_reasons.get(reason_key, 0) + 1

    for g in grouped.values():
        reasons: list[str] = []
        obs_map: dict[date, dict[str, Any]] = g["obs_by_month"]
        admin_lvl = g["admin_level"]
        actor = g["actor_level"]

        # 1. Geography rule (ADR-004)
        if admin_lvl is None or admin_lvl not in allowed_admin_levels:
            add_reason(
                reasons,
                f"ineligible_geo_granularity: admin_level={admin_lvl} (ADR-004 allows only regional/national, districts admin_level=2 rejected)",
                "ineligible_geo_granularity",
            )

        # 2. Regulated price or index rule
        if actor in EXCLUDED_ACTOR_LEVELS or actor not in allowed_actor_levels:
            add_reason(
                reasons,
                f"forbidden_price_type: actor_level='{actor}' is regulated or administrative, not an observed market price",
                "forbidden_price_type",
            )

        if not obs_map:
            add_reason(
                reasons,
                "insufficient_total_points: 0 valid points < min required",
                "insufficient_total_points",
            )
            excluded_series.append(
                ExcludedSeries(
                    series_key=g["series_key"],
                    product_code=g["product_code"],
                    location_pcode=g["location_pcode"],
                    actor_level=g["actor_level"],
                    admin_level=admin_lvl,
                    quality_grade=g["quality_grade"],
                    unit=g["unit"],
                    total_valid_points=0,
                    recent_points_24m=0,
                    reasons=reasons,
                )
            )
            continue

        # Build regular calendar grid from earliest month to data_cutoff
        earliest_month = min(obs_map.keys())
        full_months = generate_monthly_calendar(earliest_month, cutoff_month)

        grid: list[PricePoint] = []
        imputed_count = 0
        total_valid = 0
        recent_valid = 0

        for m in full_months:
            if m in obs_map:
                o = obs_map[m]
                pval = o["price"]
                obs_kind = o["observed_or_imputed"]
                grid.append(
                    PricePoint(
                        month=m,
                        price=pval,
                        observed_or_imputed=obs_kind,
                        source_id=o["source_id"],
                        source_family=o["source_family"],
                    )
                )
                total_valid += 1
                if obs_kind == "imputed":
                    imputed_count += 1
                if m >= recency_start and m <= cutoff_month:
                    recent_valid += 1
            else:
                # Explicit calendar gap / hole
                grid.append(
                    PricePoint(
                        month=m,
                        price=None,
                        observed_or_imputed=None,
                        source_id=None,
                        source_family=None,
                    )
                )

        # 3. Minimum points rule
        if total_valid < min_total_points:
            add_reason(
                reasons,
                f"insufficient_total_points: {total_valid} points < {min_total_points} required",
                "insufficient_total_points",
            )

        # 4. Recency rule
        if recent_valid < min_recent_points:
            add_reason(
                reasons,
                f"insufficient_recency: {recent_valid} points in last {recency_window_months}m < {min_recent_points} required",
                "insufficient_recency",
            )

        # 5. Cohort separation
        cohort = "observed" if imputed_count == 0 else "mixed"
        if require_observed_only and cohort != "observed":
            add_reason(
                reasons,
                f"ineligible_cohort: contains {imputed_count} imputed points, pure observed cohort required for evaluation ground truth",
                "ineligible_cohort",
            )

        coverage = total_valid / len(grid) if grid else 0.0
        can_backtest = total_valid >= 32
        can_calibrate = total_valid >= min_total_points and recent_valid >= min_recent_points

        if len(reasons) == 0:
            eligible_series.append(
                EligibleSeries(
                    series_key=g["series_key"],
                    product_id=g["product_id"],
                    product_code=g["product_code"],
                    product_name=g["product_name"],
                    quality_grade=g["quality_grade"],
                    location_id=g["location_id"],
                    location_pcode=g["location_pcode"],
                    location_name=g["location_name"],
                    actor_level=g["actor_level"],
                    admin_level=int(admin_lvl) if admin_lvl is not None else 1,
                    unit=g["unit"],
                    cohort=cohort,
                    grid=grid,
                    total_valid_points=total_valid,
                    recent_points_24m=recent_valid,
                    imputed_points_count=imputed_count,
                    coverage_ratio=round(coverage, 4),
                    can_backtest_6_windows=can_backtest,
                    can_calibrate_conformal=can_calibrate,
                )
            )
        else:
            excluded_series.append(
                ExcludedSeries(
                    series_key=g["series_key"],
                    product_code=g["product_code"],
                    location_pcode=g["location_pcode"],
                    actor_level=g["actor_level"],
                    admin_level=admin_lvl,
                    quality_grade=g["quality_grade"],
                    unit=g["unit"],
                    total_valid_points=total_valid,
                    recent_points_24m=recent_valid,
                    reasons=reasons,
                )
            )

    return SeriesEligibilityReport(
        data_cutoff=data_cutoff,
        total_series_evaluated=len(grouped),
        eligible_count=len(eligible_series),
        excluded_count=len(excluded_series),
        eligible_series=eligible_series,
        excluded_series=excluded_series,
        summary_reasons=summary_reasons,
    )


def audit_series_eligibility(
    session: Session,
    data_cutoff: date,
    min_total_points: int = MIN_TOTAL_POINTS,
    min_recent_points: int = MIN_RECENT_POINTS,
    recency_window_months: int = RECENCY_WINDOW_MONTHS,
    allowed_admin_levels: tuple[int, ...] = ALLOWED_ADMIN_LEVELS,
    allowed_actor_levels: tuple[str, ...] = ALLOWED_ACTOR_LEVELS,
    require_observed_only: bool = False,
) -> SeriesEligibilityReport:
    """Audit all price series in gold.price_monthly_best up to data_cutoff against normative criteria."""
    query = text(
        """
        SELECT
            product_id,
            product_code,
            product_name,
            location_id,
            location_pcode,
            location_name,
            admin_level,
            actor_level,
            month,
            median_price,
            observed_or_imputed,
            chosen_source_id,
            chosen_source_family
        FROM gold.price_monthly_best
        WHERE month <= :cutoff
          AND median_price IS NOT NULL
          AND median_price > 0
        ORDER BY product_code, location_pcode, actor_level, month ASC;
        """
    )
    rows = session.execute(query, {"cutoff": data_cutoff}).fetchall()

    records: list[dict[str, Any]] = [
        {
            "product_id": r.product_id,
            "product_code": r.product_code,
            "product_name": r.product_name,
            "location_id": r.location_id,
            "location_pcode": r.location_pcode,
            "location_name": r.location_name,
            "admin_level": r.admin_level,
            "actor_level": r.actor_level,
            "month": r.month,
            "median_price": float(r.median_price),
            "observed_or_imputed": r.observed_or_imputed,
            "chosen_source_id": r.chosen_source_id,
            "chosen_source_family": r.chosen_source_family,
        }
        for r in rows
    ]

    report = evaluate_series_eligibility_records(
        records=records,
        data_cutoff=data_cutoff,
        min_total_points=min_total_points,
        min_recent_points=min_recent_points,
        recency_window_months=recency_window_months,
        allowed_admin_levels=allowed_admin_levels,
        allowed_actor_levels=allowed_actor_levels,
        require_observed_only=require_observed_only,
    )

    logger.info(
        "series_eligibility_audited",
        cutoff=data_cutoff.isoformat(),
        total_evaluated=report.total_series_evaluated,
        eligible_count=report.eligible_count,
        excluded_count=report.excluded_count,
        summary_reasons=report.summary_reasons,
    )
    return report


def extract_eligible_series(
    session: Session,
    data_cutoff: date,
    min_points: int | None = None,
    min_total_points: int = MIN_TOTAL_POINTS,
    min_recent_points: int = MIN_RECENT_POINTS,
    recency_window_months: int = RECENCY_WINDOW_MONTHS,
    allowed_admin_levels: tuple[int, ...] = ALLOWED_ADMIN_LEVELS,
    allowed_actor_levels: tuple[str, ...] = ALLOWED_ACTOR_LEVELS,
    require_observed_only: bool = False,
) -> list[EligibleSeries]:
    """Extract price series from gold.price_monthly_best up to data_cutoff.

    Enforces temporal integrity and returns qualified series per SPECS §17 & ADR-073.
    """
    if min_points is not None:
        effective_min_total = min_points
        effective_min_recent = min(min_recent_points, max(1, min_points // 3))
    else:
        effective_min_total = min_total_points
        effective_min_recent = min_recent_points

    report = audit_series_eligibility(
        session=session,
        data_cutoff=data_cutoff,
        min_total_points=effective_min_total,
        min_recent_points=effective_min_recent,
        recency_window_months=recency_window_months,
        allowed_admin_levels=allowed_admin_levels,
        allowed_actor_levels=allowed_actor_levels,
        require_observed_only=require_observed_only,
    )
    return report.eligible_series
