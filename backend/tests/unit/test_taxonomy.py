"""Unit tests for product taxonomy, aliases and rice varieties."""

import pytest

from ketrika.core.taxonomy import (
    get_product,
    load_aliases,
    load_products,
    load_rice_varieties,
    resolve_product,
    validate_taxonomy,
)


def test_validate_taxonomy_has_no_errors() -> None:
    errors = validate_taxonomy()
    assert errors == []


def test_products_catalog_contains_core_ppn() -> None:
    products = load_products()
    codes = {p.product_code for p in products}
    expected = {
        "RICE_PADDY",
        "RICE_WHITE_LOCAL",
        "RICE_WHITE_IMPORTED",
        "MAIZE_GRAIN",
        "CASSAVA_FRESH",
        "CASSAVA_DRIED",
        "SWEET_POTATO",
        "BEANS_DRY",
        "BAMBARA_GROUNDNUT",
        "LIMA_BEANS",
        "LENTILS",
        "GROUNDNUT",
        "VEG_OIL",
        "SUGAR",
        "WHEAT_FLOUR",
    }
    for code in expected:
        assert code in codes


def test_get_product_success_and_failure() -> None:
    p = get_product("RICE_PADDY")
    assert p.product_code == "RICE_PADDY"
    assert p.base_unit == "kg"

    with pytest.raises(KeyError):
        get_product("NON_EXISTENT_PRODUCT")


def test_rice_varieties_loaded() -> None:
    varieties = load_rice_varieties()
    codes = {v.variety_code for v in varieties}
    assert "MAKALIOKA" in codes
    assert "TSIPALA" in codes
    assert "VARY_MENA" in codes


def test_all_fixture_commodity_labels_are_resolved() -> None:
    fixture_labels = [
        "Rice (local)",
        "Rice (imported)",
        "Maize",
        "Rice",
        "Riz paddy",
        "Riz blanc local",
        "Riz blanc importé",
        "Sucre blanc",
        "Huile alimentaire vrac",
        "Farine de ble",
        "Riz semi-blanchi ou blanchi",
        "Huile de palme et fractions",
        "Sucre de canne ou de betterave",
        "vary gasy",
        "akotry",
        "katsaka",
        "tsaramaso",
        "menaka",
        "siramamy",
    ]
    aliases = load_aliases()
    for label in fixture_labels:
        resolved = resolve_product(label, aliases=aliases, min_confidence=0.7)
        assert resolved is not None, f"Commodity label '{label}' from fixtures failed to resolve"
        assert resolved[0] is not None
        assert resolved[1] >= 0.7
