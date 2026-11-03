"""Unit tests for FEWS NET and IPC Madagascar food security connector (R4.4, ADR-083, SPECS §26)."""

import uuid
from datetime import date
from pathlib import Path

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.fewsnet_ipc import FewsnetConnector, IpcConnector
from ketrika.connectors.records import EventRecord

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "fewsnet_ipc"


class DummyBronzeStore:
    """In-memory bronze store for unit tests."""

    def __init__(self, data: bytes):
        self._data = data

    def get(self, object_key: str) -> bytes | None:
        return self._data


def test_fewsnet_ipc_discovery():
    """Test discovery for FEWS NET and IPC sources."""
    # FEWS NET discovery
    fewsnet = FewsnetConnector()
    ctx_fewsnet = RunContext(
        source_id="fewsnet_mdg",
        run_id="run-fews-1",
        bronze_store=None,
        metadata={"years": [2024]},
    )
    items_fews = list(fewsnet.discover(ctx_fewsnet))
    assert len(items_fews) == 3
    assert "fewsnet_mdg_2024_02" in items_fews[0].partition_key
    assert items_fews[0].hints["source_type"] == "fewsnet"

    # IPC discovery
    ipc = IpcConnector()
    ctx_ipc = RunContext(
        source_id="ipc_mdg",
        run_id="run-ipc-1",
        bronze_store=None,
        metadata={"years": [2024]},
    )
    items_ipc = list(ipc.discover(ctx_ipc))
    assert len(items_ipc) == 2
    assert "ipc_mdg_2024_january_april" in items_ipc[0].partition_key
    assert items_ipc[0].hints["source_type"] == "ipc"


def test_fewsnet_ipc_discovery_override():
    """Test discovery with explicit URLs."""
    connector = FewsnetConnector()
    override_urls = [
        {
            "url": "https://fews.net/custom-report.pdf",
            "partition_key": "custom_fews",
            "hints": {"custom": "true"},
        }
    ]
    ctx = RunContext(
        source_id="fewsnet_mdg",
        run_id="run-override",
        bronze_store=None,
        metadata={"urls": override_urls},
    )
    items = list(connector.discover(ctx))
    assert len(items) == 1
    assert items[0].url == "https://fews.net/custom-report.pdf"


def test_fewsnet_parse_outlook_strict_disjunction():
    """Test parsing FEWS NET outlook enforcing strict separation between current and projected."""
    fixture_path = FIXTURES_DIR / "fewsnet_mdg_outlook_2024_02.json"
    with open(fixture_path, "rb") as f:
        payload = f.read()

    connector = FewsnetConnector()
    bronze_store = DummyBronzeStore(payload)
    ctx = RunContext(
        source_id="fewsnet_mdg",
        run_id="run-parse-fews",
        bronze_store=bronze_store,
        metadata={},
    )

    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="https://fews.net/east-africa/madagascar/food-security-outlook/2024-02.pdf",
        object_key="fewsnet/2024/02.pdf",
        mime_type="application/pdf",
        content_sha256="sha-fews-123",
        is_new=True,
    )

    res = connector.parse(artifact, ctx)
    assert len(res.issues) == 0

    # 2 current situations + 1 projected outlook = 3 events
    assert len(res.records) == 3

    current_events = [r for r in res.records if not r.is_projected]
    projected_events = [r for r in res.records if r.is_projected]

    assert len(current_events) == 2
    assert len(projected_events) == 1

    # Verify Current Situation (Androy)
    cur_androy = next(r for r in current_events if r.location_raw == "Androy")
    assert cur_androy.event_type == "food_security_ipc"
    assert cur_androy.severity == 2
    assert cur_androy.period_start == date(2024, 2, 1)
    assert cur_androy.period_end == date(2024, 5, 31)
    assert cur_androy.evidence["page"] == 3
    assert cur_androy.evidence["ipc_phase"] == 2
    assert "stocks résiduels" in (cur_androy.summary or "")
    assert "stocks de maïs limités" in cur_androy.evidence["key_drivers"]

    # Verify Projected Outlook (Androy) - Strict ADR-083 Disjunction
    proj_androy = next(r for r in projected_events if r.location_raw == "Androy")
    assert proj_androy.event_type == "food_security_ipc"
    assert proj_androy.is_projected is True
    assert proj_androy.severity == 3
    assert proj_androy.period_start == date(2024, 6, 1)
    assert proj_androy.period_end == date(2024, 9, 30)
    assert proj_androy.evidence["page"] == 6
    assert proj_androy.evidence["ipc_phase"] == 3
    assert "Phase 3 de l'IPC" in (proj_androy.summary or "")
    assert len(proj_androy.evidence["assumptions"]) == 2
    assert "Pluviométrie cumulée inférieure" in proj_androy.evidence["assumptions"][0]

    # Ensure current and projected periods do NOT overlap or merge
    assert cur_androy.period_end < proj_androy.period_start
    assert cur_androy.severity != proj_androy.severity


