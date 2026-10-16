"""Bounded WB close-estimate/data-context composition (ADR-070).

Children reuse the existing byte/cell verifier. Synthetic verification IDs are
internal only, never observations, and collapse back to one result per DB row.
"""

import calendar
import copy
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid5

from ketrika.core.provenance import (
    ArtifactReference,
    ObservationClaim,
    ProofError,
    ProvenanceVerifier,
    VerificationReport,
    VerificationResult,
)

FORMAT = "rtfp_json_v1"
FIELDS = {"c_rice": "rice", "c_sugar": "sugar", "c_wheat_flour": "wheat_flour"}
EXPECTED = {
    "price_value",
    "price_raw",
    "product_raw",
    "unit_raw",
    "currency_raw",
    "period_start",
    "location_raw",
}


def is_context_proof(proof: Mapping[str, Any]) -> bool:
    return (
        type(proof.get("version")) is int
        and proof.get("version") == 2
        and proof.get("format") == FORMAT
    )


def context_reference(proof: Mapping[str, Any]) -> UUID:
    try:
        identity = UUID(proof["context_source_record_id"])
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ProofError("rtfp_context_reference_invalid") from None
    if identity.int == 0:
        raise ProofError("rtfp_context_reference_invalid")
    return identity


def _coordinates(proof: Mapping[str, Any]) -> None:
    allowed = {
        "version",
        "format",
        "context_source_record_id",
        "row",
        "ticker_index",
        "price_field",
        "location_field",
        "expected",
        "raw_encoding",
    }
    if not is_context_proof(proof) or set(proof) - allowed:
        raise ProofError("rtfp_proof_invalid")
    for field, limit in (("row", 999), ("ticker_index", 127)):
        if type(proof.get(field)) is not int or not 0 <= proof[field] <= limit:
            raise ProofError("rtfp_coordinates_invalid")
    if not isinstance(proof.get("price_field"), str) or not isinstance(
        proof.get("location_field"), str
    ):
        raise ProofError("rtfp_field_not_supported")
    if proof.get("price_field") not in FIELDS or proof.get("location_field") not in {
        "adm1_name",
        "adm2_name",
        "mkt_name",
    }:
        raise ProofError("rtfp_field_not_supported")
    if proof.get("raw_encoding") not in (None, "json_number_lexeme"):
        raise ProofError("unsupported_raw_encoding")
    context_reference(proof)


def bind_rtfp_observation(observation: Any, proof: Mapping[str, Any]) -> ObservationClaim:
    _coordinates(proof)
    if (
        observation.extraction_method != "deterministic"
        or observation.observed_or_imputed != "imputed"
        or observation.actor_level != "unknown"
        or observation.missing_code is not None
        or type(observation.period_start) is not date
        or observation.period_start.day != 1
        or observation.period_end
        != date(
            observation.period_start.year,
            observation.period_start.month,
            calendar.monthrange(observation.period_start.year, observation.period_start.month)[1],
        )
        or (observation.evidence or {}).get("price_identity", {}).get("statistical_kind") != "point"
    ):
        raise ProofError("rtfp_semantics_not_supported")
    number = observation.price_value
    if type(number) is not Decimal or not number.is_finite() or number <= 0:
        raise ProofError("invalid_bound_number")
    bound = copy.deepcopy(dict(proof))
    bound["expected"] = {field: getattr(observation, field) for field in EXPECTED}
    bound["expected"]["price_value"] = str(number)
    bound["expected"]["period_start"] = observation.period_start.isoformat()
    if any(not isinstance(value, str) or not value for value in bound["expected"].values()):
        raise ProofError("rtfp_binding_missing")
    return ObservationClaim(observation.observation_id, observation.source_record_id, bound)


