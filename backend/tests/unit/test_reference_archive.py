"""Prepared archive behavior on inert stores; not actual S3 qualification."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from ketrika.core.bronze import BronzeArtifact, BronzeStore
from ketrika.core.reference_archive import archive_reference_manifest
from ketrika.core.reference_manifest import ReferenceRow, build_reference_manifest

WHEN = datetime(2026, 1, 1, tzinfo=UTC)


def prepared():
    manifest = build_reference_manifest(
        [ReferenceRow("product", "fixture", '{"scope":"synthetic"}')]
    )
    key = f"reference_manifest/2026/01/{manifest.sha256}.json"
    store, reader = Mock(spec=BronzeStore), Mock()
    store.put.return_value = BronzeArtifact(
        key, manifest.sha256, "application/json", "", WHEN, True, len(manifest.content)
    )
    reader.get.return_value = manifest.content
    return manifest, store, reader


def test_archive_put_has_no_institutional_url_and_requires_fresh_read():
    manifest, store, reader = prepared()
    result = archive_reference_manifest(store, manifest, captured_at=WHEN, reader=reader)
    assert result.sha256 == manifest.sha256 and result.row_count == 1
    assert result.counts == manifest.counts
    kwargs = store.put.call_args.kwargs
    assert kwargs["source_id"] == "reference_manifest"
    assert kwargs["url"] == "" and kwargs["http_status"] == 0
    assert kwargs["retrieved_via"] == "manual_upload"
    assert kwargs["content"] == manifest.content
    assert kwargs["http_headers"] == {
        "x-ketrika-dataset": "internal-snapshot;source_verified=false"
    }
    reader.get.assert_called_once_with(result.object_key)


@pytest.mark.parametrize(
    "field,value",
    [
        ("sha256", "0" * 64),
        ("row_count", 2),
        ("row_count", True),
        ("counts", ()),
        ("content", b"[]"),
        ("content", b"invalid"),
    ],
)
def test_forged_manifest_refuses_before_any_store_operation(field, value):
    manifest, store, reader = prepared()
    with pytest.raises(ValueError, match="^reference_archive_invalid_manifest$"):
        archive_reference_manifest(
            store, replace(manifest, **{field: value}), captured_at=WHEN, reader=reader
        )
    store.put.assert_not_called()
    reader.get.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [
        ("object_key", "wrong/path"),
        ("content_sha256", "0" * 64),
        ("mime_type", "text/html"),
        ("url", "https://example.invalid/unverified"),
        ("size_bytes", 0),
    ],
)
def test_wrong_descriptor_refuses_before_get(field, value):
    manifest, store, reader = prepared()
    store.put.return_value = replace(store.put.return_value, **{field: value})
    with pytest.raises(ValueError, match="^reference_archive_descriptor_mismatch$"):
        archive_reference_manifest(store, manifest, captured_at=WHEN, reader=reader)
    reader.get.assert_not_called()


@pytest.mark.parametrize("content", [b"wrong", None, "not bytes"])
def test_existing_wrong_bytes_are_not_accepted_or_overwritten(content):
    manifest, store, reader = prepared()
    store.put.return_value = replace(store.put.return_value, is_new=False)
    reader.get.return_value = content
    with pytest.raises(ValueError, match="^reference_archive_content_mismatch$"):
        archive_reference_manifest(store, manifest, captured_at=WHEN, reader=reader)
    assert store.put.call_count == 1 and reader.get.call_count == 1


def test_naive_timestamp_refuses_before_put():
    manifest, store, reader = prepared()
    with pytest.raises(ValueError, match="^reference_archive_invalid_timestamp$"):
        archive_reference_manifest(
            store, manifest, captured_at=WHEN.replace(tzinfo=None), reader=reader
        )
    store.put.assert_not_called()


def test_reader_failure_never_returns_a_success_receipt():
    manifest, store, reader = prepared()
    reader.get.side_effect = OSError("inert read failure")
    with pytest.raises(OSError):
        archive_reference_manifest(store, manifest, captured_at=WHEN, reader=reader)
