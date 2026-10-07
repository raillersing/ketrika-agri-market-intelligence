"""Alerts router (SPECS §18, §19)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ketrika.api.auth import require_admin
from ketrika.api.errors import NotFoundException
from ketrika.api.schemas import AlertItem, AlertPatchRequest
from ketrika.core.db import get_db
from ketrika.core.models.db import Alert, Location, Product, UserAccount

router = APIRouter(prefix="/v1/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertItem])
def list_alerts(
    severity: str | None = Query(None, description="Filter by severity (low, medium, high)"),
    state: str | None = Query(None, description="Filter by state (open, acknowledged, resolved)"),
    session: Session = Depends(get_db),
) -> list[AlertItem]:
    """List market intelligence alerts (SPECS §18, §19)."""
    stmt = (
        select(Alert, Product.product_code, Location.pcode)
        .outerjoin(Product, Alert.product_id == Product.product_id)
        .outerjoin(Location, Alert.location_id == Location.location_id)
    )
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    if state:
        stmt = stmt.where(Alert.state == state)

    stmt = stmt.order_by(Alert.last_seen_at.desc())
    rows = session.execute(stmt).all()

    items: list[AlertItem] = []
    for alert, prod_code, loc_pcode in rows:
        items.append(
            AlertItem(
                alert_id=alert.alert_id,
                rule_code=alert.rule_code,
                dedupe_key=alert.dedupe_key,
                severity=alert.severity,
                product_code=prod_code,
                location_pcode=loc_pcode,
                title=alert.title,
                evidence=alert.evidence or {},
                state=alert.state,
                first_seen_at=alert.first_seen_at,
                last_seen_at=alert.last_seen_at,
            )
        )
    return items


@router.patch("/{alert_id}", response_model=AlertItem)
def update_alert_state(
    alert_id: uuid.UUID,
    payload: AlertPatchRequest,
    admin_user: UserAccount = Depends(require_admin),
    session: Session = Depends(get_db),
) -> AlertItem:
    """Update alert state (open / acknowledged / resolved). Requires administrator role."""
    alert = session.get(Alert, alert_id)
    if not alert:
        raise NotFoundException(f"Alert {alert_id} not found")

    alert.state = payload.state
    session.flush()

    prod = session.get(Product, alert.product_id) if alert.product_id else None
    prod_code = prod.product_code if prod else None
    loc = session.get(Location, alert.location_id) if alert.location_id else None
    loc_pcode = loc.pcode if loc else None

    return AlertItem(
        alert_id=alert.alert_id,
        rule_code=alert.rule_code,
        dedupe_key=alert.dedupe_key,
        severity=alert.severity,
        product_code=prod_code,
        location_pcode=loc_pcode,
        title=alert.title,
        evidence=alert.evidence or {},
        state=alert.state,
        first_seen_at=alert.first_seen_at,
        last_seen_at=alert.last_seen_at,
    )
