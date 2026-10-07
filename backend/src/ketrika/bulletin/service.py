"""Weekly bulletin orchestrator and generator service (SPECS §20)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from ketrika.bulletin.facts import build_bulletin_facts
from ketrika.bulletin.render import (
    render_html,
    render_pdf,
    save_bulletin_artifacts,
    substitute_facts,
)
from ketrika.bulletin.writer import generate_bulletin_prose
from ketrika.core.logging import get_logger
from ketrika.core.models.db import Bulletin

logger = get_logger(__name__)


def generate_weekly_bulletin(
    session: Session,
    period_start: date | None = None,
    period_end: date | None = None,
    llm_client: Any = None,
) -> Bulletin:
    """Generate a weekly market intelligence bulletin end-to-end.

    Steps:
    1. Extract verified facts dictionary from Gold views.
    2. Generate commentary prose with strict placeholder verification (fallback on template if invalid).
    3. Substitute fact values and render HTML + WeasyPrint PDF.
    4. Store artifacts in S3 and persist ops.bulletin record with status 'draft'.
    """
    now_utc = datetime.now(UTC)
    p_end = period_end or now_utc.date()
    p_start = period_start or (p_end - timedelta(days=7))

    logger.info(
        "bulletin_generation_started",
        period_start=p_start.isoformat(),
        period_end=p_end.isoformat(),
    )

    # 1. Facts extraction
    facts = build_bulletin_facts(session, p_start, p_end)
    logger.info("bulletin_facts_built", fact_count=len(facts))

    # 2. Prose generation
    prose_template, is_fallback = generate_bulletin_prose(
        facts, p_start, p_end, llm_client=llm_client
    )

    # 3. Facts substitution
    substituted_md = substitute_facts(prose_template, facts, p_start, p_end)

    # 4. Render HTML and PDF
    html_content = render_html(substituted_md, facts, p_start, p_end)
    pdf_bytes = render_pdf(html_content)

    # 5. Save S3 artifacts
    bulletin_id = uuid.uuid4()
    html_key, pdf_key = save_bulletin_artifacts(bulletin_id, html_content, pdf_bytes)

    # 6. Database record
    bulletin = Bulletin(
        bulletin_id=bulletin_id,
        period_start=p_start,
        period_end=p_end,
        status="draft",
        facts=facts,
        html_object_key=html_key,
        pdf_object_key=pdf_key,
        created_at=now_utc,
    )
    session.add(bulletin)
    session.flush()

    logger.info(
        "bulletin_generation_completed",
        bulletin_id=str(bulletin_id),
        status=bulletin.status,
        is_fallback=is_fallback,
    )
    return bulletin
