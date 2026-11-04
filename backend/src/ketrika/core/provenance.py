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
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from typing import Any, Literal, Protocol
from uuid import UUID

MAX_CONTENT_BYTES = 32 * 1024 * 1024
MAX_JSON_DEPTH = 128


class ProofError(ValueError):
    """Stable non-sensitive error code, never a collected snippet or exception."""


@dataclass(frozen=True)
class JsonNumberToken:
    raw: str


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProofError("duplicate_json_key")
        result[key] = value
    return result


def _check_json_depth(document: str) -> None:
    depth = 0
    quoted = escaped = False
    for character in document:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise ProofError("invalid_document")
        elif character in "]}":
            depth -= 1


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
    if not isinstance(content, bytes):
        raise ProofError("invalid_document")
    if len(content) > MAX_CONTENT_BYTES:
        raise ProofError("content_too_large")
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
    get_cell: Callable[[dict[str, Any]], tuple[tuple[Any, ...], Any]]
    try:
        if format_name == "json" and mime == "application/json":
            document = content.decode("utf-8-sig")
            _check_json_depth(document)
            payload = json.loads(
                document,
                parse_float=JsonNumberToken,
                parse_int=JsonNumberToken,
                parse_constant=_reject_constant,
                object_pairs_hook=_unique_json_object,
            )
            scope = _path(proof.get("scope_path"))
            _at(payload, scope)

            def get_json_cell(cell: dict[str, Any]) -> tuple[tuple[Any, ...], Any]:
                path = _path(cell.get("path"))
                if len(path) <= len(scope) or path[: len(scope)] != scope:
                    raise ProofError("cell_outside_record")
                actual = _at(payload, path)
                encoding = cell.get("raw_encoding")
                if "raw_encoding" in cell:
                    if encoding != "json_number_lexeme" or cell.get("kind") != "number":
                        raise ProofError("unsupported_raw_encoding")
                    if not isinstance(actual, JsonNumberToken):
                        raise ProofError("json_number_token_required")
                    return path, actual.raw
                try:
                    return path, Decimal(actual.raw) if isinstance(
                        actual, JsonNumberToken
                    ) else actual
                except InvalidOperation as exc:
                    raise ProofError("invalid_document") from exc

            get_cell = get_json_cell

        elif format_name == "csv" and mime in ("text/csv", "application/csv"):
            document = content.decode("utf-8-sig")
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

            def get_csv_cell(cell: dict[str, Any]) -> tuple[tuple[Any, ...], Any]:
                column = cell.get("column")
                if not isinstance(column, str) or column not in headers:
                    raise ProofError("cell_missing")
                return (row_index, column), row[headers.index(column)]

            get_cell = get_csv_cell

        elif format_name in ("pdf_table", "html_table", "xlsx_table"):
            from ketrika.core.provenance_tables import table_cell_reader

            get_cell = table_cell_reader(content, mime, proof)
        else:
            raise ProofError("unsupported_format")
    except (UnicodeError, json.JSONDecodeError, csv.Error, InvalidOperation, RecursionError) as exc:
        raise ProofError("invalid_document") from exc

    seen: set[tuple[Any, ...]] = set()
    fields: set[str] = set()
    verified_values: list[str] = []
    for cell in cells:
        if "raw_encoding" in cell and format_name != "json":
            raise ProofError("unsupported_raw_encoding")
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
                proof.get("number_style", "decimal_dot") if format_name != "json" else "decimal_dot"
            )
            numeric = _decimal(actual, style)
            if "normalization" in cell:
                if (
                    format_name != "json"
                    or field != "price_value"
                    or cell["normalization"] != "quantize_4_half_up"
                ):
                    raise ProofError("unsupported_normalization")
                try:
                    with localcontext() as context:
                        context.prec = 64
                        numeric = numeric.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                except InvalidOperation:
                    raise ProofError("invalid_number") from None
            if numeric != _decimal(expected):
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
        if "normalization" in cell and cell.get("kind") != "number":
            raise ProofError("unsupported_normalization")
        verified_values.append(str(actual))
    if "llm_evidence" in proof:
        from ketrika.core.provenance_llm import verify_llm_evidence

        verify_llm_evidence(content, proof, verified_values)
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
    """One read per object per batch; never retain bytes of the complete corpus."""

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
        from ketrika.core.provenance_wb_archive import is_archive_proof, verify_archive_batch

        if any(is_archive_proof(claim.proof) for claim in claims):
            return verify_archive_batch(self, claims, mode)
        from ketrika.core.provenance_rtfp import is_context_proof, verify_context_batch

        if any(is_context_proof(claim.proof) for claim in claims):
            return verify_context_batch(self, claims, mode)
        seen: set[UUID] = set()
        results: dict[int, VerificationResult] = {}
        groups: dict[str, list[tuple[int, ObservationClaim, ArtifactReference, str]]] = {}
        attempts = 0
        reads = 0
        for index, claim in enumerate(claims):
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
                groups.setdefault(key, []).append((index, claim, reference, digest))
            except ProofError as exc:
                results[index] = VerificationResult(
                    claim.observation_id, claim.source_record_id, False, str(exc)
                )

        for key, group in groups.items():
            attempts += 1
            content: bytes | None = None
            measured = ""
            try:
                content = self.reader.get(key)
                if not isinstance(content, bytes):
                    raise TypeError("Artifact must contain bytes")
            except Exception:
                content = None
            else:
                reads += 1
                measured = hashlib.sha256(content).hexdigest()
            for index, claim, reference, digest in group:
                try:
                    if content is None:
                        raise ProofError("object_unavailable")
                    if measured != digest:
                        raise ProofError("sha256_mismatch")
                    verify_cells(content, reference.mime_type, claim.proof)
                    results[index] = VerificationResult(
                        claim.observation_id, claim.source_record_id, True, None, key, digest
                    )
                except ProofError as exc:
                    results[index] = VerificationResult(
                        claim.observation_id, claim.source_record_id, False, str(exc)
                    )
            del content
        return VerificationReport(
            mode, tuple(results[index] for index in range(len(claims))), reads, attempts
        )
