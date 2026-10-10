"""Offline byte/cell verification (ADR-016), independent of source authenticity.

This module does not publish Gold, infer units, or execute collected content.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, Protocol
from uuid import UUID


class ProofError(ValueError):
    """Stable non-sensitive error code, never a collected snippet or exception."""


class ArtifactReader(Protocol):
    def get(self, object_key: str) -> bytes:
        """Read an existing artifact; no mutation or network-source discovery."""
        ...


@dataclass(frozen=True)
class ArtifactReference:
    source_record_id: UUID
    source_id: str
    object_key: str
    content_sha256: str
    mime_type: str


@dataclass(frozen=True)
class ObservationClaim:
    observation_id: UUID
    source_record_id: UUID | None
    proof: Mapping[str, Any]


@dataclass(frozen=True)
class VerificationResult:
    observation_id: UUID
    source_record_id: UUID | None
    passed: bool
    reason: str | None
    object_key: str | None = None
    content_sha256: str | None = None


@dataclass(frozen=True)
class VerificationReport:
    mode: Literal["complete", "incremental"]
    results: tuple[VerificationResult, ...]
    objects_read: int
    object_read_attempts: int

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def valid(self) -> int:
        return sum(result.passed for result in self.results)

    @property
    def passed(self) -> bool:
        return self.total > 0 and self.valid == self.total

    @property
    def rate(self) -> Decimal | None:
        return Decimal(self.valid) * 100 / self.total if self.total else None


def _path(value: Any) -> tuple[str | int, ...]:
    if (
        not isinstance(value, list)
        or not value
        or any(type(key) not in (str, int) or (isinstance(key, int) and key < 0) for key in value)
    ):
        raise ProofError("invalid_coordinates")
    return tuple(value)


def _at(payload: Any, path: tuple[str | int, ...]) -> Any:
    for key in path:
        if isinstance(payload, list) and type(key) is int:
            if key >= len(payload):
                raise ProofError("cell_missing")
        elif isinstance(payload, dict) and isinstance(key, str):
            if key not in payload:
                raise ProofError("cell_missing")
        else:
            raise ProofError("invalid_coordinates")
        payload = payload[key]
    return payload


def _decimal(value: Any, style: str = "decimal_dot") -> Decimal:
    if type(value) not in (str, int, Decimal):
        raise ProofError("invalid_number")
    text = unicodedata.normalize("NFKC", str(value)).strip().replace(" ", "")
    if style == "decimal_comma":
        if not re.fullmatch(r"[+-]?(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d+)?", text):
            raise ProofError("invalid_number")
        text = text.replace(".", "").replace(",", ".")
    elif style != "decimal_dot":
        raise ProofError("invalid_number_style")
    elif not re.fullmatch(r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", text):
        raise ProofError("invalid_number")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ProofError("invalid_number") from exc
    if not number.is_finite():
        raise ProofError("invalid_number")
    return number


def _reject_constant(_: str) -> None:
    raise ProofError("invalid_document")


def verify_cells(content: bytes, mime_type: str, proof: Mapping[str, Any]) -> int:
    """Verify caller-bound expectations at exact coordinates in one source record.

    At least one value and one identity cell are mandatory. This verifies the
    supplied binding, not whether the caller correctly bound a database row.
    """
    if (
        not isinstance(proof, Mapping)
        or type(proof.get("version")) is not int
        or proof.get("version") != 1
        or not isinstance(proof.get("cells"), list)
    ):
        raise ProofError("invalid_proof")
    cells = proof["cells"]
    if not cells or any(not isinstance(cell, dict) for cell in cells):
        raise ProofError("invalid_proof")
    if any(not isinstance(cell.get("role"), str) for cell in cells):
        raise ProofError("invalid_proof")
    roles = {cell.get("role") for cell in cells}
    if roles != {"value", "identity"}:
        raise ProofError("identity_or_value_missing")
    format_name = proof.get("format")
    if not isinstance(mime_type, str):
        raise ProofError("unsupported_format")
    mime = mime_type.split(";", 1)[0].strip().lower()
    try:
        document = content.decode("utf-8-sig")
        if format_name == "json" and mime == "application/json":
            payload = json.loads(document, parse_float=Decimal, parse_constant=_reject_constant)
            scope = _path(proof.get("scope_path"))
            _at(payload, scope)

            def get_cell(cell: dict[str, Any]) -> tuple[tuple[Any, ...], Any]:
                path = _path(cell.get("path"))
                if len(path) <= len(scope) or path[: len(scope)] != scope:
                    raise ProofError("cell_outside_record")
                return path, _at(payload, path)

        elif format_name == "csv" and mime in ("text/csv", "application/csv"):
            row_index = proof.get("row")
            delimiter = proof.get("delimiter")
            if (
                type(row_index) is not int
                or row_index < 0
                or delimiter not in (",", ";", "\t", "|")
            ):
                raise ProofError("invalid_coordinates")
            rows = list(csv.reader(io.StringIO(document), delimiter=delimiter, strict=True))
            if not rows or not rows[0] or len(set(rows[0])) != len(rows[0]) or "" in rows[0]:
                raise ProofError("invalid_header")
            if row_index + 1 >= len(rows):
                raise ProofError("cell_missing")
            headers, row = rows[0], rows[row_index + 1]
            if len(row) != len(headers):
                raise ProofError("invalid_row")

            def get_cell(cell: dict[str, Any]) -> tuple[tuple[Any, ...], Any]:
                column = cell.get("column")
                if not isinstance(column, str) or column not in headers:
                    raise ProofError("cell_missing")
                return (row_index, column), row[headers.index(column)]

        else:
            raise ProofError("unsupported_format")
    except (UnicodeError, json.JSONDecodeError, csv.Error) as exc:
        raise ProofError("invalid_document") from exc

    seen: set[tuple[Any, ...]] = set()
    fields: set[str] = set()
    for cell in cells:
        field = cell.get("field")
        if not isinstance(field, str) or not field or field in fields:
            raise ProofError("invalid_field")
        fields.add(field)
        coordinate, actual = get_cell(cell)
        if coordinate in seen:
            raise ProofError("duplicate_cell")
        seen.add(coordinate)
        expected = cell.get("expected")
        if not isinstance(expected, str):
            raise ProofError("invalid_expectation")
        if cell.get("kind") == "number":
            style = (
                proof.get("number_style", "decimal_dot") if format_name == "csv" else "decimal_dot"
            )
            if _decimal(actual, style) != _decimal(expected):
                raise ProofError("value_mismatch")
            if "raw_expected" in cell:
                raw_expected = cell["raw_expected"]
                if not isinstance(raw_expected, str):
                    raise ProofError("invalid_expectation")
                if not isinstance(actual, str) or actual != raw_expected:
                    raise ProofError("raw_value_mismatch")
        elif cell.get("kind") == "text":
            if not isinstance(actual, str) or actual != expected:
                raise ProofError(
                    "identity_mismatch" if cell["role"] == "identity" else "value_mismatch"
                )
        else:
            raise ProofError("unsupported_cell_kind")
    return len(seen)


def _validate_reference(reference: ArtifactReference) -> str:
    if not isinstance(reference.content_sha256, str):
        raise ProofError("invalid_sha256")
    digest = reference.content_sha256.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ProofError("invalid_sha256")
    if not isinstance(reference.source_id, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]+", reference.source_id
    ):
        raise ProofError("invalid_object_key")
    pattern = (
        rf"{re.escape(reference.source_id)}/(\d{{4}})/(0[1-9]|1[0-2])/{digest}\.[a-z0-9]{{1,10}}"
    )
    match = (
        re.fullmatch(pattern, reference.object_key)
        if isinstance(reference.object_key, str)
        else None
    )
    if match is None:
        raise ProofError("invalid_object_key")
    try:
        date(int(match[1]), int(match[2]), 1)
    except ValueError as exc:
        raise ProofError("invalid_object_key") from exc
    return digest


class ProvenanceVerifier:
    """Verify one batch; cache is discarded between complete/incremental calls."""

    def __init__(
        self, reader: ArtifactReader, references: Mapping[UUID, ArtifactReference]
    ) -> None:
        self.reader = reader
        self.references = references

    def verify(
        self,
        claims: Sequence[ObservationClaim],
        mode: Literal["complete", "incremental"] = "complete",
    ) -> VerificationReport:
        if mode not in ("complete", "incremental"):
            raise ValueError("Unsupported verification mode")
        cache: dict[str, tuple[bytes | None, str]] = {}
        seen: set[UUID] = set()
        results = []
        attempts = 0
        reads = 0
        for claim in claims:
            reference = (
                self.references.get(claim.source_record_id) if claim.source_record_id else None
            )
            try:
                if claim.observation_id in seen:
                    raise ProofError("duplicate_observation")
                seen.add(claim.observation_id)
                if reference is None or reference.source_record_id != claim.source_record_id:
                    raise ProofError("source_record_missing")
                digest = _validate_reference(reference)
                key = reference.object_key
                if key not in cache:
                    attempts += 1
                    try:
                        content = self.reader.get(key)
                        if not isinstance(content, bytes):
                            raise TypeError("Artifact must contain bytes")
                    except Exception:
                        cache[key] = (None, "object_unavailable")
                    else:
                        reads += 1
                        cache[key] = (content, hashlib.sha256(content).hexdigest())
                cached_content, measured = cache[key]
                if cached_content is None:
                    raise ProofError("object_unavailable")
                if measured != digest:
                    raise ProofError("sha256_mismatch")
                verify_cells(cached_content, reference.mime_type, claim.proof)
                result = VerificationResult(
                    claim.observation_id, claim.source_record_id, True, None, key, digest
                )
            except ProofError as exc:
                result = VerificationResult(
                    claim.observation_id, claim.source_record_id, False, str(exc)
                )
            results.append(result)
        return VerificationReport(mode, tuple(results), reads, attempts)
