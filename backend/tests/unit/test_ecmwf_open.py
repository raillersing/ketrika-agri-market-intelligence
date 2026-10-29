"""Unit tests for ECMWF Open Data weather prediction connector (R4.5, ADR-084, SPECS §26)."""

import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import MagicMock

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.ecmwf_open import EcmwfOpenConnector
from ketrika.connectors.records import WeatherForecastRecord
from ketrika.connectors.runner import load_record_with_supersession
from ketrika.core.models.db import WeatherForecast, WeatherObservation

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "ecmwf_open"


class DummyBronzeStore:
    """In-memory bronze store for unit tests."""

    def __init__(self, data: bytes):
        self._data = data

    def get(self, object_key: str) -> bytes | None:
        return self._data


def test_ecmwf_open_discovery():
    """Test discovery of daily NWP cycles (00z, 12z)."""
    connector = EcmwfOpenConnector()
    ctx = RunContext(
        source_id="ecmwf_open",
        run_id="run-ecmwf-disc",
        bronze_store=None,
        metadata={"target_date": "2024-03-01", "cycles": ["00z", "12z"]},
    )
    items = list(connector.discover(ctx))
    assert len(items) == 2
    assert "20240301_00z" in items[0].partition_key
    assert items[0].hints["cycle"] == "00z"
    assert "20240301_12z" in items[1].partition_key
    assert items[1].hints["cycle"] == "12z"


def test_ecmwf_open_discovery_override():
    """Test discovery with explicit URLs provided."""
    connector = EcmwfOpenConnector()
    override = [{"url": "https://data.ecmwf.int/custom.json", "partition_key": "custom_ecmwf"}]
    ctx = RunContext(
        source_id="ecmwf_open",
        run_id="run-custom",
        bronze_store=None,
        metadata={"urls": override},
    )
    items = list(connector.discover(ctx))
    assert len(items) == 1
    assert items[0].url == "https://data.ecmwf.int/custom.json"


def test_ecmwf_open_parse_standard_run():
    """Test parsing an official 00z forecast run with uncertainty quantiles."""
    fixture_path = FIXTURES_DIR / "ecmwf_ifs_20240301_00z.json"
    with open(fixture_path, "rb") as f:
        payload = f.read()

    connector = EcmwfOpenConnector()
    bronze_store = DummyBronzeStore(payload)
    ctx = RunContext(
        source_id="ecmwf_open",
        run_id="run-parse-00z",
        bronze_store=bronze_store,
        metadata={},
    )

    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="https://data.ecmwf.int/forecasts/20240301/00z/ifs_madagascar_0p4.json",
        object_key="ecmwf/20240301/00z.json",
        mime_type="application/json",
        content_sha256="sha-ecmwf-00z",
        is_new=True,
    )

    res = connector.parse(artifact, ctx)
    assert len(res.issues) == 0
    assert len(res.records) == 4

    records = [r for r in res.records if isinstance(r, WeatherForecastRecord)]
    assert len(records) == 4

    # Verify Analamanga 24h precipitation
    analamanga_precip = next(
        r for r in records if r.location_raw == "Analamanga" and r.variable == "precip_mm"
    )
    assert analamanga_precip.horizon_hours == 24
    assert analamanga_precip.predicted_value == 14.5
    assert analamanga_precip.predicted_p10 == 4.0
    assert analamanga_precip.predicted_p90 == 26.2
    assert analamanga_precip.unit == "mm"
    assert analamanga_precip.model_name == "ecmwf_ifs_open"
    assert analamanga_precip.period_start == date(2024, 3, 2)
    assert analamanga_precip.period_end == date(2024, 3, 3)

    # Verify Androy 72h precipitation (dry / 0 mm)
    androy_precip = next(r for r in records if r.location_raw == "Androy")
    assert androy_precip.horizon_hours == 72
    assert androy_precip.predicted_value == 0.0
    assert androy_precip.predicted_p10 == 0.0
    assert androy_precip.predicted_p90 == 2.1


def test_ecmwf_open_two_runs_succession():
    """Criterion: at least two representative runs available with distinct horizons."""
    f1 = FIXTURES_DIR / "ecmwf_ifs_20240301_00z.json"
    f2 = FIXTURES_DIR / "ecmwf_ifs_20240301_12z.json"
    connector = EcmwfOpenConnector()

    with open(f1, "rb") as b1:
        res1 = connector.parse(
            RawArtifact(
                source_record_id=str(uuid.uuid4()),
                url="https://data.ecmwf.int/00z.json",
                object_key="00z.json",
                mime_type="application/json",
                content_sha256="sha1",
                is_new=True,
            ),
            RunContext(
                source_id="ecmwf_open", run_id="r1", bronze_store=DummyBronzeStore(b1.read())
            ),
        )

    with open(f2, "rb") as b2:
        res2 = connector.parse(
            RawArtifact(
                source_record_id=str(uuid.uuid4()),
                url="https://data.ecmwf.int/12z.json",
                object_key="12z.json",
                mime_type="application/json",
                content_sha256="sha2",
                is_new=True,
            ),
            RunContext(
                source_id="ecmwf_open", run_id="r2", bronze_store=DummyBronzeStore(b2.read())
            ),
        )

    assert len(res1.records) == 4
    assert len(res2.records) == 1
    assert res1.records[0].issued_at != res2.records[0].issued_at


