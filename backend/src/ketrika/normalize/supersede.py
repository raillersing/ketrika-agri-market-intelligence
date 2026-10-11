"""Generic supersession and review item handling (SPECS §8.1, §13)."""

from __future__ import annotations

import uuid
from typing import Any, TypeVar

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ketrika.core.models.db import Base, ReviewItem

T = TypeVar("T", bound=Base)


def create_review_item(
    session: Session,
    kind: str,
    payload: dict[str, Any],
    source_record_id: uuid.UUID | None = None,
) -> ReviewItem:
    """Create a human review queue item in ops.review_item (SPECS §8.1, §13)."""
    item = ReviewItem(
        review_id=uuid.uuid4(),
        kind=kind,
        source_record_id=source_record_id,
        payload=payload,
        status="open",
    )
    session.add(item)
    session.flush()
    return item


def load_observation_with_supersession[T: Base](
    session: Session,
    model_cls: type[T],
    natural_key: str,
    create_instance_fn: Any,  # Callable[[uuid.UUID], T]
    compare_attrs: dict[str, Any],
    evidence_fields: dict[tuple[str, ...], Any] | None = None,
) -> tuple[str, uuid.UUID]:
    """Load observation into an obs table following SPECS §8.1 supersession logic.

    Rules:
    - If no current row (natural_key == nk AND superseded_by IS NULL):
        INSERT new row (action = 'inserted').
    - If current row exists and all compare_attrs match:
        Do nothing (action = 'idempotent_skipped').
    - If current row exists and values differ:
        In single transaction: UPDATE current row SET superseded_by = new_id,
        then INSERT new row with observation_id = new_id (action = 'superseded').

    Returns: (action, observation_id)
    """
    model_any: Any = model_cls
    stmt = select(model_cls).where(
        model_any.natural_key == natural_key,
        model_any.superseded_by.is_(None),
    )
    current_obs = session.execute(stmt).scalar_one_or_none()

    if current_obs is None:
        new_id = uuid.uuid4()
        new_obs = create_instance_fn(new_id)
        session.add(new_obs)
        session.flush()
        return "inserted", new_id

    # Check if identical
    is_identical = True
    for attr, expected_val in compare_attrs.items():
        current_val = getattr(current_obs, attr, None)
        # Normalize float comparison
        if isinstance(expected_val, float) and current_val is not None:
            if round(float(current_val), 4) != round(expected_val, 4):
                is_identical = False
                break
        elif current_val != expected_val:
            is_identical = False
            break

    for path, expected_value in (evidence_fields or {}).items():
        current_value = getattr(current_obs, "evidence", None)
        for key in path:
            current_value = current_value.get(key) if isinstance(current_value, dict) else None
        if current_value != expected_value:
            is_identical = False
            break

    obs_any: Any = current_obs
    if is_identical:
        current_id: uuid.UUID = obs_any.observation_id
        return "idempotent_skipped", current_id

    # Supersede existing observation
    new_id = uuid.uuid4()
    current_pk: uuid.UUID = obs_any.observation_id
    upd_stmt = (
        update(model_cls).where(model_any.observation_id == current_pk).values(superseded_by=new_id)
    )
    session.execute(upd_stmt)
    session.flush()

    new_obs = create_instance_fn(new_id)
    session.add(new_obs)
    session.flush()

    return "superseded", new_id
