"""Explicitly synthetic smoke on a new, network-none, Unix-socket-only database.

Never used by qualify, never seeds an authentic qualification, never resets a DB.
prepare and replay are different containers; the latter mounts /copy readonly.
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from alembic import command
from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.dummy_csv import DummyCsvConnector
from ketrika.connectors.runner import load_record_with_supersession
from ketrika.core import schema_contracts
from ketrika.core.bronze import BronzeStore
from ketrika.core.models.db import Base, Source, SourceRecord
from ketrika.core.qualification_reports import load_json_report
from ketrika.core.rebuild_bronze import LocalBronzeClient
from ketrika.core.schema_audit import CSVSchemaContract
from ketrika.core.schema_contracts import SchemaContractBinding, SchemaContractRegistry
from ketrika.core.settings import get_settings
from ketrika.gold.refresh import init_gold_views, refresh_gold_views
from ketrika.normalize.loader import seed_locations, seed_products, seed_units
from ketrika.pipelines.rebuild_qualification import (
    RebuildSafetyError,
    require_destination,
    require_network_none,
    run_offline_replay,
    versioned_recompute_receipt,
)

SOURCE = "dummy_offline_qualification"
COLUMNS = (
    "product",
    "market",
    "actor_level",
    "period_start",
    "period_end",
    "price",
    "unit",
    "currency",
)


def declare_synthetic_schema() -> None:
    schema_contracts.DEFAULT_SCHEMA_CONTRACT_REGISTRY = SchemaContractRegistry(
        (
            SchemaContractBinding(
                SOURCE,
                DummyCsvConnector.parser_version,
                "text/csv",
                CSVSchemaContract("synthetic-v1", COLUMNS),
            ),
        )
    )


def local_store() -> BronzeStore:
    inventory = load_json_report(Path("/copy/inventory.json"))
    return BronzeStore(
        bucket_name="synthetic-offline-copy",
        client=LocalBronzeClient(Path("/copy"), "synthetic-offline-copy", inventory["objects"]),
    )


def prepare(session: Session) -> None:
    # Refuse reinitialization, even on this dedicated destination. No TRUNCATE/restore.
    existing = session.execute(text("SELECT to_regclass('meta.source_record')")).scalar()
    if Path("/copy/inventory.json").exists():
        raise RebuildSafetyError("synthetic_smoke_destination_already_initialized")
    if existing is not None:
        # Resume a schema-only interrupted first setup, never clear existing rows.
        protected = sorted(
            name
            for name, table in Base.metadata.tables.items()
            if table.schema in {"ref", "obs", "ml", "meta"}
        )
        if any(
            session.execute(text("SELECT count(*) FROM " + name)).scalar() for name in protected
        ):
            raise RebuildSafetyError("synthetic_smoke_destination_already_initialized")
    session.rollback()
    configuration = Config("/workspace/backend/alembic.ini")
    configuration.set_main_option("script_location", "/workspace/backend/alembic")
    command.upgrade(configuration, "head")
    product_map = seed_products(session)
    seed_units(session, product_map)
    seed_locations(session)
    session.add(
        Source(
            source_id=SOURCE,
            status="active",
            spec={
                "name": "Synthetic offline software smoke",
                "priority": "P0",
                "freshness_sla_days": 30,
            },
        )
    )
    session.flush()
    objects = {}
    records = []
    Path("/copy").mkdir(exist_ok=True)
    reports = Path("/reports/runs")
    reports.mkdir(exist_ok=True)
    reports.chmod(0o1777)  # Dedicated public-fixture report volume only; worker is non-root.
    for day, price in ((1, "2800"), (2, "2900")):
        content = (
            ",".join(COLUMNS)
            + "\n"
            + f"Riz blanc local,Antananarivo,retail,2025-01-01,2025-01-31,{price},kg,MGA\n"
        ).encode()
        digest = hashlib.sha256(content).hexdigest()
        key = f"{SOURCE}/2025/01/{digest}.csv"
        with (Path("/copy") / (digest + ".blob")).open("xb") as stream:
            stream.write(content)
        objects[key] = {"sha256": digest, "size_bytes": len(content)}
        record = SourceRecord(
            source_record_id=uuid4(),
            source_id=SOURCE,
            source_url="",
            retrieved_via="manual_upload",
            object_key=key,
            content_sha256=digest,
            mime_type="text/csv",
            http_status=0,
            fetched_at=datetime(2025, 1, day, tzinfo=UTC),
            parser_version=DummyCsvConnector.parser_version,
            extraction_status="parsed",
        )
        session.add(record)
        records.append(record)
    session.flush()
    with Path("/copy/inventory.json").open("x") as stream:
        json.dump({"dataset": "synthetic", "objects": objects}, stream)
    store = local_store()
    connector = DummyCsvConnector()
    context = RunContext(source_id=SOURCE, bronze_store=store, offline=True)
    for descriptor in records:
        artifact = RawArtifact(
            source_record_id=str(descriptor.source_record_id),
            object_key=descriptor.object_key,
            content_sha256=descriptor.content_sha256,
            mime_type="text/csv",
            url="",
            is_new=False,
        )
        for parsed in connector.parse(artifact, context).records:
            load_record_with_supersession(session, parsed, SOURCE, descriptor.source_record_id)
    init_gold_views(session)
    from ketrika.core.provenance_bronze import BronzeProofReader

    refresh_gold_views(session, reader=BronzeProofReader(store))
    session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "replay"))
    action = parser.parse_args().action
    require_network_none()
    engine = create_engine(get_settings().database_url)
    declare_synthetic_schema()
    with Session(engine) as session:
        require_destination(session)
        if action == "prepare":
            prepare(session)
            print(json.dumps({"dataset": "synthetic", "prepared": True, "qualification": False}))
        else:
            source_ids = set(session.scalars(select(SourceRecord.source_id)))
            if source_ids != {SOURCE}:
                raise RebuildSafetyError("synthetic_smoke_contains_foreign_source")
            # Post-upgrade Gold definitions may be recreated empty; repopulate
            # the prepared clone before capture, like the authentic preview worker.
            store = local_store()
            init_gold_views(session)
            from ketrika.core.provenance_bronze import BronzeProofReader

            refresh_gold_views(session, reader=BronzeProofReader(store))
            session.commit()
            result = run_offline_replay(session, store)
            result["dataset"] = "synthetic"
            receipt = versioned_recompute_receipt(session, min_points=1)
            result["versioned_recompute"] = receipt
            result["forecasts_recomputed"] = receipt["forecasts_recomputed"]
            output = Path("/reports/runs") / uuid4().hex
            output.mkdir(exist_ok=False)
            (output / "replay.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
            print(
                json.dumps(
                    {
                        "report": str(output / "replay.json"),
                        "replay_passed": result["replay_passed"],
                        "status": "PARTIAL",
                        "dataset": "synthetic",
                    }
                )
            )
            if not result["replay_passed"]:
                raise SystemExit(1)
    engine.dispose()


if __name__ == "__main__":
    main()
