"""Crop calendar phenological modeling, versioning, and trade corridor tracking (ADR-086, SPECS §26, R4.7)."""

import uuid
from typing import Any

from ketrika.geo.contracts import (
    CalendarType,
    CropCalendarRecord,
    CropRegime,
    MarketLinkProofStatus,
)


def is_month_in_window(month: int, start_month: int, end_month: int) -> bool:
    """Determine if a month (1-12) falls within a window, handling annual calendar wrap-around."""
    if not (1 <= month <= 12 and 1 <= start_month <= 12 and 1 <= end_month <= 12):
        raise ValueError(
            f"Months must be between 1 and 12: month={month}, start={start_month}, end={end_month}"
        )

    if start_month <= end_month:
        return start_month <= month <= end_month
    else:
        # Wrap-around across year boundary (e.g., Nov (11) to Feb (2))
        return month >= start_month or month <= end_month


def detect_phenological_stage(record: CropCalendarRecord, month: int) -> str | None:
    """Identify the current phenological stage of a crop cycle for a given calendar month.

    Returns:
        'peak_harvest', 'harvest', 'planting', 'growing', or None.
    """
    if not (1 <= month <= 12):
        raise ValueError(f"Month must be between 1 and 12, got {month}")

    if record.peak_harvest_month is not None and month == record.peak_harvest_month:
        return "peak_harvest"

    if is_month_in_window(month, record.harvest_start_month, record.harvest_end_month):
        return "harvest"

    if is_month_in_window(month, record.planting_start_month, record.planting_end_month):
        return "planting"

    if is_month_in_window(month, record.growing_start_month, record.growing_end_month):
        return "growing"

    return None


def get_active_crop_calendars(records: list[CropCalendarRecord]) -> list[CropCalendarRecord]:
    """Filter only currently active crop calendar records."""
    return [r for r in records if r.is_active]


def get_alert_eligible_calendars(records: list[CropCalendarRecord]) -> list[CropCalendarRecord]:
    """Filter records eligible for automated market intelligence alerts.

    Rejects unverified entries or records lacking authentic source references (ADR-086).
    """
    return [
        r
        for r in records
        if r.is_active and r.eligible_for_alerts and r.verified and bool(r.source_reference.strip())
    ]


def get_calendar_for_basin(
    records: list[CropCalendarRecord],
    zone_code: str,
    product_code: str,
    crop_regime: CropRegime | str | None = None,
    calendar_type: CalendarType | str | None = None,
) -> CropCalendarRecord | None:
    """Retrieve the primary active crop calendar matching zone, commodity and optional regime."""
    for rec in records:
        if not rec.is_active:
            continue
        if rec.zone_code != zone_code or rec.product_code != product_code:
            continue
        if crop_regime is not None and rec.crop_regime != crop_regime:
            continue
        if calendar_type is not None and rec.calendar_type != calendar_type:
            continue
        return rec
    return None


def get_calendar_history(
    records: list[CropCalendarRecord],
    zone_code: str,
    product_code: str,
    season_name: str,
) -> list[CropCalendarRecord]:
    """Retrieve full revision history (active and superseded) for a specific cropping cycle."""
    matched = [
        r
        for r in records
        if r.zone_code == zone_code
        and r.product_code == product_code
        and r.season_name == season_name
    ]
    # Return sorted with active first, then previous versions
    return sorted(matched, key=lambda r: (not r.is_active, r.calendar_version))


def get_documented_trade_corridors_for_market(
    records: list[CropCalendarRecord],
    location_code: str,
    require_verified: bool = True,
) -> list[dict[str, Any]]:
    """Find all production basins that feed a consumer market via documented trade corridors.

    Rejects unverified geographical proximity guesses (ADR-086).
    """
    corridors: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for rec in records:
        if not rec.is_active:
            continue
        if require_verified and not rec.verified:
            continue

        for link in rec.market_links:
            if link.location_code == location_code:
                if link.proof_status == MarketLinkProofStatus.UNVERIFIED_ASSUMPTION:
                    continue  # Refuse unverified spatial assumptions

                key = (rec.zone_code, rec.product_code, rec.season_name)
                if key not in seen:
                    seen.add(key)
                    corridors.append(
                        {
                            "basin_zone_code": rec.zone_code,
                            "basin_zone_name": rec.zone_name,
                            "crop": rec.crop,
                            "product_code": rec.product_code,
                            "season_name": rec.season_name,
                            "crop_regime": rec.crop_regime,
                            "harvest_months": rec.harvest_months,
                            "peak_harvest_month": rec.peak_harvest_month,
                            "target_location_code": link.location_code,
                            "target_location_name": link.location_name,
                            "flow_role": link.flow_role,
                            "proof_status": link.proof_status,
                            "source_evidence": link.source_evidence,
                        }
                    )
    return corridors


def supersede_calendar_record(
    old_record: CropCalendarRecord,
    new_record: CropCalendarRecord,
) -> tuple[CropCalendarRecord, CropCalendarRecord]:
    """Perform non-destructive supersession between an older and newer crop calendar version.

    The old record is preserved with is_active=False and superseded_by pointer.
    """
    new_id = uuid.uuid4()
    updated_old = old_record.model_copy(
        update={
            "is_active": False,
            "superseded_by": new_id,
        }
    )
    updated_new = new_record.model_copy(
        update={
            "is_active": True,
            "superseded_by": None,
        }
    )
    return updated_old, updated_new
