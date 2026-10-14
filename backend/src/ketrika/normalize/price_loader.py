"""Normalize before append-only load; caller owns the transaction (ADR-037)."""

import re
import unicodedata
from copy import deepcopy
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from ketrika.connectors.records import PriceRecord
from ketrika.core.models.db import PriceObservation, SourceRecord
from ketrika.normalize.decimal_price import ParsedPrice, convert_price, parse_price
from ketrika.normalize.price_bridge import identity_evidence, resolve_price_identity
from ketrika.normalize.price_references import resolve_location, resolve_product, unit_factor
from ketrika.normalize.reference_snapshot import ReferenceSnapshot, reference_snapshot_evidence
from ketrika.normalize.supersede import create_review_item, load_observation_with_supersession


@dataclass(frozen=True)
class NormalizedLoad:
    action: str
    observation_id: UUID | None
    review_items: int


def load_normalized_price(
    session: Session,
    record: PriceRecord,
    source_id: str,
    source_record_id: UUID,
    *,
    admin_level: int | None = None,
    reference_snapshot: ReferenceSnapshot | None = None,
) -> NormalizedLoad:
    """No collect, seed, commit, alias insertion or update of an observed value."""
    reference = session.get(SourceRecord, source_record_id)
    if reference is None or reference.source_id != source_id:
        raise ValueError("normalization_source_reference_mismatch")
    resolution = resolve_price_identity(session, record, source_id, source_record_id)
    if resolution.review_id is not None:
        return NormalizedLoad("review_required", None, resolution.reviews_created)
    snapshot_evidence = (
        reference_snapshot_evidence(session, reference_snapshot)
        if reference_snapshot is not None
        else None
    )
    if (
        record.period_end < record.period_start
        or record.observed_or_imputed not in {"observed", "imputed"}
        or record.value_kind not in {"point", "min", "max", "avg"}
        or record.actor_level
        not in {"retail", "wholesale", "farmgate", "producer", "official_ppn", "listing", "unknown"}
    ):
        raise ValueError("invalid_price_classification")
    extraction_confidence = Decimal(str(record.confidence))
    if not extraction_confidence.is_finite() or not 0 <= extraction_confidence <= 1:
        raise ValueError("invalid_extraction_confidence")
    proof = record.evidence.get("provenance", {})
    style = proof.get("number_style", "decimal_dot") if isinstance(proof, dict) else "decimal_dot"
    parsed = parse_price(record.price_raw, number_style=style)
    if (
        parsed.issue is None
        and (not isinstance(proof, dict) or "number_style" not in proof)
        and re.fullmatch(
            r"[+-]?\d{1,3}(?:\.\d{3})+",
            unicodedata.normalize("NFKC", record.price_raw).strip().replace(" ", ""),
        )
    ):
        parsed = ParsedPrice(None, issue="ambiguous_price_number_style")
    issues: list[tuple[str, str]] = []
    if record.missing_code and record.missing_code != parsed.missing_code:
        raise ValueError("inconsistent_price_missing_code")
    if parsed.issue:
        issues.append(("extraction_conflict", parsed.issue))
    product = resolve_product(session, record.product_raw, source_id)
    location = resolve_location(session, record.location_raw, source_id, admin_level=admin_level)
    if product is None:
        issues.append(("unknown_product", "unresolved_or_ambiguous_product"))
    if location is None:
        issues.append(("unknown_location", "unresolved_or_ambiguous_location"))
    factor = unit_factor(session, record.unit_raw, product.entity.product_id) if product else None
    converted = convert_price(
        parsed.value,
        record.currency_raw,
        factor=Decimal(str(factor.factor)) if factor else None,
        factor_confidence=Decimal(str(factor.confidence)) if factor else Decimal(0),
        factor_evidence=factor.evidence if factor else None,
        base_unit=factor.base_unit if factor else None,
        product_base_unit=product.entity.base_unit if product else None,
    )
    if converted.issue and parsed.value is not None:
        issues.append(("unit_conversion", converted.issue))
    confidence = min(
        extraction_confidence,
        product.confidence if product else Decimal(0),
        location.confidence if location else Decimal(0),
        Decimal(str(factor.confidence)) if factor else Decimal(0),
    ).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    evidence = deepcopy(record.evidence)
    evidence["normalization"] = {
        "version": 2,
        "human_reviewed": False,
        "confidence_definition": "minimum_configured_components_not_calibrated_probability",
        "value_kind": record.value_kind,
        "number_style": style,
        "product_match": product.method if product else None,
        "product_references": list(product.reference_ids) if product else [],
        "location_match": location.method if location else None,
        "location_references": list(location.reference_ids) if location else [],
        "factor": str(factor.factor) if factor else None,
        "factor_confidence": str(factor.confidence) if factor else None,
        "factor_evidence": factor.evidence if factor else None,
        "scope": "configured_reference_conversion_not_market_or_source_qualification",
    }
    comparable = converted.price_mga_per_base if not issues else None
    evidence["price_identity"] = identity_evidence(record, source_id)
    if snapshot_evidence is not None:
        evidence["normalization"]["reference_snapshot"] = snapshot_evidence
    values = {
        "product_raw": record.product_raw,
        "product_id": product.entity.product_id if product else None,
        "location_raw": record.location_raw,
        "location_id": location.entity.location_id if location else None,
        "actor_level": record.actor_level,
        "period_start": record.period_start,
        "period_end": record.period_end,
        "published_at": record.published_at,
        "price_raw": record.price_raw,
        "price_value": parsed.value,
        "unit_raw": record.unit_raw,
        "currency_raw": record.currency_raw,
        "price_mga_per_base": comparable,
        "base_unit": converted.base_unit,
        "conversion_status": converted.conversion_status if comparable is not None else "uncertain",
        "missing_code": parsed.missing_code,
        "observed_or_imputed": record.observed_or_imputed,
        "variety": record.variety,
        "extraction_method": record.extraction_method,
        "confidence": confidence,
        "review_status": "pending" if issues else "accepted",
    }
    natural_key = record.compute_natural_key(source_id)

    def build(observation_id: UUID) -> PriceObservation:
        return PriceObservation(
            observation_id=observation_id,
            source_record_id=source_record_id,
            natural_key=natural_key,
            evidence=evidence,
            **values,
        )

    # Compare semantic classification as well as raw and derived values. Full
    # evidence is not compared: a repeated artifact must not create duplicates.
    comparison_evidence: dict[tuple[str, ...], Any] = {
        ("normalization", "value_kind"): record.value_kind
    }
    if snapshot_evidence is not None:
        comparison_evidence[("normalization", "reference_snapshot", "sha256")] = snapshot_evidence[
            "sha256"
        ]
    action, observation_id = load_observation_with_supersession(
        session,
        PriceObservation,
        natural_key,
        build,
        values,
        evidence_fields=comparison_evidence,
        lookup_key=resolution.lookup_key,
    )
    if action not in {"inserted", "superseded", "idempotent_skipped"}:
        raise ValueError("normalization_loader_action_invalid")
    if action != "idempotent_skipped":
        for kind, reason in issues:
            create_review_item(
                session,
                kind,
                {
                    "source_id": source_id,
                    "observation_id": str(observation_id),
                    "reason": reason,
                    "normalization_version": 2,
                },
                source_record_id,
            )
    return NormalizedLoad(
        action, observation_id, len(issues) if action != "idempotent_skipped" else 0
    )
