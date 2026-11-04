"""Synthetic ZIP/context proofs test byte binding, never authentic source quality."""

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
from ketrika.core.provenance_wb_archive import bind_archive_observation
from tests.unit.test_wb_archive import MEMBER, ROW, packet


def proof_example_data():
    primary_id, context_id = uuid4(), uuid4()
    contents = (
        packet(),
        json.dumps(
            {
                "study_desc": {
                    "title_statement": {
                        "idno": "MDG_2021_RTFP_v02_M",
                        "title": "Monthly food price estimates by product and market",
                    }
                },
                "additional": {
                    "ticker_info": [
                        {
                            "iso3": "MDG",
                            "ticker": "rice",
                            "full_name": "Rice (local)",
                            "units": "KG",
                        }
                    ]
                },
            }
        ).encode(),
    )
    references = {}
    objects = {}
    for identity, content, extension, mime in zip(
        (primary_id, context_id),
        contents,
        ("zip", "json"),
        ("application/octet-stream", "application/json"),
        strict=True,
    ):
        digest = hashlib.sha256(content).hexdigest()
        key = f"wb_rtfp_mdg/2026/11/{digest}.{extension}"
        references[identity] = ArtifactReference(identity, "wb_rtfp_mdg", key, digest, mime)
        objects[key] = content
    proof = {
        "version": 2,
        "format": "rtfp_zip_csv_v1",
        "member": MEMBER,
        "row": 0,
        "ticker_index": 0,
        "price_field": "c_rice",
        "location_field": "mkt_name",
        "context_source_record_id": str(context_id),
        "expected": {
            "price_value": "1234.5679",
            "price_raw": "1234.567890",
            "product_raw": "Rice (local)",
            "unit_raw": "KG",
            "currency_raw": "MGA",
            "period_start": "2026-09-01",
            "location_raw": "Market Average",
        },
    }
    claim = ObservationClaim(uuid4(), primary_id, proof)

    class Reader:
        def __init__(self):
            self.calls = []

        def get(self, key):
            self.calls.append(key)
            return objects[key]

    reader = Reader()
    return claim, references, objects, reader


@pytest.fixture
def example():
    return proof_example_data()


def test_original_archive_and_context_read_once_for_multiple_claims(example):
    claim, references, _, reader = example
    claims = [claim, replace(claim, observation_id=uuid4())]
    report = ProvenanceVerifier(reader, references).verify(claims)
    assert report.passed and report.total == 2
    assert report.objects_read == report.object_read_attempts == 2
    assert len(reader.calls) == len(set(reader.calls)) == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("price_value", "1234.5678"),
        ("price_raw", "1234.56789"),
        ("product_raw", "Rice (imported)"),
        ("unit_raw", "TONNE"),
        ("currency_raw", "USD"),
        ("period_start", "2026-08-01"),
        ("location_raw", "Antananarivo"),
    ],
)
def test_stored_value_and_identities_are_bound(example, field, value):
    claim, references, _, reader = example
    claim.proof["expected"][field] = value
    assert not ProvenanceVerifier(reader, references).verify([claim]).passed


@pytest.mark.parametrize(
    "field,value",
    [
        ("row", True),
        ("row", -1),
        ("row", 250000),
        ("ticker_index", True),
        ("ticker_index", 128),
        ("price_field", "rice"),
        ("location_field", "adm1_name"),
        ("member", "../data.csv"),
        ("context_source_record_id", "bad"),
    ],
)
def test_unsupported_coordinates_fail_without_primary_reads(example, field, value):
    claim, references, _, reader = example
    claim.proof[field] = value
    report = ProvenanceVerifier(reader, references).verify([claim])
    assert not report.passed and report.objects_read == 0


def test_missing_or_wrong_source_context_refused(example):
    claim, references, _, reader = example
    context_id = next(key for key in references if key != claim.source_record_id)
    references[context_id] = replace(references[context_id], source_id="other")
    assert not ProvenanceVerifier(reader, references).verify([claim]).passed
    assert reader.calls == []


def test_tampered_primary_bytes_refused(example):
    claim, references, objects, reader = example
    key = references[claim.source_record_id].object_key
    objects[key] += b"tamper"
    report = ProvenanceVerifier(reader, references).verify([claim])
    assert report.results[0].reason == "sha256_mismatch"


def test_valid_hash_cannot_turn_a_region_into_national(example):
    claim, references, objects, reader = example
    content = packet(rows=[[*ROW[:7], "gid_region", *ROW[8:]]])
    digest = hashlib.sha256(content).hexdigest()
    key = f"wb_rtfp_mdg/2026/11/{digest}.zip"
    references[claim.source_record_id] = replace(
        references[claim.source_record_id], content_sha256=digest, object_key=key
    )
    objects[key] = content
    assert not ProvenanceVerifier(reader, references).verify([claim]).passed


def test_duplicate_observation_is_not_hidden_by_composition(example):
    claim, references, _, reader = example
    report = ProvenanceVerifier(reader, references).verify([claim, claim])
    assert report.valid == 1 and report.results[1].reason == "duplicate_observation"


def stored(claim):
    return SimpleNamespace(
        observation_id=claim.observation_id,
        source_record_id=claim.source_record_id,
        extraction_method="deterministic",
        observed_or_imputed="imputed",
        actor_level="unknown",
        missing_code=None,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        evidence={"price_identity": {"statistical_kind": "point"}},
        price_value=Decimal("1234.5679"),
        price_raw="1234.567890",
        product_raw="Rice (local)",
        location_raw="Market Average",
        currency_raw="MGA",
        unit_raw="KG",
    )


def test_binding_replaces_all_caller_expectations(example):
    claim, references, _, reader = example
    observation = stored(claim)
    forged = copy.deepcopy(claim.proof)
    forged["expected"]["price_value"] = "1"
    bound = bind_archive_observation(observation, forged)
    assert bound.proof["expected"]["price_value"] == "1234.5679"
    assert ProvenanceVerifier(reader, references).verify([bound]).passed


@pytest.mark.parametrize(
    "field,value",
    [
        ("observed_or_imputed", "observed"),
        ("actor_level", "retail"),
        ("period_end", date(2026, 9, 29)),
        ("missing_code", "ND"),
        ("price_value", Decimal("NaN")),
    ],
)
def test_binding_refuses_false_semantics(example, field, value):
    claim, *_ = example
    observation = stored(claim)
    setattr(observation, field, value)
    with pytest.raises(ProofError):
        bind_archive_observation(observation, claim.proof)
