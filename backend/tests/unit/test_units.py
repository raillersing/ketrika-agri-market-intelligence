"""Unit tests and property-based tests for units of measurement and conversions."""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ketrika.core.units import (
    convert_from_base,
    convert_to_base,
    load_units,
    normalize_unit_code,
    validate_units,
)


def test_validate_units_has_no_errors() -> None:
    errors = validate_units()
    assert errors == []


def test_no_conversion_ge_80_without_evidence() -> None:
    units = load_units()
    for u in units:
        if u.factor is not None and u.confidence >= 0.8:
            assert u.evidence.strip() != "", (
                f"Unit {u.unit_code} has high confidence without evidence"
            )
        for prod, spec in u.product_specific.items():
            if spec.confidence >= 0.8:
                assert spec.evidence.strip() != "", (
                    f"Unit {u.unit_code} override for {prod} missing evidence"
                )


def test_fixture_units_are_all_present() -> None:
    fixture_unit_strings = [
        "kg",
        "KG",
        "t",
        "tonne",
        "tonnes",
        "l",
        "sac_50kg",
    ]
    for raw in fixture_unit_strings:
        canon = normalize_unit_code(raw)
        converted, base_unit, confidence, status = convert_to_base(10.0, canon)
        assert converted is not None
        assert base_unit in ("kg", "l")
        assert status in ("exact", "confident")


def test_kapoaka_conversions() -> None:
    val, base, conf, status = convert_to_base(1.0, "kapoaka", product_code="RICE_WHITE_LOCAL")
    assert val == pytest.approx(0.285)
    assert base == "kg"
    assert status == "confident"

    val_paddy, _, _, status_paddy = convert_to_base(1.0, "kapoaka", product_code="RICE_PADDY")
    assert val_paddy == pytest.approx(0.220)
    assert status_paddy == "confident"


def test_uncertain_conversions_return_none_value() -> None:
    # Gony has confidence < 0.8 without specified tare
    val, _, conf, status = convert_to_base(1.0, "gony")
    assert val is None
    assert conf < 0.8
    assert status == "uncertain"


@settings(deadline=None)
@given(
    val=st.floats(min_value=0.01, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
    unit_code=st.sampled_from(
        ["kg", "g", "t", "qx", "l", "ml", "sac_50kg", "sac_25kg", "bouteille_1l"]
    ),
)
def test_inverse_conversions_are_consistent(val: float, unit_code: str) -> None:
    converted, base_unit, conf, status = convert_to_base(val, unit_code)
    assert converted is not None
    assert status in ("exact", "confident")

    restored, r_conf, r_status = convert_from_base(converted, unit_code)
    assert restored is not None
    assert math.isclose(val, restored, rel_tol=1e-5, abs_tol=1e-8)


@settings(deadline=None)
@given(
    val=st.floats(min_value=0.1, max_value=10_000.0, allow_nan=False, allow_infinity=False),
    prod=st.sampled_from(["RICE_WHITE_LOCAL", "RICE_WHITE_IMPORTED", "RICE_PADDY", "MAIZE_GRAIN"]),
)
def test_product_specific_kapoaka_inverse_consistency(val: float, prod: str) -> None:
    converted, base_unit, conf, status = convert_to_base(val, "kapoaka", product_code=prod)
    assert converted is not None
    assert status == "confident"

    restored, _, _ = convert_from_base(converted, "kapoaka", product_code=prod)
    assert restored is not None
    assert math.isclose(val, restored, rel_tol=1e-5, abs_tol=1e-8)
