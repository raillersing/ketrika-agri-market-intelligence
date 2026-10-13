"""Real partitioned Dagster execution over isolated persisted SQL/S3."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from dagster import DagsterInstance, materialize
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from ketrika.connectors.base import RawArtifact
from ketrika.connectors.document_partitions import document_key, read_document_partition
from ketrika.connectors.dummy_csv import DummyCsvConnector
from ketrika.connectors.durable_phases import execute_durable_bronze, replay_document_silver
from ketrika.connectors.registry import _CONNECTOR_REGISTRY
from ketrika.core.db import get_session
from ketrika.core.models.db import PriceObservation, Product, ProductAlias, SourceRecord
from ketrika.pipelines.factory import build_document_replay_job, build_source_assets
from tests.integration import test_silver_recovery as recovery_module
from tests.integration.test_connector_pipeline import CSV_V2_MODIFIED

recovery_case = recovery_module.recovery_case


@pytest.mark.integration
def test_actual_partitioned_job_replays_without_bronze_and_retry_is_idempotent(recovery_case):
    connector, ctx, batch, calls = recovery_case
    key = document_key(batch, batch.artifacts[0])
    job = build_document_replay_job(type(connector))
    with DagsterInstance.ephemeral() as instance:
        instance.add_dynamic_partitions(f"{batch.source_id}__document_versions", [key])
        first = job.execute_in_process(instance=instance, partition_key=key)
        second = job.execute_in_process(instance=instance, partition_key=key)
    assert first.success and second.success
    assert first.output_for_node(f"{batch.source_id}__replay_recorded_document")["n_inserted"] == 3
    retried = second.output_for_node(f"{batch.source_id}__replay_recorded_document")
    assert retried["n_inserted"] == 0 and retried["n_skipped"] == 3
    assert calls == {"fetch": 1, "parse": 2}
    with get_session() as session:
        rows = session.execute(
            text(
                "SELECT a.resumed_from,i.partition_key,i.dagster_run_id,r.status "
                "FROM meta.silver_attempt a JOIN meta.ingestion_run i USING(run_id) "
                "JOIN meta.silver_attempt_result r USING(attempt_id) WHERE a.document_key=:key"
            ),
            {"key": key},
        ).all()
        assert len(rows) == 2
        assert {row.dagster_run_id for row in rows} == {first.run_id, second.run_id}
        assert all(
            row.resumed_from == batch.ingestion_run_id
            and row.partition_key == key
            and row.status == "success"
            for row in rows
        )
        identities = session.execute(
            text(
                "SELECT m.processing_key,m.reference_manifest_sha256 "
                "FROM meta.silver_attempt_member m JOIN meta.silver_attempt a USING(attempt_id) "
                "WHERE a.document_key=:key"
            ),
            {"key": key},
        ).all()
        assert len(identities) == 2 and identities[0] == identities[1]


@pytest.mark.integration
def test_changed_configuration_changes_processing_identity_without_changing_document(recovery_case):
    connector, ctx, batch, _ = recovery_case
    key = document_key(batch, batch.artifacts[0])
    assert replay_document_silver(connector, ctx, key)["n_inserted"] == 3
    with get_session() as session:
        product = session.scalar(select(Product).order_by(Product.product_id).limit(1))
        assert product is not None
        alias = "synthetic_reference_" + uuid4().hex
        session.add(
            ProductAlias(
                alias_id=uuid4(),
                alias_norm=alias,
                alias_display=alias,
                lang="fr",
                product_id=product.product_id,
                source_id=batch.source_id,
                confidence=Decimal("1.00"),
                origin="synthetic_test",
                human_reviewed=False,
            )
        )
    assert replay_document_silver(connector, ctx, key)["n_superseded"] == 3
    with get_session() as session:
        identities = session.execute(
            text(
                "SELECT m.processing_key,m.reference_manifest_sha256 "
                "FROM meta.silver_attempt_member m JOIN meta.silver_attempt a USING(attempt_id) "
                "WHERE a.document_key=:key"
            ),
            {"key": key},
        ).all()
        assert len(identities) == 2
        assert identities[0].processing_key != identities[1].processing_key
        assert identities[0].reference_manifest_sha256 != identities[1].reference_manifest_sha256
        assert read_document_partition(session, key, batch.source_id)[0] == batch


@pytest.mark.integration
def test_native_bronze_registers_real_dynamic_partition_keys_after_commit(recovery_case):
    connector, _, _, calls = recovery_case
    bundle = build_source_assets(type(connector))
    with DagsterInstance.ephemeral() as instance:
        result = materialize([bundle.bronze_asset], instance=instance)
        assert result.success
        batch = result.output_for_node(f"{connector.source_id}__bronze")
        keys = instance.get_dynamic_partitions(f"{connector.source_id}__document_versions")
        assert keys == [document_key(batch, batch.artifacts[0])]
        with get_session() as session:
            origin, member = read_document_partition(session, keys[0], batch.source_id)
            # The first ledger remains the origin for the same exact document.
            assert member.source_record_id == batch.artifacts[0].source_record_id
            assert origin.source_id == batch.source_id
    assert calls == {"fetch": 2, "parse": 0}


@pytest.mark.integration
def test_revised_document_new_partition_supersedes_only_changed_price(recovery_case, monkeypatch):
    connector, ctx, first_batch, calls = recovery_case
    first_key = document_key(first_batch, first_batch.artifacts[0])
    assert replay_document_silver(connector, ctx, first_key)["n_inserted"] == 3
    archived = ctx.bronze_store.put(
        source_id=first_batch.source_id,
        content=CSV_V2_MODIFIED.encode(),
        mime_type="text/csv",
        url=first_batch.artifacts[0].url,
        retrieved_via="manual_upload",
        fetched_at=datetime.now(UTC),
        http_status=0,
        http_headers={"x-ketrika-dataset": "synthetic;verified=false"},
    )
    raw = RawArtifact(
        str(uuid4()),
        archived.object_key,
        archived.content_sha256,
        "text/csv",
        archived.url,
        archived.is_new,
    )

    class Revised(DummyCsvConnector):
        source_id = first_batch.source_id

        def discover(self, context):
            yield from connector.discover(context)

        def parse(self, artifact, context):
            return connector.parse(artifact, context)

        def fetch(self, item, context):
            calls["fetch"] += 1
            return raw

    monkeypatch.setitem(_CONNECTOR_REGISTRY, first_batch.source_id, Revised)
    revised = Revised()
    second_batch = execute_durable_bronze(revised, ctx)
    second_key = document_key(second_batch, second_batch.artifacts[0])
    assert second_key != first_key
    result = replay_document_silver(revised, ctx, second_key)
    assert result["n_superseded"] == 1 and result["n_skipped"] == 2
    assert calls["fetch"] == 2
    with get_session() as session:
        observations = session.scalars(
            select(PriceObservation)
            .join(SourceRecord)
            .where(SourceRecord.source_id == first_batch.source_id)
        ).all()
        assert len(observations) == 4
        old = next(row for row in observations if row.price_raw == "2800")
        new = next(row for row in observations if row.price_raw == "2900")
        assert old.superseded_by == new.observation_id and new.superseded_by is None
        assert read_document_partition(session, first_key, first_batch.source_id)[0] == first_batch


@pytest.mark.integration
def test_other_source_cannot_replay_a_partition(recovery_case):
    _, _, batch, _ = recovery_case
    key = document_key(batch, batch.artifacts[0])
    with get_session() as session:
        with pytest.raises(ValueError, match="document_partition_source_mismatch"):
            read_document_partition(session, key, "dummy_other_source")


@pytest.mark.integration
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
def test_document_partition_sql_history_is_immutable(recovery_case, operation):
    _, _, batch, _ = recovery_case
    key = document_key(batch, batch.artifacts[0])
    statement = (
        "UPDATE meta.document_partition SET partition_key=partition_key WHERE partition_key=:key"
        if operation == "UPDATE"
        else "DELETE FROM meta.document_partition WHERE partition_key=:key"
    )
    with pytest.raises(DBAPIError) as captured:
        with get_session() as session:
            session.execute(text(statement), {"key": key})
    assert captured.value.orig.sqlstate == "55000"
    with get_session() as session:
        assert read_document_partition(session, key, batch.source_id)[0] == batch
