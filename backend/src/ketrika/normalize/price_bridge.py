"""Source-locked exact legacy reconciliation; unknown statistics stay unknown."""

import hashlib
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ketrika.connectors.records import PriceRecord
from ketrika.core.models.db import PriceObservation, ReviewItem, SourceRecord
from ketrika.core.quarantine import eligible_observation
from ketrika.normalize.price_identity import IDENTITY_VERSION
from ketrika.normalize.supersede import create_review_item


@dataclass(frozen=True)
class PriceResolution:
    lookup_key: str
    review_id: UUID | None = None
    reviews_created: int = 0


def identity_evidence(record: PriceRecord, source_id: str) -> dict[str, Any]:
    return {
        "version": IDENTITY_VERSION,
        "natural_key": record.compute_natural_key(source_id),
        "statistical_kind": record.value_kind,
        "scope": "internal_exact_raw_grain_not_source_or_human_qualification",
    }


def resolve_price_identity(
    session: Session, record: PriceRecord, source_id: str, source_record_id: UUID
) -> PriceResolution:
    reference = session.get(SourceRecord, source_record_id)
    if reference is None or reference.source_id != source_id:
        raise ValueError("price_identity_source_reference_mismatch")
    natural_key = record.compute_natural_key(source_id)
    digest = hashlib.sha256(b"ketrika_price_identity_source_v2" + source_id.encode()).digest()
    session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": int.from_bytes(digest[:8], "big", signed=True)},
    )
    # Compare all actual dimensions, not the ambiguous historical digest. This
    # also discovers a known legacy row even when a canonical row coexists.
    dimensions = (
        "product_raw",
        "variety",
        "location_raw",
        "actor_level",
        "period_start",
        "period_end",
        "unit_raw",
        "currency_raw",
        "observed_or_imputed",
    )
    candidates = list(
        session.scalars(
            select(PriceObservation)
            .join(SourceRecord, PriceObservation.source_record_id == SourceRecord.source_record_id)
            .where(
                SourceRecord.source_id == source_id,
                PriceObservation.superseded_by.is_(None),
                eligible_observation(PriceObservation),
                *(
                    getattr(PriceObservation, field) == getattr(record, field)
                    for field in dimensions
                ),
            )
            .order_by(PriceObservation.observation_id)
            .with_for_update(of=PriceObservation)
        )
    )
    matching = []
    unknown = []
    for candidate in candidates:
        evidence = candidate.evidence if isinstance(candidate.evidence, dict) else {}
        normal = evidence.get("normalization", {})
        identity = evidence.get("price_identity", {})
        kind = normal.get("value_kind") if isinstance(normal, dict) else None
        recorded = identity.get("statistical_kind") if isinstance(identity, dict) else None
        if recorded is not None and kind is not None and recorded != kind:
            unknown.append(candidate)
        elif not isinstance(kind if kind is not None else recorded, str) or (
            kind if kind is not None else recorded
        ) not in {"point", "min", "max", "avg"}:
            unknown.append(candidate)
        elif (kind if kind is not None else recorded) == record.value_kind:
            matching.append(candidate)
    if not unknown and len(matching) <= 1:
        return PriceResolution(matching[0].natural_key if matching else natural_key)
    payload = {
        "reason": "price_legacy_identity_ambiguous",
        "source_id": source_id,
        "natural_key": natural_key,
        "candidate_ids": sorted(str(row.observation_id) for row in matching + unknown),
        "human_reviewed": False,
    }
    existing = session.scalar(
        select(ReviewItem).where(
            ReviewItem.source_record_id == source_record_id,
            ReviewItem.kind == "extraction_conflict",
            ReviewItem.payload == payload,
        )
    )
    if existing is not None:
        return PriceResolution(natural_key, existing.review_id, 0)
    review = create_review_item(session, "extraction_conflict", payload, source_record_id)
    return PriceResolution(natural_key, review.review_id, 1)
