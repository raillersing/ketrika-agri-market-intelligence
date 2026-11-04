"""Synthetic ZIPs through real isolated SQL/S3; no authentic-source claim."""

import csv
import io
import json
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.batch_ledger import persist_bronze_batch
from ketrika.connectors.document_partitions import register_document_partitions
from ketrika.connectors.durable_phases import execute_durable_silver
from ketrika.connectors.rebuild_references import resolve_snapshot_keys
from ketrika.connectors.rtfp_archive import parse_persisted
from ketrika.connectors.stages import BronzeBatch
from ketrika.connectors.wb_rtfp_mdg import WbRtfpMdgConnector
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.models.db import IngestionRun, PriceObservation, SourceRecord
from ketrika.core.provenance import ProofError
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.core.schema_wb_archive import COLUMNS


def prepare():
    store, run_id = BronzeStore(), uuid4()
    assert store.bucket == "ketrika-qa-bronze"
    text = io.StringIO(newline="")
    writer = csv.writer(text)
    writer.writerow(COLUMNS)
    values = dict.fromkeys(COLUMNS, "") | {
        "ISO3": "MDG",
        "country": "Madagascar",
        "adm1_name": "Market Average",
        "adm2_name": "Market Average",
        "mkt_name": "Market Average",
        "geo_id": "gid_mdg_national_average",
        "price_date": "2026-09-01",
        "currency": "MGA",
        "c_rice": "1234.567890",
    }
    writer.writerow([values[column] for column in COLUMNS])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("MDG_RTFP_mkt_2007_2026-10-05.csv", text.getvalue())
        archive.comment = ("SYNTHETIC SOFTWARE TEST " + str(run_id)).encode()
    metadata = {
        "study_desc": {
            "title_statement": {
                "idno": "MDG_2021_RTFP_v02_M",
                "title": "Monthly food price estimates by product and market",
            }
        },
        "additional": {
            "ticker_info": [
                {
                    "iso3": "MDG",
                    "country": "Madagascar",
                    "ticker": "rice",
                    "full_name": "Rice (local)",
                    "units": "KG",
                    "food_index_weight": "0.3",
                    "data_coverage": "0.5",
                    "r2_imputation": "0.9",
                }
            ]
        },
        "_ketrika_test": {"dataset": "synthetic", "run": str(run_id)},
    }
    payloads = (
        (
            buffer.getvalue(),
            "application/octet-stream",
            "https://microdata.worldbank.org/api/downloads/download/MDG_2021_RTFP_v02_M/360780?filename=MDG_RTFP_mkt_2007_2026-10-05.zip",
        ),
        (
            json.dumps(metadata).encode(),
            "application/json",
            "https://microdata.worldbank.org/metadata/export/8240/json",
        ),
    )
    artifacts = []
    with get_session() as session:
        url = session.get_bind().engine.url
        require_synthetic_test_database(url.host, url.database)
        session.add(
            IngestionRun(
                run_id=run_id,
                source_id="wb_rtfp_mdg",
                status="running",
                started_at=datetime.now(UTC),
                n_fetched=2,
                n_new_artifacts=2,
            )
        )
        session.flush()
        for content, mime, source_url in payloads:
            archived = store.put(
                source_id="wb_rtfp_mdg",
                content=content,
                mime_type=mime,
                url=source_url,
                retrieved_via="manual_upload",
                http_status=0,
                http_headers={"x-ketrika-scope": "synthetic-software-test"},
            )
            identifier = uuid4()
            session.add(
                SourceRecord(
                    source_record_id=identifier,
                    source_id="wb_rtfp_mdg",
                    source_url=source_url,
                    object_key=archived.object_key,
                    content_sha256=archived.content_sha256,
                    mime_type=mime,
                    fetched_at=datetime.now(UTC),
                    parser_version="3.0.0",
                    extraction_status="pending",
                    retrieved_via="manual_upload",
                )
            )
            artifacts.append(
                RawArtifact(
                    str(identifier),
                    archived.object_key,
                    archived.content_sha256,
                    mime,
                    source_url,
                    True,
                )
            )
        session.flush()
        batch = BronzeBatch("wb_rtfp_mdg", run_id, "3.0.0", tuple(artifacts))
        persist_bronze_batch(session, batch)
        register_document_partitions(session, batch)
    return store, batch


@pytest.mark.integration
def test_archive_native_silver_uses_persisted_context_and_reference_identity(monkeypatch):
    store, batch = prepare()
    connector = WbRtfpMdgConnector()

    def forbidden(*args, **kwargs):
        raise AssertionError("archive_silver_must_not_fetch_or_use_legacy_parser")

    for method in ("discover", "fetch", "parse"):
        monkeypatch.setattr(connector, method, forbidden)
    context = RunContext(source_id="wb_rtfp_mdg", bronze_store=store, offline=True)
    stats = execute_durable_silver(connector, context, batch)
    assert stats["n_rejected"] == 0
    assert stats["n_inserted"] + stats["n_superseded"] + stats["n_skipped"] == 1
    assert execute_durable_silver(connector, context, batch) == stats
    with get_session() as session:
        primary = session.get(SourceRecord, batch.artifacts[0].source_record_id)
        assert primary is not None
        keys = resolve_snapshot_keys(session, [primary], store)
        assert set(keys) == {primary.source_record_id}
        run = session.get(IngestionRun, batch.ingestion_run_id)
        assert run is not None and run.status == "success"
        rows = list(
            session.scalars(
                select(PriceObservation).where(
                    PriceObservation.source_record_id == primary.source_record_id
                )
            )
        )
        assert all(
            row.observed_or_imputed == "imputed" and row.actor_level == "unknown" for row in rows
        )


@pytest.mark.integration
def test_archive_caller_cannot_substitute_the_immutable_batch_descriptor():
    store, batch = prepare()
    primary = batch.artifacts[0]
    with get_session() as session:
        with pytest.raises(ProofError, match="batch_reference_mismatch"):
            parse_persisted(
                session,
                replace(primary, url="https://example.org/synthetic-forgery"),
                BronzeProofReader(store),
            )
