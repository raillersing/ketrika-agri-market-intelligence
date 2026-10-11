"""Exact observed prices and explicitly supplied conversion factors (ADR-037)."""

import re
import unicodedata
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext


def _fits_sql_price(value: Decimal) -> bool:
    """Check exact coefficient/exponent, never context-rounded normalize()."""
    if value >= Decimal("100000000000000"):
        return False
    if value.is_zero():
        return True
    parts = value.as_tuple()
    exponent = parts.exponent
    if not isinstance(exponent, int):
        return False
    trailing_zeros = 0
    for digit in reversed(parts.digits):
        if digit != 0:
            break
        trailing_zeros += 1
    return exponent + trailing_zeros >= -4


@dataclass(frozen=True)
class ParsedPrice:
    value: Decimal | None
    missing_code: str | None = None
    issue: str | None = None


def parse_price(raw: str, *, number_style: str = "decimal_dot") -> ParsedPrice:
    """Never infer a locale, missing value, or rounded observed number."""
    if not isinstance(raw, str):
        return ParsedPrice(None, issue="invalid_price_type")
    if len(raw) > 128:
        return ParsedPrice(None, issue="price_token_too_long")
    text = unicodedata.normalize("NFKC", raw).strip()
    if text.upper() in {"ND", "NA"}:
        return ParsedPrice(None, missing_code=text.upper())
    if text in {"", "-"}:
        return ParsedPrice(None, missing_code="ND")
    if number_style not in {"decimal_dot", "decimal_comma"}:
        return ParsedPrice(None, issue="invalid_number_style")
    compact = text.replace(" ", "")
    pattern = (
        r"[+-]?(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d+)?"
        if number_style == "decimal_comma"
        else r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"
    )
    if not re.fullmatch(pattern, compact):
        return ParsedPrice(None, issue="invalid_price_number")
    if number_style == "decimal_comma":
        compact = compact.replace(".", "").replace(",", ".")
    try:
        value = Decimal(compact)
    except InvalidOperation:
        return ParsedPrice(None, issue="invalid_price_number")
    if not value.is_finite() or value < 0:
        return ParsedPrice(None, issue="invalid_price_number")
    if not _fits_sql_price(value):
        return ParsedPrice(None, issue="price_outside_sql_precision")
    return ParsedPrice(value)


@dataclass(frozen=True)
class ConvertedPrice:
    price_mga_per_base: Decimal | None
    base_unit: str | None
    conversion_status: str
    issue: str | None = None


def convert_price(
    value: Decimal | None,
    currency_raw: str,
    *,
    factor: Decimal | None,
    factor_confidence: Decimal,
    factor_evidence: str | None,
    base_unit: str | None,
    product_base_unit: str | None,
) -> ConvertedPrice:
    """Caller supplies a documented factor; no package, density or FX inference."""
    if value is None:
        return ConvertedPrice(None, base_unit, "uncertain", "price_missing_or_invalid")
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        return ConvertedPrice(None, base_unit, "uncertain", "invalid_price_number")
    if not _fits_sql_price(value):
        return ConvertedPrice(None, base_unit, "uncertain", "price_outside_sql_precision")
    currency = currency_raw.strip().lower() if isinstance(currency_raw, str) else ""
    if currency in {"mga", "ariary", "ar"}:
        currency_factor, currency_status = Decimal(1), "exact"
    elif currency in {"fmg", "franc", "francs"}:
        currency_factor, currency_status = Decimal(5), "confident"
    else:
        return ConvertedPrice(None, base_unit, "uncertain", "unknown_currency")
    if (
        not isinstance(factor, Decimal)
        or not factor.is_finite()
        or factor <= 0
        or not isinstance(factor_confidence, Decimal)
        or not factor_confidence.is_finite()
        or not Decimal("0.8") <= factor_confidence <= 1
        or not isinstance(factor_evidence, str)
        or not factor_evidence.strip()
    ):
        return ConvertedPrice(None, base_unit, "uncertain", "unqualified_unit_factor")
    if base_unit not in {"kg", "l"} or base_unit != product_base_unit:
        return ConvertedPrice(None, base_unit, "uncertain", "incompatible_product_unit")
    with localcontext() as context:
        context.prec = 50
        try:
            derived = (value / currency_factor / factor).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
        except InvalidOperation:
            return ConvertedPrice(None, base_unit, "uncertain", "conversion_outside_sql_precision")
    if derived >= Decimal("100000000000000"):
        return ConvertedPrice(None, base_unit, "uncertain", "conversion_outside_sql_precision")
    status = (
        "confident"
        if currency_status == "confident" or factor_confidence < Decimal("0.99")
        else "exact"
    )
    return ConvertedPrice(derived, base_unit, status)