def _expand(
    claim: ObservationClaim, references: Mapping[UUID, ArtifactReference]
) -> tuple[ObservationClaim, ...]:
    proof = claim.proof
    _coordinates(proof)
    expected = proof.get("expected")
    if (
        not isinstance(expected, dict)
        or set(expected) != EXPECTED
        or any(not isinstance(v, str) or not v for v in expected.values())
    ):
        raise ProofError("rtfp_binding_missing")
    primary = references.get(claim.source_record_id) if claim.source_record_id else None
    context = references.get(context_reference(proof))
    if primary is None or context is None:
        raise ProofError("source_record_missing")
    if primary.source_id != "wb_rtfp_mdg" or context.source_id != primary.source_id:
        raise ProofError("rtfp_context_source_mismatch")
    if (
        primary.source_record_id == context.source_record_id
        or primary.object_key == context.object_key
    ):
        raise ProofError("rtfp_context_self_reference")
    if any(
        item.mime_type.split(";")[0].strip().lower() != "application/json"
        for item in (primary, context)
    ):
        raise ProofError("unsupported_format")
    scope = ["data", proof["row"]]
    cells = []
    for field, column in (
        ("price_value", proof["price_field"]),
        ("location_raw", proof["location_field"]),
        ("period_start", "price_date"),
        ("currency_raw", "currency"),
    ):
        cell = {
            "field": field,
            "path": scope + [column],
            "role": "value" if field == "price_value" else "identity",
            "kind": "number" if field == "price_value" else "text",
            "expected": expected[field],
        }
        if field == "price_value":
            cell.update(raw_expected=expected["price_raw"], normalization="quantize_4_half_up")
            if proof.get("raw_encoding"):
                cell["raw_encoding"] = proof["raw_encoding"]
        cells.append(cell)
    cells.append(
        {
            "field": "country",
            "path": scope + ["ISO3"],
            "role": "identity",
            "kind": "text",
            "expected": "MDG",
        }
    )
    primary_proof = {"version": 1, "format": "json", "scope_path": scope, "cells": cells}
    scope = ["additional", "ticker_info", proof["ticker_index"]]
    cells = [
        {
            "field": "product_raw",
            "path": scope + ["full_name"],
            "role": "identity",
            "kind": "text",
            "expected": expected["product_raw"],
        },
        {
            "field": "unit_raw",
            "path": scope + ["units"],
            "role": "value",
            "kind": "text",
            "expected": expected["unit_raw"],
        },
        {
            "field": "ticker",
            "path": scope + ["ticker"],
            "role": "identity",
            "kind": "text",
            "expected": FIELDS[proof["price_field"]],
        },
        {
            "field": "country",
            "path": scope + ["iso3"],
            "role": "identity",
            "kind": "text",
            "expected": "MDG",
        },
    ]
    context_proof = {"version": 1, "format": "json", "scope_path": scope, "cells": cells}
    scope = ["study_desc", "title_statement"]
    header_proof = {
        "version": 1,
        "format": "json",
        "scope_path": scope,
        "cells": [
            {
                "field": "dataset",
                "path": scope + ["idno"],
                "role": "identity",
                "kind": "text",
                "expected": "MDG_2021_RTFP_v02_M",
            },
            {
                "field": "title",
                "path": scope + ["title"],
                "role": "value",
                "kind": "text",
                "expected": "Monthly food price estimates by product and market",
            },
        ],
    }
    return tuple(
        ObservationClaim(uuid5(claim.observation_id, label), record, part)
        for label, record, part in (
            ("data", claim.source_record_id, primary_proof),
            ("context", context.source_record_id, context_proof),
            ("dataset", context.source_record_id, header_proof),
        )
    )


def verify_context_batch(
    verifier: ProvenanceVerifier,
    claims: Sequence[ObservationClaim],
    mode: Literal["complete", "incremental"],
) -> VerificationReport:
    expanded: list[ObservationClaim] = []
    mapping: dict[int, tuple[ObservationClaim, ...]] = {}
    failures = {}
    contexts = set()
    for index, claim in enumerate(claims):
        try:
            if is_context_proof(claim.proof):
                contexts.add(context_reference(claim.proof))
                if len(contexts) > 16:
                    raise ProofError("rtfp_context_limit")
                children = _expand(claim, verifier.references)
            else:
                children = (claim,)
            mapping[index] = children
            expanded.extend(children)
        except ProofError as error:
            failures[index] = str(error)
    report = verifier.verify(expanded, mode)
    # Results are positional, not a dict by UUID: duplicate IDs must remain failures.
    cursor, results = 0, []
    for index, claim in enumerate(claims):
        if index in failures:
            results.append(
                VerificationResult(
                    claim.observation_id, claim.source_record_id, False, failures[index]
                )
            )
            continue
        child_results = report.results[cursor : cursor + len(mapping[index])]
        cursor += len(child_results)
        failed = next((item for item in child_results if not item.passed), None)
        first = child_results[0]
        results.append(
            VerificationResult(
                claim.observation_id,
                claim.source_record_id,
                failed is None,
                failed.reason if failed else None,
                first.object_key if failed is None else None,
                first.content_sha256 if failed is None else None,
            )
        )
    return VerificationReport(
        mode, tuple(results), report.objects_read, report.object_read_attempts
    )
