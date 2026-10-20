"""Prepared real SQL/Bronze Gold gate; never run concurrently with main check."""

import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from dagster import Definitions, asset
from sqlalchemy import event, text

from ketrika.connectors.dummy_csv import DummyCsvConnector
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_engine, get_session
from ketrika.core.models.db import DqResult, Location, Product, Source, SourceRecord
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.core.schema_audit import CSVSchemaContract
from ketrika.gold.refresh import init_gold_views, refresh_gold_views
from ketrika.pipelines.factory import build_gold_refresh_asset, build_source_assets
from ketrika.pipelines.rebuild import wipe_silver_gold_tables
from tests.e2e_data.schema_declarations import declare_synthetic_contract
from tests.integration.test_gold_publication_provenance import DamagedMemoryReader
from tests.unit.test_provenance_audit import price_example


def gold_signature(session):
    return session.execute(
        text(
            "SELECT count(*), md5(coalesce(string_agg(to_jsonb(p)::text, ',' "
            "ORDER BY observation_id), '')) FROM gold.price_obs_current p"
        )
    ).one()


@pytest.mark.integration
@pytest.mark.parametrize("damaged", [False, True], ids=["valid", "damaged-in-memory"])
def test_production_check_controls_actual_gold_sql(damaged, monkeypatch, request):
    source_id = f"dummy_actual_gold_{uuid4().hex}"
    observation, original = price_example()
    columns = ("price_value", "product_raw", "period_start", "unit_raw", "currency_raw")
    contract = CSVSchemaContract("synthetic-flat-price-v1", columns)
    declare_synthetic_contract(source_id, "1.0.0", "text/csv", contract)
    values = json.loads(original)[0]
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(columns)
    writer.writerow([values[field] for field in columns])
    content = output.getvalue().encode("utf-8")
    observation.evidence = {
        "provenance": {
            "version": 1,
            "format": "csv",
            "row": 0,
            "delimiter": ",",
            "cells": [
                {
                    "field": field,
                    "column": field,
                    "role": "value" if field == "price_value" else "identity",
                    "kind": "number" if field == "price_value" else "text",
                }
                for field in columns
            ],
        }
    }
    store = BronzeStore()
    with get_session() as session:
        target = session.get_bind().engine.url
        require_synthetic_test_database(target.host, target.database)
        assert store.bucket == "ketrika-qa-bronze"
        wipe_silver_gold_tables(session)
        product = Product(
            product_id=uuid4(),
            product_code=f"fixture_actual_gold_{uuid4().hex}",
            canonical_name_fr="Synthetic rice",
            category="cereal",
            base_unit="kg",
            verified=False,
        )
        location = Location(
            location_id=uuid4(),
            pcode=None,
            name="Synthetic place",
            admin_level=9,
            boundary_version="synthetic;verified=false",
        )
        session.add_all(
            [
                Source(
                    source_id=source_id,
                    status="disabled",
                    spec={"priority": "P1", "dataset": "synthetic", "verified": False},
                ),
                product,
                location,
            ]
        )
        session.flush()
        artifact = store.put(
            source_id=source_id,
            content=content,
            mime_type="text/csv",
            url="https://example.invalid/synthetic-actual-gold",
            retrieved_via="manual_upload",
            fetched_at=datetime.now(UTC),
            http_status=0,
            http_headers={"x-ketrika-dataset": "synthetic;verified=false"},
        )
        session.add(
            SourceRecord(
                source_record_id=observation.source_record_id,
                source_id=source_id,
                source_url="https://example.invalid/synthetic-actual-gold",
                object_key=artifact.object_key,
                content_sha256=artifact.content_sha256,
                mime_type="text/csv",
                retrieved_via="manual_upload",
                fetched_at=datetime.now(UTC),
                parser_version="1.0.0",
                extraction_status="parsed",
            )
        )
        session.flush()
        observation.product_id = product.product_id
        observation.location_id = location.location_id
        observation.price_mga_per_base = Decimal("3000.1250")
        observation.review_status = "accepted"
        session.add(observation)
        session.flush()
        init_gold_views(session)
        baseline_refresh = refresh_gold_views(session)
        assert baseline_refresh["source_observations_valid"] == 1
        assert baseline_refresh["source_observations_total"] == 1
        baseline = gold_signature(session)
        assert baseline[0] == 1

    reader = BronzeProofReader(store)
    original_sha = hashlib.sha256(reader.get(artifact.object_key)).hexdigest()
    assert original_sha == artifact.content_sha256
    if damaged:
        simulated = DamagedMemoryReader(reader, artifact.object_key)
        monkeypatch.setattr("ketrika.pipelines.factory.BronzeProofReader", lambda _: simulated)
    connector = type("LocalActualGold", (DummyCsvConnector,), {"source_id": source_id})
    bundle = build_source_assets(connector)

    @asset(name=f"{source_id}__silver")
    def existing_silver():
        return {"scope": "existing synthetic SQL rows; no collection or parse"}

    gold = build_gold_refresh_asset([existing_silver])
    statements = []

    def capture_sql(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("REFRESH MATERIALIZED VIEW gold."):
            statements.append(statement)

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", capture_sql)
    try:
        definitions = Definitions(assets=[existing_silver, gold], asset_checks=bundle.checks)
        result = definitions.resolve_implicit_global_asset_job_def().execute_in_process(
            raise_on_error=False
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture_sql)
    assert result.success is (not damaged)
    assert len(statements) == (0 if damaged else 13)
    assert all("economic_dashboard" not in statement for statement in statements)
    evaluations = result.get_asset_check_evaluations()
    assert len(evaluations) == 2
    provenance = next(
        item for item in evaluations if item.check_name.endswith("__provenance_complete")
    )
    structure = next(item for item in evaluations if item.check_name.endswith("__schema_drift"))
    assert provenance.passed is (not damaged) and structure.passed
    dq_id = UUID(provenance.metadata["dq_id"].value)
    with get_session() as session:
        saved = session.get(DqResult, dq_id)
        assert saved is not None and saved.passed is (not damaged)
        assert saved.details["total_records"] == 1
        assert saved.details["valid_provenance"] == int(not damaged)
        schema_dq = session.get(DqResult, UUID(structure.metadata["dq_id"].value))
        assert schema_dq is not None and schema_dq.passed
        assert schema_dq.details["total_artifacts"] == 1
        assert schema_dq.details["valid_schema_artifacts"] == 1
        assert gold_signature(session) == baseline
    assert hashlib.sha256(reader.get(artifact.object_key)).hexdigest() == original_sha
    request.node.user_properties.append(
        (
            "ketrika.connected_gold",
            json.dumps(
                {
                    "damaged_in_memory_only": damaged,
                    "gold_sql_refresh_count": len(statements),
                    "source_check_total": 1,
                    "source_check_valid": int(not damaged),
                    "dq_id": str(dq_id),
                    "schema_check_passed": True,
                    "gold_signature_unchanged": True,
                    "bronze_sha_unchanged": True,
                    "scope": "synthetic SQL/Bronze; production check and refresh; inert Silver; no economic qualification",
                }
            ),
        )
    )
