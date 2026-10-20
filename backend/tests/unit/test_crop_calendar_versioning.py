"""Unit tests for crop calendar versioning, phenology and trade corridor tracking (ADR-086, SPECS §26, R4.7)."""

import pytest
from pydantic import ValidationError

from ketrika.geo.calendar import (
    detect_phenological_stage,
    get_active_crop_calendars,
    get_alert_eligible_calendars,
    get_calendar_for_basin,
    get_calendar_history,
    get_documented_trade_corridors_for_market,
    is_month_in_window,
    supersede_calendar_record,
)
from ketrika.geo.contracts import (
    CalendarType,
    CropCalendarRecord,
    CropRegime,
    MarketLink,
    MarketLinkProofStatus,
    load_crop_calendar,
)


def test_load_crop_calendar_taxonomy_complete():
    """Verify loading, validation and complete metadata of crop calendar taxonomy."""
    records = load_crop_calendar()
    assert len(records) >= 10

    # Key commodities present
    products = {r.product_code for r in records}
    assert "RICE_PADDY" in products
    assert "MAIZE_GRAIN" in products
    assert "CASSAVA_FRESH" in products

    # Active records
    active = get_active_crop_calendars(records)
    assert len(active) >= 10

    # Month bounds [1, 12]
    for r in records:
        assert 1 <= r.planting_start_month <= 12
        assert 1 <= r.planting_end_month <= 12
        assert 1 <= r.growing_start_month <= 12
        assert 1 <= r.growing_end_month <= 12
        assert 1 <= r.harvest_start_month <= 12
        assert 1 <= r.harvest_end_month <= 12
        if r.peak_harvest_month is not None:
            assert 1 <= r.peak_harvest_month <= 12
        assert len(r.planting_months) > 0
        assert len(r.harvest_months) > 0


def test_traditional_vs_seasonal_recommendation():
    """Verify clean separation between permanent traditional baseline and campaign recommendations."""
    records = load_crop_calendar()

    # Traditional baselines
    traditional = [r for r in records if r.calendar_type == CalendarType.TRADITIONAL_BASELINE]
    assert len(traditional) >= 8

    # Seasonal recommendation for 2023/2024
    recommendations = [
        r for r in records if r.calendar_type == CalendarType.SEASONAL_RECOMMENDATION
    ]
    assert len(recommendations) >= 1

    rec_2023 = recommendations[0]
    assert rec_2023.campaign == "2023/2024"
    assert rec_2023.zone_code == "ZONE_CENTRE"
    assert rec_2023.planting_start_month == 11  # delayed planting due to late rains
    assert rec_2023.verified is True
    assert rec_2023.eligible_for_alerts is True

    # Traditional baseline for Vakiambiaty remains unchanged
    trad_vakiambiaty = get_calendar_for_basin(
        records,
        zone_code="ZONE_CENTRE",
        product_code="RICE_PADDY",
        calendar_type=CalendarType.TRADITIONAL_BASELINE,
    )
    assert trad_vakiambiaty is not None
    assert trad_vakiambiaty.planting_start_month == 10  # standard baseline starts in Oct


