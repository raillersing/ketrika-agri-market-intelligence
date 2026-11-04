"""Original WB ZIP cells plus immutable study context (ADR-163)."""

from __future__ import annotations

import calendar
import copy
import hashlib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from typing import Any, Literal
from uuid import UUID, uuid5

from ketrika.core.provenance import (
    ArtifactReference,
    ObservationClaim,
    ProofError,
    ProvenanceVerifier,
    VerificationReport,
    VerificationResult,
    _validate_reference,
)
from ketrika.core.provenance_rtfp import EXPECTED, context_reference
from ketrika.core.wb_archive import MAX_ROWS, ArchiveError, _member_name, cells

FORMAT = "rtfp_zip_csv_v1"
NATIONAL = {
    "ISO3": "MDG",
    "country": "Madagascar",
    "adm1_name": "Market Average",
    "adm2_name": "Market Average",
    "mkt_name": "Market Average",
    "geo_id": "gid_mdg_national_average",
    "lat": "",
    "lon": "",
}
MIMES = {"application/zip", "application/octet-stream"}


def is_archive_proof(proof: Mapping[str, Any]) -> bool:
    return (
        type(proof.get("version")) is int
        and proof.get("version") == 2
        and proof.get("format") == FORMAT
    )


def coordinates(proof: Mapping[str, Any]) -> None:
    if not is_archive_proof(proof) or set(proof) - {
        "version",
        "format",
        "member",
        "row",
        "ticker_index",
        "price_field",
        "location_field",
        "context_source_record_id",
        "expected",
    }:
        raise ProofError("wb_archive_proof_invalid")
    if (
        type(proof.get("row")) is not int
        or not 0 <= proof["row"] < MAX_ROWS
        or type(proof.get("ticker_index")) is not int
        or not 0 <= proof["ticker_index"] < 128
        or proof.get("price_field") != "c_rice"
        or proof.get("location_field") != "mkt_name"
    ):
        raise ProofError("wb_archive_coordinates_invalid")
    try:
        _member_name(proof.get("member"))
    except ArchiveError as exc:
        raise ProofError(str(exc)) from None
    context_reference(proof)


def bind_archive_observation(observation: Any, proof: Mapping[str, Any]) -> ObservationClaim:
    coordinates(proof)
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
        raise ProofError("wb_archive_semantics_invalid")
    number = observation.price_value
    if type(number) is not Decimal or not number.is_finite() or number <= 0:
        raise ProofError("invalid_bound_number")
    bound = copy.deepcopy(dict(proof))
    bound["expected"] = {field: getattr(observation, field) for field in EXPECTED}
    bound["expected"]["price_value"] = str(number)
    bound["expected"]["period_start"] = observation.period_start.isoformat()
    if any(not isinstance(value, str) or not value for value in bound["expected"].values()):
        raise ProofError("wb_archive_binding_missing")
    return ObservationClaim(observation.observation_id, observation.source_record_id, bound)


def _expected(proof: Mapping[str, Any]) -> dict[str, str]:
    coordinates(proof)
    expected = proof.get("expected")
    if (
        not isinstance(expected, dict)
        or set(expected) != EXPECTED
        or any(not isinstance(value, str) or not value for value in expected.values())
    ):
        raise ProofError("wb_archive_binding_missing")
    return expected


def _primary(claim: ObservationClaim, source_cells: Mapping[tuple[Any, ...], str]) -> None:
    proof = claim.proof
    expected = _expected(proof)
    row = {
        column: source_cells[(proof["member"], proof["row"], column)]
        for column in {*NATIONAL, "price_date", "currency", "c_rice"}
    }
    if any(row[key] != value for key, value in NATIONAL.items()):
        raise ProofError("wb_archive_national_identity_invalid")
    try:
        period = date.fromisoformat(row["price_date"])
        vintage = date.fromisoformat(proof["member"][-14:-4])
        if period.day != 1 or not date(2020, 1, 1) <= period <= vintage.replace(day=1):
            raise ProofError("wb_archive_period_invalid")
        number = Decimal(row["c_rice"])
        if not number.is_finite() or number <= 0 or len(row["c_rice"]) > 128:
            raise ProofError("invalid_number")
        with localcontext() as arithmetic:
            arithmetic.prec = 64
            number = number.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if (
            number <= 0
            or number >= Decimal("100000000000000")
            or number != Decimal(expected["price_value"])
        ):
            raise ProofError("value_mismatch")
    except ProofError:
        raise
    except (ValueError, InvalidOperation):
        raise ProofError("wb_archive_value_or_period_invalid") from None
    for actual, field in (
        ("c_rice", "price_raw"),
        ("price_date", "period_start"),
        ("currency", "currency_raw"),
        ("mkt_name", "location_raw"),
    ):
        if row[actual] != expected[field]:
            raise ProofError("wb_archive_raw_or_identity_mismatch")


