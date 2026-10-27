"""Integration tests for quarantine ledger, triggers, repair guards and Gold exclusion (ADR-131, AU-08)."""

import hashlib
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from ketrika.core.db import get_session
from ketrika.core.models.db import PriceObservation, QuarantineLedger
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.gold.refresh import refresh_gold_views
from ketrika.pipelines.rebuild import wipe_silver_gold_tables
from tests.e2e_data.source_backed_synthetic import attach_new_synthetic_proof


def _ensure_test_source_and_record(session) -> tuple[str, str]:
    """Helper to ensure a valid source and source_record exist for foreign keys."""
    source_id = "test_quarantine_source"
    session.execute(
        text(
            "INSERT INTO meta.source (source_id, spec, status) "
            "VALUES (:sid, '{\"priority\": \"P1\", \"source_family\": \"test\"}', 'active') "
            "ON CONFLICT (source_id) DO NOTHING"
        ),
        {"sid": source_id},
    )
    srid = str(uuid4())
    sha = hashlib.sha256(srid.encode()).hexdigest()
    session.execute(
        text(
            "INSERT INTO meta.source_record "
            "(source_record_id, source_id, source_url, retrieved_via, object_key, content_sha256, mime_type, parser_version, fetched_at, extraction_status) "
            "VALUES (:srid, :sid, 'http://test.local', 'direct', :key, :sha, 'application/json', 'synthetic-source-generator-v1', now(), 'parsed') "
            "ON CONFLICT DO NOTHING"
        ),
        {
            "srid": srid,
            "sid": source_id,
            "key": f"bronze/{source_id}/{srid}.json",
            "sha": sha,
        },
    )
    session.commit()
    return source_id, srid


def test_quarantine_ledger_schema_and_permissions():
    with get_session() as session:
        require_synthetic_test_database(session.bind.url.host, session.bind.url.database)
        cols = session.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema='obs' AND table_name='quarantine_ledger' "
                "ORDER BY ordinal_position"
            )
        ).fetchall()
        col_names = [c[0] for c in cols]
        assert "quarantine_id" in col_names
        assert "table_name" in col_names
        assert "observation_id" in col_names
        assert "source_record_id" in col_names
        assert "reason_code" in col_names
        assert "details" in col_names
        assert "operator" in col_names
        assert "quarantined_at" in col_names
        assert "revoked_at" in col_names
        assert "revocation_reason" in col_names


def test_quarantine_ledger_append_only_deletions_forbidden():
    with get_session() as session:
        require_synthetic_test_database(session.bind.url.host, session.bind.url.database)
        _, srid = _ensure_test_source_and_record(session)
        qid = str(uuid4())
        obs_id = str(uuid4())
        session.execute(
            text(
                "INSERT INTO obs.quarantine_ledger "
                "(quarantine_id, table_name, observation_id, source_record_id, reason_code, details, operator) "
                "VALUES (:qid, 'obs.price_observation', :oid, :srid, 'HISTORICAL_SELF_LINK', '{\"test\": true}', 'pytest')"
            ),
            {"qid": qid, "oid": obs_id, "srid": srid},
        )
        session.flush()

        with pytest.raises(DBAPIError) as exc_info:
            session.execute(
                text("DELETE FROM obs.quarantine_ledger WHERE quarantine_id = :qid"),
                {"qid": qid},
            )
            session.flush()
        assert "Deletions are forbidden on obs.quarantine_ledger" in str(exc_info.value)
        session.rollback()


