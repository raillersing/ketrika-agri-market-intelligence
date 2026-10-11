"""Prepared CSV structure gate over real SQL/S3; no concurrent main check."""

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
from ketrika.core.schema_audit import CSVSchemaContract, SchemaContract
from ketrika.core.schema_json import JSONSchemaContract, JSONShape
from ketrika.gold.refresh import init_gold_views
from ketrika.pipelines.factory import build_gold_refresh_asset, build_source_assets
from ketrika.pipelines.rebuild import wipe_silver_gold_tables
from tests.unit.test_provenance_audit import price_example

COLUMNS = ("price_value", "product_raw", "period_start", "unit_raw", "currency_raw")
CONTRACT = CSVSchemaContract("synthetic-flat-price-v1", COLUMNS)
JSON_CONTRACT = JSONSchemaContract(
    "synthetic-flat-price-json-v1",
    JSONShape(
        "array",
        items=JSONShape(
            "object", properties=tuple((field, JSONShape("string"), True) for field in COLUMNS)
        ),
    ),
)


@pytest.mark.integration
@pytest.mark.parametrize("format_id", ["csv", "json"])
@pytest.mark.parametrize("drift", [False, True], ids=["known-columns", "unexpected-column"])
def test_explicit_structure_blocks_actual_gold_refresh(drift, format_id, request):
    source_id = f"dummy_schema_gold_{uuid4().hex}"
    observation, original = price_example()
    values = json.loads(original)[0]
    header = list(COLUMNS) + (["unexpected_tool"] if drift else [])
    cells = [values[field] for field in COLUMNS] + (["RUN_TOOL_NOW"] if drift else [])
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(header)
    writer.writerow(cells)
    content = output.getvalue().encode("utf-8")
    csv_evidence = {
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
                for field in COLUMNS
            ],
        }
    }
    contract: SchemaContract
    if format_id == "csv":
        observation.evidence = csv_evidence
        contract, mime = CONTRACT, "text/csv"
    else:
        if drift:
            values["unexpected_tool"] = "RUN_TOOL_NOW"
        content = json.dumps([values]).encode("utf-8")
        contract, mime = JSON_CONTRACT, "application/json"
    store = BronzeStore()
    with get_session() as session:
        target = session.get_bind().engine.url
        require_synthetic_test_database(target.host, target.database)
        assert store.bucket == "ketrika-qa-bronze"
        wipe_silver_gold_tables(session)
        product = Product(
            product_id=uuid4(),
            product_code=f"fixture_schema_{uuid4().hex}",
            canonical_name_fr="Synthetic rice",
            category="cereal",
            base_unit="kg",
            verified=False,
        )
        location = Location(
            location_id=uuid4(),
            name="Synthetic place",
            admin_level=9,
            pcode=None,
            boundary_version="synthetic;verified=false",
        )
        session.add_all(
            [
                Source(
                    source_id=source_id,
                    status="disabled",
                    spec={"priority": "P1", "verified": False, "dataset": "synthetic"},
                ),
                product,
                location,
            ]
        )
        session.flush()
        artifact = store.put(
            source_id=source_id,
            content=content,
            mime_type=mime,
            url="https://example.invalid/synthetic-schema-gold",
            retrieved_via="manual_upload",
            fetched_at=datetime.now(UTC),
            http_status=0,
            http_headers={"x-ketrika-dataset": "synthetic;verified=false"},
        )
        session.add(
            SourceRecord(
                source_record_id=observation.source_record_id,
                source_id=source_id,
                source_url="https://example.invalid/synthetic-schema-gold",
                object_key=artifact.object_key,
                content_sha256=artifact.content_sha256,
                mime_type=mime,
                retrieved_via="manual_upload",
                fetched_at=datetime.now(UTC),
                parser_version="1.0.1",
                extraction_status="parsed",
            )
        )
        session.flush()
        observation.product_id, observation.location_id = product.product_id, location.location_id
        observation.price_mga_per_base = Decimal("3000.1250")
        observation.review_status = "accepted"
        session.add(observation)
        session.flush()
        assert init_gold_views(session)["views_populated"] == 0
    connector = type("LocalSchemaGold", (DummyCsvConnector,), {"source_id": source_id})
    bundle = build_source_assets(connector, schema_contract=contract)

    @asset(name=f"{source_id}__silver")
    def existing_silver():
        return {"scope": "inert Silver, existing synthetic SQL; no parse/acquisition"}

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
    assert result.success is (not drift)
    assert len(statements) == (0 if drift else 12)
    evaluations = result.get_asset_check_evaluations()
    assert len(evaluations) == 2
    provenance = next(
        item for item in evaluations if item.check_name.endswith("__provenance_complete")
    )
    structure = next(item for item in evaluations if item.check_name.endswith("__schema_drift"))
    assert provenance.passed and structure.passed is (not drift)
    dq_id = UUID(structure.metadata["dq_id"].value)
    with get_session() as session:
        saved = session.get(DqResult, dq_id)
        assert saved is not None and saved.passed is (not drift)
        assert saved.details["total_artifacts"] == 1
        assert saved.details["valid_schema_artifacts"] == int(not drift)
        assert saved.metric == int(drift)
        populated = session.scalar(
            text("SELECT count(*) FROM pg_matviews WHERE schemaname='gold' AND ispopulated")
        )
        assert populated == (0 if drift else 12)
        if not drift:
            assert session.scalar(text("SELECT count(*) FROM gold.price_obs_current")) == 1
            assert session.scalar(
                text("SELECT price_mga_per_base FROM gold.price_obs_current")
            ) == Decimal("3000.1250")
    assert (
        hashlib.sha256(BronzeProofReader(store).get(artifact.object_key)).hexdigest()
        == artifact.content_sha256
    )
    request.node.user_properties.append(
        (
            "ketrika.schema.gold",
            json.dumps(
                {
                    "schema_drift": drift,
                    "format": format_id,
                    "source_provenance_passed": True,
                    "schema_total": 1,
                    "schema_valid": int(not drift),
                    "gold_refresh_statements": len(statements),
                    "gold_populated_views": populated,
                    "dq_id": str(dq_id),
                    "bronze_sha_unchanged": True,
                    "scope": "synthetic CSV or JSON/SQL/S3; real checks and Gold; inert Silver; not normalization or source qualification",
                }
            ),
        )
    )
