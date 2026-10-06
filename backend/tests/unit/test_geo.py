"""Unit tests for geographic boundaries, location resolution, and crop calendar."""

import pytest

from ketrika.core.geo import (
    load_admin_geojson,
    load_crop_calendar,
    load_location_aliases,
    resolve_location,
    validate_geo,
)


def test_validate_geo_has_no_errors() -> None:
    errors = validate_geo()
    assert errors == []


def test_admin0_geojson_valid() -> None:
    admin0 = load_admin_geojson("admin0")
    assert admin0.get("type") == "FeatureCollection"
    features = admin0.get("features", [])
    assert len(features) == 1
    props = features[0].get("properties", {})
    assert props.get("ADM0_PCODE") == "MDG"
    assert props.get("ADM0_FR") == "Madagascar"
    assert features[0].get("geometry", {}).get("type") in ("Polygon", "MultiPolygon")


def test_admin1_geojson_has_23_official_regions() -> None:
    admin1 = load_admin_geojson("admin1")
    assert admin1.get("type") == "FeatureCollection"
    features = admin1.get("features", [])
    assert len(features) == 23

    expected_pcodes = {
        "MDG11",
        "MDG12",
        "MDG13",
        "MDG14",
        "MDG21",
        "MDG22",
        "MDG23",
        "MDG24",
        "MDG25",
        "MDG26",
        "MDG31",
        "MDG32",
        "MDG33",
        "MDG41",
        "MDG42",
        "MDG43",
        "MDG44",
        "MDG51",
        "MDG52",
        "MDG53",
        "MDG54",
        "MDG71",
        "MDG72",
    }
    actual_pcodes = {f.get("properties", {}).get("ADM1_PCODE") for f in features}
    assert actual_pcodes == expected_pcodes

    # Explicit check: Vatovavy (MDG23) and Fitovinany (MDG24) are present (23 regions law)
    assert "MDG23" in actual_pcodes
    assert "MDG24" in actual_pcodes


def test_admin2_geojson_sample_districts() -> None:
    admin2 = load_admin_geojson("admin2")
    features = admin2.get("features", [])
    assert len(features) >= 3
    pcodes = {f.get("properties", {}).get("ADM2_PCODE") for f in features}
    assert "MDG1101" in pcodes  # Antananarivo Renivohitra
    assert "MDG1201" in pcodes  # Antsirabe I
    assert "MDG3101" in pcodes  # Toamasina I


def test_load_admin_geojson_invalid_level_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_admin_geojson("admin99_non_existent")


def test_resolve_location_fixture_locations() -> None:
    test_cases = [
        ("Madagascar", "MDG", "admin0", 1.0),
        ("Analamanga", "MDG11", "admin1", 1.0),
        ("Vakinankaratra", "MDG12", "admin1", 1.0),
        ("Atsinanana", "MDG31", "admin1", 1.0),
        ("Antananarivo Renivohitra", "MDG1101", "admin2", 1.0),
        ("Antananarivo", "MDG1101", "admin2", 0.95),
        ("Tananarive", "MDG1101", "admin2", 0.95),
        ("Antsirabe I", "MDG1201", "admin2", 1.0),
        ("Antsirabe", "MDG1201", "admin2", 0.95),
        ("Toamasina I", "MDG3101", "admin2", 1.0),
        ("Toamasina", "MDG3101", "admin2", 0.95),
        ("Tamatave", "MDG3101", "admin2", 0.95),
        ("Anosibe", "MKT_ANOSIBE", "market", 1.0),
        ("Bazar Be", "MKT_BAZAR_BE", "market", 1.0),
        ("Asabotsy", "MKT_ASABOTSY", "market", 1.0),
    ]

    aliases = load_location_aliases()
    for raw_label, expected_pcode, expected_level, min_conf in test_cases:
        resolved = resolve_location(raw_label, aliases=aliases, min_confidence=0.8)
        assert resolved is not None, f"Failed to resolve location: {raw_label}"
        pcode, level, conf = resolved
        assert pcode == expected_pcode, f"Wrong P-Code for {raw_label}: got {pcode}"
        assert level == expected_level, f"Wrong level for {raw_label}: got {level}"
        assert conf >= min_conf


def test_resolve_location_normalization_and_unmapped() -> None:
    aliases = load_location_aliases()
    # Case and space normalization
    resolved = resolve_location("  anosibe  ", aliases=aliases)
    assert resolved is not None
    assert resolved[0] == "MKT_ANOSIBE"

    resolved = resolve_location("bazar be", aliases=aliases)
    assert resolved is not None
    assert resolved[0] == "MKT_BAZAR_BE"

    # Unknown location
    assert resolve_location("unknown_place_xyz", aliases=aliases) is None


def test_load_crop_calendar_structure_and_sources() -> None:
    calendar = load_crop_calendar()
    assert len(calendar) >= 5

    crops = {c.crop for c in calendar}
    assert "RICE" in crops
    assert "MAIZE" in crops

    rice_cycles = {c.crop_cycle for c in calendar if c.crop == "RICE"}
    assert "vakiambiaty" in rice_cycles
    assert "hosy" in rice_cycles
    assert "asara" in rice_cycles

    for entry in calendar:
        assert entry.verified is True
        assert len(entry.source) > 5
        assert all(1 <= m <= 12 for m in entry.planting_months)
        assert all(1 <= m <= 12 for m in entry.harvest_months)
