"""Unit tests and physical coherence validation for NASA POWER connector (CC1, R1.11)."""

import json
from unittest.mock import MagicMock

import pytest

from ketrika.connectors.base import DiscoveredItem, RawArtifact, RunContext
from ketrika.connectors.nasa_power import NasaPowerConnector
from ketrika.connectors.records import WeatherRecord
from ketrika.core.bronze import BronzeStore
from ketrika.core.policy import PolicyStop
from ketrika.core.registry import find_repo_root

FIXTURE_PATH = (
    find_repo_root()
    / "backend"
    / "tests"
    / "fixtures"
    / "nasa_power"
    / "nasa_power_point_sample.json"
)


@pytest.fixture
def nasa_power_fixture_bytes() -> bytes:
    with open(FIXTURE_PATH, "rb") as f:
        return f.read()


def test_nasa_power_parse_fixture(nasa_power_fixture_bytes: bytes) -> None:
    """CC1: Unit test verifying parsing of NASA POWER GeoJSON point fixture."""
    connector = NasaPowerConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = nasa_power_fixture_bytes
    ctx = RunContext(source_id="nasa_power", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-nasa-id",
        object_key="bronze/nasa_power/sample.json",
        content_sha256="dummy-sha",
        mime_type="application/json",
        url="https://power.larc.nasa.gov/api/temporal/daily/point?test=1",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)

    # 1. Total records check: 9 valid dates * 4 variables = 36 records
    assert len(result.issues) == 0
    assert len(result.records) == 36

    weather_records = [r for r in result.records if isinstance(r, WeatherRecord)]
    assert len(weather_records) == 36

    # 2. Sentinel filtering: 2024-01-06 contained -999.0 for all variables -> must be skipped
    # No temperature converted to 0.0
    dates = {r.date.isoformat() for r in weather_records}
    assert "2024-01-06" not in dates
    assert "2024-01-01" in dates
    assert "2024-01-10" in dates

    # 3. Variable presence
    variables = {r.variable for r in weather_records}
    assert variables == {"precip_mm", "t2m_max_c", "t2m_min_c", "rh2m_pct"}

    # 4. District resolution
    districts = {r.location_raw for r in weather_records}
    assert districts == {"MDG1101"}

    # 5. Evidence metadata validation (R1.11 requirements)
    for r in weather_records:
        assert r.provider == "nasa_power"
        assert r.method == "point_centroid"
        assert r.extraction_method == "deterministic"
        assert r.confidence == 1.0
        assert r.value_raw is not None
        assert r.evidence["source"] == "nasa_power"
        assert r.evidence["source_family"] == "nasa"
        assert r.evidence["time_reference"] == "UTC"
        assert r.evidence["is_forecast_or_estimated"] is False
        assert r.evidence["value_kind"] == "observed"


