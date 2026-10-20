"""Unit tests for Météo Madagascar agrometeorological connector (R4.3, ADR-082, SPECS §26)."""

import uuid
from datetime import date
from pathlib import Path

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.meteo_mg import MeteoMgConnector
from ketrika.connectors.records import EventRecord, WeatherRecord
from ketrika.geo.contracts import WeatherVariable

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "meteo_mg"


class DummyBronzeStore:
    """In-memory bronze store for unit tests."""

    def __init__(self, data: bytes):
        self._data = data

    def get(self, object_key: str) -> bytes | None:
        return self._data


def test_meteo_mg_discovery():
    """Test discovery of dekadal bulletins with issued_at and validity window hints."""
    connector = MeteoMgConnector()
    ctx = RunContext(
        source_id="meteo_mg",
        run_id="run-1",
        bronze_store=None,
        metadata={"years": [2024], "months": [1], "dekads": [1, 2]},
    )

    items = list(connector.discover(ctx))
    assert len(items) == 2

    d1 = items[0]
    assert "bulletin_decadaire_2024_01_d1.pdf" in d1.url
    assert d1.partition_key == "meteo_mg_2024_01_d1"
    assert d1.hints["issued_at"] == "2024-01-11"
    assert d1.hints["valid_from"] == "2024-01-01"
    assert d1.hints["valid_to"] == "2024-01-10"

    d2 = items[1]
    assert "bulletin_decadaire_2024_01_d2.pdf" in d2.url
    assert d2.partition_key == "meteo_mg_2024_01_d2"
    assert d2.hints["issued_at"] == "2024-01-21"
    assert d2.hints["valid_from"] == "2024-01-11"
    assert d2.hints["valid_to"] == "2024-01-20"


def test_meteo_mg_discovery_override():
    """Test discovery when specific URLs are provided in metadata."""
    connector = MeteoMgConnector()
    override_urls = [
        {
            "url": "https://www.meteomadagascar.mg/bulletins/custom.pdf",
            "partition_key": "custom_1",
            "hints": {"custom": "true"},
        }
    ]
    ctx = RunContext(
        source_id="meteo_mg",
        run_id="run-2",
        bronze_store=None,
        metadata={"urls": override_urls},
    )

    items = list(connector.discover(ctx))
    assert len(items) == 1
    assert items[0].url == "https://www.meteomadagascar.mg/bulletins/custom.pdf"
    assert items[0].partition_key == "custom_1"


def test_meteo_mg_parse_standard_bulletin():
    """Test parsing of an official dekadal bulletin with rainfall and qualitative advisories."""
    fixture_path = FIXTURES_DIR / "bulletin_decadaire_2024_01_d1.json"
    with open(fixture_path, "rb") as f:
        payload = f.read()

    connector = MeteoMgConnector()
    bronze_store = DummyBronzeStore(payload)
    ctx = RunContext(
        source_id="meteo_mg",
        run_id="run-parse-1",
        bronze_store=bronze_store,
        metadata={},
    )

    sr_id = str(uuid.uuid4())
    artifact = RawArtifact(
        source_record_id=sr_id,
        url="https://www.meteomadagascar.mg/bulletins/agrometeo/2024/bulletin_decadaire_2024_01_d1.pdf",
        object_key="meteo_mg/2024/01/d1.pdf",
        mime_type="application/pdf",
        content_sha256="abc123sha",
        is_new=True,
    )

    res = connector.parse(artifact, ctx)
    assert len(res.issues) == 0

    # 3 weather observations + 2 qualitative advisories = 5 records
    assert len(res.records) == 5

    weather_records = [r for r in res.records if isinstance(r, WeatherRecord)]
    advisory_records = [r for r in res.records if isinstance(r, EventRecord)]

    assert len(weather_records) == 3
    assert len(advisory_records) == 2

    # Verify weather records
    analamanga = next(r for r in weather_records if r.location_raw == "Analamanga")
    assert analamanga.variable == WeatherVariable.PRECIP_MM
    assert analamanga.value == 68.5
    assert analamanga.stage == "final"
    assert analamanga.provider == "meteo_mg"
    assert analamanga.spatial_resolution == "station_point"
    assert analamanga.evidence["page"] == 2
    assert "Cumul décadaire observé de 68.5 mm" in analamanga.evidence["excerpt"]
    assert analamanga.evidence["issued_at"] == "2024-01-11T08:00:00Z"
    assert analamanga.evidence["valid_from"] == "2024-01-01"
    assert analamanga.evidence["valid_to"] == "2024-01-10"

    # Verify qualitative advisories (ADR-082 strict adherence: no invented probabilities)
    adv_alaotra = next(
        r for r in advisory_records if r.evidence.get("location_scope") == "Alaotra-Mangoro"
    )
    assert adv_alaotra.event_type == "agroclimate_advisory"
    assert "Avis agro-climatique DGM: favorable" in adv_alaotra.title
    assert "développement végétatif du paddy" in (adv_alaotra.summary or "")
    assert adv_alaotra.period_start == date(2024, 1, 1)
    assert adv_alaotra.period_end == date(2024, 1, 10)
    assert adv_alaotra.evidence["page"] == 4
    assert adv_alaotra.evidence["qualitative_category"] == "favorable"
    # Ensure no fabricated probability field exists
    assert "probability" not in adv_alaotra.evidence


