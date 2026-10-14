"""Transport regressions with simulated DB/SDK; not source qualification."""

import hashlib
import uuid
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

import pytest

from ketrika.connectors.base import DiscoveredItem, ParseResult, RawArtifact, RunContext
from ketrika.connectors.dummy_csv import DummyCsvConnector
from ketrika.connectors.records import PriceRecord
from ketrika.connectors.registry import _CONNECTOR_REGISTRY, get_connector_class
from ketrika.connectors.runner import execute_connector_pipeline
from ketrika.connectors.stages import (
    BronzeBatch,
    collect_connector_bronze,
    consume_connector_silver,
)
from ketrika.core.bronze import BronzeStore
from ketrika.core.models.db import IngestionRun, SourceRecord
from ketrika.core.policy import OfflineError, PolicyStop
from ketrika.core.qualification import QualificationSafetyError
from ketrika.normalize.price_loader import NormalizedLoad
from ketrika.pipelines.factory import build_source_assets


def fixture():
    content = b"source bytes"
    digest, source_id = hashlib.sha256(content).hexdigest(), "dummy_stages"
    artifact = RawArtifact(
        str(uuid.uuid4()),
        f"{source_id}/2026/10/{digest}.csv",
        digest,
        "text/csv",
        "https://example.invalid/fixture",
        True,
    )
    run = IngestionRun(
        run_id=uuid.uuid4(),
        source_id=source_id,
        started_at=datetime.now(UTC),
        status="running",
        n_fetched=1,
        n_new_artifacts=1,
        n_records=0,
        n_rejected=0,
        n_review=0,
    )
    reference = SourceRecord(
        source_record_id=uuid.UUID(artifact.source_record_id),
        source_id=source_id,
        source_url=artifact.url,
        object_key=artifact.object_key,
        content_sha256=digest,
        mime_type="text/csv",
        parser_version="1.0.0",
    )
    session = MagicMock()
    session.get.side_effect = lambda model, key: run if model is IngestionRun else reference
    connector = MagicMock()
    connector.source_id, connector.parser_version = source_id, "1.0.0"
    connector.parse.return_value = ParseResult(parser_version="1.0.0")
    store = MagicMock(spec=BronzeStore)
    store.bucket, store.client = "test-bucket", MagicMock()
    body = MagicMock()
    body.read.return_value = content
    store.client.get_object.return_value = {"Body": body, "ContentLength": len(content)}
    ctx = RunContext(source_id=source_id, bronze_store=store, http_client=MagicMock())
    batch = BronzeBatch(source_id, run.run_id, "1.0.0", (artifact,))
    return connector, ctx, session, batch, run, reference, content


def test_collection_binds_the_actual_sql_uuid_without_parsing():
    connector, ctx, session, batch, run, reference, _ = fixture()
    run.n_fetched = run.n_new_artifacts = 0
    unbound = replace(batch.artifacts[0], source_record_id=str(uuid.uuid4()))
    connector.discover.return_value = [DiscoveredItem(url=unbound.url)]
    connector.fetch.return_value = unbound
    with (
        patch("ketrika.connectors.stages.get_source", return_value=None),
        patch("ketrika.connectors.runner.ensure_ingestion_run_started", return_value=run),
        patch("ketrika.connectors.runner.record_bronze_artifact", return_value=(reference, True)),
    ):
        result = collect_connector_bronze(connector, ctx, session)
    assert result.artifacts[0].source_record_id == str(reference.source_record_id)
    assert result.ingestion_run_id == run.run_id
    assert ctx.run_id == run.run_id
    assert run.n_fetched == run.n_new_artifacts == 1
    connector.parse.assert_not_called()
    session.commit.assert_not_called()
    with pytest.raises(FrozenInstanceError):
        result.source_id = "other"


@pytest.mark.parametrize("reason", ["disabled", "forbidden"])
def test_registered_policy_stop_precedes_discovery(reason):
    connector, ctx, session, *_ = fixture()
    definition = MagicMock(
        status="disabled" if reason == "disabled" else "active",
        crawl_permission="forbidden" if reason == "forbidden" else "public_open_data",
    )
    with (
        patch("ketrika.connectors.stages.get_source", return_value=definition),
        pytest.raises(PolicyStop, match="source_collection_disabled"),
    ):
        collect_connector_bronze(connector, ctx, session)
    connector.discover.assert_not_called()
    connector.fetch.assert_not_called()
    session.add.assert_not_called()


