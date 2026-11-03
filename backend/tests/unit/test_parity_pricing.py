"""Unit tests for econometric parity and caloric substitution pricing engine (ADR-140, ADR-141)."""

from datetime import date

import pytest

from ketrika.gold.parity_pricing import (
    CANONICAL_PPN_PRODUCTS,
    IPP_PRODUCTS,
    SUBSTITUTION_PRODUCTS,
    compute_import_parity_price,
    compute_substitution_price,
    get_macro_benchmarks,
    get_monthly_dates,
)


def test_canonical_ppn_products_count():
    """Verify all 15 canonical PPN vivriers are cataloged."""
    assert len(CANONICAL_PPN_PRODUCTS) == 15
    assert "RICE_WHITE_LOCAL" in CANONICAL_PPN_PRODUCTS
    assert "WHEAT_FLOUR" in CANONICAL_PPN_PRODUCTS
    assert "VEG_OIL" in CANONICAL_PPN_PRODUCTS
    assert "SUGAR" in CANONICAL_PPN_PRODUCTS
    assert "MAIZE_GRAIN" in CANONICAL_PPN_PRODUCTS
    assert "CASSAVA_FRESH" in CANONICAL_PPN_PRODUCTS
    assert "BEANS_DRY" in CANONICAL_PPN_PRODUCTS
    assert len(IPP_PRODUCTS) == 4
    assert len(SUBSTITUTION_PRODUCTS) == 10


def test_get_macro_benchmarks():
    """Verify macro indicators generation for USD/MGA, freight, and diesel."""
    d = date(2026, 10, 1)
    macro = get_macro_benchmarks(d)
    assert "fx_usd_mga" in macro
    assert "freight_ocean_usd" in macro
    assert "diesel_mga" in macro
    assert 4000.0 < macro["fx_usd_mga"] < 5000.0
    assert 50.0 < macro["freight_ocean_usd"] < 200.0
    assert macro["diesel_mga"] >= 3400.0


def test_get_monthly_dates():
    """Verify date sequence spans from 2020-01 to 2026-10 (82 months)."""
    dates = get_monthly_dates()
    assert len(dates) == 82
    assert dates[0] == date(2020, 1, 1)
    assert dates[-1] == date(2026, 10, 1)


def test_import_parity_pricing_calculation():
    """Verify IPP formula for imported staples."""
    d = date(2026, 10, 1)
    macro = get_macro_benchmarks(d)

    for pcode in IPP_PRODUCTS:
        res = compute_import_parity_price(pcode, d, macro)
        assert res["price"] > 1000.0
        assert res["unit"] in ("kg", "l")
        assert res["method"] == "Import Parity Pricing (IPP)"
        assert "source_citation" in res

    # Unknown product should raise ValueError
    with pytest.raises(ValueError, match="Unknown IPP product"):
        compute_import_parity_price("UNKNOWN_CROP", d, macro)


def test_substitution_pricing_calculation():
    """Verify IFPRI caloric substitution model and seasonality."""
    d_soudure = date(2026, 2, 1)  # February is soudure (lean season)
    d_harvest = date(2026, 5, 1)  # May is harvest season
    macro = get_macro_benchmarks(d_soudure)
    anchor_rice = 2800.0

    # During soudure, substitution ratios are higher
    maize_soudure = compute_substitution_price("MAIZE_GRAIN", d_soudure, anchor_rice, macro)
    maize_harvest = compute_substitution_price("MAIZE_GRAIN", d_harvest, anchor_rice, macro)

    assert maize_soudure["price"] > maize_harvest["price"]
    assert maize_soudure["is_soudure"] is True
    assert maize_harvest["is_soudure"] is False
    assert maize_soudure["unit"] == "kg"
    assert "IFPRI" in maize_soudure["method"]

    # Test all substitution products
    for pcode in SUBSTITUTION_PRODUCTS:
        res = compute_substitution_price(pcode, d_soudure, anchor_rice, macro)
        assert res["price"] > 0
        assert res["unit"] == "kg"

    # Unknown product should raise ValueError
    with pytest.raises(ValueError, match="Unknown substitution product"):
        compute_substitution_price("UNKNOWN_PRODUCT", d_soudure, anchor_rice, macro)
