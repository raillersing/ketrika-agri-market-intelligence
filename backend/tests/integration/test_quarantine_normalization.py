"""Quarantine never counts as a current observation or a genuine revision."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text

from ketrika.connectors.records import PriceRecord
from ketrika.core.db import get_session
from ketrika.core.models.db import PriceObservation, QuarantineLedger, SourceRecord
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.core.quarantine import eligible_observation
from ketrika.normalize.price_bridge import resolve_price_identity
from ketrika.normalize.supersede import load_observation_with_supersession
from ketrika.pipelines.rebuild import wipe_silver_gold_tables
from tests.e2e_data.source_backed_synthetic import attach_new_synthetic_proof
from tests.integration.test_quarantine_integration import _ensure_test_source_and_record


def price(session, reference, key, value):
    observation = PriceObservation(
        observation_id=uuid4(),
        source_record_id=reference,
        natural_key=key,
        product_raw="Riz blanc",
        location_raw="Analamanga",
        actor_level="retail",
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 1),
        price_raw=value,
        price_value=Decimal(value),
        currency_raw="MGA",
        unit_raw="kg",
        price_mga_per_base=Decimal(value),
        base_unit="kg",
        conversion_status="exact",
        observed_or_imputed="observed",
        extraction_method="deterministic",
        confidence=1.0,
        review_status="accepted",
        superseded_by=None,
    )
    attach_new_synthetic_proof(session, observation)
    return observation


def quarantine(session, observation, *, source=False):
    entry = QuarantineLedger(
        quarantine_id=uuid4(),
        table_name="meta.source_record" if source else "obs.price_observation",
        observation_id=observation.source_record_id if source else observation.observation_id,
        source_record_id=observation.source_record_id,
        reason_code="TEST_FIXTURE_ISOLATION",
        details={"authenticity": "synthetic", "scope": "software regression only"},
        operator="pytest",
    )
    session.add(entry)
    session.flush()
    return entry


@pytest.mark.parametrize("new_value", ["2500", "2600"])
def test_quarantined_past_is_neither_idempotence_nor_revision(new_value):
    with get_session() as session:
        require_synthetic_test_database(session.bind.url.host, session.bind.url.database)
        _, reference = _ensure_test_source_and_record(session)
        key = "synthetic_quarantine_ingest_" + uuid4().hex
        old = price(session, UUID(reference), key, "2500")
        candidate = price(session, UUID(reference), key, new_value)
        session.add(old)
        session.flush()
        quarantine(session, old)

        def create(identifier):
            candidate.observation_id = identifier
            return candidate

        with pytest.raises(ValueError, match="quarantined_identity_reserved"):
            load_observation_with_supersession(
                session, PriceObservation, key, create, {"price_raw": new_value}
            )
        session.refresh(old)
        assert old.superseded_by is None and old.price_raw == "2500"
        assert session.get(PriceObservation, candidate.observation_id) is None
        current = list(
            session.scalars(
                select(PriceObservation.observation_id).where(
                    PriceObservation.natural_key == key, eligible_observation(PriceObservation)
                )
            )
        )
        assert current == []
        session.rollback()


def test_quarantined_input_is_refused_before_mutating_valid_current_row():
    with get_session() as session:
        require_synthetic_test_database(session.bind.url.host, session.bind.url.database)
        _, reference = _ensure_test_source_and_record(session)
        key = "synthetic_source_quarantine_" + uuid4().hex
        old = price(session, UUID(reference), key, "2500")
        candidate = price(session, UUID(reference), key, "2600")
        session.add(old)
        session.flush()
        quarantine(session, candidate, source=True)

        def create(identifier):
            candidate.observation_id = identifier
            return candidate

        with pytest.raises(ValueError, match="source_quarantined"):
            load_observation_with_supersession(
                session, PriceObservation, key, create, {"price_raw": "2600"}
            )
        session.refresh(old)
        assert old.superseded_by is None and old.price_raw == "2500"
        assert session.get(PriceObservation, candidate.observation_id) is None
        session.rollback()


def test_source_quarantine_excludes_current_rows_until_explicit_revocation():
    with get_session() as session:
        require_synthetic_test_database(session.bind.url.host, session.bind.url.database)
        _, reference = _ensure_test_source_and_record(session)
        key = "synthetic_source_cohort_" + uuid4().hex
        old = price(session, UUID(reference), key, "2500")
        session.add(old)
        session.flush()
        entry = quarantine(session, old, source=True)
        query = select(PriceObservation.observation_id).where(
            PriceObservation.natural_key == key, eligible_observation(PriceObservation)
        )
        assert list(session.scalars(query)) == []
        session.execute(
            text(
                "UPDATE obs.quarantine_ledger SET revoked_at=now(),revocation_reason='synthetic recheck' "
                "WHERE quarantine_id=:id"
            ),
            {"id": entry.quarantine_id},
        )
        assert list(session.scalars(query)) == [old.observation_id]
        session.rollback()


def test_legacy_identity_bridge_does_not_review_a_quarantined_reference():
    with get_session() as session:
        require_synthetic_test_database(session.bind.url.host, session.bind.url.database)
        _, reference = _ensure_test_source_and_record(session)
        key = "synthetic_legacy_bridge_" + uuid4().hex
        old = price(session, UUID(reference), key, "2500")
        session.add(old)
        session.flush()
        quarantine(session, old)
        source = session.get(SourceRecord, old.source_record_id)
        record = PriceRecord(
            product_raw=old.product_raw,
            location_raw=old.location_raw,
            period_start=old.period_start,
            period_end=old.period_end,
            price_raw="2500",
            unit_raw="kg",
            currency_raw="MGA",
            actor_level="retail",
        )
        resolution = resolve_price_identity(session, record, source.source_id, old.source_record_id)
        assert resolution.lookup_key == record.compute_natural_key(source.source_id)
        assert resolution.review_id is None and resolution.reviews_created == 0
        session.rollback()


def test_wipe_refusal_keeps_quarantined_values_and_references():
    with get_session() as session:
        require_synthetic_test_database(session.bind.url.host, session.bind.url.database)
        _, reference = _ensure_test_source_and_record(session)
        old = price(session, UUID(reference), "synthetic_wipe_guard_" + uuid4().hex, "2500")
        session.add(old)
        session.flush()
        entry = quarantine(session, old)
        with pytest.raises(ValueError, match="quarantine_preservation_required"):
            wipe_silver_gold_tables(session)
        session.expire_all()
        assert session.get(PriceObservation, old.observation_id).price_raw == "2500"
        assert session.get(QuarantineLedger, entry.quarantine_id) is not None
        session.rollback()