def test_quarantine_ledger_update_restrictions():
    with get_session() as session:
        require_synthetic_test_database(session.bind.url.host, session.bind.url.database)
        _, srid = _ensure_test_source_and_record(session)
        qid = str(uuid4())
        obs_id = str(uuid4())
        session.execute(
            text(
                "INSERT INTO obs.quarantine_ledger "
                "(quarantine_id, table_name, observation_id, source_record_id, reason_code, details, operator) "
                "VALUES (:qid, 'obs.price_observation', :oid, :srid, 'MANUAL_INVESTIGATION', '{\"test\": true}', 'pytest')"
            ),
            {"qid": qid, "oid": obs_id, "srid": srid},
        )
        session.flush()

        # Modifying immutable fields like reason_code or operator is forbidden
        with pytest.raises(DBAPIError) as exc_info:
            session.execute(
                text(
                    "UPDATE obs.quarantine_ledger SET reason_code = 'MODIFIED' WHERE quarantine_id = :qid"
                ),
                {"qid": qid},
            )
            session.flush()
        assert (
            "Quarantine ledger only permits updating revoked_at and revocation_reason"
            in str(exc_info.value)
        )
        session.rollback()

        # Allowed: updating revoked_at and revocation_reason on revocable quarantine when revoked_at IS NULL
        session.execute(
            text(
                "INSERT INTO obs.quarantine_ledger "
                "(quarantine_id, table_name, observation_id, source_record_id, reason_code, details, operator) "
                "VALUES (:qid, 'obs.price_observation', :oid, :srid, 'MANUAL_INVESTIGATION', '{\"test\": true}', 'pytest')"
            ),
            {"qid": qid, "oid": obs_id, "srid": srid},
        )
        session.execute(
            text(
                "UPDATE obs.quarantine_ledger "
                "SET revoked_at = now(), revocation_reason = 'audited_and_restored' "
                "WHERE quarantine_id = :qid"
            ),
            {"qid": qid},
        )
        session.flush()

        # Second update once revoked is rejected
        with pytest.raises(DBAPIError) as exc_info2:
            session.execute(
                text(
                    "UPDATE obs.quarantine_ledger SET revocation_reason = 'changed_again' WHERE quarantine_id = :qid"
                ),
                {"qid": qid},
            )
            session.flush()
        assert "Quarantine record is already revoked and cannot be modified" in str(exc_info2.value)
        session.rollback()


def test_quarantine_ledger_prohibits_revocation_of_historical_self_links():
    """Verify Codex recommendation 3: non-republication guarantee for historical self-links."""
    with get_session() as session:
        require_synthetic_test_database(session.bind.url.host, session.bind.url.database)
        _, srid = _ensure_test_source_and_record(session)
        qid = str(uuid4())
        obs_id = str(uuid4())
        session.execute(
            text(
                "INSERT INTO obs.quarantine_ledger "
                "(quarantine_id, table_name, observation_id, source_record_id, reason_code, details, operator) "
                "VALUES (:qid, 'obs.price_observation', :oid, :srid, 'HISTORICAL_SELF_LINK', '{\"test\": true}', 'pytest')"
            ),
            {"qid": qid, "oid": obs_id, "srid": srid},
        )
        session.flush()

        # Attempting to revoke a HISTORICAL_SELF_LINK quarantine record MUST fail permanently
        with pytest.raises(DBAPIError) as exc_info:
            session.execute(
                text(
                    "UPDATE obs.quarantine_ledger "
                    "SET revoked_at = now(), revocation_reason = 'attempted_republication' "
                    "WHERE quarantine_id = :qid"
                ),
                {"qid": qid},
            )
            session.flush()
        assert "Quarantine for historical self-links is permanent and cannot be revoked" in str(
            exc_info.value
        )
        session.rollback()


def test_anti_self_link_trigger_on_price_observation():
    """Verify Codex recommendation 2: anti-self-link trigger on both INSERT and UPDATE."""
    with get_session() as session:
        require_synthetic_test_database(session.bind.url.host, session.bind.url.database)
        _, srid = _ensure_test_source_and_record(session)
        obs_id = str(uuid4())

        # 1. Attempting self-supersession on INSERT: superseded_by = observation_id
        with pytest.raises(DBAPIError) as exc_insert:
            session.execute(
                text(
                    "INSERT INTO obs.price_observation "
                    "(observation_id, source_record_id, natural_key, product_raw, actor_level, "
                    "period_start, period_end, price_raw, unit_raw, conversion_status, "
                    "observed_or_imputed, extraction_method, "
                    "confidence, review_status, price_mga_per_base, superseded_by) "
                    "VALUES (:oid, :srid, 'nk_self_insert_test', 'riz', 'retail', '2026-10-01', '2026-10-01', "
                    "'2500', 'kg', 'converted', 'observed', 'deterministic', 1.0, 'accepted', 2500, :oid)"
                ),
                {"oid": obs_id, "srid": srid},
            )
            session.flush()
        assert "Self-supersession is forbidden" in str(exc_insert.value)
        session.rollback()

        # 2. Insert clean observation without superseded_by
        session.execute(
            text(
                "INSERT INTO obs.price_observation "
                "(observation_id, source_record_id, natural_key, product_raw, actor_level, "
                "period_start, period_end, price_raw, unit_raw, conversion_status, "
                "observed_or_imputed, extraction_method, "
                "confidence, review_status, price_mga_per_base) "
                "VALUES (:oid, :srid, 'nk_self_update_test', 'riz', 'retail', '2026-10-01', '2026-10-01', "
                "'2500', 'kg', 'converted', 'observed', 'deterministic', 1.0, 'accepted', 2500)"
            ),
            {"oid": obs_id, "srid": srid},
        )
        session.flush()

        # 3. Attempting self-supersession on UPDATE: superseded_by = observation_id
        with pytest.raises(DBAPIError) as exc_update:
            session.execute(
                text(
                    "UPDATE obs.price_observation "
                    "SET superseded_by = observation_id "
                    "WHERE observation_id = :oid"
                ),
                {"oid": obs_id},
            )
            session.flush()
        assert "Self-supersession is forbidden" in str(exc_update.value)
        session.rollback()


