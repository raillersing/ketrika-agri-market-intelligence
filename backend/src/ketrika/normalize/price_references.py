"""Source-scoped SQL reference matching; ambiguity never silently wins."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ketrika.core.models.db import Location, LocationAlias, Product, ProductAlias, UnitConversion
from ketrika.normalize.locations import normalize_location_string
from ketrika.normalize.products import normalize_product_string


@dataclass(frozen=True)
class ReferenceMatch:
    entity: Any
    confidence: Decimal
    method: str
    reference_ids: tuple[str, ...]


def _unique(rows: Sequence[Any], identity: str, method: str) -> ReferenceMatch | None:
    if not rows:
        return None
    identifiers = {getattr(row[0], identity) for row in rows}
    confidences = [Decimal(str(row[1])) for row in rows]
    if len(identifiers) != 1 or any(
        not confidence.is_finite() or not Decimal("0.85") <= confidence <= 1
        for confidence in confidences
    ):
        return None
    return ReferenceMatch(
        rows[0][0], min(confidences), method, tuple(sorted({str(row[2]) for row in rows}))
    )


def resolve_product(session: Session, raw: str, source_id: str) -> ReferenceMatch | None:
    normalized = normalize_product_string(raw)
    if not normalized:
        return None
    for scope, method in ((source_id, "exact_source_alias"), (None, "exact_global_alias")):
        query = (
            select(Product, ProductAlias.confidence, ProductAlias.alias_id)
            .join(ProductAlias, ProductAlias.product_id == Product.product_id)
            .where(ProductAlias.alias_norm == normalized, ProductAlias.source_id == scope)
        )
        rows = session.execute(query).all()
        if rows:
            return _unique(rows, "product_id", method)
    score = func.similarity(ProductAlias.alias_norm, normalized)
    rows = session.execute(
        select(Product, func.least(ProductAlias.confidence, score), ProductAlias.alias_id)
        .join(ProductAlias, ProductAlias.product_id == Product.product_id)
        .where(
            ProductAlias.source_id.is_(None) | (ProductAlias.source_id == source_id),
            score >= Decimal("0.85"),
        )
    ).all()
    return _unique(rows, "product_id", "fuzzy_trigram")


def resolve_location(
    session: Session, raw: str | None, source_id: str, *, admin_level: int | None = None
) -> ReferenceMatch | None:
    if not raw:
        return None
    normalized = normalize_location_string(raw)
    if not normalized:
        return None
    pcode_query = select(Location).where(Location.pcode == raw.strip().upper())
    if admin_level is not None:
        pcode_query = pcode_query.where(Location.admin_level == admin_level)
    pcodes = session.scalars(pcode_query).all()
    if pcodes:
        return _unique(
            [(row, Decimal(1), row.pcode) for row in pcodes], "location_id", "exact_pcode"
        )
    for scope, method in ((source_id, "exact_source_alias"), (None, "exact_global_alias")):
        query = (
            select(Location, LocationAlias.confidence, LocationAlias.alias_norm)
            .join(LocationAlias, LocationAlias.location_id == Location.location_id)
            .where(LocationAlias.alias_norm == normalized, LocationAlias.source_id == scope)
        )
        if admin_level is not None:
            query = query.where(Location.admin_level == admin_level)
        rows = session.execute(query).all()
        if rows:
            return _unique(rows, "location_id", method)
    if admin_level is None:
        return None
    score = func.similarity(LocationAlias.alias_norm, normalized)
    rows = session.execute(
        select(Location, func.least(LocationAlias.confidence, score), LocationAlias.alias_norm)
        .join(LocationAlias, LocationAlias.location_id == Location.location_id)
        .where(
            LocationAlias.source_id.is_(None) | (LocationAlias.source_id == source_id),
            Location.admin_level == admin_level,
            score >= Decimal("0.85"),
        )
    ).all()
    return _unique(rows, "location_id", "fuzzy_trigram")


def unit_factor(session: Session, unit_raw: str, product_id: UUID) -> UnitConversion | None:
    """No generic 'sac' assumption; only an explicit registered unit."""
    normalized = unit_raw.strip().lower()
    aliases = {
        "kilogramme": "kg",
        "kilogrammes": "kg",
        "kilo": "kg",
        "litre": "l",
        "litres": "l",
        "liter": "l",
        "gramme": "g",
        "grammes": "g",
        "tonne": "t",
        "tonnes": "t",
        "sac 50kg": "sac_50kg",
        "sac 50 kg": "sac_50kg",
        "sac 25kg": "sac_25kg",
        "sac 25 kg": "sac_25kg",
    }
    normalized = aliases.get(normalized, normalized)
    for scope in (product_id, None):
        rows = session.scalars(
            select(UnitConversion).where(
                UnitConversion.unit_code == normalized, UnitConversion.product_id == scope
            )
        ).all()
        if rows:
            return rows[0] if len(rows) == 1 else None
    return None
