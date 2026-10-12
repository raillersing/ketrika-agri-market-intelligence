"""Prepared explicit missing-marker binding, not source or SQL qualification."""

import copy
import json
from decimal import Decimal

import pytest

from ketrika.core.provenance import ProofError, verify_cells
from ketrika.core.provenance_audit import bind_observation
from tests.unit.test_provenance_audit import price_example


def missing(raw="ND", code="ND"):
    observation, content = price_example()
    observation.price_value = None
    observation.price_mga_per_base = None
    observation.price_raw, observation.missing_code = raw, code
    proof = observation.evidence["provenance"]
    proof["cells"][0].update(field="price_raw", kind="text", expected="UNTRUSTED_EXPECTATION")
    payload = json.loads(content)
    payload[0]["price_value"] = raw
    return observation, json.dumps(payload).encode()


@pytest.mark.parametrize(
    "raw,code",
    [
        ("ND", "ND"),
        ("NA", "NA"),
        ("nd", "ND"),
        (" ND ", "ND"),
        ("-", "ND"),
        ("", "ND"),
        ("ＮＤ", "ND"),
    ],
)
def test_explicit_missing_marker_matches_exact_source_without_mutating_evidence(raw, code):
    row, content = missing(raw, code)
    before = copy.deepcopy(row.evidence)
    claim = bind_observation("price_observation", row)
    assert claim.proof["cells"][0]["expected"] == raw
    assert verify_cells(content, "application/json", claim.proof) == 5
    assert row.evidence == before
    assert row.price_value is None and row.price_mga_per_base is None


@pytest.mark.parametrize("field", ["price_value", "price_mga_per_base"])
def test_numeric_value_cannot_also_claim_missingness(field):
    row, _ = missing()
    setattr(row, field, Decimal("0"))
    with pytest.raises(ProofError, match="^binding_missingness_conflict$"):
        bind_observation("price_observation", row)


@pytest.mark.parametrize(
    "raw,code",
    [
        ("ND", "NA"),
        ("NA", "ND"),
        ("0", "ND"),
        ("N.D.", "ND"),
        ("unknown", "ND"),
        ("ND", "invented"),
        ("x" * 129, "ND"),
    ],
)
def test_invalid_or_discordant_marker_is_not_guessed(raw, code):
    row, _ = missing(raw, code)
    with pytest.raises(ProofError, match="^binding_missing_marker_invalid$"):
        bind_observation("price_observation", row)


def test_null_without_explicit_code_keeps_historical_refusal():
    row, _ = missing(code=None)
    with pytest.raises(ProofError, match="^binding_value_or_identity_missing$"):
        bind_observation("price_observation", row)


def test_old_numeric_cell_is_not_implicitly_reinterpreted_as_absence():
    row, _ = missing()
    row.evidence["provenance"]["cells"][0].update(field="price_value", kind="number")
    with pytest.raises(ProofError, match="^invalid_bound_field$"):
        bind_observation("price_observation", row)


@pytest.mark.parametrize("actual", ["NA", "0", 0, None])
def test_document_marker_must_equal_the_stored_raw_text(actual):
    row, content = missing()
    payload = json.loads(content)
    payload[0]["price_value"] = actual
    with pytest.raises(ProofError, match="^value_mismatch$"):
        verify_cells(
            json.dumps(payload).encode(),
            "application/json",
            bind_observation("price_observation", row).proof,
        )


def test_all_identity_cells_still_required_for_missing_observation():
    row, _ = missing()
    row.evidence["provenance"]["cells"].pop()
    with pytest.raises(ProofError, match="^binding_fields_missing$"):
        bind_observation("price_observation", row)
