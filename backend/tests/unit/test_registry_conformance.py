"""Unit tests for Phase R1 registry conformance and source permissions (R1.1, C1, C3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ketrika.core.models.source import SourceDefinition
from ketrika.core.registry import load_sources, validate_registry


def test_registry_file_validates_without_errors() -> None:
    """Verify that validate_registry finds zero errors on sources.yaml."""
    errors = validate_registry(check_fixtures=True, check_docs=True)
    assert errors == [], f"Registry validation failed with errors: {errors}"


def test_all_sources_define_source_family() -> None:
    """Verify every registered source specifies a source_family (C3 anti-leakage rule)."""
    sources = load_sources()
    assert len(sources) == 12

    for s in sources:
        assert s.source_family is not None, f"Source '{s.source_id}' is missing source_family"
        assert len(s.source_family) > 0, f"Source '{s.source_id}' has empty source_family"

    # Verify WFP and World Bank RTFP belong to distinct families
    family_map = {s.source_id: s.source_family for s in sources}
    assert family_map["wfp_hdx_mdg"] == "un_wfp"
    assert family_map["wb_rtfp_mdg"] == "world_bank"
    assert family_map["wfp_hdx_mdg"] != family_map["wb_rtfp_mdg"]
    assert family_map["bfm_public"] == "bfm"

    # Verify national Madagascar sources share madagascar_gov family
    gov_sources = ["instat_nipc", "miasa_odr", "mincc_ppn", "douanes_stats", "instat_tbe"]
    for src in gov_sources:
        assert family_map[src] == "madagascar_gov"


def test_all_sources_define_distinct_cadences() -> None:
    """Verify collection, observation and publication cadences are distinct and defined."""
    sources = load_sources()
    valid_cadences = {"daily", "weekly", "monthly", "quarterly", "annual", "event", "static"}

    for s in sources:
        assert s.collection_cadence in valid_cadences, (
            f"Source '{s.source_id}' has invalid collection_cadence: {s.collection_cadence}"
        )
        assert s.observation_cadence in valid_cadences, (
            f"Source '{s.source_id}' has invalid observation_cadence: {s.observation_cadence}"
        )
        assert s.publication_cadence in valid_cadences, (
            f"Source '{s.source_id}' has invalid publication_cadence: {s.publication_cadence}"
        )

    # Specific check: FAOSTAT collects monthly, observes annually, publishes annually
    fao = next(s for s in sources if s.source_id == "faostat")
    assert fao.collection_cadence == "monthly"
    assert fao.observation_cadence == "annual"
    assert fao.publication_cadence == "annual"


def test_all_entrypoints_define_verified_flag() -> None:
    """Verify all entrypoint URLs explicitly declare verified boolean status."""
    sources = load_sources()
    for s in sources:
        assert len(s.entrypoints) >= 1
        for ep in s.entrypoints:
            assert isinstance(ep.verified, bool), (
                f"Source '{s.source_id}' entrypoint '{ep.url}' has non-bool verified"
            )
            if ep.verified:
                assert ep.verified_at is not None, (
                    f"Source '{s.source_id}' entrypoint '{ep.url}' is verified but verified_at is None"
                )


def test_reject_forbidden_extra_fields() -> None:
    """Verify extra='forbid' rejects unknown fields in SourceDefinition."""
    valid_data = {
        "source_id": "test_src",
        "name": "Test Source",
        "owner": "Test Owner",
        "access_method": "file",
        "connector": "ketrika.connectors.test:Connector",
        "cadence": "monthly",
        "freshness_sla_days": 30,
        "partitioning": "static",
        "entrypoints": [{"url": "https://test.example.org", "kind": "landing"}],
        "data_kinds": ["price"],
        "unknown_extra_field": "disallowed_value",
    }
    with pytest.raises(ValidationError):
        SourceDefinition.model_validate(valid_data)


def test_reject_direct_pii_in_registry() -> None:
    """Verify registry rejects any source declaring pii_class='direct'."""
    sources = load_sources()
    for s in sources:
        assert s.pii_class != "direct", (
            f"Direct PII is strictly prohibited in MVP: source '{s.source_id}'"
        )