def test_phenological_stage_detection_and_wrap_around():
    """Verify month-in-window logic and phenological stage detection with year wrap-around."""
    # 1. Standard window within calendar year (months 4 to 6)
    assert is_month_in_window(month=4, start_month=4, end_month=6) is True
    assert is_month_in_window(month=5, start_month=4, end_month=6) is True
    assert is_month_in_window(month=6, start_month=4, end_month=6) is True
    assert is_month_in_window(month=3, start_month=4, end_month=6) is False
    assert is_month_in_window(month=7, start_month=4, end_month=6) is False

    # 2. Window wrapping across calendar year boundary (Nov to Feb: months 11 to 2)
    assert is_month_in_window(month=11, start_month=11, end_month=2) is True
    assert is_month_in_window(month=12, start_month=11, end_month=2) is True
    assert is_month_in_window(month=1, start_month=11, end_month=2) is True
    assert is_month_in_window(month=2, start_month=11, end_month=2) is True
    assert is_month_in_window(month=3, start_month=11, end_month=2) is False
    assert is_month_in_window(month=10, start_month=11, end_month=2) is False

    # 3. Invalid month bounds raise ValueError
    with pytest.raises(ValueError):
        is_month_in_window(month=13, start_month=1, end_month=5)
    with pytest.raises(ValueError):
        is_month_in_window(month=0, start_month=1, end_month=5)

    # 4. Phenological stage detection on Hosy rice cycle
    records = load_crop_calendar()
    hosy_records = [r for r in records if r.zone_code == "ZONE_CENTRE" and r.crop_cycle == "hosy"]
    assert len(hosy_records) == 1
    hosy = hosy_records[0]

    # planting 6-7, growing 7-11, harvest 11-1, peak 12
    assert detect_phenological_stage(hosy, month=6) == "planting"
    assert detect_phenological_stage(hosy, month=7) in ("planting", "growing")
    assert detect_phenological_stage(hosy, month=9) == "growing"
    assert detect_phenological_stage(hosy, month=12) == "peak_harvest"
    assert detect_phenological_stage(hosy, month=1) == "harvest"
    assert detect_phenological_stage(hosy, month=4) is None


def test_multi_cycle_overlap_management():
    """Verify co-existence and retrieval of multiple seasonal cycles in the same production basin."""
    records = load_crop_calendar()

    centre_rice_cycles = [
        r
        for r in records
        if r.zone_code == "ZONE_CENTRE"
        and r.product_code == "RICE_PADDY"
        and r.calendar_type == CalendarType.TRADITIONAL_BASELINE
    ]
    # Two distinct cycles: vakiambiaty (grande saison) and hosy (contre-saison précoce)
    assert len(centre_rice_cycles) == 2
    cycle_names = {r.crop_cycle for r in centre_rice_cycles}
    assert "vakiambiaty" in cycle_names
    assert "hosy" in cycle_names


def test_market_links_and_documented_trade_corridors():
    """Verify documented supply trade corridors linking basins to consumer markets."""
    records = load_crop_calendar()

    # Antananarivo (MDG11) corridors
    tana_corridors = get_documented_trade_corridors_for_market(records, location_code="MDG11")
    assert len(tana_corridors) >= 3

    supplying_basins = {c["basin_zone_code"] for c in tana_corridors}
    assert "ZONE_ALAOTRA" in supplying_basins
    assert "ZONE_BOENY" in supplying_basins
    assert "ZONE_CENTRE" in supplying_basins

    # Alaotra corridor must have documented trade corridor proof
    alaotra_tana = next(c for c in tana_corridors if c["basin_zone_code"] == "ZONE_ALAOTRA")
    assert alaotra_tana["proof_status"] == MarketLinkProofStatus.DOCUMENTED_TRADE_CORRIDOR
    assert "ODR" in alaotra_tana["source_evidence"]

    # Rejection of unverified spatial proximity assumption
    synthetic_record = CropCalendarRecord(
        zone_code="ZONE_SYNTHETIC",
        zone_name="Zone Fictive",
        crop="RICE",
        product_code="RICE_PADDY",
        season_name="fictive",
        crop_regime=CropRegime.RAINFED,
        planting_start_month=1,
        planting_end_month=2,
        growing_start_month=3,
        growing_end_month=5,
        harvest_start_month=6,
        harvest_end_month=7,
        source_reference="Source Fictive 2024",
        verified=True,
        market_links=[
            MarketLink(
                location_code="MDG99",
                location_name="Marche Fictif",
                flow_role="primary_supply",
                proof_status=MarketLinkProofStatus.UNVERIFIED_ASSUMPTION,  # unverified proximity!
                source_evidence="Supposition géographique non vérifiée",
            )
        ],
    )
    unverified_corridors = get_documented_trade_corridors_for_market(
        [synthetic_record], location_code="MDG99"
    )
    assert len(unverified_corridors) == 0  # Safely rejected!


