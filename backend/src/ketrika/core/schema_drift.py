"""Explicit CSV document contracts; pure prototype, not a publication gate."""

import csv
import hashlib
import io
import json
from dataclasses import dataclass

MAX_BYTES = 32 * 1024 * 1024
MAX_COLUMNS = 256
MAX_HEADER_TOKEN = 256


@dataclass(frozen=True)
class SchemaInspection:
    state: str
    content_sha256: str
    contract_sha256: str | None
    header_sha256: str | None
    columns: int
    rows: int
    missing_columns: int
    unexpected_columns: int
    duplicate_columns: int
    invalid_rows: int
    reasons: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.state == "verified" and not self.reasons


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def inspect_csv_schema(
    content: bytes,
    *,
    required_columns: tuple[str, ...] | None,
    optional_columns: tuple[str, ...] = (),
    delimiter: str = ",",
) -> SchemaInspection:
    """Never infer a contract from a document or expose its cell/header text."""
    if not isinstance(content, bytes):
        raise ValueError("schema_content_requires_bytes")
    if not isinstance(delimiter, str) or len(delimiter) != 1 or delimiter in {"\n", "\r", '"'}:
        raise ValueError("schema_invalid_delimiter")
    contract_sha: str | None = None
    if required_columns is not None:
        if not isinstance(required_columns, tuple) or not isinstance(optional_columns, tuple):
            raise ValueError("schema_contract_requires_tuples")
        declared = required_columns + optional_columns
        if (
            not required_columns
            or len(declared) > MAX_COLUMNS
            or any(
                not isinstance(name, str) or not name or len(name) > MAX_HEADER_TOKEN
                for name in declared
            )
            or len(set(declared)) != len(declared)
        ):
            raise ValueError("schema_invalid_column_contract")
        contract_sha = _fingerprint([sorted(required_columns), sorted(optional_columns), delimiter])
    content_sha = hashlib.sha256(content).hexdigest()

    def refused(reason: str, *, unknown: bool = False) -> SchemaInspection:
        return SchemaInspection(
            "unknown" if unknown else "drift",
            content_sha,
            contract_sha,
            None,
            0,
            0,
            0,
            0,
            0,
            0,
            (reason,),
        )

    if len(content) > MAX_BYTES:
        return refused("schema_document_too_large")
    if required_columns is None:
        return refused("schema_contract_absent", unknown=True)
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return refused("schema_invalid_utf8")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    try:
        header = next(reader, None)
        if not header:
            return refused("schema_header_absent", unknown=True)
        if len(header) > MAX_COLUMNS or any(len(token) > MAX_HEADER_TOKEN for token in header):
            return refused("schema_header_outside_bounds")
        actual, required = set(header), set(required_columns)
        missing = len(required - actual)
        unexpected = len(actual - required - set(optional_columns))
        duplicate = len(header) - len(actual)
        rows = invalid_rows = 0
        for row in reader:
            rows += 1
            invalid_rows += int(len(row) != len(header))
    except csv.Error:
        return refused("schema_invalid_csv")
    reasons = tuple(
        name
        for name, count in (
            ("schema_missing_columns", missing),
            ("schema_unexpected_columns", unexpected),
            ("schema_duplicate_columns", duplicate),
            ("schema_invalid_row_width", invalid_rows),
        )
        if count
    )
    return SchemaInspection(
        "drift" if reasons else "verified",
        content_sha,
        contract_sha,
        _fingerprint(header),
        len(header),
        rows,
        missing,
        unexpected,
        duplicate,
        invalid_rows,
        reasons,
    )
