"""Contract tests of the price grain; not a loader or market qualification."""

from dataclasses import replace
from datetime import date, datetime
from typing import Any

import pytest

from ketrika.normalize.price_identity import PriceIdentity


def identity() -> PriceIdentity:
    return PriceIdentity(
        "synthetic_price",
        "riz",
        None,
        "marché",
        "retail",
        date(2025, 1, 1),
        date(2025, 1, 31),
        "point",
        "kg",
        "MGA",
        "observed",
    )


def test_repeat_is_exact_and_deterministic() -> None:
    assert identity().natural_key == identity().natural_key
    assert len(identity().natural_key) == 64


@pytest.mark.parametrize(
    "changes",
    [
        {"source_id": "other"},
        {"product_raw": "maïs"},
        {"variety": "blanc"},
        {"location_raw": None},
        {"actor_level": "wholesale"},
        {"period_start": date(2025, 1, 2)},
        {"period_end": date(2025, 1, 30)},
        {"value_kind": "min"},
        {"value_kind": "max"},
        {"value_kind": "avg"},
        {"unit_raw": "sac"},
        {"currency_raw": "USD"},
        {"observed_or_imputed": "imputed"},
        {"product_raw": " riz "},
    ],
)
def test_every_dimension_changes_identity(changes: dict[str, Any]) -> None:
    assert replace(identity(), **changes).natural_key != identity().natural_key


def test_null_empty_and_literal_none_are_distinct() -> None:
    assert len({replace(identity(), variety=x).natural_key for x in (None, "", "None")}) == 3


def test_separator_does_not_collapse_dimensions() -> None:
    first = replace(identity(), product_raw="riz|blanc", variety="local")
    second = replace(identity(), product_raw="riz", variety="blanc|local")
    assert first.natural_key != second.natural_key


@pytest.mark.parametrize(
    "changes",
    [
        {"source_id": ""},
        {"product_raw": " "},
        {"unit_raw": ""},
        {"currency_raw": ""},
        {"variety": 42},
        {"location_raw": False},
        {"value_kind": "forecast"},
        {"observed_or_imputed": "forecast"},
        {"actor_level": "invalid"},
        {"period_end": date(2024, 1, 1)},
        {"period_start": datetime(2025, 1, 1)},
        {"product_raw": "x" * 4097},
    ],
)
def test_invalid_grains_fail_closed(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="price_identity_invalid"):
        replace(identity(), **changes)
