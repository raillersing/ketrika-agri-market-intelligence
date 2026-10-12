"""Prepared SQL snapshot checks, not a processing ledger or source qualification."""

import hashlib
import json
from decimal import Decimal

import pytest
from sqlalchemy import text

from ketrika.core.db import get_session
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.core.reference_manifest import (
    ReferenceRow,
    build_reference_manifest,
    read_reference_manifest,
)


def readonly(session):
    target = session.get_bind().engine.url
    require_synthetic_test_database(target.host, target.database)
    session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
    assert session.scalar(text("SHOW transaction_read_only")) == "on"


@pytest.mark.integration
def test_actual_reference_snapshot_repeats_and_matches_sql_counts():
    with get_session() as session:
        readonly(session)
        first = read_reference_manifest(session)
        second = read_reference_manifest(session)
        expected = dict(
            session.execute(
                text("""
            SELECT 'product', count(*) FROM ref.product
            UNION ALL SELECT 'product_alias', count(*) FROM ref.product_alias
            UNION ALL SELECT 'location', count(*) FROM ref.location
            UNION ALL SELECT 'location_alias', count(*) FROM ref.location_alias
            UNION ALL SELECT 'unit_conversion', count(*) FROM ref.unit_conversion
        """)
            ).all()
        )
        assert first == second
        assert dict(first.counts) == expected
        assert first.row_count == sum(expected.values()) > 0
        assert hashlib.sha256(first.content).hexdigest() == first.sha256
        members = json.loads(first.content)[1]
        assert len(members) == first.row_count
        assert members == sorted(members)
        session.rollback()


@pytest.mark.integration
@pytest.mark.parametrize(
    "token", ["0.000000000000000000000000000000001", "123456789012345678901234567890.123456789"]
)
def test_postgres_numeric_payload_retains_exact_decimal_lexeme(token):
    with get_session() as session:
        readonly(session)
        payload = session.scalar(
            text("SELECT jsonb_build_object('factor', CAST(:token AS numeric))::text"),
            {"token": token},
        )
        assert isinstance(payload, str)
        manifest = build_reference_manifest(
            [ReferenceRow("unit_conversion", '["fixture",null]', payload)]
        )
        stored = json.loads(manifest.content)[1][0][2]
        assert stored == payload
        assert token in stored
        assert json.loads(stored, parse_float=Decimal)["factor"] == Decimal(token)
        session.rollback()


@pytest.mark.integration
def test_postgres_composite_keys_preserve_null_and_delimiters():
    with get_session() as session:
        readonly(session)
        keys = [
            session.scalar(
                text("SELECT jsonb_build_array(CAST(:unit AS text), CAST(:product AS text))::text"),
                {"unit": unit, "product": product},
            )
            for unit, product in [("a|b", "c"), ("a", "b|c"), ("a", None), ("a", "None")]
        ]
        assert len(set(keys)) == 4
        rows = [
            ReferenceRow("unit_conversion", key, '{"scope":"synthetic SQL expression"}')
            for key in keys
        ]
        manifest = build_reference_manifest(rows)
        assert manifest.row_count == 4
        assert len(json.loads(manifest.content)[1]) == 4
        session.rollback()
