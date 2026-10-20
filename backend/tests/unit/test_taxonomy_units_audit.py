"""Comprehensive audit tests for taxonomy, units, grains, and aggregation guards (R2.2).

Acceptance criteria:
- 100 % des libellés acquis résolus ou en revue.
- Conversions faible confiance (<0.80) exclues des prix comparables.
- Conversions massiques/volumiques sans densité prouvée refusées.
- Aliases <0.90 dirigés vers la file de revue sans prix comparable.
- Propriétés d'inversion mathématique et formats numériques verts.
- Ni ND ni lieu inconnu remplacés par zéro ou défaut.
- Interdiction stricte de moyenner devises, unités, indices ou acteurs incompatibles.
"""

import math
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ketrika.connectors.records import PriceRecord
from ketrika.core.aggregation import (
    ComparablePriceItem,
    IncompatibleAggregationError,
    compute_safe_arithmetic_average,
    compute_safe_weighted_average,
    filter_comparable_items,
    validate_comparable_group,
)
from ketrika.core.models.db import Location, Product, SourceRecord, UnitConversion
from ketrika.core.taxonomy import (
    get_product,
    load_aliases,
    load_products,
    load_rice_varieties,
    validate_taxonomy,
)
from ketrika.core.units import (
    convert_from_base,
    convert_to_base,
    validate_units,
)
from ketrika.normalize.decimal_price import parse_price
from ketrika.normalize.price_loader import load_normalized_price
from ketrika.normalize.price_references import ReferenceMatch
from ketrika.normalize.units import parse_numeric_value

# ============================================================================
# 1. TAXONOMY AUDIT TESTS
# ============================================================================


def test_production_taxonomy_passes_strict_audit() -> None:
    """Validate that the active taxonomy/ definitions conform 100% to R2.2."""
    errors = validate_taxonomy()
    assert errors == [], f"Taxonomy validation failed with errors: {errors}"


