"""Integration test for weekly bulletin generation service and S3 artifacts (SPECS §20, T8.2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ketrika.bulletin.facts import build_bulletin_facts
from ketrika.bulletin.service import generate_weekly_bulletin
from ketrika.core.bronze import get_s3_client
from ketrika.core.db import check_db_connection
from ketrika.core.models.db import Bulletin
from ketrika.core.settings import get_settings
from ketrika.gold.refresh import init_gold_views, refresh_gold_views
from ketrika.pipelines.rebuild import wipe_silver_gold_tables
from tests.e2e_data.synthetic_gold_dataset import seed_synthetic_gold_data


@pytest.fixture
def db_session():
    """Create database session."""
    if not check_db_connection():
        pytest.skip("Database is not reachable (skipping integration tests)")
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session = Session(engine)
    try:
        init_gold_views(session)
        wipe_silver_gold_tables(session)
        seed_synthetic_gold_data(session)
        refresh_gold_views(session)
        session.commit()
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.mark.integration
def test_generate_weekly_bulletin_integration(db_session: Session) -> None:
    """Verify that generate_weekly_bulletin produces a certified draft bulletin with HTML and PDF in S3."""
    settings = get_settings()
    now_utc = datetime.now(UTC)
    p_end = now_utc.date()
    p_start = p_end - timedelta(days=7)

    # 1. Facts extraction
    facts = build_bulletin_facts(db_session, p_start, p_end)
    assert isinstance(facts, dict)
    assert len(facts) >= 1
    assert "sources_attribution" in facts
    assert facts["sources_attribution"]["value"] >= 1

    # 2. Service execution
    bulletin = generate_weekly_bulletin(db_session, p_start, p_end)
    db_session.commit()

    assert bulletin.status == "draft"
    assert bulletin.html_object_key is not None
    assert bulletin.pdf_object_key is not None
    assert bulletin.bulletin_id is not None

    # 3. Verify S3 artifacts existence
    s3 = get_s3_client()
    bucket = settings.s3_bucket_bronze

    html_obj = s3.get_object(Bucket=bucket, Key=bulletin.html_object_key)
    html_data = html_obj["Body"].read().decode("utf-8")
    assert "KETRIKA" in html_data
    assert "Bulletin de Veille PPN Vivriers" in html_data

    pdf_obj = s3.get_object(Bucket=bucket, Key=bulletin.pdf_object_key)
    pdf_bytes = pdf_obj["Body"].read()
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000

    # 4. Check DB retrieval via ORM
    fetched = db_session.get(Bulletin, bulletin.bulletin_id)
    assert fetched is not None
    assert fetched.status == "draft"
    assert fetched.facts is not None
