"""Tests for IA-DATA-07: Multisource price ingestion (WFP HDX HAPI & FAO FPMA) and double-counting mitigation."""

from unittest.mock import MagicMock

from ketrika.connectors.base import DiscoveredItem, RawArtifact, RunContext
from ketrika.connectors.fao_fpma_mdg import FaoFpmaConnector
from ketrika.connectors.records import PriceRecord
from ketrika.connectors.registry import get_connector_class
from ketrika.connectors.wfp_hdx_mdg import WfpHdxMdgConnector
from ketrika.core.bronze import BronzeStore
from ketrika.gold.kpi import audit_source_family_independence


def test_registry_contains_both_price_connectors():
    """Verify that both WFP HDX and FAO FPMA connectors are registered."""
    assert get_connector_class("wfp_hdx_mdg") is WfpHdxMdgConnector
    assert get_connector_class("fao_fpma_mdg") is FaoFpmaConnector


def test_wfp_hdx_hapi_discovery_with_pagination_and_app_id():
    """Verify HDX HAPI discovery correctly builds paginated offset/limit queries."""
    connector = WfpHdxMdgConnector()
    ctx = RunContext(
        source_id="wfp_hdx_mdg",
        metadata={
            "api_type": "hapi",
            "app_identifier": "sec-test-app-id",
            "limit": 500,
            "max_pages": 3,
        },
    )
    items = list(connector.discover(ctx))
    assert len(items) == 3

    assert "limit=500" in items[0].url
    assert "offset=0" in items[0].url
    assert "app_identifier=sec-test-app-id" in items[0].url
    assert items[0].hints.get("page") == 0

    assert "offset=500" in items[1].url
    assert items[1].hints.get("page") == 1

    assert "offset=1000" in items[2].url
    assert items[2].hints.get("page") == 2


def test_wfp_hdx_offline_fetch_loads_hapi_sample():
    """Verify offline fetch correctly selects JSON fixture when hints indicate JSON format."""
    connector = WfpHdxMdgConnector()
    ctx = RunContext(
        source_id="wfp_hdx_mdg",
        offline=True,
    )
    item = DiscoveredItem(
        url="https://hapi.humdata.org/api/v2/food-security-nutrition-poverty/food-prices-market-monitor",
        partition_key="hdx_hapi_v2_mdg",
        hints={"format": "json"},
    )
    artifact = connector.fetch(item, ctx)
    assert artifact.mime_type == "application/json"
    assert artifact.object_key.endswith(".json")
    assert len(artifact.content_sha256) == 64


def test_wfp_hdx_parse_hapi_sample_ppn():
    """Verify parsing of WFP HDX HAPI v2 payload into standardized PPN records."""
    connector = WfpHdxMdgConnector()
    ctx = RunContext(
        source_id="wfp_hdx_mdg",
        offline=True,
    )
    item = DiscoveredItem(
        url="https://hapi.humdata.org/api/v2/food-security-nutrition-poverty/food-prices-market-monitor",
        partition_key="hdx_hapi_v2_mdg",
        hints={"format": "json"},
    )
    artifact = connector.fetch(item, ctx)

    # Mock bronze store to return artifact content
    from ketrika.core.registry import find_repo_root

    root = find_repo_root()
    base_dir = root / "backend" if (root / "backend").exists() else root
    fixture_path = base_dir / "tests" / "fixtures" / "wfp_hdx_mdg" / "wfp_hapi_mdg_sample.json"

    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = fixture_path.read_bytes()
    parse_ctx = RunContext(source_id="wfp_hdx_mdg", bronze_store=mock_bronze)

    result = connector.parse(artifact, parse_ctx)
    assert len(result.issues) == 0
    assert len(result.records) == 6

    # Verify PPN commodities
    commodities = {r.product_raw for r in result.records}
    assert "Rice (local)" in commodities
    assert "Rice (imported)" in commodities
    assert "Maize" in commodities
    assert "Cassava (fresh)" in commodities
    assert "Sugar" in commodities
    assert "Wheat flour" in commodities

    # Verify markets
    markets = {r.location_raw for r in result.records}
    assert "Anosibe" in markets
    assert "Anjozorobe" in markets
    assert "Bazar Be" in markets

    # Verify evidence metadata
    for rec in result.records:
        assert isinstance(rec, PriceRecord)
        assert rec.evidence["source_family"] == "un_wfp"
        assert rec.evidence["underlying_collector"] == "WFP VAM"
        assert rec.currency_raw == "MGA"
        assert rec.unit_raw == "KG"

    # Verify observed vs imputed
    observed_recs = [r for r in result.records if r.observed_or_imputed == "observed"]
    imputed_recs = [r for r in result.records if r.observed_or_imputed == "imputed"]
    assert len(observed_recs) == 5
    assert len(imputed_recs) == 1  # Wheat flour is estimated


def test_wfp_hdx_parse_rejects_missing_market():
    """Verify strict no_arbitrary_default rule: record with missing market is sent to review queue."""
    connector = WfpHdxMdgConnector()
    payload = {
        "data": [
            {
                "commodity_name": "Rice (local)",
                "market_name": "",  # missing market
                "price": 3000.0,
                "reference_period_start": "2025-04-15",
            }
        ]
    }
    issues: list[dict] = []
    import json

    recs = connector._parse_hapi_json(json.dumps(payload), issues)
    assert len(recs) == 0
    assert len(issues) == 1
    assert issues[0]["kind"] == "unresolved_market_needs_review"