def test_core_ppn_catalog_conformance() -> None:
    """Verify that all 15 core PPN products have valid attributes, HS codes and FAOSTAT codes."""
    products = load_products()
    assert len(products) >= 15

    expected_products = {
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
    prod_map = {p.product_code: p for p in products}

    for expected in expected_products:
        assert expected in prod_map, f"Missing core product: {expected}"
        p = prod_map[expected]
        assert p.base_unit in {"kg", "l"}, f"Invalid base_unit for {expected}: {p.base_unit}"
        assert p.canonical_name_fr.strip() != "", f"Empty French name for {expected}"
        assert p.verified is True, f"Product {expected} should be marked verified"

        # HS6 code validation
        for hs in p.hs6_codes:
            assert len(hs) == 6 and hs.isdigit(), f"Invalid HS6 code '{hs}' in {expected}"

        # FAOSTAT code validation
        for fao in p.faostat_item_codes:
            assert isinstance(fao, int) and fao > 0, f"Invalid FAOSTAT code '{fao}' in {expected}"


def test_strict_rice_vs_paddy_vs_variety_separation() -> None:
    """Ensure paddy (unmilled) is strictly separated from milled rice and rice varieties."""
    paddy = get_product("RICE_PADDY")
    white_local = get_product("RICE_WHITE_LOCAL")
    white_imported = get_product("RICE_WHITE_IMPORTED")

    assert paddy.product_code != white_local.product_code
    assert white_local.product_code != white_imported.product_code

    # Check HS6 separation: Paddy is 1006.10, Milled is 1006.30
    assert "100610" in paddy.hs6_codes
    assert "100630" in white_local.hs6_codes
    assert "100630" in white_imported.hs6_codes
    assert "100610" not in white_local.hs6_codes

    # Check that rice varieties do not collide with product codes
    varieties = load_rice_varieties()
    variety_codes = {v.variety_code for v in varieties}
    product_codes = {p.product_code for p in load_products()}

    assert len(variety_codes & product_codes) == 0, (
        "Variety codes collide with canonical product codes"
    )
    for v in varieties:
        assert v.rice_type in {"local", "imported", "paddy"}
        assert v.grain_type in {"long", "round", "medium", "unknown"}


def test_alias_evidence_and_review_note_integrity() -> None:
    """Verify that aliases >= 0.9 have evidence and aliases < 0.9 have review notes."""
    aliases = load_aliases()
    for a in aliases:
        if a.confidence >= 0.90:
            assert a.evidence.strip() != "", (
                f"Alias '{a.alias}' has confidence {a.confidence} >= 0.9 but missing evidence"
            )
            assert len(a.evidence.strip()) >= 5
        else:
            assert a.note.strip() != "", (
                f"Alias '{a.alias}' has confidence {a.confidence} < 0.9 but missing disambiguation note"
            )


def test_validate_taxonomy_detects_defects(tmp_path) -> None:
    """Verify that validate_taxonomy flags invalid configurations."""
    import yaml

    # 1. High confidence without evidence
    bad_alias = [
        {
            "alias": "vary no evidence",
            "lang": "mg",
            "product_code": "RICE_WHITE_LOCAL",
            "confidence": 0.95,
            "note": "",
            "evidence": "",
        }
    ]
    with open(tmp_path / "aliases.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(bad_alias, f)

    # Copy products and varieties
    prod_data = [p.model_dump() for p in load_products()]
    with open(tmp_path / "products.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(prod_data, f)
    var_data = [v.model_dump() for v in load_rice_varieties()]
    with open(tmp_path / "rice_varieties.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(var_data, f)

    errors = validate_taxonomy(tmp_path)
    assert any("missing or insufficient evidence" in e for e in errors)


# ============================================================================
# 2. UNITS AND CONVERSION AUDIT TESTS
# ============================================================================


def test_production_units_pass_strict_audit() -> None:
    """Validate that the active taxonomy/units.yaml conforms 100% to R2.2."""
    errors = validate_units()
    assert errors == [], f"Units validation failed with errors: {errors}"


def test_mass_volume_cross_conversion_refused_without_density() -> None:
    """Directive R2.2: conversions massiques/volumiques sans densité prouvée refusées."""
    # 1. Attempt to convert solid product (RICE_WHITE_LOCAL, base_unit=kg) using volume unit (l)
    val, base, conf, status = convert_to_base(1.0, "l", product_code="RICE_WHITE_LOCAL")
    assert val is None, "Cross mass-volume conversion without density MUST return None"
    assert status == "uncertain"

    # 2. Attempt to convert liquid product (VEG_OIL, base_unit=l) using mass unit (kg)
    val_oil, base_oil, conf_oil, status_oil = convert_to_base(1.0, "kg", product_code="VEG_OIL")
    assert val_oil is None, "Liquid product with mass unit without density MUST return None"
    assert status_oil == "uncertain"

    # 3. Inverse conversion also refused
    inv_val, inv_conf, inv_status = convert_from_base(1.0, "l", product_code="RICE_WHITE_LOCAL")
    assert inv_val is None
    assert inv_status == "uncertain"

    inv_oil, _, inv_oil_status = convert_from_base(1.0, "kg", product_code="VEG_OIL")
    assert inv_oil is None
    assert inv_oil_status == "uncertain"


def test_calibrated_density_kapoaka_conversions() -> None:
    """Verify calibrated empirical kapoaka density factors from ODR/INSTAT/CIRAD studies."""
    # RICE_WHITE_LOCAL: 1 kapoaka = 0.285 kg
    val_white, base_w, conf_w, status_w = convert_to_base(
        1.0, "kapoaka", product_code="RICE_WHITE_LOCAL"
    )
    assert val_white == pytest.approx(0.285)
    assert base_w == "kg"
    assert conf_w == 0.85
    assert status_w == "confident"

    # RICE_PADDY: 1 kapoaka = 0.220 kg (apparent density lower)
    val_paddy, base_p, conf_p, status_p = convert_to_base(1.0, "kapoaka", product_code="RICE_PADDY")
    assert val_paddy == pytest.approx(0.220)
    assert base_p == "kg"
    assert conf_p == 0.85
    assert status_p == "confident"

    # MAIZE_GRAIN: 1 kapoaka = 0.260 kg
    val_maize, _, _, _ = convert_to_base(1.0, "kapoaka", product_code="MAIZE_GRAIN")
    assert val_maize == pytest.approx(0.260)

    # BEANS_DRY: 1 kapoaka = 0.280 kg
    val_beans, _, _, _ = convert_to_base(1.0, "kapoaka", product_code="BEANS_DRY")
    assert val_beans == pytest.approx(0.280)


def test_uncalibrated_units_excluded_from_comparable() -> None:
    """Directive R2.2: conversions faible confiance (<0.80) exclues des prix comparables."""
    # Gony (generic unmeasured sack): confidence 0.50 -> uncertain, val is None
    val_gony, _, conf_gony, status_gony = convert_to_base(1.0, "gony")
    assert val_gony is None
    assert conf_gony < 0.80
    assert status_gony == "uncertain"

    # Daba for CASSAVA_FRESH: confidence 0.70 -> uncertain, val is None
    val_daba, _, conf_daba, status_daba = convert_to_base(1.0, "daba", product_code="CASSAVA_FRESH")
    assert val_daba is None
    assert conf_daba < 0.80
    assert status_daba == "uncertain"


@settings(deadline=None)
@given(
    val=st.floats(min_value=0.01, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
    unit_code=st.sampled_from(["kg", "g", "t", "qx", "sac_50kg", "sac_25kg"]),
)
def test_mass_inverse_conversions_exact(val: float, unit_code: str) -> None:
    """Verify mathematical inversion property for mass units."""
    converted, base_unit, conf, status = convert_to_base(val, unit_code)
    assert converted is not None
    assert base_unit == "kg"

    restored, r_conf, r_status = convert_from_base(converted, unit_code)
    assert restored is not None
    assert math.isclose(val, restored, rel_tol=1e-5, abs_tol=1e-8)


@settings(deadline=None)
@given(
    val=st.floats(min_value=0.01, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
    unit_code=st.sampled_from(["l", "ml", "bouteille_1l"]),
)
def test_volume_inverse_conversions_exact(val: float, unit_code: str) -> None:
    """Verify mathematical inversion property for volume units."""
    converted, base_unit, conf, status = convert_to_base(val, unit_code)
    assert converted is not None
    assert base_unit == "l"

    restored, r_conf, r_status = convert_from_base(converted, unit_code)
    assert restored is not None
    assert math.isclose(val, restored, rel_tol=1e-5, abs_tol=1e-8)


# ============================================================================
# 3. NUMERIC PARSING AND MISSING VALUES TESTS
# ============================================================================


def test_numeric_parsing_french_malagasy_formats() -> None:
    """Verify parsing of Malagasy/French number formats with commas, spaces, currency."""
    test_cases = [
        ("2 850,50", 2850.5),
        ("2.850,50", 2850.5),
        ("2 850", 2850.0),
        ("2850", 2850.0),
        ("2 850 Ar", 2850.0),
        ("2850Ar", 2850.0),
        ("2 850,00 MGA", 2850.0),
        ("14 250 FMG", 14250.0),
        ("3\u00a0000,50", 3000.5),  # Non-breaking space
        ("3\u202f000,50", 3000.5),  # Thin space
    ]
    for raw, expected in test_cases:
        val, missing = parse_numeric_value(raw)
        assert val == pytest.approx(expected), f"Failed parsing '{raw}'"
        assert missing is None


def test_missing_values_never_default_to_zero() -> None:
    """Directive R2.2: ni ND ni valeur manquante remplacés par zéro ou défaut."""
    missing_tokens = ["ND", "nd", "NA", "na", "-", "none", "null", "", "   ", None]
    for token in missing_tokens:
        val, missing = parse_numeric_value(token)
        assert val is None, f"Token '{token}' must parse to None, got {val}"
        assert missing == "ND", f"Token '{token}' must produce missing code 'ND'"

    # parse_price contract from decimal_price
    for token in ["ND", "NA", "-", ""]:
        res = parse_price(token)
        assert res.value is None
        assert res.missing_code in {"ND", "NA"}


# ============================================================================
# 4. GOLD AGGREGATION GUARDS TESTS
# ============================================================================


def test_aggregation_guard_refuses_mixed_currencies() -> None:
    """Interdire moyenne entre devises différentes sans conversion préalable."""
    item_mga = ComparablePriceItem(
        price_mga_per_base=Decimal("3000"), base_unit="kg", currency="MGA"
    )
    item_usd = ComparablePriceItem(price_mga_per_base=Decimal("1"), base_unit="kg", currency="USD")

    with pytest.raises(IncompatibleAggregationError, match="incompatible_currencies"):
        validate_comparable_group([item_mga, item_usd])


def test_aggregation_guard_refuses_mixed_base_units() -> None:
    """Interdire moyenne entre unités physiques incompatibles (kg vs l)."""
    item_kg = ComparablePriceItem(price_mga_per_base=Decimal("3000"), base_unit="kg")
    item_l = ComparablePriceItem(price_mga_per_base=Decimal("7500"), base_unit="l")

    with pytest.raises(IncompatibleAggregationError, match="cannot_aggregate_mixed_base_units"):
        validate_comparable_group([item_kg, item_l])


def test_aggregation_guard_refuses_mixing_index_and_price() -> None:
    """Interdire moyenne entre indice (base 100) et prix nominal en Ariary."""
    item_price = ComparablePriceItem(
        price_mga_per_base=Decimal("3000"), base_unit="kg", is_index=False
    )
    item_index = ComparablePriceItem(
        price_mga_per_base=Decimal("125.4"), base_unit="kg", is_index=True
    )

    with pytest.raises(
        IncompatibleAggregationError, match="cannot_aggregate_index_with_nominal_prices"
    ):
        validate_comparable_group([item_price, item_index])

    with pytest.raises(IncompatibleAggregationError, match="cannot_aggregate_index_as_price"):
        validate_comparable_group([item_index])


def test_aggregation_guard_refuses_unsegmented_actor_levels() -> None:
    """Interdire mélange farmgate (bord champ) et retail (détail) sans partitionnement."""
    item_retail = ComparablePriceItem(
        price_mga_per_base=Decimal("3000"), base_unit="kg", actor_level="retail"
    )
    item_farmgate = ComparablePriceItem(
        price_mga_per_base=Decimal("1500"), base_unit="kg", actor_level="farmgate"
    )

    with pytest.raises(
        IncompatibleAggregationError, match="cannot_aggregate_incompatible_actor_levels"
    ):
        validate_comparable_group([item_retail, item_farmgate], allow_mixed_actors=False)

    # When explicit opt-in is granted, validation passes
    validate_comparable_group([item_retail, item_farmgate], allow_mixed_actors=True)


def test_aggregation_safe_averaging_computations() -> None:
    """Verify arithmetic and weighted averaging with filtering of missing/uncertain observations."""
    i1 = ComparablePriceItem(price_mga_per_base=Decimal("2000"), base_unit="kg")
    i2 = ComparablePriceItem(price_mga_per_base=Decimal("4000"), base_unit="kg")
    # Low confidence item (< 0.80) -> must be excluded
    i_low = ComparablePriceItem(
        price_mga_per_base=Decimal("9999"), base_unit="kg", confidence=Decimal("0.50")
    )
    # Uncertain conversion -> must be excluded
    i_unc = ComparablePriceItem(
        price_mga_per_base=Decimal("8888"), base_unit="kg", conversion_status="uncertain"
    )
    # Missing price -> must be excluded (not treated as 0!)
    i_none = ComparablePriceItem(price_mga_per_base=None, base_unit="kg")

    avg = compute_safe_arithmetic_average([i1, i2, i_low, i_unc, i_none])
    assert avg == Decimal("3000.0000")

    # Weighted average: i1 has weight 1, i2 has weight 3 -> (2000*1 + 4000*3) / 4 = 14000 / 4 = 3500
    weighted_avg = compute_safe_weighted_average(
        [(i1, Decimal("1.0")), (i2, Decimal("3.0")), (i_low, Decimal("10.0"))]
    )
    assert weighted_avg == Decimal("3500.0000")

    # If only invalid items exist, returns None (NEVER Decimal("0"))
    assert compute_safe_arithmetic_average([i_low, i_unc, i_none]) is None
    assert compute_safe_weighted_average([(i_none, Decimal("1.0"))]) is None


# ============================================================================
# 5. REVIEW QUEUE AND COMPARABLE EXCLUSION INTEGRATION
# ============================================================================


def test_alias_below_90_directed_to_review_and_excluded_from_comparable() -> None:
    """Directive R2.2: Aliases < 0.90 directed to review queue and excluded from comparable price."""
    session = MagicMock()
    source_record_id = uuid4()
    session.get.return_value = SourceRecord(source_id="dummy_source")

    # Mock product match with confidence 0.85 (< 0.90)
    low_conf_product = ReferenceMatch(
        Product(product_id=uuid4(), base_unit="kg"),
        Decimal("0.85"),
        "exact_global_alias",
        ("alias-0.85",),
    )
    good_location = ReferenceMatch(
        Location(location_id=uuid4()),
        Decimal("1.0"),
        "exact_global_alias",
        ("loc-1.0",),
    )
    good_factor = UnitConversion(
        unit_code="kg",
        factor=Decimal("1"),
        confidence=Decimal("1"),
        base_unit="kg",
        evidence="SI metric",
    )

    rec = PriceRecord(
        product_raw="vary vahiny",
        location_raw="Antananarivo",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 31),
        price_raw="3000",
        price_value=3000.0,
        unit_raw="kg",
        currency_raw="MGA",
        evidence={"provenance": {"version": 1, "format": "csv", "cells": []}},
    )

    captured_obs = []

    def fake_loader(*args, **kwargs):
        obs = args[3](uuid4())
        captured_obs.append(obs)
        return "inserted", obs.observation_id

    with (
        patch("ketrika.normalize.price_loader.resolve_product", return_value=low_conf_product),
        patch("ketrika.normalize.price_loader.resolve_location", return_value=good_location),
        patch("ketrika.normalize.price_loader.unit_factor", return_value=good_factor),
        patch(
            "ketrika.normalize.price_loader.load_observation_with_supersession",
            side_effect=fake_loader,
        ),
        patch("ketrika.normalize.price_loader.create_review_item") as mock_review,
    ):
        result = load_normalized_price(session, rec, "dummy_source", source_record_id)

    assert len(captured_obs) == 1
    obs = captured_obs[0]

    # Verify: review_status must be 'pending'
    assert obs.review_status == "pending"
    # Verify: price_mga_per_base must be None (excluded from comparable prices!)
    assert obs.price_mga_per_base is None
    # Verify: review item created
    assert result.review_items == 1
    mock_review.assert_called_once()
    assert mock_review.call_args[0][1] == "unqualified_alias"


def test_canonical_product_with_high_confidence_is_accepted() -> None:
    """Product resolved with confidence >= 0.90 is accepted and comparable is computed."""
    session = MagicMock()
    source_record_id = uuid4()
    session.get.return_value = SourceRecord(source_id="dummy_source")

    high_conf_product = ReferenceMatch(
        Product(product_id=uuid4(), base_unit="kg"),
        Decimal("0.95"),
        "exact_global_alias",
        ("alias-0.95",),
    )
    good_location = ReferenceMatch(
        Location(location_id=uuid4()),
        Decimal("1.0"),
        "exact_global_alias",
        ("loc-1.0",),
    )
    good_factor = UnitConversion(
        unit_code="kg",
        factor=Decimal("1"),
        confidence=Decimal("1"),
        base_unit="kg",
        evidence="SI metric",
    )

    rec = PriceRecord(
        product_raw="Riz blanc local",
        location_raw="Antananarivo",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 31),
        price_raw="3000",
        price_value=3000.0,
        unit_raw="kg",
        currency_raw="MGA",
        evidence={"provenance": {"version": 1, "format": "csv", "cells": []}},
    )

    captured_obs = []

    def fake_loader(*args, **kwargs):
        obs = args[3](uuid4())
        captured_obs.append(obs)
        return "inserted", obs.observation_id

    with (
        patch("ketrika.normalize.price_loader.resolve_product", return_value=high_conf_product),
        patch("ketrika.normalize.price_loader.resolve_location", return_value=good_location),
        patch("ketrika.normalize.price_loader.unit_factor", return_value=good_factor),
        patch(
            "ketrika.normalize.price_loader.load_observation_with_supersession",
            side_effect=fake_loader,
        ),
        patch("ketrika.normalize.price_loader.create_review_item") as mock_review,
    ):
        result = load_normalized_price(session, rec, "dummy_source", source_record_id)

    obs = captured_obs[0]
    assert obs.review_status == "accepted"
    assert obs.price_mga_per_base == Decimal("3000.0000")
    assert result.review_items == 0
    mock_review.assert_not_called()


# ============================================================================
# 6. DEFECT DETECTION AND ROBUSTNESS EDGE CASES
# ============================================================================


def test_validate_taxonomy_catches_all_defects(tmp_path) -> None:
    """Ensure validate_taxonomy rejects all invalid taxonomy schema configurations."""
    import yaml

    # 1. Duplicate product codes and schema errors
    prods = [
        {
            "product_code": "RICE_PADDY",
            "canonical_name_fr": "Paddy",
            "category": "cereal",
            "base_unit": "kg",
        },
        {
            "product_code": "RICE_PADDY",
            "canonical_name_fr": "Paddy Bis",
            "category": "cereal",
            "base_unit": "kg",
        },
        {
            "product_code": "RICE_WHITE_LOCAL",
            "canonical_name_fr": "Riz Blanc",
            "category": "cereal",
            "base_unit": "pound",
        },
        {
            "product_code": "RICE_WHITE_IMPORTED",
            "canonical_name_fr": "Riz Imp",
            "category": "cereal",
            "base_unit": "kg",
            "hs6_codes": ["123"],
        },
        {
            "product_code": "MAIZE_GRAIN",
            "canonical_name_fr": "Maïs",
            "category": "cereal",
            "base_unit": "kg",
            "faostat_item_codes": [0],
        },
    ]
    with open(tmp_path / "products.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(prods, f)

    # 2. Defective aliases
    aliases = [
        {
            "alias": "unknown product ref",
            "lang": "fr",
            "product_code": "DOES_NOT_EXIST",
            "confidence": 0.95,
            "evidence": "Some proof",
        },
        {
            "alias": "dup alias",
            "lang": "fr",
            "product_code": "RICE_PADDY",
            "confidence": 0.95,
            "evidence": "Proof 1",
        },
        {
            "alias": "dup  alias",
            "lang": "fr",
            "product_code": "RICE_PADDY",
            "confidence": 0.95,
            "evidence": "Proof 2",
        },
        {
            "alias": "low conf no note",
            "lang": "fr",
            "product_code": "RICE_PADDY",
            "confidence": 0.85,
            "note": "",
            "evidence": "Proof",
        },
        {
            "alias": "paddy blanc blanchi",
            "lang": "fr",
            "product_code": "RICE_PADDY",
            "confidence": 0.95,
            "evidence": "Contradictory proof",
        },
        {
            "alias": "akotry milled",
            "lang": "fr",
            "product_code": "RICE_WHITE_LOCAL",
            "confidence": 0.95,
            "evidence": "Contradictory proof",
        },
    ]
    with open(tmp_path / "aliases.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(aliases, f)

    # 3. Defective varieties
    varieties = [
        {"variety_code": "V1", "name": "V1", "rice_type": "local"},
        {"variety_code": "V1", "name": "V1 Duplicate", "rice_type": "local"},
        {"variety_code": "RICE_PADDY", "name": "Colliding with product", "rice_type": "local"},
    ]
    with open(tmp_path / "rice_varieties.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(varieties, f)

    errors = validate_taxonomy(tmp_path)
    assert any("Duplicate product_code" in e for e in errors)
    assert any("invalid base_unit" in e for e in errors)
    assert any("invalid HS6 code" in e for e in errors)
    assert any("invalid FAOSTAT item code" in e for e in errors)
    assert any("references non-existent product_code" in e for e in errors)
    assert any("Duplicate normalized alias" in e for e in errors)
    assert any("missing disambiguation note" in e for e in errors)
    assert any("mistakenly references milled white rice" in e for e in errors)
    assert any("mistakenly references unmilled paddy" in e for e in errors)
    assert any("Duplicate variety_code" in e for e in errors)
    assert any("must not collide with product_code" in e for e in errors)


def test_validate_units_catches_all_defects(tmp_path) -> None:
    """Ensure validate_units rejects all invalid unit schema configurations."""
    import yaml

    bad_units = [
        {
            "unit_code": "kg",
            "name_fr": "Kilo 1",
            "kind": "mass",
            "target_unit": "kg",
            "factor": 1.0,
            "confidence": 1.0,
            "evidence": "SI proof",
        },
        {
            "unit_code": "kg",
            "name_fr": "Kilo Duplicate",
            "kind": "mass",
            "target_unit": "kg",
            "factor": 1.0,
            "confidence": 1.0,
            "evidence": "SI proof",
        },
        {
            "unit_code": "bad_mass",
            "name_fr": "Bad Mass",
            "kind": "mass",
            "target_unit": "l",
            "factor": 1.0,
            "confidence": 1.0,
            "evidence": "Contradictory SI",
        },
        {
            "unit_code": "bad_volume",
            "name_fr": "Bad Volume",
            "kind": "volume",
            "target_unit": "kg",
            "factor": 1.0,
            "confidence": 1.0,
            "evidence": "Contradictory SI",
        },
        {
            "unit_code": "high_no_ev",
            "name_fr": "High No Ev",
            "kind": "package",
            "target_unit": "kg",
            "factor": 10.0,
            "confidence": 0.85,
            "evidence": "",
        },
        {
            "unit_code": "bad_override",
            "name_fr": "Bad Override",
            "kind": "local",
            "product_specific": {
                "RICE_WHITE_LOCAL": {
                    "factor": 1.0,
                    "target_unit": "yards",
                    "confidence": 0.85,
                    "evidence": "",
                }
            },
        },
    ]
    units_file = tmp_path / "units.yaml"
    with open(units_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(bad_units, f)

    errors = validate_units(units_file)
    assert any("Duplicate unit_code" in e for e in errors)
    assert any("Mass unit 'bad_mass' must have target_unit 'kg'" in e for e in errors)
    assert any("Volume unit 'bad_volume' must have target_unit 'l'" in e for e in errors)
    assert any("has confidence 0.85 >= 0.8 but missing evidence" in e for e in errors)
    assert any(
        "override for 'RICE_WHITE_LOCAL' has confidence >= 0.8 but missing evidence" in e
        for e in errors
    )
    assert any(
        "override for 'RICE_WHITE_LOCAL' has invalid target_unit 'yards'" in e for e in errors
    )


def test_get_unit_and_conversion_exceptions() -> None:
    """Verify KeyError exceptions when unknown unit codes are queried."""
    from ketrika.core.units import get_unit

    u = get_unit("kg")
    assert u.unit_code == "kg"

    with pytest.raises(KeyError, match="not found in taxonomy"):
        get_unit("NON_EXISTENT_UNIT")

    with pytest.raises(KeyError, match="Unknown unit code"):
        convert_to_base(10.0, "NON_EXISTENT_UNIT")

    with pytest.raises(KeyError, match="Unknown unit code"):
        convert_from_base(10.0, "NON_EXISTENT_UNIT")


def test_aggregation_guards_additional_invariants() -> None:
    """Verify multiple products refusal, empty groups and negative price filtering."""
    # 1. Multiple products
    i1 = ComparablePriceItem(
        price_mga_per_base=Decimal("2000"), base_unit="kg", product_code="RICE_WHITE_LOCAL"
    )
    i2 = ComparablePriceItem(
        price_mga_per_base=Decimal("1500"), base_unit="kg", product_code="MAIZE_GRAIN"
    )
    with pytest.raises(IncompatibleAggregationError, match="cannot_aggregate_multiple_products"):
        validate_comparable_group([i1, i2])

    # 2. Empty group
    with pytest.raises(ValueError, match="empty_aggregation_group"):
        validate_comparable_group([])

    # 3. Filtering negative and zero prices
    i_neg = ComparablePriceItem(price_mga_per_base=Decimal("-500"), base_unit="kg")
    i_zero = ComparablePriceItem(price_mga_per_base=Decimal("0"), base_unit="kg")
    assert filter_comparable_items([i_neg, i_zero]) == []
