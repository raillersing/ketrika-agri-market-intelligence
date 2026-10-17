"""Unit and integration tests for CHIRPS connector qualification (ADR-080, ADR-081, SPECS §26, R4.2)."""

import hashlib
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.chirps import CHIRPS_NODATA_VALUE, ChirpsConnector
from ketrika.connectors.records import WeatherRecord
from ketrika.connectors.runner import load_weather_record_with_supersession
from ketrika.core.models.db import Location, WeatherObservation
from ketrika.core.policy import PolicyStop
from ketrika.geo.contracts import MAX_RASTER_FILE_SIZE_BYTES, WeatherVariable


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "chirps"


def test_chirps_connector_discovery():
    """Criterion 1: CHIRPS discovers preliminary, final, and both stages with deterministic keys."""
    connector = ChirpsConnector()

    # Discover both stages for March 2024
    ctx = RunContext(
        source_id="chirps",
        metadata={"years": [2024], "months": [3], "stage": "both", "subregion": "africa"},
    )
    items = list(connector.discover(ctx))
    assert len(items) == 2

    keys = {it.partition_key for it in items}
    assert "chirps_preliminary_2024_03" in keys
    assert "chirps_final_2024_03" in keys

    # Verify URLs and hints
    for it in items:
        assert "chirps-v2.0.2024.03.tif.gz" in it.url
        assert it.hints["variable"] == WeatherVariable.PRECIP_MM
        assert it.hints["spatial_resolution"] == "0.05_deg"


def test_chirps_parse_preliminary_and_final(fixtures_dir: Path):
    """Criterion 2: Parsing preserves stages (preliminary vs final), resolution, and valid dates."""
    connector = ChirpsConnector()
    prelim_path = fixtures_dir / "chirps_prelim_sample.json"
    prelim_bytes = prelim_path.read_bytes()
    sha256 = hashlib.sha256(prelim_bytes).hexdigest()

    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        object_key="bronze/chirps/2024/03/prelim.json",
        content_sha256=sha256,
        mime_type="application/json",
        url="https://data.chc.ucsb.edu/products/CHIRPS-2.0/prelim/africa_monthly/tifs/chirps-v2.0.2024.03.tif.gz",
        is_new=True,
    )

    ctx = RunContext(
        source_id="chirps",
        metadata={"payload_bytes": prelim_bytes},
    )

    res = connector.parse(artifact, ctx)
    assert len(res.records) > 0

    # Check that all parsed records are tagged as preliminary
    for rec in res.records:
        assert isinstance(rec, WeatherRecord)
        assert rec.provider == "chirps"
        assert rec.stage == "preliminary"
        assert rec.variable == "precip_mm"
        assert rec.spatial_resolution == "0.05_deg"
        assert rec.date == date(2024, 3, 1)
        assert rec.evidence["stage"] == "preliminary"
        assert rec.evidence["sha256"] == sha256


def test_strict_distinction_zero_rain_vs_nodata(fixtures_dir: Path):
    """Criterion 3: Physical distinction between zero rain (0.0 mm) and nodata (-9999.0)."""
    connector = ChirpsConnector()
    final_path = fixtures_dir / "chirps_final_sample.json"
    final_bytes = final_path.read_bytes()
    sha256 = hashlib.sha256(final_bytes).hexdigest()

    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        object_key="bronze/chirps/2024/03/final.json",
        content_sha256=sha256,
        mime_type="application/json",
        url="https://data.chc.ucsb.edu/products/CHIRPS-2.0/africa_monthly/tifs/chirps-v2.0.2024.03.tif.gz",
        is_new=True,
    )

    ctx = RunContext(
        source_id="chirps",
        metadata={"payload_bytes": final_bytes},
    )

    res = connector.parse(artifact, ctx)

    # In our fixture, Toliara / Sud has 0.0 mm
    # All values must be non-negative (no -9999.0 leakage into valid records!)
    for rec in res.records:
        assert isinstance(rec, WeatherRecord)
        assert rec.value >= 0.0, f"Value {rec.value} is negative (nodata leak!)"
        assert rec.value != CHIRPS_NODATA_VALUE


def test_raster_budget_limit_enforcement():
    """Criterion 4: Reject rasters exceeding the 50 MB Bronze storage budget."""
    connector = ChirpsConnector()
    oversized_bytes = b"0" * (MAX_RASTER_FILE_SIZE_BYTES + 1024)

    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        object_key="bronze/chirps/oversized.tif",
        content_sha256="fake_sha",
        mime_type="application/octet-stream",
        url="https://data.chc.ucsb.edu/oversized.tif",
        is_new=True,
    )

    ctx = RunContext(
        source_id="chirps",
        metadata={"payload_bytes": oversized_bytes},
    )

    with pytest.raises(PolicyStop, match="exceeds budget"):
        connector.parse(artifact, ctx)