def test_nasa_power_physical_coherence(nasa_power_fixture_bytes: bytes) -> None:
    """CC2 equivalent (T3.4, R1.11): Physical coherence check.

    Ensures t2m_min <= t2m_max, precip >= 0, and 0 <= rh2m <= 100 for all observation dates.
    """
    connector = NasaPowerConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = nasa_power_fixture_bytes
    ctx = RunContext(source_id="nasa_power", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="test-coherence-id",
        object_key="bronze/nasa_power/sample.json",
        content_sha256="dummy-sha",
        mime_type="application/json",
        url="https://power.larc.nasa.gov/api/temporal/daily/point?test=1",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    records_by_date: dict[str, dict[str, float]] = {}

    for rec in result.records:
        assert isinstance(rec, WeatherRecord)
        d_str = rec.date.isoformat()
        if d_str not in records_by_date:
            records_by_date[d_str] = {}
        records_by_date[d_str][rec.variable] = rec.value

    assert len(records_by_date) == 9

    for d_str, vars_dict in records_by_date.items():
        # Check precip >= 0
        precip = vars_dict["precip_mm"]
        assert precip >= 0.0, f"Negative precipitation {precip} on {d_str}"

        # Check t2m_min <= t2m_max
        t_min = vars_dict["t2m_min_c"]
        t_max = vars_dict["t2m_max_c"]
        assert t_min <= t_max, f"t2m_min ({t_min}) > t2m_max ({t_max}) on {d_str}"

        # Check 0 <= rh2m <= 100
        rh = vars_dict["rh2m_pct"]
        assert 0.0 <= rh <= 100.0, f"Relative humidity {rh}% out of bounds [0, 100] on {d_str}"


def test_nasa_power_physical_coherence_violations() -> None:
    """R1.11: Test that physical violations (Tmin > Tmax, precip < 0, rh > 100) are flagged and excluded."""
    connector = NasaPowerConnector()

    corrupt_payload = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [47.525, -18.924, 1280.0]},
        "properties": {
            "district_pcode": "MDG1101",
            "parameter": {
                "PRECTOTCORR": {
                    "20240101": -5.0,  # Negative precip
                    "20240102": 10.0,
                },
                "T2M_MAX": {
                    "20240101": 20.0,
                    "20240102": 15.0,  # Tmax < Tmin
                },
                "T2M_MIN": {
                    "20240101": 15.0,
                    "20240102": 25.0,  # Tmin > Tmax
                },
                "RH2M": {
                    "20240101": 150.0,  # RH > 100%
                    "20240102": 80.0,
                },
            },
        },
    }

    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = json.dumps(corrupt_payload).encode("utf-8")
    ctx = RunContext(source_id="nasa_power", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="corrupt-id",
        object_key="bronze/nasa_power/corrupt.json",
        content_sha256="dummy",
        mime_type="application/json",
        url="https://test.local",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)

    # Check that issues were recorded
    issues = [i for i in result.issues if i.get("kind") == "physical_coherence_error"]
    assert len(issues) >= 3

    # Check specific errors
    issue_details = [i.get("detail", "") for i in issues]
    assert any("Negative precipitation" in d for d in issue_details)
    assert any("t2m_min" in d and "t2m_max" in d for d in issue_details)
    assert any("Relative humidity" in d for d in issue_details)

    # Valid values still emitted (20240102 precip and RH, 20240101 temp)
    weather_records = [r for r in result.records if isinstance(r, WeatherRecord)]
    valid_vars = {(r.date.isoformat(), r.variable) for r in weather_records}
    assert ("2024-01-01", "precip_mm") not in valid_vars
    assert ("2024-01-01", "rh2m_pct") not in valid_vars
    assert ("2024-01-02", "t2m_max_c") not in valid_vars
    assert ("2024-01-02", "t2m_min_c") not in valid_vars
    assert ("2024-01-02", "precip_mm") in valid_vars
    assert ("2024-01-02", "rh2m_pct") in valid_vars


def test_nasa_power_unresolved_location_rejection() -> None:
    """R1.11 & R1.10: Unresolved location must NOT fall back to MDG1101, but emit issue."""
    connector = NasaPowerConnector()

    # Point located far away in the ocean, no district_pcode supplied
    ocean_payload = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [0.0, 0.0, 0.0]},
        "properties": {
            "parameter": {
                "PRECTOTCORR": {"20240101": 5.0},
                "T2M_MAX": {"20240101": 25.0},
                "T2M_MIN": {"20240101": 18.0},
                "RH2M": {"20240101": 80.0},
            }
        },
    }

    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = json.dumps(ocean_payload).encode("utf-8")
    ctx = RunContext(source_id="nasa_power", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="ocean-id",
        object_key="bronze/nasa_power/ocean.json",
        content_sha256="dummy",
        mime_type="application/json",
        url="https://test.local",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)

    # Zero records produced; issue emitted
    assert len(result.records) == 0
    assert any(i.get("kind") == "unresolved_location_needs_review" for i in result.issues)
    assert not any(
        isinstance(r, WeatherRecord) and r.location_raw == "MDG1101" for r in result.records
    )


def test_nasa_power_discover() -> None:
    """Verify connector.discover yields valid query targets with explicit parameters (A14)."""
    connector = NasaPowerConnector()
    ctx = RunContext(source_id="nasa_power", metadata={"start": "20240101", "end": "20240110"})

    items = list(connector.discover(ctx))
    assert len(items) >= 3  # At least 3 sample districts

    for item in items:
        assert "parameters=PRECTOTCORR,T2M_MAX,T2M_MIN,RH2M" in item.url
        assert "community=AG" in item.url
        assert "start=20240101" in item.url
        assert "end=20240110" in item.url
        assert "time-standard=UTC" in item.url
        assert "longitude=" in item.url
        assert "latitude=" in item.url
        assert "district_pcode" in item.hints
        assert item.hints["district_pcode"].startswith("MDG")
        assert "grid_cell" in item.hints


