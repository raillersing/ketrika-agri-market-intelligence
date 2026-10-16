"""Recorded identity resolution on inert SQL/S3 doubles; not live qualification."""

from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from ketrika.connectors.rebuild_references import resolve_snapshot_keys
from ketrika.core.artifact_identity import ArtifactProcessingIdentity
from ketrika.core.bronze import BronzeStore
from ketrika.core.models.db import SourceRecord


@pytest.mark.parametrize(
    "variant",
    ["valid", "legacy", "absent", "ambiguous", "normalizer", "forged", "missing", "duplicate"],
)
def test_resolution_requires_unique_verified_processing_identity_and_archive(variant):
    record = SourceRecord(
        source_record_id=uuid4(),
        source_id="wb_rtfp_mdg",
        parser_version="1.0.0" if variant == "legacy" else "2.0.0",
        content_sha256="a" * 64,
    )
    digest = "b" * 64
    identity = ArtifactProcessingIdentity(
        record.source_id,
        record.source_record_id,
        record.content_sha256,
        record.parser_version,
        "price_normalizer_v2",
        digest,
    )
    row = {
        "processing_key": "0" * 64 if variant == "forged" else identity.processing_key,
        "normalizer_version": "unknown" if variant == "normalizer" else "price_normalizer_v2",
        "reference_manifest_sha256": digest,
    }
    session = Mock(spec=Session)
    session.execute.return_value.mappings.return_value.all.return_value = (
        [] if variant == "absent" else [row, row] if variant == "ambiguous" else [row]
    )
    store = Mock(spec=BronzeStore)
    store.client = Mock()
    store.bucket = "synthetic"
    key = f"reference_manifest/2026/10/{digest}.json"
    keys = [] if variant == "missing" else [key]
    if variant == "duplicate":
        keys.append(f"reference_manifest/2026/09/{digest}.json")
    store.client.get_paginator.return_value.paginate.return_value = [
        {"Contents": [{"Key": value} for value in keys]}
    ]
    if variant in ("valid", "legacy", "absent"):
        expected = {record.source_record_id: (key, digest)} if variant == "valid" else {}
        assert resolve_snapshot_keys(session, [record], store) == expected
        if variant != "valid":
            store.client.get_paginator.assert_not_called()
        if variant == "legacy":
            session.execute.assert_not_called()
    else:
        with pytest.raises(ValueError, match="rebuild_reference_"):
            resolve_snapshot_keys(session, [record], store)
    store.put.assert_not_called()
