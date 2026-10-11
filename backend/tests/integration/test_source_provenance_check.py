"""Fresh SQL and real immutable QA Bronze; corrupt-object tests use memory only."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from dagster import Definitions, asset
from sqlalchemy import select

from ketrika.connectors.dummy_csv import DummyCsvConnector
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.models.db import DqResult, Source, SourceRecord
from ketrika.core.provenance_audit import audit_source_provenance
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.core.schema_json import JSONSchemaContract, JSONShape
from ketrika.pipelines.factory import build_source_assets
from tests.unit.test_provenance import MemoryReader
from tests.unit.test_provenance_audit import price_example


@pytest.mark.integration
@pytest.mark.parametrize(
    "variant", ["valid", "missing_evidence", "corrupt_memory", "absent_memory"]
)
def test_source_measurement_and_receipt_survive_new_session(variant, monkeypatch, request):
    source_id = f"dummy_source_check_{uuid4().hex}"
    observation, content = price_example()
    with get_session() as session:
        url = session.get_bind().engine.url
        require_synthetic_test_database(url.host, url.database)
        store = BronzeStore()
        assert store.bucket == "ketrika-qa-bronze"
        artifact = store.put(
            source_id=source_id,
            content=content,
            mime_type="application/json",
            url="https://example.invalid/synthetic-source-check",
            retrieved_via="manual_upload",
            fetched_at=datetime(2026, 10, 11, tzinfo=UTC),
            http_status=0,
            http_headers={"x-ketrika-dataset": "synthetic; verified=false"},
        )
        assert artifact.content_sha256 == hashlib.sha256(content).hexdigest()
        session.add(
            Source(source_id=source_id, spec={"authenticity": "synthetic"}, status="disabled")
        )
        session.flush()
        session.add(
            SourceRecord(
                source_record_id=observation.source_record_id,
                source_id=source_id,
                source_url="https://example.invalid/synthetic-source-check",
                retrieved_via="manual_upload",
                object_key=artifact.object_key,
                content_sha256=artifact.content_sha256,
                mime_type="application/json",
                fetched_at=datetime.now(UTC),
                extraction_status="parsed",
                parser_version="1.0.0",
            )
        )
        session.flush()
        observation.review_status = "pending"
        if variant == "missing_evidence":
            observation.evidence = None
        session.add(observation)
        session.flush()
        reader = (
            MemoryReader({artifact.object_key: b"damaged only in RAM"})
            if variant == "corrupt_memory"
            else MemoryReader({})
            if variant == "absent_memory"
            else BronzeProofReader(store)
        )
        receipt = audit_source_provenance(session, reader, source_id)
        assert receipt.report.total == 1
        assert receipt.report.valid == int(variant == "valid")
        assert receipt.report.passed is (variant == "valid")
        assert receipt.targets[0].observation_id == observation.observation_id
        dq_id = receipt.dq_id
    with get_session() as session:
        saved = session.get(DqResult, dq_id)
        assert saved is not None and saved.passed is (variant == "valid")
        assert saved.source_id == source_id and saved.asset_key == f"{source_id}__silver"
        assert saved.details["total_records"] == 1
        assert saved.details["valid_provenance"] == int(variant == "valid")
        assert saved.details["scope"] == "all_source_observations"
        empty = audit_source_provenance(
            session, BronzeProofReader(BronzeStore()), source_id + "_absent"
        )
        assert empty.report.total == 0 and not empty.report.passed and empty.report.rate is None
        empty_id = empty.dq_id
    with get_session() as session:
        saved = session.scalar(select(DqResult).where(DqResult.dq_id == empty_id))
        assert saved is not None and saved.metric is None and not saved.passed
        assert saved.details["state"] == "empty"

    # Real Dagster scheduling of the production check, with an inert Silver
    # stand-in and downstream sentinel. No acquisition or Gold mutation here.
    connector = type("LocalSourceCheck", (DummyCsvConnector,), {"source_id": source_id})
    contract = JSONSchemaContract(
        "synthetic-source-check-json-v1",
        JSONShape(
            "array",
            items=JSONShape(
                "object",
                properties=tuple(
                    (field, JSONShape("string"), True)
                    for field in (
                        "product_raw",
                        "period_start",
                        "unit_raw",
                        "currency_raw",
                        "price_value",
                    )
                ),
            ),
        ),
    )
    bundle = build_source_assets(connector, schema_contract=contract)
    downstream_calls = []

    @asset(name=f"{source_id}__silver")
    def silver_stand_in():
        return {"scope": "synthetic existing SQL rows; no collection"}

    @asset(name=f"{source_id}__downstream", deps=[silver_stand_in])
    def downstream_sentinel():
        downstream_calls.append("executed")
        return {"scope": "sentinel only; not a real Gold refresh"}

    # Simulated missing/corrupt stores never alter an immutable QA object.
    monkeypatch.setattr("ketrika.pipelines.factory.BronzeProofReader", lambda _: reader)
    definitions = Definitions(
        assets=[silver_stand_in, downstream_sentinel], asset_checks=bundle.checks
    )
    result = definitions.resolve_implicit_global_asset_job_def().execute_in_process(
        raise_on_error=False
    )
    assert result.success is (variant == "valid")
    assert downstream_calls == (["executed"] if variant == "valid" else [])
    evaluations = result.get_asset_check_evaluations()
    assert len(evaluations) == 2
    evaluation = next(
        item for item in evaluations if item.check_name == f"{source_id}__provenance_complete"
    )
    schema_evaluation = next(
        item for item in evaluations if item.check_name == f"{source_id}__schema_drift"
    )
    assert schema_evaluation.passed
    assert evaluation.passed is (variant == "valid")
    check_dq_id = evaluation.metadata["dq_id"].value
    with get_session() as session:
        persisted = session.get(DqResult, UUID(check_dq_id))
        assert persisted is not None and persisted.passed is (variant == "valid")
        assert persisted.details["total_records"] == 1
    request.node.user_properties.append(
        (
            "ketrika.source_check",
            json.dumps(
                {
                    "variant": variant,
                    "dq_id": check_dq_id,
                    "total": 1,
                    "valid": int(variant == "valid"),
                    "dagster_success": result.success,
                    "downstream_executed": bool(downstream_calls),
                    "scope": "synthetic SQL/Bronze; production check; inert downstream, not Gold qualification",
                }
            ),
        )
    )
