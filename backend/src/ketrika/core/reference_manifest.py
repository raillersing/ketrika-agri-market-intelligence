"""Bounded reference snapshot; not verified mapping provenance or a ledger."""

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

TABLES = ("product", "product_alias", "location", "location_alias", "unit_conversion")
MAX_ROWS = 100_000
MAX_BYTES = 32 * 1024 * 1024

_REFERENCE_QUERY = """
SELECT table_name, row_key, payload_json FROM (
 SELECT 'product' AS table_name, product_id::text AS row_key,
        to_jsonb(r)::text AS payload_json FROM ref.product r
 UNION ALL
 SELECT 'product_alias', alias_id::text, to_jsonb(r)::text FROM ref.product_alias r
 UNION ALL
 SELECT 'location', location_id::text, to_jsonb(r)::text FROM ref.location r
 UNION ALL
 SELECT 'location_alias', jsonb_build_array(alias_norm)::text,
        to_jsonb(r)::text FROM ref.location_alias r
 UNION ALL
 SELECT 'unit_conversion', jsonb_build_array(unit_code, product_id)::text,
        to_jsonb(r)::text FROM ref.unit_conversion r
) refs ORDER BY table_name COLLATE "C", row_key COLLATE "C" LIMIT 100001
"""


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("reference_manifest_invalid_payload")
        result[key] = value
    return result


def _constant(value: str) -> Any:
    raise ValueError("reference_manifest_invalid_payload")


@dataclass(frozen=True)
class ReferenceRow:
    table_name: str
    row_key: str
    payload_json: str = field(repr=False)


@dataclass(frozen=True)
class ReferenceManifest:
    content: bytes = field(repr=False)
    sha256: str
    row_count: int
    counts: tuple[tuple[str, int], ...]


def build_reference_manifest(rows: Iterable[ReferenceRow]) -> ReferenceManifest:
    members: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    counts = dict.fromkeys(TABLES, 0)
    input_bytes = 0
    for row in rows:
        if not isinstance(row, ReferenceRow) or row.table_name not in TABLES:
            raise ValueError("reference_manifest_invalid_table")
        if not isinstance(row.row_key, str) or not 1 <= len(row.row_key) <= 1024:
            raise ValueError("reference_manifest_invalid_key")
        if not isinstance(row.payload_json, str):
            raise ValueError("reference_manifest_invalid_payload")
        try:
            input_bytes += len(row.payload_json.encode("utf-8"))
            if input_bytes > MAX_BYTES:
                raise ValueError("reference_manifest_size_limit")
            decoded = json.loads(
                row.payload_json,
                parse_int=Decimal,
                parse_float=Decimal,
                parse_constant=_constant,
                object_pairs_hook=_object,
            )
        except (UnicodeError, RecursionError, json.JSONDecodeError):
            raise ValueError("reference_manifest_invalid_payload") from None
        if not isinstance(decoded, dict):
            raise ValueError("reference_manifest_invalid_payload")
        identity = (row.table_name, row.row_key)
        if identity in seen:
            raise ValueError("reference_manifest_duplicate_key")
        seen.add(identity)
        counts[row.table_name] += 1
        members.append((row.table_name, row.row_key, row.payload_json))
        if len(members) > MAX_ROWS:
            raise ValueError("reference_manifest_row_limit")
    try:
        content = json.dumps(
            ["reference_manifest_v1", sorted(members)],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (UnicodeError, ValueError):
        raise ValueError("reference_manifest_invalid_payload") from None
    if len(content) > MAX_BYTES:
        raise ValueError("reference_manifest_size_limit")
    return ReferenceManifest(
        content, hashlib.sha256(content).hexdigest(), len(members), tuple(sorted(counts.items()))
    )


def read_reference_manifest(session: Session) -> ReferenceManifest:
    """One SQL statement, no caller commit; processing-transaction binding not certified."""
    result = session.execute(
        text(_REFERENCE_QUERY), execution_options={"stream_results": True, "yield_per": 256}
    )
    try:
        return build_reference_manifest(
            ReferenceRow(row["table_name"], row["row_key"], row["payload_json"])
            for row in result.mappings()
        )
    finally:
        result.close()