def test_silver_consumes_verified_bytes_and_does_not_touch_collection_context():
    connector, ctx, session, batch, run, _, content = fixture()
    original_http, original_store = ctx.http_client, ctx.bronze_store
    stats = consume_connector_silver(connector, ctx, session, batch)
    artifact, parse_ctx = connector.parse.call_args.args
    assert artifact == batch.artifacts[0]
    assert parse_ctx.offline is True and parse_ctx.run_id == batch.ingestion_run_id
    assert parse_ctx.bronze_store.get(artifact.object_key) == content
    assert (
        ctx.offline is False
        and ctx.http_client is original_http
        and ctx.bronze_store is original_store
    )
    assert stats == {
        "n_fetched": 1,
        "n_new_artifacts": 1,
        "n_inserted": 0,
        "n_superseded": 0,
        "n_skipped": 0,
        "n_rejected": 0,
    }
    assert run.status == "success"
    connector.discover.assert_not_called()
    connector.fetch.assert_not_called()
    original_http.get.assert_not_called()
    original_store.client.put_object.assert_not_called()
    session.commit.assert_not_called()
    with pytest.raises(OfflineError):
        parse_ctx.http_client.get("https://example.invalid/not-authorized")
    with pytest.raises(ValueError, match="silver_object_outside_batch"):
        parse_ctx.bronze_store.get("another-key")
    with pytest.raises(ValueError, match="silver_bronze_write_forbidden"):
        parse_ctx.bronze_store.put(source_id="other", content=b"x", mime_type="text/plain", url="")


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_id", "other"),
        ("object_key", "different-key"),
        ("content_sha256", "0" * 64),
        ("mime_type", "application/json"),
        ("parser_version", "2.0.0"),
        ("source_url", "https://example.invalid/different"),
        ("published_at", datetime(2026, 10, 10, tzinfo=UTC)),
    ],
)
def test_sql_reference_mismatch_prevents_parse(field, value):
    connector, ctx, session, batch, _, reference, _ = fixture()
    setattr(reference, field, value)
    with pytest.raises(ValueError, match="silver_reference_mismatch"):
        consume_connector_silver(connector, ctx, session, batch)
    connector.parse.assert_not_called()
    ctx.bronze_store.client.get_object.assert_not_called()


def test_altered_object_prevents_parse_without_mutating_store():
    connector, ctx, session, batch, *_ = fixture()
    ctx.bronze_store.client.get_object.return_value["Body"].read.return_value = b"changedbytes"
    with pytest.raises(ValueError, match="silver_object_sha256_mismatch"):
        consume_connector_silver(connector, ctx, session, batch)
    connector.parse.assert_not_called()
    ctx.bronze_store.client.put_object.assert_not_called()
    ctx.bronze_store.client.delete_object.assert_not_called()


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"source_id": "other"}, "silver_batch_source_mismatch"),
        ({"parser_version": "2.0.0"}, "silver_batch_parser_mismatch"),
    ],
)
def test_batch_binding_errors_are_explicit(change, reason):
    connector, ctx, session, batch, *_ = fixture()
    with pytest.raises(ValueError, match=reason):
        consume_connector_silver(connector, ctx, session, replace(batch, **change))
    connector.parse.assert_not_called()


def test_duplicate_receipt_reference_is_not_silently_replayed():
    connector, ctx, session, batch, *_ = fixture()
    with pytest.raises(ValueError, match="silver_batch_duplicate_reference"):
        consume_connector_silver(
            connector, ctx, session, replace(batch, artifacts=batch.artifacts * 2)
        )
    connector.parse.assert_not_called()


@pytest.mark.parametrize("action,reviews", [("inserted", 2), ("idempotent_skipped", 0)])
def test_silver_routes_prices_to_normalization_and_counts_actual_reviews(action, reviews):
    connector, ctx, session, batch, run, *_ = fixture()
    record = PriceRecord(
        product_raw="Synthetic unknown product",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 1),
        price_raw="2850",
        unit_raw="kg",
    )
    connector.parse.return_value = ParseResult(parser_version="1.0.0", records=[record])
    with (
        patch(
            "ketrika.normalize.price_loader.load_normalized_price",
            return_value=NormalizedLoad(action, uuid.uuid4(), reviews),
        ) as normalize,
        patch("ketrika.normalize.reference_snapshot.prepare_reference_snapshot") as prepare,
        patch("ketrika.connectors.runner.load_record_with_supersession") as raw_loader,
    ):
        stats = consume_connector_silver(connector, ctx, session, batch)
    normalize.assert_called_once_with(
        session,
        record,
        batch.source_id,
        uuid.UUID(batch.artifacts[0].source_record_id),
        reference_snapshot=prepare.return_value,
    )
    prepare.assert_called_once_with(session, ctx.bronze_store)
    raw_loader.assert_not_called()
    assert stats["n_review"] == run.n_review == reviews
    assert stats["n_inserted"] == int(action == "inserted")
    assert stats["n_skipped"] == int(action == "idempotent_skipped")
    connector.fetch.assert_not_called()
    session.commit.assert_not_called()


