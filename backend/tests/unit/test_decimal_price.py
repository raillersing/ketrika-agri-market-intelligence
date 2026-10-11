"""Pure prototype: conversion arithmetic is not market/source qualification."""

from decimal import Decimal

import pytest

from ketrika.normalize.decimal_price import convert_price, parse_price


@pytest.mark.parametrize(
    "raw,style,expected",
    [
        ("2 850", "decimal_dot", "2850"),
        ("2\u00a0850,50", "decimal_comma", "2850.50"),
        ("2\u202f850,50", "decimal_comma", "2850.50"),
        ("2.850", "decimal_comma", "2850"),
        ("2.850", "decimal_dot", "2.850"),
        ("3000.1250", "decimal_dot", "3000.1250"),
        ("0", "decimal_dot", "0"),
        ("1e3", "decimal_dot", "1000"),
        ("99999999999999.9999", "decimal_dot", "99999999999999.9999"),
    ],
)
def test_observed_value_exact_with_explicit_style(raw, style, expected):
    parsed = parse_price(raw, number_style=style)
    assert parsed.value == Decimal(expected)
    assert parsed.missing_code is parsed.issue is None


@pytest.mark.parametrize("raw,code", [("ND", "ND"), ("na", "NA"), ("-", "ND"), ("", "ND")])
def test_missing_is_not_zero(raw, code):
    parsed = parse_price(raw)
    assert parsed.value is None and parsed.missing_code == code and parsed.issue is None


@pytest.mark.parametrize(
    "raw",
    [
        "NaN",
        "Infinity",
        "-1",
        "banana",
        "2800 USD",
        "1,23",
        "1.23456",
        "100000000000000",
        "1e-1000000",
        "1e1000000",
        "1e-1000000000",
        "1.00000000000000000000000000000001",
        "1" * 129,
    ],
)
def test_invalid_is_not_invented_missing_code(raw):
    parsed = parse_price(raw)
    assert parsed.value is parsed.missing_code is None and parsed.issue is not None


def conversion(**changes):
    arguments = {
        "value": Decimal("2850"),
        "currency_raw": "MGA",
        "factor": Decimal(1),
        "factor_confidence": Decimal(1),
        "factor_evidence": "SI base unit; synthetic test",
        "base_unit": "kg",
        "product_base_unit": "kg",
    }
    return convert_price(**(arguments | changes))


def test_mga_exact_fmg_explicit_confident_and_unknown_refused():
    assert conversion().price_mga_per_base == Decimal("2850.0000")
    assert conversion().conversion_status == "exact"
    result = conversion(currency_raw="FMG", value=Decimal("14250"))
    assert result.price_mga_per_base == Decimal("2850.0000")
    assert result.conversion_status == "confident"
    for currency in ("USD", "", None):
        rejected = conversion(currency_raw=currency)
        assert rejected.price_mga_per_base is None and rejected.issue == "unknown_currency"


@pytest.mark.parametrize(
    "changes",
    [
        {"factor": None},
        {"factor": Decimal(0)},
        {"factor": Decimal(-1)},
        {"factor": Decimal("NaN")},
        {"factor_confidence": Decimal("0.79")},
        {"factor_confidence": Decimal("1.01")},
        {"factor_confidence": Decimal("NaN")},
        {"factor_evidence": None},
        {"factor_evidence": " "},
    ],
)
def test_unqualified_factor_never_converts(changes):
    result = conversion(**changes)
    assert result.price_mga_per_base is None and result.conversion_status == "uncertain"
    assert result.issue == "unqualified_unit_factor"


def test_dimension_and_product_unknown_refuse_even_known_factor():
    for changes in ({"base_unit": "l"}, {"product_base_unit": None}):
        result = conversion(**changes)
        assert result.price_mga_per_base is None and result.issue == "incompatible_product_unit"


def test_rounding_only_derived_and_precision_bound():
    value = Decimal("1.0000")
    converted = conversion(value=value, factor=Decimal("3"))
    assert converted.price_mga_per_base == Decimal("0.3333") and value == Decimal("1.0000")
    assert conversion(value=Decimal("1.0000"), factor=Decimal("32")).price_mga_per_base == Decimal(
        "0.0313"
    )
    assert conversion(value=Decimal("1.23445")).issue == "price_outside_sql_precision"
    assert (
        conversion(value=Decimal("99999999999999.9999"), factor=Decimal("0.001")).issue
        == "conversion_outside_sql_precision"
    )


@pytest.mark.parametrize("value", [None, Decimal("NaN"), Decimal(-1)])
def test_missing_invalid_value_never_converts(value):
    assert conversion(value=value).price_mga_per_base is None


@pytest.mark.parametrize(
    "raw", ["1e1000000", "1e-1000000000", "1.00000000000000000000000000000001"]
)
def test_conversion_refuses_exact_precision_without_context_rounding(raw):
    original = Decimal(raw)
    result = conversion(value=original)
    assert result.price_mga_per_base is None
    assert result.issue == "price_outside_sql_precision"
    assert original.as_tuple() == Decimal(raw).as_tuple()


def test_precision_validation_is_independent_of_ambient_decimal_context():
    from decimal import localcontext

    with localcontext() as context:
        context.prec = 2
        assert parse_price("2850.1250").value == Decimal("2850.1250")
        assert parse_price("1.00000000000000000000000000000001").value is None
        assert parse_price("1e-1000000000").value is None