def test_ipc_parse_analysis():
    """Test parsing IPC acute food insecurity analysis."""
    fixture_path = FIXTURES_DIR / "ipc_mdg_analysis_2024.json"
    with open(fixture_path, "rb") as f:
        payload = f.read()

    connector = IpcConnector()
    bronze_store = DummyBronzeStore(payload)
    ctx = RunContext(
        source_id="ipc_mdg",
        run_id="run-parse-ipc",
        bronze_store=bronze_store,
        metadata={},
    )

    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="https://www.ipcinfo.org/ipc_acute_food_insecurity_2024.pdf",
        object_key="ipc/2024.pdf",
        mime_type="application/pdf",
        content_sha256="sha-ipc-456",
        is_new=True,
    )

    res = connector.parse(artifact, ctx)
    assert len(res.issues) == 0
    assert len(res.records) == 2

    current = next(r for r in res.records if not r.is_projected)
    projected = next(r for r in res.records if r.is_projected)

    assert current.location_raw == "Atsimo-Andrefana"
    assert current.severity == 3
    assert current.period_start == date(2024, 1, 1)
    assert current.period_end == date(2024, 4, 30)

    assert projected.location_raw == "Atsimo-Andrefana"
    assert projected.severity == 3
    assert projected.period_start == date(2024, 5, 1)
    assert projected.period_end == date(2024, 9, 30)
    assert len(projected.evidence["assumptions"]) == 2


def test_fewsnet_parse_unavailable():
    """Test fail-safe behavior when publication is unavailable."""
    fixture_path = FIXTURES_DIR / "fewsnet_unavailable.json"
    with open(fixture_path, "rb") as f:
        payload = f.read()

    connector = FewsnetConnector()
    bronze_store = DummyBronzeStore(payload)
    ctx = RunContext(
        source_id="fewsnet_mdg",
        run_id="run-unavailable",
        bronze_store=bronze_store,
        metadata={},
    )

    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="https://fews.net/missing.pdf",
        object_key="fewsnet/missing.pdf",
        mime_type="application/pdf",
        content_sha256="empty",
        is_new=True,
    )

    res = connector.parse(artifact, ctx)
    assert len(res.records) == 0
    assert len(res.issues) == 1
    assert res.issues[0]["kind"] == "document_unavailable"


def test_fewsnet_parse_empty_bytes():
    """Test behavior when bronze payload is completely empty."""
    connector = FewsnetConnector()
    bronze_store = DummyBronzeStore(b"")
    ctx = RunContext(
        source_id="fewsnet_mdg",
        run_id="run-empty",
        bronze_store=bronze_store,
        metadata={},
    )

    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="https://fews.net/empty.pdf",
        object_key="fewsnet/empty.pdf",
        mime_type="application/pdf",
        content_sha256="empty",
        is_new=True,
    )

    res = connector.parse(artifact, ctx)
    assert len(res.records) == 0
    assert len(res.issues) == 1
    assert res.issues[0]["kind"] == "document_unavailable"


def test_fewsnet_parse_text_fallback():
    """Test text fallback when document is plain text."""
    raw_text = b"Situation alimentaire de crise dans le sud de Madagascar suite a la secheresse."
    connector = FewsnetConnector()
    bronze_store = DummyBronzeStore(raw_text)
    ctx = RunContext(
        source_id="fewsnet_mdg",
        run_id="run-text",
        bronze_store=bronze_store,
        metadata={},
    )

    artifact = RawArtifact(
        source_record_id=str(uuid.uuid4()),
        url="https://fews.net/report.txt",
        object_key="fewsnet/report.txt",
        mime_type="text/plain",
        content_sha256="sha-txt",
        is_new=True,
    )

    res = connector.parse(artifact, ctx)
    assert len(res.issues) == 0
    assert len(res.records) == 1
    assert res.records[0].event_type == "food_security_ipc"
    assert res.records[0].location_raw == "Grand Sud"


def test_fewsnet_ipc_loader_insertion_and_idempotence():
    """Test loading EventRecord into obs.event via load_record_with_supersession."""
    from unittest.mock import MagicMock

    from ketrika.connectors.runner import load_record_with_supersession
    from ketrika.core.models.db import Event

    session = MagicMock()
    session.scalar.return_value = False
    source_record_id = uuid.uuid4()
    source_id = "fewsnet_mdg"

    # 1. Insertion run
    session.execute.return_value.scalar_one_or_none.return_value = None

    rec = EventRecord(
        event_type="food_security_ipc",
        title="FEWS NET Outlook - Androy Crise (Phase 3)",
        summary="Crise alimentaire projetée dans l'Androy suite à la sécheresse.",
        location_raw="Androy",
        is_projected=True,
        event_date=date(2024, 2, 15),
        severity=3,
        period_start=date(2024, 6, 1),
        period_end=date(2024, 9, 30),
        evidence={"page": 5, "ipc_phase": 3, "assumptions": ["sécheresse"]},
    )

    status1, event_id1 = load_record_with_supersession(session, rec, source_id, source_record_id)
    assert status1 == "inserted"
    assert isinstance(event_id1, uuid.UUID)

    session.add.assert_called_once()
    added_event = session.add.call_args[0][0]
    assert isinstance(added_event, Event)
    assert added_event.title == "FEWS NET Outlook - Androy Crise (Phase 3)"
    assert added_event.severity == 3
    assert added_event.evidence["is_projected"] is True
    assert added_event.evidence["location_raw"] == "Androy"
    assert added_event.evidence["period_start"] == "2024-06-01"

    # 2. Idempotent replay
    session.execute.return_value.scalar_one_or_none.return_value = added_event
    status2, event_id2 = load_record_with_supersession(session, rec, source_id, source_record_id)
    assert status2 == "idempotent_skipped"
    assert event_id2 == added_event.event_id
