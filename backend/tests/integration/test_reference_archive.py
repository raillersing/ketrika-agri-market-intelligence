"""Prepared immutable internal S3 snapshot, never source qualification."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ketrika.core.bronze import BronzeStore
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.reference_archive import archive_reference_manifest
from ketrika.core.reference_manifest import ReferenceRow, build_reference_manifest


class SimulatedDamagedRead:
    def __init__(self, store):
        self.reader = BronzeProofReader(store)

    def get(self, key):
        return self.reader.get(key) + b"simulated damage; no object mutation"


@pytest.mark.integration
@pytest.mark.parametrize("simulate_bad_read", [False, True])
def test_internal_reference_archive_repeats_without_new_versions(simulate_bad_read):
    store = BronzeStore()
    assert store.bucket == "ketrika-qa-bronze"
    assert store.client.get_bucket_versioning(Bucket=store.bucket)["Status"] == "Enabled"
    manifest = build_reference_manifest(
        [
            ReferenceRow(
                "product",
                uuid4().hex,
                json.dumps({"dataset": "synthetic", "source_verified": False}),
            )
        ]
    )
    when = datetime.now(UTC)
    archived = archive_reference_manifest(store, manifest, captured_at=when)
    assert archived.sha256 == manifest.sha256 and archived.row_count == 1
    content = BronzeProofReader(store).get(archived.object_key)
    assert content == manifest.content and hashlib.sha256(content).hexdigest() == manifest.sha256

    def versions():
        response = store.client.list_object_versions(
            Bucket=store.bucket, Prefix=archived.object_key
        )
        assert not response.get("DeleteMarkers")
        return tuple(
            (item["Key"], item["VersionId"], item["Size"])
            for item in response.get("Versions", [])
            if item["Key"] == archived.object_key
        )

    before = versions()
    assert len(before) == 1
    if simulate_bad_read:
        with pytest.raises(ValueError, match="^reference_archive_content_mismatch$"):
            archive_reference_manifest(
                store, manifest, captured_at=when, reader=SimulatedDamagedRead(store)
            )
    else:
        assert archive_reference_manifest(store, manifest, captured_at=when) == archived
    assert versions() == before
    assert BronzeProofReader(store).get(archived.object_key) == manifest.content