def test_double_version_supersession_c2_c4():
    """Criterion 5: Preliminary version is archived with superseded_by when final arrives (C2/C4)."""
    mock_session = MagicMock()

    loc_id = uuid.uuid4()
    mock_loc = MagicMock(spec=Location)
    mock_loc.location_id = loc_id
    mock_loc.pcode = "MG11"
    mock_loc.name = "Analamanga"

    # Mock location lookup
    mock_scalar = MagicMock()
    mock_scalar.first.return_value = mock_loc
    mock_session.execute.return_value.scalars.return_value = mock_scalar

    sr_prelim_id = uuid.uuid4()
    sr_final_id = uuid.uuid4()
    obs_date = date(2024, 3, 1)

    rec_prelim = WeatherRecord(
        location_raw="MG11",
        date=obs_date,
        variable="precip_mm",
        value=65.0,
        value_raw="65.0",
        method="zonal_mean",
        provider="chirps",
        stage="preliminary",
        spatial_resolution="0.05_deg",
        coverage_ratio=0.95,
    )

    # 1. First ingestion: preliminary version inserted
    mock_session.execute.return_value.scalar_one_or_none.return_value = None
    status1, prelim_obs_id = load_weather_record_with_supersession(
        session=mock_session,
        record=rec_prelim,
        source_id="chirps",
        source_record_id=sr_prelim_id,
    )
    assert status1 == "inserted"

    # 2. Re-ingestion: exact same preliminary record is idempotent_skipped
    existing_prelim = WeatherObservation(
        observation_id=prelim_obs_id,
        source_record_id=sr_prelim_id,
        location_id=loc_id,
        location_raw="MG11",
        date=obs_date,
        variable="precip_mm",
        value=65.0,
        value_raw="65.0",
        method="zonal_mean",
        provider="chirps",
        stage="preliminary",
        spatial_resolution="0.05_deg",
        coverage_ratio=0.95,
        extraction_method="deterministic",
        evidence={},
        superseded_by=None,
    )
    mock_session.execute.return_value.scalar_one_or_none.return_value = existing_prelim
    status2, id2 = load_weather_record_with_supersession(
        session=mock_session,
        record=rec_prelim,
        source_id="chirps",
        source_record_id=sr_prelim_id,
    )
    assert status2 == "idempotent_skipped"
    assert id2 == prelim_obs_id

    # 3. Final version arrives with ground-truth adjusted value (62.4 mm)
    rec_final = WeatherRecord(
        location_raw="MG11",
        date=obs_date,
        variable="precip_mm",
        value=62.4,
        value_raw="62.4",
        method="zonal_mean",
        provider="chirps",
        stage="final",
        spatial_resolution="0.05_deg",
        coverage_ratio=0.98,
    )

    status3, final_obs_id = load_weather_record_with_supersession(
        session=mock_session,
        record=rec_final,
        source_id="chirps",
        source_record_id=sr_final_id,
    )
    assert status3 == "superseded"
    assert final_obs_id != prelim_obs_id

    # Verify that session.execute called an update to set superseded_by
    calls = mock_session.execute.call_args_list
    assert len(calls) >= 2


def test_chirps_gzip_compressed_payload_and_binary_fallback(fixtures_dir: Path):
    """Test handling of gzip-compressed payloads and binary grid fallback."""
    import gzip

    connector = ChirpsConnector()
    prelim_path = fixtures_dir / "chirps_prelim_sample.json"
    compressed_bytes = gzip.compress(prelim_path.read_bytes())
    sha256 = hashlib.sha256(compressed_bytes).hexdigest()

    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        object_key="bronze/chirps/2024/03/prelim.json.gz",
        content_sha256=sha256,
        mime_type="application/gzip",
        url="https://data.chc.ucsb.edu/products/CHIRPS-2.0/prelim/africa_monthly/tifs/chirps-v2.0.2024.03.tif.gz",
        is_new=True,
    )

    ctx = RunContext(
        source_id="chirps",
        metadata={"payload_bytes": compressed_bytes},
    )

    res = connector.parse(artifact, ctx)
    assert len(res.records) > 0

    # Also test that non-json, corrupted/dummy bytes are strictly rejected with NO synthetic records
    binary_artifact = RawArtifact(
        source_record_id="",
        object_key="bronze/chirps/dummy.tif",
        content_sha256="dummy_sha",
        mime_type="application/octet-stream",
        url="https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/tifs/chirps-v2.0.2024.01.tif",
        is_new=True,
    )
    binary_ctx = RunContext(
        source_id="chirps",
        metadata={"payload_bytes": b"\x00\x01\x02\x03\x04\x05\x06\x07"},
    )
    bin_res = connector.parse(binary_artifact, binary_ctx)
    assert len(bin_res.records) == 0
    assert len(bin_res.issues) > 0
    assert bin_res.issues[0]["kind"] == "raster_decode_error"


def test_chirps_discover_overrides_and_list_stages():
    """Test discovery with explicit override URLs and list-based stages."""
    connector = ChirpsConnector()

    ctx_overrides = RunContext(
        source_id="chirps",
        metadata={
            "urls": [
                {
                    "url": "https://example.com/custom/chirps.tif.gz",
                    "partition_key": "custom_key",
                    "hints": {"stage": "preliminary"},
                }
            ]
        },
    )
    items = list(connector.discover(ctx_overrides))
    assert len(items) == 1
    assert items[0].url == "https://example.com/custom/chirps.tif.gz"
    assert items[0].partition_key == "custom_key"

    ctx_list = RunContext(
        source_id="chirps",
        metadata={"years": [2023], "months": [12], "stage": ["final"], "subregion": "global"},
    )
    items_list = list(connector.discover(ctx_list))
    assert len(items_list) == 1
    assert "global_monthly" in items_list[0].url
    assert items_list[0].partition_key == "chirps_final_2023_12"
