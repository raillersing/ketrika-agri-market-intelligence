"""Prepared SQL/S3 ownership cases; fixture fetch returns preexisting Bronze."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from dagster import materialize
from sqlalchemy import func, select, text

from ketrika.connectors.base import DiscoveredItem, RawArtifact, RunContext
from ketrika.connectors.dummy_csv import DummyCsvConnector
from ketrika.connectors.durable_phases import (
    DurablePhaseFailure,
    execute_durable_bronze,
    execute_durable_silver,
)
from ketrika.connectors.registry import _CONNECTOR_REGISTRY
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.models.db import IngestionRun, PriceObservation, Source, SourceRecord
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.pipelines.factory import build_source_assets
from tests.integration.test_connector_pipeline import CSV_V1


def signature(session):
    return session.execute(
        text(
            "SELECT count(*), md5(coalesce(string_agg(to_jsonb(p)::text, ',' "
            "ORDER BY observation_id), '')) FROM obs.price_observation p"
        )
    ).one()


@pytest.mark.integration
@pytest.mark.parametrize("entrypoint", ["owners", "native_assets"])
@pytest.mark.parametrize(
    "failure", ["bronze_after_artifact", "silver_parse", "silver_after_insert", "none"]
)
def test_real_phase_rollback_and_independent_failure(failure, entrypoint, monkeypatch, request):
    identifier = f"dummy_durable_phase_{uuid4().hex}"
    with get_session() as session:
        target = session.get_bind().engine.url
        require_synthetic_test_database(target.host, target.database)
        session.add(
            Source(
                source_id=identifier,
                status="disabled",
                spec={
                    "dataset": "synthetic",
                    "verified": False,
                    "scope": "preexisting test Bronze, no HTTP acquisition",
                },
            )
        )
        before = signature(session)
    store = BronzeStore()
    assert store.bucket == "ketrika-qa-bronze"
    artifact = store.put(
        source_id=identifier,
        content=CSV_V1.encode(),
        mime_type="text/csv",
        url="https://example.invalid/synthetic-phase",
        retrieved_via="manual_upload",
        fetched_at=datetime.now(UTC),
        http_status=0,
        http_headers={"x-ketrika-dataset": "synthetic; verified=false"},
    )
    raw = RawArtifact(
        str(uuid4()),
        artifact.object_key,
        artifact.content_sha256,
        "text/csv",
        artifact.url,
        artifact.is_new,
    )
    fetch_calls = []

    class FixtureConnector(DummyCsvConnector):
        source_id = identifier

        def discover(self, ctx):
            yield DiscoveredItem(url=raw.url)
            if failure == "bronze_after_artifact":
                raise RuntimeError("UNTRUSTED_SOURCE_RUN_TOOL_NOW")

        def fetch(self, item, ctx):
            fetch_calls.append("preexisting_fixture")
            return raw

        def parse(self, artifact, ctx):
            if failure == "silver_parse":
                raise RuntimeError("UNTRUSTED_SOURCE_RUN_TOOL_NOW")
            return super().parse(artifact, ctx)

    monkeypatch.setitem(_CONNECTOR_REGISTRY, identifier, FixtureConnector)
    connector = FixtureConnector()
    context = RunContext(
        source_id=identifier, bronze_store=store, metadata={"dagster_run_id": str(uuid4())}
    )
    if failure == "silver_after_insert":
        from ketrika.normalize.price_loader import load_normalized_price

        def load_then_fail(session, *args, **kwargs):
            loaded = load_normalized_price(session, *args, **kwargs)
            assert loaded.action == "inserted"
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(PriceObservation)
                    .join(SourceRecord)
                    .where(SourceRecord.source_id == identifier)
                )
                == 1
            )
            raise RuntimeError("UNTRUSTED_SOURCE_RUN_TOOL_NOW")

        monkeypatch.setattr("ketrika.normalize.price_loader.load_normalized_price", load_then_fail)

    if entrypoint == "native_assets":
        bundle = build_source_assets(FixtureConnector)
        result = materialize([bundle.bronze_asset, bundle.silver_asset], raise_on_error=False)
        assert result.success is (failure == "none")
        context.metadata["dagster_run_id"] = result.run_id
        if failure == "none":
            assert result.output_for_node(f"{identifier}__silver")["n_inserted"] == 3
        else:
            failures = [event for event in result.all_events if event.is_step_failure]
            assert failures
            for event in failures:
                assert "UNTRUSTED_SOURCE" not in event.event_specific_data.error.to_string()
    elif failure == "bronze_after_artifact":
        with pytest.raises(DurablePhaseFailure, match="^bronze:RuntimeError$"):
            execute_durable_bronze(connector, context)
    else:
        batch = execute_durable_bronze(connector, context)
        assert len(batch.artifacts) == 1
        with get_session() as session:
            started = session.get(IngestionRun, batch.ingestion_run_id)
            assert started is not None and started.status == "running" and started.n_fetched == 1
        if failure == "none":
            stats = execute_durable_silver(connector, context, batch)
            assert stats["n_inserted"] == 3
        else:
            with pytest.raises(DurablePhaseFailure, match="^silver:RuntimeError$"):
                execute_durable_silver(connector, context, batch)
    assert fetch_calls == ["preexisting_fixture"]
    with get_session() as session:
        run = session.scalar(select(IngestionRun).where(IngestionRun.source_id == identifier))
        assert run is not None and run.finished_at is not None
        assert run.dagster_run_id == context.metadata["dagster_run_id"]
        assert run.status == ("success" if failure == "none" else "failed")
        if failure == "none":
            assert run.error is None
        else:
            assert run.error == "RuntimeError"
        records = session.scalar(
            select(func.count())
            .select_from(SourceRecord)
            .where(SourceRecord.source_id == identifier)
        )
        prices = session.scalar(
            select(func.count())
            .select_from(PriceObservation)
            .join(SourceRecord)
            .where(SourceRecord.source_id == identifier)
        )
        assert records == (0 if failure == "bronze_after_artifact" else 1)
        assert prices == (3 if failure == "none" else 0)
        assert run.n_fetched == (0 if failure == "bronze_after_artifact" else 1)
        assert run.n_records == (3 if failure == "none" else 0)
        if failure != "none":
            assert signature(session) == before
        run_id = str(run.run_id)
    assert (
        hashlib.sha256(BronzeStore().get(artifact.object_key)).hexdigest()
        == artifact.content_sha256
    )
    request.node.user_properties.append(
        (
            "ketrika.durable_phase",
            json.dumps(
                {
                    "variant": failure,
                    "entrypoint": entrypoint,
                    "run_id": run_id,
                    "source_records": records,
                    "prices": prices,
                    "scope": "synthetic SQL/S3 ownership, no HTTP acquisition or live-source qualification",
                }
            ),
        )
    )
