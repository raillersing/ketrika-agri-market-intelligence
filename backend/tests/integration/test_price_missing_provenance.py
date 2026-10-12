"""Prepared SQL/S3 absence proof; never a numeric price or live source."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.models.db import DqResult, PriceObservation, Source, SourceRecord
from ketrika.core.provenance_audit import ObservationTarget, audit_observation_provenance
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.gold.refresh import init_gold_views, refresh_gold_views
from ketrika.pipelines.rebuild import wipe_silver_gold_tables
from tests.unit.test_price_missing_provenance import missing


@pytest.mark.integration
@pytest.mark.parametrize("code,source_marker", [("ND", "ND"), ("NA", "NA"), ("ND", "NA")])
def test_missing_price_reloads_with_real_proof_and_never_enters_numeric_gold(code, source_marker):
    source_id = f"fixture_missing_{uuid4().hex}"
    row, content = missing(code, code)
    payload = json.loads(content)
    payload[0]["price_value"] = source_marker
    content = json.dumps(payload).encode()
    store = BronzeStore()
    assert store.bucket == "ketrika-qa-bronze"
    with get_session() as session:
        target = session.get_bind().engine.url
        require_synthetic_test_database(target.host, target.database)
        wipe_silver_gold_tables(session)
        session.add(
            Source(
                source_id=source_id,
                status="disabled",
                spec={"dataset": "synthetic", "verified": False},
            )
        )
        session.flush()
        artifact = store.put(
            source_id=source_id,
            content=content,
            mime_type="application/json",
            url="https://example.invalid/synthetic-missing",
            retrieved_via="manual_upload",
            fetched_at=datetime.now(UTC),
            http_status=0,
            http_headers={"x-ketrika-dataset": "synthetic;verified=false"},
        )
        session.add(
            SourceRecord(
                source_record_id=row.source_record_id,
                source_id=source_id,
                source_url=artifact.url,
                object_key=artifact.object_key,
                content_sha256=artifact.content_sha256,
                mime_type="application/json",
                retrieved_via="manual_upload",
                fetched_at=datetime.now(UTC),
                parser_version="synthetic-missing-v1",
                extraction_status="parsed",
            )
        )
        session.flush()
        session.add(row)
        session.flush()
        assert init_gold_views(session)["views_populated"] == 0
    with get_session() as session:
        reloaded = session.get(PriceObservation, row.observation_id)
        assert reloaded is not None
        assert reloaded.price_value is None and reloaded.price_mga_per_base is None
        assert reloaded.price_raw == reloaded.missing_code == code
        receipt = audit_observation_provenance(
            session,
            BronzeProofReader(store),
            mode="incremental",
            targets=[ObservationTarget("price_observation", reloaded.observation_id)],
        )
        assert receipt.report.total == 1
        assert receipt.report.valid == int(code == source_marker)
        assert receipt.report.passed is (code == source_marker)
        if code != source_marker:
            assert receipt.report.results[0].reason == "value_mismatch"
        published = refresh_gold_views(
            session, views=["price_obs_current"], reader=BronzeProofReader(store)
        )
        assert published["provenance_state"] == "empty"
        assert published["source_observations_total"] == published["source_observations_valid"] == 0
        assert published["source_cell_rate"] is None
        assert session.scalar(text("SELECT count(*) FROM gold.price_obs_current")) == 0
        receipt_id = receipt.dq_id
    with get_session() as session:
        saved = session.get(DqResult, receipt_id)
        assert saved is not None and saved.passed is (code == source_marker)
        assert (
            session.scalar(
                select(PriceObservation.price_value).where(
                    PriceObservation.observation_id == row.observation_id
                )
            )
            is None
        )
        assert session.scalar(text("SELECT count(*) FROM gold.price_obs_current")) == 0
    assert (
        hashlib.sha256(BronzeProofReader(store).get(artifact.object_key)).hexdigest()
        == artifact.content_sha256
    )