def test_anti_self_link_repair_requires_quarantine_record():
    with get_session() as session:
        require_synthetic_test_database(session.bind.url.host, session.bind.url.database)
        _, srid = _ensure_test_source_and_record(session)
        obs_id = str(uuid4())

        # In order to simulate a historical self-link existing prior to migration 0020,
        # we temporarily disable the trigger to insert the defective historical row
        session.execute(
            text("ALTER TABLE obs.price_observation DISABLE TRIGGER trg_price_obs_superseded_only")
        )
        session.execute(
            text(
                "INSERT INTO obs.price_observation "
                "(observation_id, source_record_id, natural_key, product_raw, actor_level, "
                "period_start, period_end, price_raw, unit_raw, conversion_status, "
                "observed_or_imputed, extraction_method, "
                "confidence, review_status, price_mga_per_base, superseded_by) "
                "VALUES (:oid, :srid, 'nk_repair_test', 'riz', 'retail', '2026-10-01', '2026-10-01', "
                "'2500', 'kg', 'converted', 'observed', 'deterministic', 1.0, 'accepted', 2500, :oid)"
            ),
            {"oid": obs_id, "srid": srid},
        )
        session.execute(
            text("ALTER TABLE obs.price_observation ENABLE TRIGGER trg_price_obs_superseded_only")
        )
        session.flush()

        # 1. Attempting to clear superseded_by without quarantine record fails
        with pytest.raises(DBAPIError) as exc_info:
            session.execute(
                text(
                    "UPDATE obs.price_observation "
                    "SET superseded_by = NULL "
                    "WHERE observation_id = :oid"
                ),
                {"oid": obs_id},
            )
            session.flush()
        assert (
            "Historical self-link cannot be cleared without an active quarantine ledger record"
            in str(exc_info.value)
        )
        session.rollback()

        # Re-insert the historical self-linked row with trigger disabled
        session.execute(
            text("ALTER TABLE obs.price_observation DISABLE TRIGGER trg_price_obs_superseded_only")
        )
        session.execute(
            text(
                "INSERT INTO obs.price_observation "
                "(observation_id, source_record_id, natural_key, product_raw, actor_level, "
                "period_start, period_end, price_raw, unit_raw, conversion_status, "
                "observed_or_imputed, extraction_method, "
                "confidence, review_status, price_mga_per_base, superseded_by) "
                "VALUES (:oid, :srid, 'nk_repair_test', 'riz', 'retail', '2026-10-01', '2026-10-01', "
                "'2500', 'kg', 'converted', 'observed', 'deterministic', 1.0, 'accepted', 2500, :oid)"
            ),
            {"oid": obs_id, "srid": srid},
        )
        session.execute(
            text("ALTER TABLE obs.price_observation ENABLE TRIGGER trg_price_obs_superseded_only")
        )
        # 2. Insert quarantine record
        qid = str(uuid4())
        session.execute(
            text(
                "INSERT INTO obs.quarantine_ledger "
                "(quarantine_id, table_name, observation_id, source_record_id, reason_code, details, operator) "
                "VALUES (:qid, 'obs.price_observation', :oid, :srid, 'HISTORICAL_SELF_LINK', '{\"repaired\": true}', 'pytest')"
            ),
            {"qid": qid, "oid": obs_id, "srid": srid},
        )
        session.flush()

        # 3. Now clearing superseded_by succeeds under quarantine guard!
        session.execute(
            text(
                "UPDATE obs.price_observation SET superseded_by = NULL WHERE observation_id = :oid"
            ),
            {"oid": obs_id},
        )
        session.flush()

        repaired_superseded_by = session.execute(
            text("SELECT superseded_by FROM obs.price_observation WHERE observation_id = :oid"),
            {"oid": obs_id},
        ).scalar_one()
        assert repaired_superseded_by is None
        session.rollback()


