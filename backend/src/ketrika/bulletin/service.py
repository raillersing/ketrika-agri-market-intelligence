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


def get_bulletin(session: Session, bulletin_id: uuid.UUID) -> Bulletin | None:
    """Retrieve a bulletin by its unique ID."""
    return session.get(Bulletin, bulletin_id)


def approve_bulletin(
    session: Session,
    bulletin_id: uuid.UUID,
    approved_by: str,
) -> Bulletin:
    """Approve a draft bulletin with an auditable actor trail (R6.5).

    Note: Approval changes status to 'approved' and records an audit timestamp.
    Under Gate H3, approval DOES NOT trigger external dispatch to real recipients.
    External dispatch is strictly quarantined to Mailpit preview in dev environments.
    """
    bulletin = session.get(Bulletin, bulletin_id)
    if bulletin is None:
        raise ValueError(f"Bulletin {bulletin_id} introuvable.")

    if bulletin.status != "draft":
        raise ValueError(
            f"Impossible d'approuver un bulletin avec le statut '{bulletin.status}' (statut 'draft' requis)."
        )

    now_utc = datetime.now(UTC)
    bulletin.status = "approved"
    bulletin.approved_by = approved_by
    bulletin.approved_at = now_utc

    session.flush()

    logger.info(
        "bulletin_approved_audited",
        bulletin_id=str(bulletin_id),
        approved_by=approved_by,
        approved_at=now_utc.isoformat(),
        gate_h3_enforced=True,
    )
    return bulletin


def send_bulletin_preview_to_mailpit(
    bulletin: Bulletin,
    html_content: str,
    smtp_host: str = "mailpit",
    smtp_port: int = 1025,
) -> bool:
    """Send a draft bulletin preview strictly to local Mailpit (Gate H3, dev only).

    NEVER connects to real external SMTP servers or third-party recipients.
    """
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"[KETRIKA PREVIEW] Bulletin Vivrier PPN - Semaine du {bulletin.period_start} au {bulletin.period_end}"
    )
    msg["From"] = "bulletin-preview@ketrika.local"
    msg["To"] = "preview@mailpit.local"

    part = MIMEText(html_content, "html", "utf-8")
    msg.attach(part)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=5) as server:
            server.sendmail(
                "bulletin-preview@ketrika.local", ["preview@mailpit.local"], msg.as_string()
            )
        logger.info("bulletin_preview_sent_to_mailpit", bulletin_id=str(bulletin.bulletin_id))
        return True
    except Exception as e:
        logger.warning("bulletin_mailpit_preview_skipped", error=str(e))
        return False
