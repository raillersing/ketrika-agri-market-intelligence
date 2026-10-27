"""Bulletins router (SPECS §19, §20)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ketrika.api.auth import require_admin
from ketrika.api.errors import NotFoundException
from ketrika.api.schemas import BulletinItem
from ketrika.core.db import get_db
from ketrika.core.models.db import Bulletin, UserAccount

router = APIRouter(prefix="/v1/bulletins", tags=["bulletins"])


@router.get("", response_model=list[BulletinItem])
def list_bulletins(session: Session = Depends(get_db)) -> list[BulletinItem]:
    """List weekly market bulletins (SPECS §19, §20)."""
    stmt = select(Bulletin).order_by(Bulletin.period_end.desc())
    bulletins = list(session.execute(stmt).scalars().all())

    return [
        BulletinItem(
            bulletin_id=b.bulletin_id,
            period_start=str(b.period_start),
            period_end=str(b.period_end),
            status=b.status,
            facts=b.facts or {},
            created_at=b.created_at,
            approved_at=b.approved_at,
            approved_by=b.approved_by,
        )
        for b in bulletins
    ]


@router.get("/{bulletin_id}", response_model=BulletinItem)
def get_bulletin(
    bulletin_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> BulletinItem:
    """Retrieve single market bulletin by ID."""
    b = session.get(Bulletin, bulletin_id)
    if not b:
        raise NotFoundException(f"Bulletin {bulletin_id} not found")

    return BulletinItem(
        bulletin_id=b.bulletin_id,
        period_start=str(b.period_start),
        period_end=str(b.period_end),
        status=b.status,
        facts=b.facts or {},
        created_at=b.created_at,
        approved_at=b.approved_at,
        approved_by=b.approved_by,
    )


@router.post("/{bulletin_id}/approve", response_model=BulletinItem)
def approve_bulletin(
    bulletin_id: uuid.UUID,
    admin_user: UserAccount = Depends(require_admin),
    session: Session = Depends(get_db),
) -> BulletinItem:
    """Approve draft market bulletin for distribution. Requires administrator role."""
    b = session.get(Bulletin, bulletin_id)
    if not b:
        raise NotFoundException(f"Bulletin {bulletin_id} not found")

    b.status = "approved"
    b.approved_at = datetime.now(UTC)
    b.approved_by = admin_user.email
    session.flush()
    session.commit()

    return BulletinItem(
        bulletin_id=b.bulletin_id,
        period_start=str(b.period_start),
        period_end=str(b.period_end),
        status=b.status,
        facts=b.facts or {},
        created_at=b.created_at,
        approved_at=b.approved_at,
        approved_by=b.approved_by,
    )
