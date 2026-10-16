"""Synthetic adversarial composition tests, not market/model qualification."""

import copy
import hashlib
import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ketrika.core.provenance import (
    ArtifactReference,
    ObservationClaim,
    ProofError,
    ProvenanceVerifier,
)
from ketrika.core.provenance_rtfp import bind_rtfp_observation


def sample():
    data = {
        "data": [
            {
                "ISO3": "MDG",
                "c_rice": "1234.56785",
                "currency": "MGA",
                "price_date": "2024-02-01",
                "mkt_name": "Test market",
            }
        ]
    }
    study = {
        "study_desc": {
            "title_statement": {
                "idno": "MDG_2021_RTFP_v02_M",
                "title": "Monthly food price estimates by product and market",
            }
        },
        "additional": {
            "ticker_info": [
                {"iso3": "MDG", "ticker": "rice", "full_name": "Rice (local)", "units": "KG"}
            ]
        },
    }
    references, objects = {}, {}
    identifiers = []
    for document in (data, study):
        content = json.dumps(document).encode()
        sha = hashlib.sha256(content).hexdigest()
        identifier = uuid4()
        key = f"wb_rtfp_mdg/2026/10/{sha}.json"
        references[identifier] = ArtifactReference(
            identifier, "wb_rtfp_mdg", key, sha, "application/json"
        )
        objects[key] = content
        identifiers.append(identifier)
    proof = {
        "version": 2,
        "format": "rtfp_json_v1",
        "context_source_record_id": str(identifiers[1]),
        "row": 0,
        "ticker_index": 0,
        "price_field": "c_rice",
        "location_field": "mkt_name",
    }
    observation = SimpleNamespace(
        observation_id=uuid4(),
        source_record_id=identifiers[0],
        extraction_method="deterministic",
        observed_or_imputed="imputed",
        actor_level="unknown",
        missing_code=None,
        period_start=date(2024, 2, 1),
        period_end=date(2024, 2, 29),
        evidence={"price_identity": {"statistical_kind": "point"}},
        price_value=Decimal("1234.5679"),
        price_raw="1234.56785",
        product_raw="Rice (local)",
        unit_raw="KG",
        currency_raw="MGA",
        location_raw="Test market",
    )
    return observation, proof, references, objects


class Reader:
    def __init__(self, objects):
        self.objects = objects
        self.calls = []

    def get(self, key):
        self.calls.append(key)
        return self.objects[key]


def test_composition_verifies_both_objects_once_and_counts_observations():
    observation, proof, references, objects = sample()
    reader = Reader(objects)
    claim = bind_rtfp_observation(observation, proof)
    report = ProvenanceVerifier(reader, references).verify([claim])
    assert report.passed, report.results
    assert (report.total, report.valid, report.objects_read) == (1, 1, 2)
    assert len(reader.calls) == 2


def test_numeric_json_lexeme_is_preserved_before_rounding():
    observation, proof, references, objects = sample()
    reference = references[observation.source_record_id]
    content = objects.pop(reference.object_key).replace(b'"1234.56785"', b"1234.56785")
    sha = hashlib.sha256(content).hexdigest()
    key = f"wb_rtfp_mdg/2026/10/{sha}.json"
    references[reference.source_record_id] = replace(reference, object_key=key, content_sha256=sha)
    objects[key] = content
    proof["raw_encoding"] = "json_number_lexeme"
    assert (
        ProvenanceVerifier(Reader(objects), references)
        .verify([bind_rtfp_observation(observation, proof)])
        .passed
    )


def test_wrong_country_with_valid_hash_is_still_rejected():
    observation, proof, references, objects = sample()
    identifier = next(key for key in references if key != observation.source_record_id)
    reference = references[identifier]
    content = objects.pop(reference.object_key).replace(b"MDG", b"XXX")
    sha = hashlib.sha256(content).hexdigest()
    key = f"wb_rtfp_mdg/2026/10/{sha}.json"
    references[identifier] = replace(reference, object_key=key, content_sha256=sha)
    objects[key] = content
    report = ProvenanceVerifier(Reader(objects), references).verify(
        [bind_rtfp_observation(observation, proof)]
    )
    assert not report.passed
    assert report.results[0].reason == "identity_mismatch"


@pytest.mark.parametrize(
    "field,value",
    [
        ("price_value", Decimal("1234.5678")),
        ("price_raw", "1234.5679"),
        ("product_raw", "Other rice"),
        ("unit_raw", "L"),
        ("currency_raw", "USD"),
        ("location_raw", "Elsewhere"),
    ],
)
def test_persisted_value_cannot_be_replaced_by_proof_expectations(field, value):
    observation, proof, references, objects = sample()
    setattr(observation, field, value)
    proof["expected"] = {"price_value": "1234.5679"}
    report = ProvenanceVerifier(Reader(objects), references).verify(
        [bind_rtfp_observation(observation, proof)]
    )
    assert not report.passed


@pytest.mark.parametrize(
    "field,value",
    [
        ("actor_level", "retail"),
        ("observed_or_imputed", "observed"),
        ("extraction_method", "llm_verified"),
        ("period_end", date(2024, 2, 28)),
        ("period_start", date(2024, 2, 2)),
        ("price_value", Decimal("NaN")),
    ],
)
def test_unsupported_semantics_fail_before_artifact_reads(field, value):
    observation, proof, _, _ = sample()
    setattr(observation, field, value)
    with pytest.raises(ProofError):
        bind_rtfp_observation(observation, proof)


@pytest.mark.parametrize(
    "failure",
    ["missing", "foreign", "mime", "corrupt", "self", "wrong_ticker", "wrong_country", "duplicate"],
)
def test_invalid_context_fails_closed(failure):
    observation, proof, references, objects = sample()
    context_id = next(key for key in references if key != observation.source_record_id)
    context = references[context_id]
    if failure == "missing":
        del references[context_id]
    elif failure == "foreign":
        references[context_id] = replace(context, source_id="other")
    elif failure == "mime":
        references[context_id] = replace(context, mime_type="text/html")
    elif failure == "corrupt":
        objects[context.object_key] += b" "
    elif failure == "self":
        proof["context_source_record_id"] = str(observation.source_record_id)
    elif failure in {"wrong_ticker", "wrong_country"}:
        proof["price_field"] = "c_sugar" if failure == "wrong_ticker" else "c_rice"
        if failure == "wrong_country":
            objects[context.object_key] = objects[context.object_key].replace(b"MDG", b"XXX")
    claim = bind_rtfp_observation(observation, proof)
    report = ProvenanceVerifier(Reader(objects), references).verify(
        [claim, copy.deepcopy(claim)] if failure == "duplicate" else [claim]
    )
    assert not report.passed
    assert report.total == (2 if failure == "duplicate" else 1)


@pytest.mark.parametrize(
    "field,value",
    [
        ("row", True),
        ("ticker_index", -1),
        ("price_field", "rice"),
        ("context_source_record_id", "bad"),
        ("version", 2.0),
    ],
)
def test_coordinates_are_bounded_and_typed(field, value):
    observation, proof, _, _ = sample()
    proof[field] = value
    with pytest.raises(ProofError):
        bind_rtfp_observation(observation, proof)


def test_unknown_composite_version_is_not_silently_accepted():
    observation, proof, references, objects = sample()
    claim = bind_rtfp_observation(observation, proof)
    invalid = dict(claim.proof, version=3)
    report = ProvenanceVerifier(Reader(objects), references).verify(
        [ObservationClaim(claim.observation_id, claim.source_record_id, invalid)]
    )
    assert not report.passed
