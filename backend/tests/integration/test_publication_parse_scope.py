"""Real isolated SQL: unrelated failures excluded, failed batch siblings retained."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from ketrika.core.db import get_session
from ketrika.core.models.db import IngestionRun, Source, SourceRecord
from ketrika.gold.dq import check_publication_parse_success


@pytest.mark.integration
def test_parse_scope_counts_all_batch_members_but_not_foreign_history():
    with get_session() as session:
        try:
            source_id = "synthetic_parse_scope_" + uuid4().hex
            session.add(Source(source_id=source_id, status="active", spec={"synthetic": True}))
            session.flush()
            records = []
            for status in ["parsed", "failed", "parsed", "failed"]:
                digest = uuid4().hex * 2
                record = SourceRecord(
                    source_record_id=uuid4(),
                    source_id=source_id,
                    source_url="https://example.invalid/synthetic",
                    object_key=f"synthetic/{digest}.json",
                    content_sha256=digest,
                    mime_type="application/json",
                    extraction_status=status,
                    fetched_at=datetime.now(UTC),
                )
                records.append(record)
                session.add(record)
            run = IngestionRun(
                run_id=uuid4(),
                source_id=source_id,
                status="success",
                started_at=datetime.now(UTC),
            )
            session.add(run)
            session.flush()
            session.execute(
                text("""INSERT INTO meta.ingestion_batch
                (run_id, source_id, parser_version, n_artifacts, batch_sha256)
                VALUES (:run, :source, 'synthetic-test', 2, :sha)"""),
                {"run": run.run_id, "source": source_id, "sha": "b" * 64},
            )
            for ordinal, record in enumerate(records[2:]):
                session.execute(
                    text("""INSERT INTO meta.ingestion_batch_member
                    (run_id, ordinal, source_record_id, object_key, content_sha256, mime_type,
                     source_url, is_new)
                    VALUES (:run, :ordinal, :record, :key, :sha, 'application/json',
                        'https://example.invalid/synthetic', true)"""),
                    {
                        "run": run.run_id,
                        "ordinal": ordinal,
                        "record": record.source_record_id,
                        "key": record.object_key,
                        "sha": record.content_sha256,
                    },
                )
            legacy = check_publication_parse_success(session, (records[0].source_record_id,))
            assert legacy.passed and legacy.metric == 100
            batch = check_publication_parse_success(session, (records[2].source_record_id,))
            assert not batch.passed and batch.metric == 50
            assert batch.details["groups"][0]["total"] == 2
            assert not check_publication_parse_success(session, (uuid4(),)).passed
        finally:
            session.rollback()
