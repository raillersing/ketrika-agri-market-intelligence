"""Gold aggregation guards and mathematical consistency invariants (SPECS §6, §7, R2.2).

Directive R2.2:
- Interdire moyenne entre devises/unités/indices/acteurs incompatibles.
- Conversions massiques/volumiques sans densité prouvée refusées.
- Conversions faible confiance exclues des prix comparables.
- Ni ND ni lieu inconnu remplacés par zéro ou défaut.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal


class IncompatibleAggregationError(ValueError):
    """Raised when an aggregation violates physical, economic, or semantic comparability."""


@dataclass(frozen=True)
class ComparablePriceItem:
    """Represents a price observation candidate for Gold aggregation."""

    price_mga_per_base: Decimal | None
    base_unit: str | None
    currency: str = "MGA"
    actor_level: str = "retail"
    value_kind: str = "point"
    conversion_status: str = "exact"
    confidence: Decimal = Decimal("1.0")
    is_index: bool = False
    product_code: str | None = None
    location_id: str | None = None
    period_start: date | None = None
    period_end: date | None = None


def validate_comparable_group(
    items: Sequence[ComparablePriceItem],
    *,
    allow_mixed_actors: bool = False,
) -> None:
    """Validate that a collection of price observations forms a semantically sound group.

    Rules:
    1. No index numbers (e.g. NIPC base 100) mixed with nominal price observations.
    2. No mixed currencies (all observations must be normalized to MGA).
    3. No mixed physical units (cannot average kg and l).
    4. No cross mass/volume without density (base_unit must be valid and uniform).
    5. No unsegmented actor levels (cannot aggregate farmgate and retail without explicit opt-in).
    6. Non-empty sequence required.
    """
    if not items:
        raise ValueError("empty_aggregation_group")

    # 1. Index vs nominal price check
    has_index = any(item.is_index for item in items)
    has_nominal = any(not item.is_index for item in items)
    if has_index and has_nominal:
        raise IncompatibleAggregationError(
            "cannot_aggregate_index_with_nominal_prices: indices and prices cannot be averaged together"
        )
    if has_index:
        raise IncompatibleAggregationError(
            "cannot_aggregate_index_as_price: index series require dedicated statistical chaining"
        )

    # 2. Currency check
    currencies = {item.currency.strip().upper() for item in items if item.currency}
    if len(currencies) > 1 or (currencies and "MGA" not in currencies):
        raise IncompatibleAggregationError(
            f"incompatible_currencies_in_aggregation: all prices must be in MGA, found {currencies}"
        )

    # 3. Base unit check
    base_units = {item.base_unit for item in items if item.base_unit}
    if len(base_units) > 1:
        raise IncompatibleAggregationError(
            f"cannot_aggregate_mixed_base_units: cannot average incompatible units {base_units}"
        )
    if not base_units or any(u not in {"kg", "l"} for u in base_units):
        raise IncompatibleAggregationError(
            f"invalid_base_unit_in_aggregation: base units must be in {{'kg', 'l'}}, found {base_units}"
        )

    # 4. Product code consistency
    products = {item.product_code for item in items if item.product_code}
    if len(products) > 1:
        raise IncompatibleAggregationError(
            f"cannot_aggregate_multiple_products: found multiple product codes {products}"
        )

    # 5. Actor level consistency
    if not allow_mixed_actors:
        actors = {item.actor_level for item in items if item.actor_level}
        if len(actors) > 1:
            raise IncompatibleAggregationError(
                f"cannot_aggregate_incompatible_actor_levels: mixing {actors} requires explicit segmentation"
            )


def filter_comparable_items(
    items: Sequence[ComparablePriceItem],
) -> list[ComparablePriceItem]:
    """Filter out non-comparable items (uncertain conversion, confidence < 0.80, or missing value).

    Ni ND ni valeur manquante ne sont remplacés par zéro.
    """
    valid: list[ComparablePriceItem] = []
    for item in items:
        if item.price_mga_per_base is None:
            continue
        if item.conversion_status == "uncertain":
            continue
        if item.confidence < Decimal("0.80"):
            continue
        if item.price_mga_per_base <= 0:
            continue
        valid.append(item)
    return valid


def compute_safe_arithmetic_average(
    items: Sequence[ComparablePriceItem],
    *,
    allow_mixed_actors: bool = False,
) -> Decimal | None:
    """Compute arithmetic average of comparable prices in MGA per base unit.

    Returns None if no qualifying observations exist (never 0).
    """
    valid = filter_comparable_items(items)
    if not valid:
        return None

    validate_comparable_group(valid, allow_mixed_actors=allow_mixed_actors)

    total = sum(
        (item.price_mga_per_base for item in valid if item.price_mga_per_base is not None),
        start=Decimal("0"),
    )
    avg = total / Decimal(len(valid))
    return avg.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def compute_safe_weighted_average(
    weighted_items: Sequence[tuple[ComparablePriceItem, Decimal]],
    *,
    allow_mixed_actors: bool = False,
) -> Decimal | None:
    """Compute weighted average of comparable prices in MGA per base unit.

    Returns None if no qualifying observations exist (never 0).
    """
    valid_weighted: list[tuple[ComparablePriceItem, Decimal]] = []
    for item, weight in weighted_items:
        if weight <= 0:
            continue
        if item.price_mga_per_base is None:
            continue
        if item.conversion_status == "uncertain":
            continue
        if item.confidence < Decimal("0.80"):
            continue
        if item.price_mga_per_base <= 0:
            continue
        valid_weighted.append((item, weight))

    if not valid_weighted:
        return None

    items_only = [item for item, _ in valid_weighted]
    validate_comparable_group(items_only, allow_mixed_actors=allow_mixed_actors)

    total_weight = sum((weight for _, weight in valid_weighted), start=Decimal("0"))
    if total_weight <= 0:
        return None

    weighted_sum = sum(
        (
            item.price_mga_per_base * weight
            for item, weight in valid_weighted
            if item.price_mga_per_base is not None
        ),
        start=Decimal("0"),
    )
    avg = weighted_sum / total_weight
    return avg.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