def test_ecmwf_open_physical_consistency_checks():
    """Test physical consistency controls: negative rain and unrealistic temperatures rejected (ADR-084)."""
    fixture_path = FIXTURES_DIR / "ecmwf_invalid_physical.json"
    with open(fixture_path, "rb") as f:
        payload = f.read()

    connector = EcmwfOpenConnector()
    bronze_store = DummyBronzeStore(payload)
    ctx = RunContext(source_id="ecmwf_open", run_id="run-invalid", bronze_store=bronze_store)

    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="https://data.ecmwf.int/invalid.json",
        object_key="invalid.json",
        mime_type="application/json",
        content_sha256="sha-inv",
        is_new=True,
    )

    res = connector.parse(artifact, ctx)
    assert len(res.records) == 0
    assert len(res.issues) == 2
    issue_kinds = [i["kind"] for i in res.issues]
    assert "invalid_physical_value" in issue_kinds
    assert "unrealistic_temperature" in issue_kinds


def test_ecmwf_open_unavailable_and_empty():
    """Test fail-safe behavior when forecast cycle is unavailable or empty."""
    fixture_path = FIXTURES_DIR / "ecmwf_unavailable.json"
    with open(fixture_path, "rb") as f:
        payload = f.read()

    connector = EcmwfOpenConnector()
    res1 = connector.parse(
        RawArtifact(
            source_record_id=str(uuid.uuid4()),
            url="https://data.ecmwf.int/unavail.json",
            object_key="unavail.json",
            mime_type="application/json",
            content_sha256="sha-u",
            is_new=True,
        ),
        RunContext(source_id="ecmwf_open", run_id="r1", bronze_store=DummyBronzeStore(payload)),
    )
    assert len(res1.records) == 0
    assert len(res1.issues) == 1
    assert res1.issues[0]["kind"] == "document_unavailable"

    res2 = connector.parse(
        RawArtifact(
            source_record_id=str(uuid.uuid4()),
            url="https://data.ecmwf.int/empty.json",
            object_key="empty.json",
            mime_type="application/json",
            content_sha256="sha-e",
            is_new=True,
        ),
        RunContext(source_id="ecmwf_open", run_id="r2", bronze_store=DummyBronzeStore(b"")),
    )
    assert len(res2.records) == 0
    assert len(res2.issues) == 1
    assert res2.issues[0]["kind"] == "document_unavailable"


def test_ecmwf_loader_watertight_separation_and_supersession():
    """Test loader into obs.weather_forecast, never contaminating obs.weather_observation (ADR-084)."""
    session = MagicMock()
    session.scalar.return_value = False
    source_record_id = uuid.uuid4()
    source_id = "ecmwf_open"

    # 1. Insertion run
    session.execute.return_value.scalar_one_or_none.return_value = None

    rec = WeatherForecastRecord(
        location_raw="Analamanga",
        issued_at=datetime(2024, 3, 1, 0, 0, 0, tzinfo=UTC),
        valid_from=datetime(2024, 3, 2, 0, 0, 0, tzinfo=UTC),
        valid_to=datetime(2024, 3, 3, 0, 0, 0, tzinfo=UTC),
        horizon_hours=24,
        variable="precip_mm",
        model_name="ecmwf_ifs_open",
        predicted_value=14.5,
        predicted_p10=4.0,
        predicted_p90=26.2,
        unit="mm",
    )

    status1, fc_id1 = load_record_with_supersession(session, rec, source_id, source_record_id)
    assert status1 == "inserted"
    assert isinstance(fc_id1, uuid.UUID)

    session.add.assert_called_once()
    added_fc = session.add.call_args[0][0]

    # Watertight separation check: MUST be WeatherForecast, NEVER WeatherObservation!
    assert isinstance(added_fc, WeatherForecast)
    assert not isinstance(added_fc, WeatherObservation)
    assert added_fc.horizon_hours == 24
    assert added_fc.predicted_value == 14.5
    assert added_fc.model_name == "ecmwf_ifs_open"

    # 2. Idempotent replay
    session.execute.return_value.scalar_one_or_none.return_value = added_fc
    status2, fc_id2 = load_record_with_supersession(session, rec, source_id, source_record_id)
    assert status2 == "idempotent_skipped"
    assert fc_id2 == added_fc.forecast_id