def test_unverified_entry_excluded_from_alerts():
    """Verify entries without official source or marked unverified are barred from alerts (ADR-086)."""
    records = load_crop_calendar()

    # Find the draft entry for ZONE_NORD
    drafts = [r for r in records if r.zone_code == "ZONE_NORD"]
    assert len(drafts) == 1
    draft = drafts[0]

    assert draft.verified is False
    assert draft.eligible_for_alerts is False

    # Confirm it is excluded by get_alert_eligible_calendars
    eligible = get_alert_eligible_calendars(records)
    assert draft not in eligible
    assert all(r.eligible_for_alerts and r.verified for r in eligible)

    # Confirm validator forces eligible_for_alerts=False if verified=False or source is empty
    tampered_record = CropCalendarRecord(
        zone_code="ZONE_TEST",
        zone_name="Zone Test",
        crop="RICE",
        product_code="RICE_PADDY",
        season_name="saison_test",
        crop_regime=CropRegime.RAINFED,
        planting_start_month=1,
        planting_end_month=2,
        growing_start_month=3,
        growing_end_month=5,
        harvest_start_month=6,
        harvest_end_month=7,
        source_reference="",  # Empty source reference!
        verified=False,
        eligible_for_alerts=True,  # Tampered flag!
    )
    assert tampered_record.eligible_for_alerts is False  # Forced to False by validator


def test_rejection_of_prohibited_projections():
    """Verify CropCalendarRecord strictly rejects invented tonnage and price projections (ADR-086)."""
    # Valid record creation
    rec = CropCalendarRecord(
        zone_code="ZONE_CENTRE",
        zone_name="Hauts Plateaux",
        crop="RICE",
        product_code="RICE_PADDY",
        season_name="vakiambiaty",
        crop_regime=CropRegime.IRRIGATED,
        planting_start_month=10,
        planting_end_month=12,
        growing_start_month=12,
        growing_end_month=4,
        harvest_start_month=4,
        harvest_end_month=6,
        source_reference="MinAE 2021",
        verified=True,
    )
    assert rec.harvest_end_month == 6

    # Attempting to inject prohibited fields must fail
    with pytest.raises(ValidationError):
        CropCalendarRecord(
            zone_code="ZONE_CENTRE",
            zone_name="Hauts Plateaux",
            crop="RICE",
            product_code="RICE_PADDY",
            season_name="vakiambiaty",
            crop_regime=CropRegime.IRRIGATED,
            planting_start_month=10,
            planting_end_month=12,
            growing_start_month=12,
            growing_end_month=4,
            harvest_start_month=4,
            harvest_end_month=6,
            source_reference="MinAE 2021",
            tonnage=50000.0,  # Prohibited!
        )


def test_supersede_calendar_record_immutability():
    """Verify non-destructive supersession and retrieval of previous versions."""
    records = load_crop_calendar()
    original = next(
        r
        for r in records
        if r.zone_code == "ZONE_ALAOTRA" and r.calendar_type == CalendarType.TRADITIONAL_BASELINE
    )
    assert original.is_active is True
    assert original.superseded_by is None

    # Create a revised version
    revised = original.model_copy(
        update={
            "calendar_version": "v1.1",
            "notes": "Révision validée suite aux nouvelles enquêtes agronomiques 2024",
        }
    )

    old_rec, new_rec = supersede_calendar_record(original, revised)

    assert old_rec.is_active is False
    assert old_rec.superseded_by is not None
    assert new_rec.is_active is True
    assert new_rec.superseded_by is None
    assert new_rec.calendar_version == "v1.1"

    # Querying history includes both versions
    history = get_calendar_history(
        [old_rec, new_rec],
        zone_code="ZONE_ALAOTRA",
        product_code="RICE_PADDY",
        season_name="saison_principale",
    )
    assert len(history) == 2
    assert history[0].is_active is True
    assert history[1].is_active is False
