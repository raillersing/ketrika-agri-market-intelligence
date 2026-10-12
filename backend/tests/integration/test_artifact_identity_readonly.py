"""Prepared SQL identity binding, not artifact bytes or a durable ledger."""

from dataclasses import replace

import pytest
from sqlalchemy import select, text

from ketrika.core.artifact_identity import ArtifactProcessingIdentity
from ketrika.core.db import get_session
from ketrika.core.models.db import SourceRecord
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.core.reference_manifest import read_reference_manifest


@pytest.mark.integration
def test_identity_uses_explicit_sql_reference_and_actual_manifest_without_writes():
    with get_session() as session:
        target = session.get_bind().engine.url
        require_synthetic_test_database(target.host, target.database)
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        assert session.scalar(text("SHOW transaction_read_only")) == "on"
        reference = session.scalar(
            select(SourceRecord)
            .where(SourceRecord.parser_version.is_not(None))
            .order_by(SourceRecord.source_record_id)
            .limit(1)
        )
        assert reference is not None, "synthetic QA reference required; do not fabricate or skip"
        manifest = read_reference_manifest(session)
        assert manifest.row_count > 0
        identity = ArtifactProcessingIdentity(
            reference.source_id,
            reference.source_record_id,
            reference.content_sha256,
            reference.parser_version,
            "1",
            manifest.sha256,
        )
        assert identity.processing_key == replace(identity).processing_key
        assert identity.reference_manifest_sha256 == read_reference_manifest(session).sha256
        assert identity.source_record_id == reference.source_record_id
        assert (
            replace(identity, parser_version="synthetic-test-change").processing_key
            != identity.processing_key
        )
        assert (
            replace(identity, normalizer_version="synthetic-test-change").processing_key
            != identity.processing_key
        )
        # Explicit synthetic changed snapshot digest, not a claimed stored artifact.
        assert (
            replace(identity, reference_manifest_sha256="0" * 64).processing_key
            != identity.processing_key
        )
        session.rollback()
