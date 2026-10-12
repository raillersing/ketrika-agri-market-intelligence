"""Pure manifest and SQL-dispatch tests; no live SQL or archive qualification."""

import hashlib
from unittest.mock import MagicMock

import pytest

from ketrika.core import reference_manifest as module
from ketrika.core.reference_manifest import (
    ReferenceRow,
    build_reference_manifest,
    read_reference_manifest,
)


def row(table="product", key="one", payload='{"factor":1.000000,"verified":false}'):
    return ReferenceRow(table, key, payload)


def test_sorted_snapshot_preserves_exact_numeric_tokens_and_all_table_counts():
    rows = [row("unit_conversion", '["kg",null]'), row()]
    manifest = build_reference_manifest(rows)
    assert manifest.content == build_reference_manifest(reversed(rows)).content
    assert b"1.000000" in manifest.content
    assert manifest.sha256 == hashlib.sha256(manifest.content).hexdigest()
    assert manifest.row_count == 2
    assert dict(manifest.counts) == {
        "product": 1,
        "product_alias": 0,
        "location": 0,
        "location_alias": 0,
        "unit_conversion": 1,
    }
    assert "factor" not in repr(manifest) and "factor" not in repr(rows[0])
    assert (
        build_reference_manifest([row(payload='{"factor":1.000001}')]).sha256
        != build_reference_manifest([row()]).sha256
    )


def test_empty_snapshot_is_explicit_not_reference_qualification():
    manifest = build_reference_manifest([])
    assert manifest.row_count == 0 and all(count == 0 for _, count in manifest.counts)


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "[]",
        "null",
        '{"a":NaN}',
        '{"a":Infinity}',
        '{"a":1,"a":2}',
        42,
    ],
)
def test_invalid_payload_is_refused(payload):
    with pytest.raises(ValueError, match="reference_manifest_invalid_payload"):
        build_reference_manifest([row(payload=payload)])


@pytest.mark.parametrize("key", ["", None, "x" * 1025])
def test_invalid_key_is_refused(key):
    with pytest.raises(ValueError, match="reference_manifest_invalid_key"):
        build_reference_manifest([row(key=key)])


def test_unknown_table_and_duplicate_members_are_refused():
    with pytest.raises(ValueError, match="reference_manifest_invalid_table"):
        build_reference_manifest([row("source_record")])
    with pytest.raises(ValueError, match="reference_manifest_duplicate_key"):
        build_reference_manifest([row(), row()])
    assert build_reference_manifest([row(), row("location")]).row_count == 2


def test_limits_refuse_instead_of_returning_partial_manifest(monkeypatch):
    monkeypatch.setattr(module, "MAX_ROWS", 1)
    with pytest.raises(ValueError, match="reference_manifest_row_limit"):
        build_reference_manifest([row(), row(key="two")])
    monkeypatch.setattr(module, "MAX_BYTES", 10)
    with pytest.raises(ValueError, match="reference_manifest_size_limit"):
        build_reference_manifest([row()])


def test_single_bounded_stream_query_never_commits_and_closes_cursor():
    session = MagicMock()
    result = session.execute.return_value
    result.mappings.return_value = [
        {"table_name": "product", "row_key": "one", "payload_json": "{}"}
    ]
    assert read_reference_manifest(session).row_count == 1
    session.execute.assert_called_once()
    query = str(session.execute.call_args.args[0])
    assert query.count("UNION ALL") == 4 and "LIMIT 100001" in query
    assert session.execute.call_args.kwargs["execution_options"] == {
        "stream_results": True,
        "yield_per": 256,
    }
    session.commit.assert_not_called()
    result.close.assert_called_once()


def test_invalid_snapshot_still_closes_cursor_without_commit():
    session = MagicMock()
    result = session.execute.return_value
    result.mappings.return_value = [
        {"table_name": "product", "row_key": "one", "payload_json": "bad"}
    ]
    with pytest.raises(ValueError, match="reference_manifest_invalid_payload"):
        read_reference_manifest(session)
    session.commit.assert_not_called()
    result.close.assert_called_once()