def test_factory_silver_has_a_real_bronze_input_dependency():
    with patch("ketrika.pipelines.factory.get_source", return_value=None):
        bundle = build_source_assets(DummyCsvConnector)
    bronze_key, silver_key = bundle.bronze_asset.key, bundle.silver_asset.key
    assert bronze_key in bundle.silver_asset.asset_deps[silver_key]
    assert bundle.silver_asset.keys_by_input_name["bronze_batch"] == bronze_key


def test_fixture_alias_cannot_resolve_outside_validated_qa():
    with patch(
        "ketrika.core.qualification.validate_environment",
        side_effect=QualificationSafetyError("outside_qa"),
    ):
        assert get_connector_class("fixture_nasa_power_" + "a" * 32) is None


def test_registered_fixture_alias_still_cannot_bypass_qa_guard(monkeypatch):
    source_id = "fixture_nasa_power_" + "a" * 32
    monkeypatch.setitem(_CONNECTOR_REGISTRY, source_id, DummyCsvConnector)
    with patch(
        "ketrika.core.qualification.validate_environment",
        side_effect=QualificationSafetyError("outside_qa"),
    ):
        assert get_connector_class(source_id) is None


def test_unknown_real_source_is_refused_before_discovery():
    connector, ctx, session, *_ = fixture()
    ctx.run_id = uuid.uuid4()
    connector.source_id = ctx.source_id = "unregistered_real_source"
    with (
        patch("ketrika.connectors.stages.get_source", side_effect=KeyError("missing")),
        pytest.raises(PolicyStop, match="source_not_registered"),
    ):
        collect_connector_bronze(connector, ctx, session)
    connector.discover.assert_not_called()
    connector.fetch.assert_not_called()
    assert ctx.run_id is None


def test_collection_failure_keeps_actual_run_identity_and_safe_notification():
    connector, ctx, session, _, run, *_ = fixture()
    ctx.run_id = uuid.uuid4()
    connector.discover.side_effect = RuntimeError("untrusted secret source text")
    with (
        patch("ketrika.connectors.stages.get_source", return_value=None),
        patch("ketrika.connectors.runner.ensure_ingestion_run_started", return_value=run),
        patch("ketrika.connectors.runner.send_pipeline_failure_email") as notify,
        pytest.raises(RuntimeError, match="untrusted secret source text"),
    ):
        execute_connector_pipeline(connector, ctx, session)
    assert ctx.run_id == run.run_id
    assert run.status == "failed" and run.finished_at is not None
    assert run.error == "RuntimeError"
    assert notify.call_args.kwargs["run_id"] == str(run.run_id)
    assert notify.call_args.kwargs["error_message"] == "RuntimeError"
    session.commit.assert_not_called()
    connector.fetch.assert_not_called()


def test_policy_refusal_does_not_mark_a_stale_run_failed():
    connector, ctx, session, _, run, *_ = fixture()
    ctx.run_id = run.run_id
    definition = MagicMock(status="disabled", crawl_permission="public_open_data")
    with (
        patch("ketrika.connectors.stages.get_source", return_value=definition),
        patch("ketrika.connectors.runner.send_pipeline_failure_email") as notify,
        pytest.raises(PolicyStop, match="source_collection_disabled"),
    ):
        execute_connector_pipeline(connector, ctx, session)
    assert ctx.run_id is None and run.status == "running"
    session.get.assert_not_called()
    notify.assert_called_once()
    assert notify.call_args.kwargs["run_id"] == "bronze_collection"


def test_dummy_fixture_collection_requires_actual_qa_environment():
    connector = DummyCsvConnector()
    ctx = RunContext(source_id=connector.source_id)
    with (
        patch("ketrika.connectors.stages.get_source", side_effect=KeyError("missing")),
        patch(
            "ketrika.connectors.stages.validate_environment",
            side_effect=QualificationSafetyError("outside_qa"),
        ),
        pytest.raises(PolicyStop, match="fixture_collection_outside_qa"),
    ):
        collect_connector_bronze(connector, ctx, MagicMock())


@pytest.mark.parametrize("suffix", ["", "a" * 31, "g" * 32, "a" * 33])
def test_invalid_fixture_namespace_is_not_a_connector(suffix):
    with patch("ketrika.core.qualification.validate_environment"):
        assert get_connector_class("fixture_nasa_power_" + suffix) is None
