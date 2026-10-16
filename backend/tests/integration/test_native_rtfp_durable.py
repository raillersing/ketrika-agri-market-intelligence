"""Synthetic envelopes of verified samples through SQL/S3; no source qualification."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.batch_ledger import persist_bronze_batch
from ketrika.connectors.document_partitions import register_document_partitions
from ketrika.connectors.durable_phases import execute_durable_silver
from ketrika.connectors.rebuild_references import resolve_snapshot_keys
from ketrika.connectors.stages import BronzeBatch
from ketrika.connectors.wb_rtfp_mdg import WbRtfpMdgConnector
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.models.db import IngestionRun, PriceObservation, SourceRecord
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.core.registry import find_repo_root
from ketrika.normalize.reference_snapshot import reopen_reference_snapshot


@pytest.mark.integration
def test_native_batch_records_reusable_reference_identity_without_collecting(monkeypatch):
    store = BronzeStore()
    assert store.bucket == "ketrika-qa-bronze"
    root = find_repo_root() / "backend"
    run_id = uuid4()
    artifacts = []
    with get_session() as session:
        url = session.get_bind().engine.url
        require_synthetic_test_database(url.host, url.database)
        session.add(
            IngestionRun(
                run_id=run_id,
                source_id="wb_rtfp_mdg",
                started_at=datetime.now(UTC),
                status="running",
                n_fetched=2,
                n_new_artifacts=2,
            )
        )
        session.flush()
        for filename, receipt_name in (
            ("mdg_close_estimates_20261015.json", "close-estimates-acquisition.json"),
            ("mdg_study_20261005.json", "study-acquisition.json"),
        ):
            content = (root / "tests/fixtures/authentic/world_bank_rtfp" / filename).read_bytes()
            receipt = json.loads(
                (root / "tests/corpus-evidence/world_bank_rtfp" / receipt_name).read_text()
            )
            assert hashlib.sha256(content).hexdigest() == receipt["sha256"]
            # Preserve every publisher data/context value, but namespace the test
            # envelope: SourceRecord correctly forbids duplicate source/content.
            # These derived bytes are synthetic, NOT an authentic source archive.
            document = json.loads(content)
            document["_ketrika_test"] = {
                "dataset": "synthetic",
                "run": str(run_id),
                "original_sha256": receipt["sha256"],
            }
            content = json.dumps(document, ensure_ascii=False).encode()
            archived = store.put(
                source_id="wb_rtfp_mdg",
                content=content,
                mime_type="application/json",
                url=receipt["source_url"],
                retrieved_via="manual_upload",
                fetched_at=datetime.now(UTC),
                http_status=0,
                http_headers={"x-ketrika-scope": "synthetic-envelope-software-test"},
            )
            identifier = uuid4()
            session.add(
                SourceRecord(
                    source_record_id=identifier,
                    source_id="wb_rtfp_mdg",
                    source_url=receipt["source_url"],
                    object_key=archived.object_key,
                    content_sha256=archived.content_sha256,
                    mime_type="application/json",
                    fetched_at=datetime.now(UTC),
                    parser_version="2.0.0",
                    extraction_status="pending",
                    retrieved_via="manual_upload",
                )
            )
            artifacts.append(
                RawArtifact(
                    str(identifier),
                    archived.object_key,
                    archived.content_sha256,
                    "application/json",
                    receipt["source_url"],
                    True,
                )
            )
        session.flush()
        batch = BronzeBatch("wb_rtfp_mdg", run_id, "2.0.0", tuple(artifacts))
        persist_bronze_batch(session, batch)
        register_document_partitions(session, batch)

    def forbidden(*args, **kwargs):
        raise AssertionError("native_silver_must_not_discover_fetch_or_use_legacy_parser")

    connector = WbRtfpMdgConnector()
    monkeypatch.setattr(connector, "discover", forbidden)
    monkeypatch.setattr(connector, "fetch", forbidden)
    monkeypatch.setattr(connector, "parse", forbidden)
    context = RunContext(source_id="wb_rtfp_mdg", bronze_store=store, offline=True)
    stats = execute_durable_silver(connector, context, batch)
    assert stats["n_rejected"] == 0
    assert stats["n_inserted"] + stats["n_superseded"] + stats["n_skipped"] == 15
    assert execute_durable_silver(connector, context, batch) == stats
    with get_session() as session:
        primary = session.get(SourceRecord, artifacts[0].source_record_id)
        assert primary is not None
        keys = resolve_snapshot_keys(session, [primary], store)
        assert set(keys) == {primary.source_record_id}
        snapshot = reopen_reference_snapshot(session, store, *keys[primary.source_record_id])
        assert snapshot.archive.sha256 == keys[primary.source_record_id][1]
        run = session.get(IngestionRun, run_id)
        assert run is not None and run.status == "success"
        rows = list(
            session.scalars(
                select(PriceObservation).where(
                    PriceObservation.source_record_id == primary.source_record_id
                )
            )
        )
        if stats["n_inserted"]:
            assert len(rows) == 15
        assert all(row.observed_or_imputed == "imputed" for row in rows)
