"""Negative object checks use a simulated store, never mutate original Bronze."""

import hashlib
import importlib.util
import io
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "quarantine_bronze_copy", Path("/workspace/backend/scripts/copy_quarantine_bronze.py")
)
assert spec is not None and spec.loader is not None
copy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(copy)


def descriptor(content=b"synthetic bytes"):
    return {
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
        "key": "synthetic",
        "clone_version_id": "clone-version",
        "latest": True,
    }


def test_exported_bytes_are_verified_before_copy(tmp_path):
    item = descriptor()
    path = tmp_path / (item["sha256"] + ".blob")
    path.write_bytes(b"synthetic bytes")
    assert copy.payload(tmp_path, item) == b"synthetic bytes"
    path.write_bytes(b"corrupted bytes")
    with pytest.raises(ValueError, match="changed"):
        copy.payload(tmp_path, item)


def test_symlink_and_malformed_digest_are_rejected(tmp_path):
    item = descriptor()
    target = tmp_path / "other"
    target.write_bytes(b"synthetic bytes")
    (tmp_path / (item["sha256"] + ".blob")).symlink_to(target)
    with pytest.raises(ValueError, match="Unsafe"):
        copy.payload(tmp_path, item)
    item["sha256"] = "../other"
    with pytest.raises(ValueError, match="digest"):
        copy.payload(tmp_path, item)


@pytest.mark.parametrize("content", [b"wrong", b"synthetic bytes with extra content"])
def test_wrong_clone_bytes_cannot_pass(content):
    body = io.BytesIO(content)

    class FakeStore:
        def get_bucket_versioning(self, **kwargs):
            return {"Status": "Enabled"}

        def get_object(self, **kwargs):
            return {"Body": body}

    with pytest.raises(ValueError, match="does not match"):
        copy.verify_objects(FakeStore(), "synthetic-clone", [descriptor()])
    assert body.closed


def test_existing_bucket_is_not_written(tmp_path):
    class FakeStore:
        def head_bucket(self, **kwargs):
            return {}

        def create_bucket(self, **kwargs):
            raise AssertionError("Existing bucket must not be written")

    source = {
        "versioning": "Enabled",
        "unchanged_during_audit": True,
        "invalid_objects": [],
        "inventory_after": [],
        "objects": [],
    }
    with pytest.raises(ValueError, match="already exists"):
        copy.copy(FakeStore(), "synthetic-clone", tmp_path, source)


@pytest.mark.parametrize("size", [-1, True, 256 * 1024 * 1024 + 1])
def test_invalid_budget_is_rejected_before_contacting_store(size):
    class NoCalls:
        def __getattr__(self, name):
            raise AssertionError("Invalid input must not contact a store")

    item = descriptor()
    item["size_bytes"] = size
    with pytest.raises(ValueError, match="budget"):
        copy.verify_objects(NoCalls(), "synthetic-clone", [item])


def test_missing_clone_version_is_not_hidden():
    class FakeStore:
        def get_bucket_versioning(self, **kwargs):
            return {"Status": "Enabled"}

        def get_object(self, **kwargs):
            return {"Body": io.BytesIO(b"synthetic bytes")}

        def get_paginator(self, name):
            return self

        def paginate(self, **kwargs):
            return [{"Versions": []}]

    with pytest.raises(ValueError, match="inventory mismatch"):
        copy.verify_objects(FakeStore(), "synthetic-clone", [descriptor()])