def _context_claims(claim: ObservationClaim) -> tuple[ObservationClaim, ...]:
    expected = _expected(claim.proof)
    scope = ["additional", "ticker_info", claim.proof["ticker_index"]]
    proof = {
        "version": 1,
        "format": "json",
        "scope_path": scope,
        "cells": [
            {
                "field": field,
                "path": scope + [column],
                "role": "value" if field == "unit_raw" else "identity",
                "kind": "text",
                "expected": value,
            }
            for field, column, value in (
                ("product_raw", "full_name", expected["product_raw"]),
                ("unit_raw", "units", expected["unit_raw"]),
                ("ticker", "ticker", "rice"),
                ("country", "iso3", "MDG"),
            )
        ],
    }
    header = ["study_desc", "title_statement"]
    dataset = {
        "version": 1,
        "format": "json",
        "scope_path": header,
        "cells": [
            {
                "field": field,
                "path": header + [column],
                "role": "value" if field == "title" else "identity",
                "kind": "text",
                "expected": value,
            }
            for field, column, value in (
                ("dataset", "idno", "MDG_2021_RTFP_v02_M"),
                ("title", "title", "Monthly food price estimates by product and market"),
            )
        ],
    }
    return tuple(
        ObservationClaim(uuid5(claim.observation_id, label), context_reference(claim.proof), part)
        for label, part in (("archive-context", proof), ("archive-dataset", dataset))
    )


def verify_archive_batch(
    verifier: ProvenanceVerifier,
    claims: Sequence[ObservationClaim],
    mode: Literal["complete", "incremental"],
) -> VerificationReport:
    """Read each primary once; prepare all requested cells in a single bounded pass."""
    groups: dict[str, list[tuple[int, ObservationClaim, ArtifactReference]]] = defaultdict(list)
    results: dict[int, VerificationResult] = {}
    pending: list[ObservationClaim] = []
    mapping: list[tuple[int, int]] = []
    seen: set[UUID] = set()
    contexts: set[UUID] = set()

    def failed(index: int, claim: ObservationClaim, reason: str) -> None:
        results[index] = VerificationResult(
            claim.observation_id, claim.source_record_id, False, reason
        )

    for index, claim in enumerate(claims):
        try:
            if claim.observation_id in seen:
                raise ProofError("duplicate_observation")
            seen.add(claim.observation_id)
            if not is_archive_proof(claim.proof):
                mapping.append((index, 1))
                pending.append(claim)
                continue
            _expected(claim.proof)
            primary = (
                verifier.references.get(claim.source_record_id) if claim.source_record_id else None
            )
            context = verifier.references.get(context_reference(claim.proof))
            if primary is None or context is None:
                raise ProofError("source_record_missing")
            if (
                primary.source_record_id != claim.source_record_id
                or primary.source_id != "wb_rtfp_mdg"
                or context.source_id != primary.source_id
                or primary.source_record_id == context.source_record_id
                or primary.object_key == context.object_key
                or primary.mime_type.split(";")[0].strip().lower() not in MIMES
                or context.mime_type.split(";")[0].strip().lower() != "application/json"
            ):
                raise ProofError("wb_archive_reference_invalid")
            _validate_reference(primary)
            _validate_reference(context)
            contexts.add(context.source_record_id)
            if len(contexts) > 16:
                raise ProofError("rtfp_context_limit")
            groups[primary.object_key].append((index, claim, primary))
        except ProofError as exc:
            failed(index, claim, str(exc))
    reads = attempts = 0
    for key, group in groups.items():
        attempts += 1
        try:
            content = verifier.reader.get(key)
            if not isinstance(content, bytes):
                raise TypeError
        except Exception:
            for index, claim, _ in group:
                failed(index, claim, "object_unavailable")
            continue
        reads += 1
        digest = hashlib.sha256(content).hexdigest()
        valid = []
        for index, claim, reference in group:
            if digest != reference.content_sha256.lower():
                failed(index, claim, "sha256_mismatch")
            else:
                valid.append((index, claim, reference))
        if not valid:
            continue
        try:
            requested = sorted(
                {
                    (claim.proof["member"], claim.proof["row"], column)
                    for _, claim, _ in valid
                    for column in {*NATIONAL, "price_date", "currency", "c_rice"}
                }
            )
            source_cells = cells(content, requested)
        except ArchiveError as exc:
            for index, claim, _ in valid:
                failed(index, claim, str(exc))
            continue
        for index, claim, _ in valid:
            try:
                _primary(claim, source_cells)
                children = _context_claims(claim)
                mapping.append((index, len(children)))
                pending.extend(children)
                results[index] = VerificationResult(
                    claim.observation_id, claim.source_record_id, True, None, key, digest
                )
            except ProofError as exc:
                failed(index, claim, str(exc))
    if pending:
        report = verifier.verify(pending, mode)
        reads += report.objects_read
        attempts += report.object_read_attempts
        cursor = 0
        for index, count in mapping:
            child_results = report.results[cursor : cursor + count]
            cursor += count
            bad = next((result for result in child_results if not result.passed), None)
            claim = claims[index]
            if bad:
                failed(index, claim, bad.reason or "wb_archive_context_invalid")
            elif count == 1:
                results[index] = child_results[0]
    return VerificationReport(
        mode, tuple(results[index] for index in range(len(claims))), reads, attempts
    )
