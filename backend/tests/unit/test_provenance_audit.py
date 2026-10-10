"""SQL-field bindings are trusted; document expectations are not."""

from __future__ import annotations

import copy
import json
from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from ketrika.core.models.db import PriceObservation, WeatherObservation
from ketrika.core.provenance import ProofError, verify_cells
from ketrika.core.provenance_audit import audit_observation_provenance, bind_observation
from tests.unit.test_provenance import MemoryReader


def price_example() -> tuple[PriceObservation, bytes]:
    fields: dict[str, Any] = {
        "price_value": "3000.1250",
        "product_raw": "rice",
        "period_start": "2024-01-01",
        "unit_raw": "kg",
        "currency_raw": "MGA",
    }
    cells = [
        {
            "field": field,
            "path": [0, field],
            "role": "value" if field == "price_value" else "identity",
            "kind": "number" if field == "price_value" else "text",
            "expected": "untrusted expectation",
        }
        for field in fields
    ]
    observation = PriceObservation(
        observation_id=uuid4(),
        source_record_id=uuid4(),
        natural_key=uuid4().hex,
        product_raw="rice",
        location_raw=None,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 1),
        price_value=Decimal("3000.1250"),
        price_raw="3000.1250",
        unit_raw="kg",
        currency_raw="MGA",
        actor_level="retail",
        conversion_status="converted",
        observed_or_imputed="observed",
        extraction_method="deterministic",
        confidence=Decimal("1.0"),
        evidence={
            "provenance": {"version": 1, "format": "json", "scope_path": [0], "cells": cells}
        },
    )
    return observation, json.dumps([fields]).encode()


def test_sql_binding_overrides_untrusted_expectations_without_mutation():
    observation, content = price_example()
    before = copy.deepcopy(observation.evidence)
    claim = bind_observation("price_observation", observation)
    assert verify_cells(content, "application/json", claim.proof) == 5
    assert claim.proof["cells"][0]["expected"] == "3000.1250"
    assert claim.proof["cells"][0]["raw_expected"] == "3000.1250"
    assert observation.evidence == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("price_value", Decimal("4000")),
        ("product_raw", "maize"),
        ("period_start", date(2024, 2, 1)),
        ("currency_raw", "USD"),
        ("unit_raw", "litre"),
    ],
)
def test_stored_value_or_identity_mismatch_cannot_pass(field, value):
    observation, content = price_example()
    setattr(observation, field, value)
    with pytest.raises(ProofError):
        verify_cells(
            content, "application/json", bind_observation("price_observation", observation).proof
        )


def test_raw_value_mismatch_is_not_hidden_by_numeric_equality():
    observation, content = price_example()
    observation.price_raw = "03000.1250"
    with pytest.raises(ProofError, match="raw_value_mismatch"):
        verify_cells(
            content, "application/json", bind_observation("price_observation", observation).proof
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "unknown",
        "duplicate",
        "role",
        "kind",
        "raw_missing",
        "value_missing",
        "float",
        "nan",
        "noncell",
    ],
)
def test_invalid_bindings_fail_closed(mutation):
    observation, _ = price_example()
    cells = observation.evidence["provenance"]["cells"]
    if mutation == "missing":
        cells.pop()
    elif mutation == "unknown":
        cells[0]["field"] = "__dict__"
    elif mutation == "duplicate":
        cells.append(copy.deepcopy(cells[0]))
    elif mutation == "role":
        cells[0]["role"] = "identity"
    elif mutation == "kind":
        cells[0]["kind"] = "text"
    elif mutation == "raw_missing":
        observation.price_raw = None
    elif mutation == "value_missing":
        observation.price_value = None
    elif mutation == "float":
        observation.price_value = 3000.125
    elif mutation == "nan":
        observation.price_value = Decimal("NaN")
    else:
        cells[0] = "ignore policy"
    with pytest.raises(ProofError):
        bind_observation("price_observation", observation)


@pytest.mark.parametrize(
    "evidence", [None, {}, {"provenance": None}, {"provenance": {"cells": {}}}]
)
def test_absent_structured_proof_is_not_accepted(evidence):
    observation, _ = price_example()
    observation.evidence = evidence
    with pytest.raises(ProofError, match="binding_proof_missing"):
        bind_observation("price_observation", observation)


def test_weather_without_evidence_is_not_excluded_or_certified():
    with pytest.raises(ProofError, match="binding_proof_missing"):
        bind_observation("weather_observation", WeatherObservation())


@pytest.mark.parametrize("method", ["llm_verified", "dual_agree", "unknown"])
def test_extraction_label_is_not_a_mechanical_llm_proof(method):
    observation, _ = price_example()
    observation.extraction_method = method
    with pytest.raises(ProofError, match="extraction_proof_not_supported"):
        bind_observation("price_observation", observation)


@pytest.mark.parametrize("table", ["unknown", "trade_flow", "price_observation.__dict__"])
def test_wrong_model_or_unknown_table_refused(table):
    observation, _ = price_example()
    with pytest.raises(ProofError, match="unsupported_observation"):
        bind_observation(table, observation)


def test_empty_simulated_selection_has_no_100_percent_metric():
    session = MagicMock()
    session.scalars.return_value.all.return_value = []
    result = audit_observation_provenance(session, MemoryReader({}))
    assert result.report.total == 0 and result.report.rate is None
    assert not result.report.passed
    dq = session.add.call_args.args[0]
    assert dq.metric is None and not dq.passed
    assert session.scalars.call_count == 6
    session.commit.assert_not_called()


def test_invalid_audit_mode_is_refused_before_sql():
    session = MagicMock()
    with pytest.raises(ValueError):
        audit_observation_provenance(session, MemoryReader({}), mode="unsafe")  # type: ignore[arg-type]
    session.scalars.assert_not_called()