def test_nasa_power_strict_policy_disabled_guard() -> None:
    """R1.11 & B-R010: Connector must raise PolicyStop if source is disabled and network fetch is attempted."""
    connector = NasaPowerConnector()
    item = DiscoveredItem(
        url="https://power.larc.nasa.gov/api/temporal/daily/point?test=1",
        partition_key="test",
        hints={},
    )
    ctx = RunContext(source_id="nasa_power", offline=False)

    with pytest.raises(PolicyStop, match="marked disabled in sources.yaml"):
        connector.fetch(item, ctx)


def test_nasa_power_offline_reproducibility() -> None:
    """R1.11: Connector must load local fixture in offline mode into BronzeStore."""
    connector = NasaPowerConnector()
    item = DiscoveredItem(
        url="https://power.larc.nasa.gov/api/temporal/daily/point?test=1",
        partition_key="test",
        hints={},
    )
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.put.return_value = MagicMock(
        object_key="nasa_power/2026/10/offline.json", is_new=True
    )
    ctx = RunContext(source_id="nasa_power", bronze_store=mock_bronze, offline=True)

    artifact = connector.fetch(item, ctx)
    assert artifact.mime_type == "application/json"
    assert len(artifact.content_sha256) == 64
    assert mock_bronze.put.called


def test_nasa_power_discover_override_urls() -> None:
    """Verify discover honors override urls in metadata."""
    connector = NasaPowerConnector()
    ctx = RunContext(
        source_id="nasa_power",
        metadata={
            "urls": [
                {
                    "url": "https://power.larc.nasa.gov/api/custom",
                    "partition_key": "custom_part",
                    "hints": {"custom": "hint"},
                }
            ]
        },
    )
    items = list(connector.discover(ctx))
    assert len(items) == 1
    assert items[0].url == "https://power.larc.nasa.gov/api/custom"
    assert items[0].partition_key == "custom_part"


def test_nasa_power_parse_coordinates_resolution() -> None:
    """Verify parsing resolves coordinates within Madagascar when district_pcode is omitted."""
    connector = NasaPowerConnector()
    # Coordinates of Antananarivo Renivohitra
    payload = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [47.525, -18.924, 1280.0]},
        "properties": {
            "parameter": {
                "PRECTOTCORR": {"20240101": 2.5},
            }
        },
    }
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = json.dumps(payload).encode("utf-8")
    ctx = RunContext(source_id="nasa_power", bronze_store=mock_bronze)

    artifact = RawArtifact(
        source_record_id="coord-res-id",
        object_key="bronze/nasa_power/coord.json",
        content_sha256="dummy",
        mime_type="application/json",
        url="https://test.local",
        is_new=True,
    )
    result = connector.parse(artifact, ctx)
    assert len(result.records) == 1
    rec = result.records[0]
    assert isinstance(rec, WeatherRecord)
    assert rec.location_raw == "MDG1101"


def test_nasa_power_parse_error_branches() -> None:
    """Verify parser handles json errors, unexpected payload, and missing parameter block."""
    connector = NasaPowerConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    ctx = RunContext(source_id="nasa_power", bronze_store=mock_bronze)

    # 1. JSON decode error
    mock_bronze.get.return_value = b"invalid json content"
    art1 = RawArtifact(
        source_record_id="err1",
        object_key="err1.json",
        content_sha256="d1",
        mime_type="application/json",
        url="https://test.local",
        is_new=True,
    )
    res1 = connector.parse(art1, ctx)
    assert any(i.get("kind") == "json_decode_error" for i in res1.issues)

    # 2. Unexpected payload type (list instead of dict)
    mock_bronze.get.return_value = b"[1, 2, 3]"
    art2 = RawArtifact(
        source_record_id="err2",
        object_key="err2.json",
        content_sha256="d2",
        mime_type="application/json",
        url="https://test.local",
        is_new=True,
    )
    res2 = connector.parse(art2, ctx)
    assert any(i.get("kind") == "unexpected_payload" for i in res2.issues)

    # 3. Missing parameter dict
    mock_bronze.get.return_value = json.dumps(
        {
            "properties": {"district_pcode": "MDG1101"},
            "geometry": {"coordinates": [47.5, -18.9]},
        }
    ).encode()
    art3 = RawArtifact(
        source_record_id="err3",
        object_key="err3.json",
        content_sha256="d3",
        mime_type="application/json",
        url="https://test.local",
        is_new=True,
    )
    res3 = connector.parse(art3, ctx)
    assert any(i.get("kind") == "missing_parameters" for i in res3.issues)
