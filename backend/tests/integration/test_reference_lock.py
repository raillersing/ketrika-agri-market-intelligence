"""Prepared QA locks/rollback; no normalizer or ledger qualification."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from ketrika.core.db import get_sessionmaker
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.core.reference_lock import lock_reference_manifest
from ketrika.core.reference_manifest import read_reference_manifest


def guard(session):
    target = session.get_bind().engine.url
    require_synthetic_test_database(target.host, target.database)


@pytest.mark.integration
def test_five_reference_locks_are_held_until_caller_rollback():
    session = get_sessionmaker()()
    try:
        guard(session)
        manifest = lock_reference_manifest(session)
        assert manifest.row_count > 0 and session.in_transaction()
        names = set(
            session.scalars(
                text("""
            SELECT c.relname FROM pg_locks l
            JOIN pg_class c ON c.oid=l.relation
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE l.pid=pg_backend_pid() AND l.mode='ShareLock'
              AND l.granted AND n.nspname='ref'
        """)
            ).all()
        )
        assert names == {
            "product",
            "product_alias",
            "location",
            "location_alias",
            "unit_conversion",
        }
        assert read_reference_manifest(session) == manifest
        session.rollback()
        assert not session.in_transaction()
    finally:
        session.rollback()
        session.close()


@pytest.mark.integration
def test_other_writer_times_out_then_can_write_after_release_without_persisting_changes():
    owner, other = get_sessionmaker()(), get_sessionmaker()()
    try:
        guard(owner)
        guard(other)
        before = lock_reference_manifest(owner)
        parameters = (
            owner.execute(
                text(
                    "SELECT unit_code, product_id FROM ref.unit_conversion ORDER BY unit_code LIMIT 1"
                )
            )
            .mappings()
            .one()
        )
        statement = text(
            "UPDATE ref.unit_conversion SET factor=factor WHERE unit_code=:unit_code AND product_id IS NOT DISTINCT FROM CAST(:product_id AS uuid)"
        )
        other.execute(text("SET LOCAL lock_timeout = '200ms'"))
        with pytest.raises(OperationalError) as captured:
            other.execute(statement, dict(parameters))
        assert getattr(captured.value.orig, "sqlstate", None) == "55P03"
        other.rollback()
        assert read_reference_manifest(owner) == before
        owner.rollback()
        other.execute(text("SET LOCAL lock_timeout = '200ms'"))
        assert other.execute(statement, dict(parameters)).rowcount == 1
        other.rollback()
        assert read_reference_manifest(owner) == before
        owner.rollback()
    finally:
        owner.rollback()
        other.rollback()
        owner.close()
        other.close()
