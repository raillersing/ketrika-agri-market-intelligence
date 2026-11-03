"""Eligibility predicates; quarantine is never an observation revision."""

from typing import Any
from uuid import UUID

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from ketrika.core.models.db import Base, QuarantineLedger


def eligible_observation(model: type[Base]) -> ColumnElement[bool]:
    row: Any = model
    source_excluded = and_(
        QuarantineLedger.table_name == "meta.source_record",
        or_(
            QuarantineLedger.observation_id == row.source_record_id,
            QuarantineLedger.source_record_id == row.source_record_id,
        ),
    )
    observation_excluded = and_(
        QuarantineLedger.table_name == row.__table__.fullname,
        QuarantineLedger.observation_id == row.observation_id,
    )
    return ~exists().where(
        QuarantineLedger.revoked_at.is_(None), or_(source_excluded, observation_excluded)
    ).correlate(model)


def require_eligible_source(session: Session, identifier: Any) -> None:
    try:
        source_id = UUID(str(identifier))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("observation_source_identity_required") from None
    excluded = session.scalar(
        select(
            exists().where(
                QuarantineLedger.table_name == "meta.source_record",
                QuarantineLedger.revoked_at.is_(None),
                or_(
                    QuarantineLedger.observation_id == source_id,
                    QuarantineLedger.source_record_id == source_id,
                ),
            )
        )
    )
    if type(excluded) is not bool:
        raise ValueError("quarantine_check_unavailable")
    if excluded:
        raise ValueError("observation_source_quarantined")


def require_eligible_observation(session: Session, model: type[Base], identifier: Any) -> None:
    row: Any = model
    try:
        observation_id = UUID(str(identifier))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("observation_identity_required") from None
    excluded = session.scalar(
        select(~eligible_observation(model)).where(row.observation_id == observation_id)
    )
    if type(excluded) is not bool:
        raise ValueError("quarantine_check_unavailable")
    if excluded:
        raise ValueError("observation_quarantined_identity_reserved")


def require_no_active_quarantine(session: Session) -> None:
    excluded = session.scalar(select(exists().where(QuarantineLedger.revoked_at.is_(None))))
    if type(excluded) is not bool:
        raise ValueError("quarantine_check_unavailable")
    if excluded:
        raise ValueError("rebuild_quarantine_preservation_required")
