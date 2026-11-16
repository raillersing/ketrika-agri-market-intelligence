"""Real isolated SQL/S3 and local HTTP; no official live-source qualification."""

import uuid
from decimal import Decimal

import pytest
from dagster import materialize
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from ketrika.connectors.base import DiscoveredItem, RunContext
from ketrika.connectors.dummy_csv import DummyCsvConnector
from ketrika.connectors.stages import collect_connector_bronze, consume_connector_silver
from ketrika.core.bronze import BronzeStore
from ketrika.core.http import PoliteHttpClient
from ketrika.core.models.db import PriceObservation, Source, SourceRecord
from ketrika.core.policy import PolicyEngine
from ketrika.core.provenance_audit import ObservationTarget, audit_observation_provenance
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.core.settings import get_settings
from ketrika.pipelines.factory import build_source_assets
from tests.integration.test_connector_pipeline import CSV_V1, CSV_V2_MODIFIED


@pytest.mark.integration
def test_committed_bronze_replayed_without_http_then_revision_is_append_only(httpserver):
    identifier = f"dummy_stages_{uuid.uuid4().hex}"
    path = f"/{identifier}.csv"
    httpserver.expect_request("/robots.txt").respond_with_data("", status=404)
    httpserver.expect_request(path).respond_with_data(CSV_V1, content_type="text/csv")
    request_count = [0]

    class CountingHttp(PoliteHttpClient):
        def _execute_request(self, *args, **kwargs):
            request_count[0] += 1
            return super()._execute_request(*args, **kwargs)

    policy, store = PolicyEngine(), BronzeStore()
    connector = DummyCsvConnector()
    connector.source_id = identifier
    engine = create_engine(get_settings().database_url)
    try:
        with CountingHttp(policy_engine=policy, allow_loopback=True) as http:
            ctx = RunContext(
                source_id=identifier,
                http_client=http,
                bronze_store=store,
                policy_engine=policy,
                metadata={"csv_url": httpserver.url_for(path)},
            )
            with Session(engine) as session:
                batch = collect_connector_bronze(connector, ctx, session)
                session.commit()
            assert request_count == [2]
            assert len(batch.artifacts) == 1
            with Session(engine) as session:
                stats = consume_connector_silver(connector, ctx, session, batch)
                session.commit()
            assert stats["n_inserted"] == 3 and request_count == [2]
            with Session(engine) as session:
                replay = consume_connector_silver(connector, ctx, session, batch)
                session.commit()
            assert replay["n_inserted"] == 0 and replay["n_skipped"] == 3 and request_count == [2]
            httpserver.clear()
            httpserver.expect_request(path).respond_with_data(
                CSV_V2_MODIFIED, content_type="text/csv"
            )
            with Session(engine) as session:
                revision = collect_connector_bronze(connector, ctx, session)
                session.commit()
            assert request_count == [3]
            assert revision.ingestion_run_id != batch.ingestion_run_id
            assert revision.artifacts[0].source_record_id != batch.artifacts[0].source_record_id
            with Session(engine) as session:
                updated = consume_connector_silver(connector, ctx, session, revision)
                session.commit()
            assert (
                updated["n_superseded"] == 1 and updated["n_skipped"] == 2 and request_count == [3]
            )
        with Session(engine) as session:
            rows = session.scalars(
                select(PriceObservation)
                .join(SourceRecord)
                .where(SourceRecord.source_id == identifier)
            ).all()
            assert len(rows) == 4
            assert sum(row.superseded_by is None for row in rows) == 3
            current_rice = next(
                row
                for row in rows
                if row.location_raw == "Antananarivo" and row.superseded_by is None
            )
            assert str(current_rice.price_value) == "2900.0000"
            assert current_rice.price_mga_per_base == Decimal("2900.0000")
            assert current_rice.base_unit == "kg"
            assert current_rice.review_status == "accepted"
            assert current_rice.currency_raw == "MGA" and current_rice.unit_raw == "kg"
            assert current_rice.evidence["normalization"]["version"] == 2
            assert current_rice.evidence["normalization"]["human_reviewed"] is False
            targets = [ObservationTarget("price_observation", row.observation_id) for row in rows]
            receipt = audit_observation_provenance(
                session, BronzeProofReader(store), mode="incremental", targets=targets
            )
            # The connector uses an explicitly synthetic test source: its raw
            # objects remain replayable, but none may qualify for Gold.
            assert receipt.report.total == 4
            assert receipt.report.valid == 0
            assert all(
                result.reason == "synthetic_source_record_forbidden"
                for result in receipt.report.results
            )
            assert receipt.report.objects_read == 0
            session.commit()
    finally:
        engine.dispose()


@pytest.mark.integration
def test_dagster_materializes_real_bronze_input_once_and_silver_rows(httpserver, monkeypatch):
    monkeypatch.setattr(
        "ketrika.pipelines.factory.PoliteHttpClient",
        lambda **kwargs: PoliteHttpClient(**kwargs, allow_loopback=True),
    )
    identifier = f"dummy_dagster_{uuid.uuid4().hex}"
    path = f"/{identifier}.csv"
    httpserver.expect_request("/robots.txt").respond_with_data("", status=404)
    httpserver.expect_request(path).respond_with_data(CSV_V1, content_type="text/csv")
    discoveries = [0]

    class LocalCsv(DummyCsvConnector):
        source_id = identifier

        def discover(self, ctx):
            discoveries[0] += 1
            yield DiscoveredItem(url=httpserver.url_for(path), partition_key="fixture")

    bundle = build_source_assets(LocalCsv)
    setup_engine = create_engine(get_settings().database_url)
    try:
        with Session(setup_engine) as session:
            target = session.get_bind().engine.url
            require_synthetic_test_database(target.host, target.database)
            session.add(
                Source(
                    source_id=identifier,
                    spec={"dataset_mode": "test", "authenticity": "synthetic", "verified": False},
                    status="active",
                )
            )
            session.commit()
    finally:
        setup_engine.dispose()
    result = materialize([bundle.bronze_asset, bundle.silver_asset], raise_on_error=True)
    assert result.success and discoveries == [1]
    silver = result.output_for_node(f"{identifier}__silver")
    assert silver["n_fetched"] == 1 and silver["n_inserted"] == 3
    engine = create_engine(get_settings().database_url)
    try:
        with Session(engine) as session:
            count = session.scalar(
                select(func.count())
                .select_from(PriceObservation)
                .join(SourceRecord)
                .where(SourceRecord.source_id == identifier)
            )
            assert count == 3
    finally:
        engine.dispose()
