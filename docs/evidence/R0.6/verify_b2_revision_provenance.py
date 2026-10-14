"""Additional reception command on isolated QA; not a source qualification."""

import json
import os
from decimal import Decimal
from uuid import uuid4

from ketrika.connectors.base import RecordBase
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.models.db import PriceObservation, Source
from ketrika.core.provenance_audit import ObservationTarget, audit_observation_provenance
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.qualification import require_synthetic_test_database, validate_environment
from ketrika.normalize.price_loader import load_normalized_price
from tests.integration.test_normalized_price_load import persist_artifact

validate_environment(os.environ)
source = "dummy_b2_proof_" + uuid4().hex
store = BronzeStore()
assert store.bucket == "ketrika-qa-bronze"
with get_session() as session:
    url = session.get_bind().engine.url
    require_synthetic_test_database(url.host, url.database)
    session.add(
        Source(
            source_id=source,
            status="disabled",
            spec={
                "authenticity": "synthetic",
                "verified": False,
                "human_reviewed": False,
            },
        )
    )
    session.flush()
    old_ref, old_record = persist_artifact(session, store, source, "Riz blanc local", "2850", "MGA")
    old_id = uuid4()
    old_key = RecordBase.compute_natural_key(old_record, source)
    old_evidence = old_record.evidence | {"normalization": {"version": 1, "value_kind": "point"}}
    session.add(
        PriceObservation(
            observation_id=old_id,
            source_record_id=old_ref,
            natural_key=old_key,
            product_raw=old_record.product_raw,
            location_raw=old_record.location_raw,
            variety=old_record.variety,
            actor_level=old_record.actor_level,
            period_start=old_record.period_start,
            period_end=old_record.period_end,
            price_raw="2850",
            price_value=Decimal("2850"),
            unit_raw="kg",
            currency_raw="MGA",
            observed_or_imputed="observed",
            conversion_status="uncertain",
            extraction_method="deterministic",
            confidence=Decimal(1),
            review_status="pending",
            evidence=old_evidence,
        )
    )
    session.flush()
    new_ref, new_record = persist_artifact(session, store, source, "Riz blanc local", "2855", "MGA")
    result = load_normalized_price(session, new_record, source, new_ref)
    assert result.action == "superseded" and result.observation_id is not None
    new_id = result.observation_id
    assert (
        load_normalized_price(session, new_record, source, new_ref).action == "idempotent_skipped"
    )
with get_session() as session:
    old = session.get(PriceObservation, old_id)
    new = session.get(PriceObservation, new_id)
    assert old is not None and new is not None
    assert old.natural_key == old_key and old.evidence == old_evidence
    assert old.price_raw == "2850" and old.superseded_by == new_id
    assert new.source_record_id == new_ref != old_ref
    assert new.price_raw == "2855" and new.price_value == Decimal("2855")
    assert new.natural_key == new_record.compute_natural_key(source) != old_key
    assert new.evidence is not None
    assert new.evidence["provenance"] == new_record.evidence["provenance"]
    receipt = audit_observation_provenance(
        session,
        BronzeProofReader(store),
        mode="incremental",
        targets=[
            ObservationTarget("price_observation", old_id),
            ObservationTarget("price_observation", new_id),
        ],
    )
    assert receipt.report.passed and receipt.report.total == receipt.report.valid == 2
    print(
        json.dumps(
            {
                "source_id": source,
                "old_id": str(old_id),
                "new_id": str(new_id),
                "old_source_record_id": str(old_ref),
                "new_source_record_id": str(new_ref),
                "total": receipt.report.total,
                "valid": receipt.report.valid,
                "objects_read": receipt.report.objects_read,
                "action": "superseded",
                "retry_action": "idempotent_skipped",
                "old_key_evidence_value_preserved": True,
                "scope": "synthetic SQL and fresh immutable QA Bronze source cells; not authenticity, market or human qualification",
            }
        )
    )
