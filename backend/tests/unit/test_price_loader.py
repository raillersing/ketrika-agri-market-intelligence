"""Normalization/load contract; actual SQL receipt still required for delivery."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from ketrika.connectors.records import PriceRecord
from ketrika.core.models.db import Location, PriceObservation, Product, SourceRecord, UnitConversion
from ketrika.normalize.price_loader import load_normalized_price
from ketrika.normalize.price_references import ReferenceMatch
from ketrika.normalize.supersede import load_observation_with_supersession


def record(**changes):
    return PriceRecord(
        **(
            {
                "product_raw": "Riz blanc local",
                "location_raw": "Antananarivo",
                "period_start": date(2024, 1, 1),
                "period_end": date(2024, 1, 31),
                "price_raw": "2850.1250",
                "price_value": 999.0,
                "unit_raw": "kg",
                "currency_raw": "MGA",
                "evidence": {"provenance": {"version": 1, "format": "csv", "cells": []}},
            }
            | changes
        )
    )


def environment():
    session = MagicMock()
    source_record_id = uuid4()
    session.get.return_value = SourceRecord(source_id="dummy_normalize")
    product = ReferenceMatch(
        Product(product_id=uuid4(), base_unit="kg"),
        Decimal(1),
        "exact_global_alias",
        ("synthetic-product-alias",),
    )
    location = ReferenceMatch(
        Location(location_id=uuid4()),
        Decimal(1),
        "exact_global_alias",
        ("synthetic-location-alias",),
    )
    factor = UnitConversion(
        unit_code="kg",
        factor=Decimal(1),
        confidence=Decimal(1),
        base_unit="kg",
        evidence="SI; synthetic test",
    )
    return session, source_record_id, product, location, factor


@pytest.mark.parametrize(
    "actor", ["retail", "wholesale", "producer", "farmgate", "official_ppn", "listing", "unknown"]
)
def test_raw_decimal_and_proof_preserved_derived_currency_and_compare_fields(actor):
    session, reference, product, location, factor = environment()
    rec = record(
        price_raw="14250.1250",
        currency_raw="FMG",
        value_kind="avg",
        confidence=0.98765,
        actor_level=actor,
    )
    original = deepcopy(rec.evidence)
    captured = []

    def loader(*args, **kwargs):
        captured.append(args[3](uuid4()))
        assert args[4]["currency_raw"] == "FMG"
        assert kwargs["evidence_fields"] == {("normalization", "value_kind"): "avg"}
        return "inserted", captured[0].observation_id

    with (
        patch("ketrika.normalize.price_loader.resolve_product", return_value=product),
        patch("ketrika.normalize.price_loader.resolve_location", return_value=location),
        patch("ketrika.normalize.price_loader.unit_factor", return_value=factor),
        patch(
            "ketrika.normalize.price_loader.load_observation_with_supersession", side_effect=loader
        ),
        patch("ketrika.normalize.price_loader.create_review_item") as review,
    ):
        result = load_normalized_price(session, rec, "dummy_normalize", reference)
    observation = captured[0]
    assert observation.price_value == Decimal("14250.1250")
    assert observation.price_raw == rec.price_raw and observation.currency_raw == "FMG"
    assert observation.actor_level == actor
    assert observation.price_mga_per_base == Decimal("2850.0250")
    assert observation.confidence == Decimal("0.98")
    assert observation.evidence["provenance"] == original["provenance"]
    assert rec.evidence == original and observation.review_status == "accepted"
    assert result.review_items == 0
    review.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "variant", ["product", "location", "currency", "factor", "number", "ambiguous_style"]
)
@pytest.mark.parametrize("action", ["inserted", "idempotent_skipped"])
def test_unresolved_nonconvertible_retained_without_duplicate_review(variant, action):
    session, reference, product, location, factor = environment()
    rec = record(
        **(
            {"currency_raw": "USD"}
            if variant == "currency"
            else {"price_raw": "invalid"}
            if variant == "number"
            else {"price_raw": "2.850"}
            if variant == "ambiguous_style"
            else {}
        )
    )
    captured = []
    observation_id = uuid4()

    def loader(*args, **kwargs):
        captured.append(args[3](observation_id))
        return action, observation_id

    with (
        patch(
            "ketrika.normalize.price_loader.resolve_product",
            return_value=None if variant == "product" else product,
        ),
        patch(
            "ketrika.normalize.price_loader.resolve_location",
            return_value=None if variant == "location" else location,
        ),
        patch(
            "ketrika.normalize.price_loader.unit_factor",
            return_value=None if variant == "factor" else factor,
        ),
        patch(
            "ketrika.normalize.price_loader.load_observation_with_supersession", side_effect=loader
        ),
        patch("ketrika.normalize.price_loader.create_review_item") as review,
    ):
        result = load_normalized_price(session, rec, "dummy_normalize", reference)
    observation = captured[0]
    assert observation.price_mga_per_base is None and observation.review_status == "pending"
    assert observation.price_raw == rec.price_raw and observation.unit_raw == rec.unit_raw
    if action == "idempotent_skipped":
        assert result.review_items == 0
        review.assert_not_called()
    else:
        assert result.review_items > 0 and review.call_count == result.review_items
        assert all(
            "reason" in call.args[2] and "raw" not in call.args[2] for call in review.call_args_list
        )


@pytest.mark.parametrize("source", [None, "other_source"])
def test_reference_mismatch_refused_before_resolution(source):
    session = MagicMock()
    session.get.return_value = SourceRecord(source_id=source) if source else None
    with patch("ketrika.normalize.price_loader.resolve_product") as resolve:
        with pytest.raises(ValueError, match="normalization_source_reference_mismatch"):
            load_normalized_price(session, record(), "dummy_normalize", uuid4())
    resolve.assert_not_called()


@pytest.mark.parametrize(
    "changes",
    [
        {"observed_or_imputed": "forecast"},
        {"value_kind": "unknown"},
        {"actor_level": "invented"},
        {"confidence": float("nan")},
        {"period_end": date(2023, 12, 31)},
        {"missing_code": "ND"},
    ],
)
def test_invalid_semantics_refused(changes):
    session, reference, *_ = environment()
    with pytest.raises(ValueError):
        load_normalized_price(session, record(**changes), "dummy_normalize", reference)


@pytest.mark.parametrize(
    "current_kind,wanted_kind,expected",
    [
        ("point", "point", "idempotent_skipped"),
        ("point", "avg", "superseded"),
        (None, "point", "superseded"),
    ],
)
def test_semantic_metadata_supersession_not_full_evidence(current_kind, wanted_kind, expected):
    session = MagicMock()
    current = PriceObservation(
        observation_id=uuid4(),
        price_raw="2850",
        evidence={"normalization": {"value_kind": current_kind}, "source_document": "prior"},
    )
    session.execute.return_value.scalar_one_or_none.return_value = current
    action, _ = load_observation_with_supersession(
        session,
        PriceObservation,
        "synthetic_key",
        lambda identifier: PriceObservation(observation_id=identifier),
        {"price_raw": "2850"},
        evidence_fields={("normalization", "value_kind"): wanted_kind},
    )
    assert action == expected
    if expected == "idempotent_skipped":
        session.add.assert_not_called()
    else:
        assert session.add.call_count == 1
    assert current.price_raw == "2850" and current.evidence["source_document"] == "prior"
    session.commit.assert_not_called()
