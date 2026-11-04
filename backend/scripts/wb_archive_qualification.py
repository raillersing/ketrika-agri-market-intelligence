"""Owned offline WB reception destination; refuses existing initialization.

Uses original bytes and a read-only filesystem Bronze copy, never an active DB.
S3 version retention, source freshness, human review and market models remain
separate qualifications. Commands are prepare and replay, on a Unix socket only.
"""

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from alembic import command
from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.batch_ledger import persist_bronze_batch
from ketrika.connectors.document_partitions import register_document_partitions
from ketrika.connectors.durable_phases import execute_durable_silver
from ketrika.connectors.stages import BronzeBatch
from ketrika.connectors.wb_rtfp_mdg import WbRtfpMdgConnector
from ketrika.core.bronze import BronzeStore
from ketrika.core.corpus import load_manifest, validate_manifest
from ketrika.core.models.db import (
    IngestionRun,
    Location,
    LocationAlias,
    PriceObservation,
    Source,
    SourceRecord,
)
from ketrika.core.provenance_audit import audit_observation_provenance
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.rebuild_bronze import LocalBronzeClient
from ketrika.core.reference_lock import lock_reference_manifest
from ketrika.core.settings import get_settings
from ketrika.gold.refresh import init_gold_views, refresh_gold_views
from ketrika.normalize.loader import seed_locations, seed_products, seed_units
from ketrika.normalize.locations import normalize_location_string
from ketrika.pipelines.rebuild_qualification import (
    require_destination,
    require_network_none,
    run_offline_replay,
    versioned_recompute_receipt,
)

SOURCE = "wb_rtfp_mdg"
BUCKET = "wb-replay-original-copy"
PACKET = Path("/packet/corpus")
COPY = Path("/copy")


def store() -> BronzeStore:
    inventory = json.loads((COPY / "inventory.json").read_text())
    return BronzeStore(
        bucket_name=BUCKET, client=LocalBronzeClient(COPY, BUCKET, inventory["objects"])
    )


def write_report(kind: str, report: dict) -> None:
    report.update(
        uid=os.getuid(),
        network=require_network_none(),
        human_reviewed=False,
        source_freshness_qualified=False,
        model_qualified=False,
        s3_retention_qualified=False,
        finished_at=datetime.now(UTC).isoformat(),
    )
    path = Path("/out") / (kind + "-" + uuid4().hex + ".json")
    with path.open("x") as output:
        json.dump(report, output, indent=2, default=str)
    print(
        json.dumps(
            {"report": str(path), "result": report.get("replay_passed", report.get("loaded"))}
        )
    )


