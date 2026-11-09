"""Admin and DataOps management router (SPECS §19)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ketrika.api.auth import create_api_key_for_user, require_admin
from ketrika.api.errors import BadRequestException, NotFoundException
from ketrika.api.schemas import (
    ApiKeyCreateRequest,
    ApiKeyResponse,
    GoldDomainRefreshResponse,
    ReviewItemOut,
    ReviewResolveRequest,
)
from ketrika.core.db import get_db
from ketrika.core.models.db import ReviewItem, UserAccount

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get("/review", response_model=list[ReviewItemOut])
def list_review_items(
    status: str | None = Query(
        "open", description="Filter by status (open, approved, rejected, created_alias)"
    ),
    admin_user: UserAccount = Depends(require_admin),
    session: Session = Depends(get_db),
) -> list[ReviewItemOut]:
    """List items in human review queue (unknown products, out of bounds, ambiguities). Requires admin."""
    stmt = select(ReviewItem)
    if status:
        stmt = stmt.where(ReviewItem.status == status)
    stmt = stmt.order_by(ReviewItem.created_at.desc())
    items = list(session.execute(stmt).scalars().all())

    return [
        ReviewItemOut(
            review_id=r.review_id,
            kind=r.kind,
            source_record_id=r.source_record_id,
            payload=r.payload or {},
            status=r.status,
            created_at=r.created_at,
            resolved_at=r.resolved_at,
            resolved_by=r.resolved_by,
        )
        for r in items
    ]


@router.post("/review/{review_id}", response_model=ReviewItemOut)
def resolve_review_item(
    review_id: uuid.UUID,
    payload: ReviewResolveRequest,
    admin_user: UserAccount = Depends(require_admin),
    session: Session = Depends(get_db),
) -> ReviewItemOut:
    """Resolve a review item (approved, rejected, created_alias). Requires admin."""
    item = session.get(ReviewItem, review_id)
    if not item:
        raise NotFoundException(f"Review item {review_id} not found")

    item.status = payload.status
    item.resolved_at = datetime.now(UTC)
    item.resolved_by = admin_user.email
    session.flush()

    return ReviewItemOut(
        review_id=item.review_id,
        kind=item.kind,
        source_record_id=item.source_record_id,
        payload=item.payload or {},
        status=item.status,
        created_at=item.created_at,
        resolved_at=item.resolved_at,
        resolved_by=item.resolved_by,
    )


@router.post("/api-keys", response_model=ApiKeyResponse)
def create_api_key(
    payload: ApiKeyCreateRequest,
    admin_user: UserAccount = Depends(require_admin),
    session: Session = Depends(get_db),
) -> ApiKeyResponse:
    """Create a new programmatic API key. The raw_key is only returned once upon creation! Requires admin."""
    raw_key, api_key_obj = create_api_key_for_user(session, admin_user)
    session.commit()

    return ApiKeyResponse(
        api_key_id=api_key_obj.api_key_id,
        prefix=api_key_obj.prefix,
        raw_key=raw_key,
        created_at=api_key_obj.created_at,
        revoked_at=api_key_obj.revoked_at,
        last_used_at=api_key_obj.last_used_at,
    )


@router.post("/gold/refresh", response_model=GoldDomainRefreshResponse)
def refresh_gold(
    domain: str | None = Query(
        None,
        description="Optional domain (price, trade, climate, macro). If omitted, refreshes all domains independently.",
    ),
    concurrently: bool = Query(False, description="Whether to refresh concurrently if possible."),
    admin_user: UserAccount = Depends(require_admin),
    session: Session = Depends(get_db),
) -> GoldDomainRefreshResponse:
    """Trigger a refresh of Gold materialized views by domain or across all domains independently (IA-DATA-06)."""
    from ketrika.gold.dq import GoldDqRejected
    from ketrika.gold.refresh import (
        GOLD_DOMAINS,
        refresh_all_domains_independent,
        refresh_domain_views,
    )

    if domain is not None:
        if domain not in GOLD_DOMAINS:
            raise BadRequestException(
                f"unsupported_gold_domain: {domain}. Allowed domains: {sorted(GOLD_DOMAINS.keys())}"
            )
        try:
            res = refresh_domain_views(session, domain=domain, concurrently=concurrently)
            return GoldDomainRefreshResponse(
                status="success",
                domains_succeeded=[domain],
                domains_failed=[],
                domain_errors={},
                views_refreshed=res.get("views_refreshed", []),
                count=len(res.get("views_refreshed", [])),
                refreshed_at=datetime.now(UTC),
            )
        except (GoldDqRejected, ValueError) as exc:
            return GoldDomainRefreshResponse(
                status="failed",
                domains_succeeded=[],
                domains_failed=[domain],
                domain_errors={domain: str(exc)},
                views_refreshed=[],
                count=0,
                refreshed_at=datetime.now(UTC),
            )

    res = refresh_all_domains_independent(session, concurrently=concurrently)
    return GoldDomainRefreshResponse(
        status=res["status"],
        domains_succeeded=res["domains_succeeded"],
        domains_failed=res["domains_failed"],
        domain_errors=res["domain_errors"],
        views_refreshed=res["views_refreshed"],
        count=res["count"],
        refreshed_at=datetime.now(UTC),
    )

