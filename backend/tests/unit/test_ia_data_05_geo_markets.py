"""Unit tests for IA-DATA-05: Markets, geography, dated boundaries, and alias candidate review."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from ketrika.api.auth import get_current_user
from ketrika.api.main import app
from ketrika.core.db import get_db
from ketrika.core.geo import load_geo_manifest, validate_geo
from ketrika.normalize.locations import LocationResolver


@pytest.fixture
def resolver() -> LocationResolver:
    return LocationResolver()


def test_validate_geo_and_manifest_concordance() -> None:
    manifest = load_geo_manifest()
    assert manifest["boundary_version"] == "2024.1"
    assert manifest["levels"]["admin1"]["feature_count"] == 23
    assert manifest["resolution_rules"]["no_arbitrary_default"] is not None

    errors = validate_geo()
    assert errors == []


def test_exact_pcode_and_alias_resolution(resolver: LocationResolver) -> None:
    # 1. P-Code resolution
    match_nat = resolver.resolve("MDG")
    assert match_nat is not None
    assert match_nat.pcode == "MDG"
    assert match_nat.admin_level == 0
    assert match_nat.match_type == "exact_pcode"

    match_reg = resolver.resolve("MDG11")
    assert match_reg is not None
    assert match_reg.pcode == "MDG11"
    assert match_reg.admin_level == 1
    assert match_reg.match_type == "exact_pcode"

    # 2. Canonical French and Malagasy names
    match_fr = resolver.resolve("Analamanga")
    assert match_fr is not None
    assert match_fr.pcode == "MDG11"
    assert match_fr.confidence == 1.0

    match_mg = resolver.resolve("Matsiatra Ambony")
    assert match_mg is not None
    assert match_mg.pcode == "MDG21"
    assert match_mg.name == "Matsiatra Ambony"


def test_market_resolution_with_subnational_entities(resolver: LocationResolver) -> None:
    # Market aliases
    match_analakely = resolver.resolve("Analakely")
    assert match_analakely is not None
    assert match_analakely.pcode == "MKT_ANALAKELY"
    assert match_analakely.admin_level == 9

    match_anosibe = resolver.resolve("Anosibe")
    assert match_anosibe is not None
    assert match_anosibe.pcode == "MKT_ANOSIBE"
    assert match_anosibe.admin_level == 9

    match_alakamisy = resolver.resolve("Alakamisy")
    assert match_alakamisy is not None
    assert match_alakamisy.pcode == "MKT_ALAKAMISY"
    assert match_alakamisy.admin_level == 9

    # National synthetic market average
    match_avg = resolver.resolve("Market Average")
    assert match_avg is not None
    assert match_avg.pcode == "MDG"
    assert match_avg.admin_level == 0


def test_provider_geo_id_matching(resolver: LocationResolver) -> None:
    # World Bank RTFP provider geo_id
    match_wb_nat = resolver.resolve("Whatever", geo_id="gid_mdg_national_average")
    assert match_wb_nat is not None
    assert match_wb_nat.pcode == "MDG"
    assert match_wb_nat.match_type == "exact_geo_id"

    match_wb_mkt = resolver.resolve("Unknown Raw", geo_id="mkt_mdg_analakely")
    assert match_wb_mkt is not None
    assert match_wb_mkt.pcode == "MKT_ANALAKELY"
    assert match_wb_mkt.match_type == "exact_geo_id"


def test_no_arbitrary_default_rule(resolver: LocationResolver) -> None:
    # Unknown and ambiguous locations must resolve to None, NEVER falling back to arbitrary default
    unknown_inputs = [
        "Inconnu Market XYZ",
        "NonExistentZone_9999",
        "Random Station 42",
        "Foobar 12345",
        "",
        "   ",
    ]
    for raw in unknown_inputs:
        match = resolver.resolve(raw)
        assert match is None, f"Arbitrary default violation: '{raw}' resolved to {match}"


def test_historical_divergences_composite_regions(resolver: LocationResolver) -> None:
    # Vatovavy-Fitovinany before 2021 split
    match_vato = resolver.resolve(
        "Vatovavy-Fitovinany",
        date_reference=date(2020, 6, 1),
    )
    assert match_vato is not None
    assert match_vato.pcode == "MDG23"
    assert match_vato.match_type == "historical_composite"
    assert match_vato.confidence == 0.85
    assert "2020-06-01" in (match_vato.note or "")

    # 24th region Ambatosoa (split in 2024 from Analanjirofo)
    match_amba = resolver.resolve("Ambatosoa")
    assert match_amba is not None
    assert match_amba.pcode == "MDG32"
    assert match_amba.confidence >= 0.85


def test_propose_alias_candidates_without_auto_approval(resolver: LocationResolver) -> None:
    # Slightly misspelled market / district
    candidates = resolver.propose_alias_candidates("Analakelyy Market", min_fuzzy_score=65.0)
    assert len(candidates) >= 1
    top = candidates[0]
    assert top.pcode == "MKT_ANALAKELY"
    assert top.match_type == "fuzzy_candidate"
    assert top.confidence > 0.6
    # Note must explain candidate rationale
    assert "Similarity score" in (top.note or "")


def test_api_location_resolution_endpoint() -> None:
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        role="admin", user_id="test"
    )
    try:
        client = TestClient(app)

        # 1. Successful resolution
        resp = client.get("/v1/locations/resolve", params={"query": "Analamanga"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved"] is True
        assert data["pcode"] == "MDG11"
        assert data["admin_level"] == 1

        # 2. Market resolution
        resp_mkt = client.get("/v1/locations/resolve", params={"query": "Analakely"})
        assert resp_mkt.status_code == 200
        data_mkt = resp_mkt.json()
        assert data_mkt["resolved"] is True
        assert data_mkt["pcode"] == "MKT_ANALAKELY"
        assert data_mkt["admin_level"] == 9

        # 3. Unresolved query (no arbitrary default)
        resp_unresolved = client.get(
            "/v1/locations/resolve", params={"query": "Zone_Totalement_Inconnue_XYZ"}
        )
        assert resp_unresolved.status_code == 200
        data_unres = resp_unresolved.json()
        assert data_unres["resolved"] is False
        assert data_unres["pcode"] is None
        assert "no arbitrary default" in data_unres["note"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_api_unresolved_locations_review_queue() -> None:
    # Mock DB session returning unmapped location rows
    mock_session = MagicMock()
    mock_session.execute.return_value.all.return_value = [
        ("Alaotra Mangoro (Region)", "wb_rtfp_mdg", 39),
        ("Inconnu Local Market", "wfp_hdx_mdg", 12),
    ]

    def override_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        role="admin", user_id="test"
    )
    try:
        client = TestClient(app)
        resp = client.get("/v1/locations/unresolved")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2

        first = items[0]
        assert first["location_raw"] == "Alaotra Mangoro (Region)"
        assert first["observation_count"] == 39
        assert first["source_id"] == "wb_rtfp_mdg"
        assert first["review_status"] == "pending"
        assert first["human_reviewed"] is False
        assert first["suggested_pcode"] == "MDG33"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