def test_meteo_mg_parse_unavailable_bulletin():
    """Test fail-safe behavior when bulletin is marked unavailable or empty."""
    fixture_path = FIXTURES_DIR / "bulletin_unavailable.json"
    with open(fixture_path, "rb") as f:
        payload = f.read()

    connector = MeteoMgConnector()
    bronze_store = DummyBronzeStore(payload)
    ctx = RunContext(
        source_id="meteo_mg",
        run_id="run-unavailable",
        bronze_store=bronze_store,
        metadata={},
    )

    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="https://www.meteomadagascar.mg/bulletins/agrometeo/2024/bulletin_decadaire_2024_01_d3.pdf",
        object_key="meteo_mg/2024/01/d3.pdf",
        mime_type="application/pdf",
        content_sha256="empty",
        is_new=True,
    )

    res = connector.parse(artifact, ctx)
    assert len(res.records) == 0
    assert len(res.issues) == 1
    assert res.issues[0]["kind"] == "document_unavailable"
    assert "non publié" in res.issues[0]["detail"]


def test_meteo_mg_parse_empty_bytes():
    """Test behavior when bronze payload is completely empty."""
    connector = MeteoMgConnector()
    bronze_store = DummyBronzeStore(b"")
    ctx = RunContext(
        source_id="meteo_mg",
        run_id="run-empty",
        bronze_store=bronze_store,
        metadata={},
    )

    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="https://www.meteomadagascar.mg/bulletins/agrometeo/2024/empty.pdf",
        object_key="meteo_mg/2024/01/empty.pdf",
        mime_type="application/pdf",
        content_sha256="empty",
        is_new=True,
    )

    res = connector.parse(artifact, ctx)
    assert len(res.records) == 0
    assert len(res.issues) == 1
    assert res.issues[0]["kind"] == "document_unavailable"


def test_meteo_mg_parse_text_fallback():
    """Test text fallback when document is not JSON."""
    raw_text = b"Station Analamanga: 45.2 mm\nStation Vakinankaratra: 52.0 mm"
    connector = MeteoMgConnector()
    bronze_store = DummyBronzeStore(raw_text)
    ctx = RunContext(
        source_id="meteo_mg",
        run_id="run-text",
        bronze_store=bronze_store,
        metadata={},
    )

    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="https://www.meteomadagascar.mg/bulletins/agrometeo/2024/bulletin.txt",
        object_key="meteo_mg/2024/01/bulletin.txt",
        mime_type="text/plain",
        content_sha256="sha-txt",
        is_new=True,
    )

    res = connector.parse(artifact, ctx)
    assert len(res.issues) == 0
    assert len(res.records) == 2
    assert res.records[0].location_raw == "Analamanga"
    assert res.records[0].value == 45.2
    assert res.records[1].location_raw == "Vakinankaratra"
    assert res.records[1].value == 52.0
