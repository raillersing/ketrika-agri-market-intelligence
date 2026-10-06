"""Unit tests for the source registry loader and validator."""

import pytest

from ketrika.core.models.source import SourceDefinition
from ketrika.core.registry import (
    REQUIRED_SOURCES,
    get_source,
    load_sources,
    validate_registry,
)


def test_load_sources_returns_all_required_sources() -> None:
    sources = load_sources()
    assert len(sources) >= len(REQUIRED_SOURCES)
    ids = {s.source_id for s in sources}
    for req in REQUIRED_SOURCES:
        assert req in ids


def test_get_source_success() -> None:
    wfp = get_source("wfp_hdx_mdg")
    assert wfp.source_id == "wfp_hdx_mdg"
    assert wfp.priority == "P1"
    assert "price" in wfp.data_kinds


def test_get_source_not_found_raises_key_error() -> None:
    with pytest.raises(KeyError):
        get_source("unknown_source_xyz")


def test_validate_registry_passes() -> None:
    errors = validate_registry()
    assert errors == []


def test_source_definition_rejects_direct_pii() -> None:
    sample_data = {
        "source_id": "test_src",
        "name": "Test",
        "owner": "Test Owner",
        "priority": "P1",
        "status": "active",
        "access_method": "file",
        "connector": "test:Connector",
        "cadence": "daily",
        "freshness_sla_days": 7,
        "partitioning": "daily",
        "entrypoints": [{"url": "http://example.com", "kind": "landing"}],
        "data_kinds": ["price"],
        "pii_class": "direct",
    }
    src = SourceDefinition.model_validate(sample_data)
    assert src.pii_class == "direct"