def prepare() -> None:
    require_network_none()
    engine = create_engine(get_settings().database_url)
    with Session(engine) as session:
        require_destination(session)
        if (
            session.scalar(text("SELECT to_regclass('meta.source_record')"))
            or (COPY / "inventory.json").exists()
        ):
            raise ValueError("wb_reception_already_initialized_no_overwrite")
        session.rollback()
        manifest = load_manifest(PACKET)
        corpus = validate_manifest(PACKET, manifest)
        if corpus["verified_annotation_cells"] != 664 or len(corpus["authentic_documents"]) != 3:
            raise ValueError("expected_two_edition_packet_required")
        config = Config("/workspace/backend/alembic.ini")
        config.set_main_option("script_location", "/workspace/backend/alembic")
        command.upgrade(config, "head")
        seed_units(session, seed_products(session))
        seed_locations(session)
        session.add(
            Source(
                source_id=SOURCE,
                status="active",
                spec={
                    "scope": "isolated authentic historical WB replay; not active collection",
                    "human_reviewed": False,
                },
            )
        )
        session.flush()
        country = session.scalar(
            select(Location).where(Location.pcode == "MDG", Location.admin_level == 0)
        )
        if country is None:
            raise ValueError("verified_country_reference_required")
        alias = normalize_location_string("Market Average")
        if session.get(LocationAlias, alias) is not None:
            raise ValueError("refuse_existing_national_alias_overwrite")
        session.add(
            LocationAlias(
                alias_norm=alias,
                location_id=country.location_id,
                source_id=SOURCE,
                confidence=1,
                origin="ADR163: explicit gid_mdg_national_average; source scoped, human_reviewed=false",
            )
        )
        session.commit()
        artifacts = []
        inventory = {}
        for entry in manifest["entries"]:
            if entry["origin"]["kind"] != "official_acquisition":
                continue
            receipt = json.loads((PACKET / entry["origin"]["reference"]).read_text())
            content = (PACKET / entry["path"]).read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if digest != entry["sha256"] or receipt["source_id"] != SOURCE:
                raise ValueError("packet_original_mismatch")
            extension = "zip" if entry["artifact_type"] == "wb_zip_csv_v1" else "json"
            key = f"{SOURCE}/2026/11/{digest}.{extension}"
            with (COPY / (digest + ".blob")).open("xb") as output:
                output.write(content)
            (COPY / (digest + ".blob")).chmod(0o444)
            inventory[key] = {"sha256": digest, "size_bytes": len(content)}
            identity = uuid4()
            mime = receipt["mime_type"].split(";")[0].strip().lower()
            fetched = datetime.fromisoformat(receipt["fetched_at"])
            session.add(
                SourceRecord(
                    source_record_id=identity,
                    source_id=SOURCE,
                    source_url=receipt["source_url"],
                    object_key=key,
                    content_sha256=digest,
                    mime_type=mime,
                    http_status=200,
                    retrieved_via="direct",
                    fetched_at=fetched,
                    published_at=None,
                    parser_version="3.0.0",
                    extraction_status="pending",
                )
            )
            artifacts.append(
                RawArtifact(str(identity), key, digest, mime, receipt["source_url"], True)
            )
        session.commit()
        # Pre-export the internal, non-institutional reference snapshot. The native
        # archiver subsequently finds these exact bytes and performs no PUT.
        reference = lock_reference_manifest(session)
        key = f"reference_manifest/{datetime.now(UTC):%Y/%m}/{reference.sha256}.json"
        with (COPY / (reference.sha256 + ".blob")).open("xb") as output:
            output.write(reference.content)
        (COPY / (reference.sha256 + ".blob")).chmod(0o444)
        inventory[key] = {"sha256": reference.sha256, "size_bytes": len(reference.content)}
        session.commit()
        with (COPY / "inventory.json").open("x") as output:
            json.dump(
                {"objects": inventory, "scope": "owned filesystem copy, not complete S3 inventory"},
                output,
            )
        (COPY / "inventory.json").chmod(0o444)
        context = next(item for item in artifacts if item.mime_type == "application/json")
        primaries = [item for item in artifacts if item != context]
        # Manifest order is old edition, new edition; original fetched times are
        # preserved in SourceRecord and independently determine rebuild order.
        batches = []
        for index, primary in enumerate(primaries):
            run_id = uuid4()
            session.add(
                IngestionRun(
                    run_id=run_id,
                    source_id=SOURCE,
                    status="running",
                    started_at=datetime.now(UTC),
                    n_fetched=2,
                    n_new_artifacts=2 if index == 0 else 1,
                )
            )
            session.flush()
            from dataclasses import replace

            member_context = replace(context, is_new=index == 0)
            batch = BronzeBatch(SOURCE, run_id, "3.0.0", (primary, member_context))
            persist_bronze_batch(session, batch)
            register_document_partitions(session, batch)
            batches.append(batch)
        session.commit()
    bronze = store()
    connector = WbRtfpMdgConnector()
    run_context = RunContext(source_id=SOURCE, bronze_store=bronze, offline=True)
    stats = [execute_durable_silver(connector, run_context, batch) for batch in batches]
    assert [execute_durable_silver(connector, run_context, batch) for batch in batches] == stats
    with Session(engine) as session:
        require_destination(session)
        rows = list(session.scalars(select(PriceObservation)))
        if len(rows) != 163 or sum(row.superseded_by is not None for row in rows) != 81:
            raise ValueError("expected_authentic_revision_lineage_missing")
        if any(
            row.observed_or_imputed != "imputed" or row.actor_level != "unknown" for row in rows
        ):
            raise ValueError("archive_semantics_changed")
        audit = audit_observation_provenance(session, BronzeProofReader(bronze))
        if not audit.report.passed:
            raise ValueError("archive_stored_cell_audit_failed")
        init_gold_views(session)
        refreshed = refresh_gold_views(session, reader=BronzeProofReader(bronze))
        session.commit()
        write_report(
            "prepared",
            {
                "loaded": True,
                "rows": len(rows),
                "superseded": 81,
                "current": 82,
                "stats": stats,
                "provenance_valid": audit.report.valid,
                "gold": refreshed,
                "corpus": corpus,
                "replay_qualified": False,
            },
        )
    engine.dispose()


def replay() -> None:
    if os.getuid() == 0:
        raise ValueError("nonroot_replay_required")
    require_network_none()
    engine = create_engine(get_settings().database_url)
    with Session(engine) as session:
        require_destination(session)
        result = run_offline_replay(session, store())
        if not result["replay_passed"]:
            write_report("replay-red", result)
            raise ValueError("authentic_archive_replay_diverged")
        result["versioned_recompute"] = versioned_recompute_receipt(session)
        result["genuine_revision_rows"] = session.scalar(
            select(func.count())
            .select_from(PriceObservation)
            .where(PriceObservation.superseded_by.is_not(None))
        )
        result.update(
            available_editions=2,
            complete_r08_qualified=False,
            scope="authentic bounded national c_rice corpus; final gate and false-parser counterproof separate",
        )
        write_report("replayed", result)
    engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "replay"))
    arguments = parser.parse_args()
    {"prepare": prepare, "replay": replay}[arguments.action]()
