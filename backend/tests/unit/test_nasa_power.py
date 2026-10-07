"""Unit tests and physical coherence validation for NASA POWER connector (CC1, T3.4)."""

from unittest.mock import MagicMock

import pytest

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.nasa_power import NasaPowerConnector
from ketrika.connectors.records import WeatherRecord
from ketrika.core.bronze import BronzeStore
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


def test_nasa_power_physical_coherence(nasa_power_fixture_bytes: bytes) -> None:
    """CC2 equivalent (T3.4): Physical coherence check replacing golden test.

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


def test_nasa_power_discover() -> None:
    """Verify connector.discover yields valid query targets for all districts."""
    connector = NasaPowerConnector()
    ctx = RunContext(source_id="nasa_power")

    items = list(connector.discover(ctx))
    assert len(items) >= 3  # At least 3 sample districts (Antananarivo, Antsirabe, Toamasina)

    for item in items:
        assert "parameters=PRECTOTCORR,T2M_MAX,T2M_MIN,RH2M" in item.url
        assert "community=AG" in item.url
        assert "longitude=" in item.url
        assert "latitude=" in item.url
        assert "district_pcode" in item.hints
        assert item.hints["district_pcode"].startswith("MDG")