def test_quarantined_observation_excluded_from_gold():
    with get_session() as session:
        require_synthetic_test_database(session.bind.url.host, session.bind.url.database)
        wipe_silver_gold_tables(session)
        _, srid = _ensure_test_source_and_record(session)
        obs_id = uuid4()

        natural_key = f"nk_quarantine_gold_test_{uuid4().hex[:8]}"
        p_obs = PriceObservation(
            observation_id=obs_id,
            source_record_id=UUID(srid),
            natural_key=natural_key,
            product_raw="Riz blanc",
            location_raw="Analamanga",
            actor_level="retail",
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 1),
            price_raw="2800",
            price_value=Decimal("2800"),
            currency_raw="MGA",
            unit_raw="kg",
            price_mga_per_base=Decimal("2800"),
            base_unit="kg",
            conversion_status="exact",
            observed_or_imputed="observed",
            extraction_method="deterministic",
            confidence=1.0,
            review_status="accepted",
            superseded_by=None,
        )
        attach_new_synthetic_proof(session, p_obs)
        session.add(p_obs)
        session.flush()

        # Also quarantine it
        qid = uuid4()
        session.add(
            QuarantineLedger(
                quarantine_id=qid,
                table_name="obs.price_observation",
                observation_id=p_obs.observation_id,
                source_record_id=p_obs.source_record_id,
                reason_code="TEST_FIXTURE_ISOLATION",
                details={"test": True},
                operator="pytest",
            )
        )
        session.commit()

        # Refresh gold views: quarantined observation is skipped by provenance gate AND excluded from gold views
        try:
            refresh_gold_views(session)
        except Exception as exc:
            if hasattr(exc, "receipts") and exc.receipts:
                for rcpt in exc.receipts:
                    if not rcpt.report.passed:
                        print(f"FAILED RECEIPT passed={rcpt.report.passed} total={rcpt.report.total_artifacts} valid={rcpt.report.valid_artifacts}")
                        for r in rcpt.report.results:
                            if r.get("state") != "verified":
                                print(f"  FAILED SCHEMA ROW: srid={r.get('source_record_id')} reasons={r.get('reasons')}")
            if hasattr(exc, "receipt") and exc.receipt:
                failed = [r for r in exc.receipt.report.results if not r.passed]
                for f in failed[:10]:
                    print(f"FAILED ROW: oid={f.observation_id} srid={f.source_record_id} key={f.object_key} reason={f.reason}")
            raise

        # Quarantined observation MUST NOT be published in gold.price_obs_current
        in_gold = session.execute(
            text("SELECT count(*) FROM gold.price_obs_current WHERE observation_id = :oid"),
            {"oid": str(p_obs.observation_id)},
        ).scalar_one()
        assert in_gold == 0

        # Revoke quarantine: now active quarantine is revoked
        session.execute(
            text(
                "UPDATE obs.quarantine_ledger "
                "SET revoked_at = now(), revocation_reason = 'test_unquarantine' "
                "WHERE quarantine_id = :qid"
            ),
            {"qid": str(qid)},
        )
        session.commit()
        refresh_gold_views(session)

        in_gold_after = session.execute(
            text("SELECT count(*) FROM gold.price_obs_current WHERE observation_id = :oid"),
            {"oid": str(p_obs.observation_id)},
        ).scalar_one()
        assert in_gold_after == 1

        # Clean up test observations
        wipe_silver_gold_tables(session)
        session.commit()