def test_fao_fpma_discovery_and_offline_fetch():
    """Verify FAO FPMA discovery and offline fetch from fixture."""
    connector = FaoFpmaConnector()
    ctx = RunContext(source_id="fao_fpma_mdg", offline=True)
    items = list(connector.discover(ctx))
    assert len(items) == 1
    assert "fpma.fao.org" in items[0].url

    artifact = connector.fetch(items[0], ctx)
    assert artifact.mime_type == "application/json"
    assert artifact.object_key.endswith(".json")
    assert len(artifact.content_sha256) == 64


def test_fao_fpma_parse_ppn_sample():
    """Verify FAO FPMA parsing of food prices in Madagascar."""
    connector = FaoFpmaConnector()
    from ketrika.core.registry import find_repo_root

    root = find_repo_root()
    base_dir = root / "backend" if (root / "backend").exists() else root
    fixture_path = base_dir / "tests" / "fixtures" / "fao_fpma_mdg" / "fpma_prices_mdg_sample.json"

    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = fixture_path.read_bytes()
    ctx = RunContext(source_id="fao_fpma_mdg", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="rec-fpma-1",
        object_key="fao_fpma_mdg/sample.json",
        content_sha256="dummy-fpma-sha",
        mime_type="application/json",
        url="https://fpma.fao.org/giews/fpma/api/v1/prices?country=MDG",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    assert len(result.issues) == 0
    assert len(result.records) == 5

    commodities = {r.product_raw for r in result.records}
    assert "Rice (milled)" in commodities
    assert "Maize (white)" in commodities
    assert "Cassava (fresh)" in commodities

    markets = {r.location_raw for r in result.records}
    assert "Antananarivo" in markets
    assert "Toamasina" in markets
    assert "Mahajanga" in markets

    for r in result.records:
        assert isinstance(r, PriceRecord)
        assert r.evidence["source_family"] == "un_fao"
        assert r.evidence["provider"] == "FAO GIEWS FPMA Tool"
        assert r.currency_raw == "MGA"
        assert r.price_value is not None and r.price_value > 0


def test_fao_fpma_rejects_missing_market():
    """Verify FAO FPMA rejects records without market and issues review warning."""
    connector = FaoFpmaConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    invalid_data = {
        "data": [
            {
                "commodity": "Rice (milled)",
                "market": "   ",  # empty
                "price": 3200.0,
                "date": "2025-04-01",
            }
        ]
    }
    import json

    mock_bronze.get.return_value = json.dumps(invalid_data).encode("utf-8")
    ctx = RunContext(source_id="fao_fpma_mdg", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="rec-inv",
        object_key="inv.json",
        content_sha256="sha",
        mime_type="application/json",
        url="http://example.com",
        is_new=True,
    )
    res = connector.parse(artifact, ctx)
    assert len(res.records) == 0
    assert len(res.issues) == 1
    assert res.issues[0]["kind"] == "unresolved_market_needs_review"


def test_double_counting_detection_across_wb_wfp_fao():
    """Verify that co-occurrence of WB RTFP, WFP HDX, or FAO FPMA is detected as non-independent."""
    # 1. Truly independent sources: ODR + FAOSTAT + ECMWF
    clean_audit = audit_source_family_independence(
        [
            {"source_id": "miasa_odr", "source_family": "madagascar_gov"},
            {"source_id": "faostat", "source_family": "un_fao"},
            {"source_id": "ecmwf_open", "source_family": "ecmwf"},
        ]
    )
    assert clean_audit["is_truly_independent"] is True
    assert clean_audit["has_dependent_derivation"] is False
    assert clean_audit["n_independent_families"] == 3

    # 2. WFP HDX + WB RTFP (WB derives from WFP primary data)
    wb_wfp_audit = audit_source_family_independence(
        [
            {"source_id": "wfp_hdx_mdg", "source_family": "un_wfp"},
            {"source_id": "wb_rtfp_mdg", "source_family": "world_bank"},
        ]
    )
    assert wb_wfp_audit["has_dependent_derivation"] is True
    assert wb_wfp_audit["is_truly_independent"] is False
    assert wb_wfp_audit["n_independent_families"] == 1  # Both mapped to un_wfp

    # 3. WFP HDX + FAO FPMA (shared primary market observations)
    wfp_fao_audit = audit_source_family_independence(
        [
            {"source_id": "wfp_hdx_mdg", "source_family": "un_wfp"},
            {"source_id": "fao_fpma_mdg", "source_family": "un_fao"},
        ]
    )
    assert wfp_fao_audit["has_dependent_derivation"] is True
    assert wfp_fao_audit["is_truly_independent"] is False

    # 4. Triplet WB RTFP + WFP HDX + FAO FPMA
    triplet_audit = audit_source_family_independence(["wb_rtfp_mdg", "wfp_hdx_mdg", "fao_fpma_mdg"])
    assert triplet_audit["has_dependent_derivation"] is True
    assert triplet_audit["is_truly_independent"] is False
