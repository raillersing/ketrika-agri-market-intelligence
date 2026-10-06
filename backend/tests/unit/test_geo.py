"""Unit tests for geographic boundaries, location resolution, and crop calendar."""

import pytest

from ketrika.core.geo import (
    load_admin_geojson,
    load_crop_calendar,
    load_geographic_entities,
    load_location_aliases,
    resolve_location,
    validate_geo,
)
from ketrika.core.models.geo import GeographicEntity


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


def test_admin3_geojson_sample_communes() -> None:
    admin3 = load_admin_geojson("admin3")
    features = admin3.get("features", [])
    assert len(features) >= 1
    pcodes = {f.get("properties", {}).get("ADM3_PCODE") for f in features}
    assert "MDG110101" in pcodes  # Commune Urbaine d'Antananarivo


def test_load_geographic_entities_admin1() -> None:
    entities = load_geographic_entities("admin1")
    assert len(entities) == 23
    for e in entities:
        assert isinstance(e, GeographicEntity)
        assert e.admin_level == "admin1"
        assert e.pcode.startswith("MDG")
        assert len(e.name_fr) > 2
        assert e.latitude is not None
        assert e.longitude is not None
        assert -26.0 <= e.latitude <= -11.0
        assert 43.0 <= e.longitude <= 51.0


def test_load_admin_geojson_invalid_level_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_admin_geojson("admin99_non_existent")


def test_all_23_official_regions_resolve() -> None:
    regions_map = {
        "Analamanga": "MDG11",
        "Vakinankaratra": "MDG12",
        "Itasy": "MDG13",
        "Bongolava": "MDG14",
        "Haute Matsiatra": "MDG21",
        "Amoron'i Mania": "MDG22",
        "Vatovavy": "MDG23",
        "Fitovinany": "MDG24",
        "Ihorombe": "MDG25",
        "Atsimo-Atsinanana": "MDG26",
        "Atsinanana": "MDG31",
        "Analanjirofo": "MDG32",
        "Alaotra-Mangoro": "MDG33",
        "Boeny": "MDG41",
        "Sofia": "MDG42",
        "Betsiboka": "MDG43",
        "Melaky": "MDG44",
        "Atsimo-Andrefana": "MDG51",
        "Androy": "MDG52",
        "Anosy": "MDG53",
        "Menabe": "MDG54",
        "Diana": "MDG71",
        "Sava": "MDG72",
    }
    aliases = load_location_aliases()
    for name, expected_pcode in regions_map.items():
        res = resolve_location(name, aliases=aliases)
        assert res is not None, f"Region '{name}' failed to resolve"
        assert res[0] == expected_pcode, f"Region '{name}': expected {expected_pcode}, got {res[0]}"
        assert res[1] == "admin1"
        assert res[2] == 1.0


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


def test_resolve_location_edge_cases_and_normalization() -> None:
    aliases = load_location_aliases()

    # Direct P-Codes
    res_mdg = resolve_location("MDG", aliases=aliases)
    assert res_mdg == ("MDG", "admin0", 1.0)

    res_pcode1 = resolve_location("MDG11", aliases=aliases)
    assert res_pcode1 == ("MDG11", "admin1", 1.0)

    res_pcode2 = resolve_location("MDG1101", aliases=aliases)
    assert res_pcode2 == ("MDG1101", "admin2", 1.0)

    # Typographic curly apostrophe in Amoron'i Mania
    res_apo = resolve_location("Amoron’i Mania", aliases=aliases)
    assert res_apo is not None
    assert res_apo[0] == "MDG22"

    # Hyphen vs space fallback
    res_hyphen = resolve_location("Alaotra Mangoro", aliases=aliases)
    assert res_hyphen is not None
    assert res_hyphen[0] == "MDG33"

    res_hyphen2 = resolve_location("Atsimo Andrefana", aliases=aliases)
    assert res_hyphen2 is not None
    assert res_hyphen2[0] == "MDG51"

    # Historical composite region
    res_vato = resolve_location("Vatovavy-Fitovinany", aliases=aliases)
    assert res_vato is not None
    assert res_vato[0] == "MDG23"
    assert res_vato[2] == 0.85

    # 24th region Ambatosoa
    res_amba = resolve_location("Ambatosoa", aliases=aliases)
    assert res_amba is not None
    assert res_amba[0] == "MDG32"

    # Case and space normalization
    resolved = resolve_location("  anosibe  ", aliases=aliases)
    assert resolved is not None
    assert resolved[0] == "MKT_ANOSIBE"

    resolved = resolve_location("bazar be", aliases=aliases)
    assert resolved is not None
    assert resolved[0] == "MKT_BAZAR_BE"

    # Empty and unknown locations
    assert resolve_location("", aliases=aliases) is None
    assert resolve_location("   ", aliases=aliases) is None
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
