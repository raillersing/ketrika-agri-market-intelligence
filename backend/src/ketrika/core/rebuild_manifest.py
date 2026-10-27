"""Complete read-only Silver/Gold content projections, not a rebuild certification."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.core.models.db import Base
from ketrika.gold.refresh import ORDERED_GOLD_VIEWS, UNPUBLISHED_GOLD_VIEWS

OBS_COLUMNS = {
    name: frozenset(column.name for column in table.columns)
    for name, table in Base.metadata.tables.items()
    if table.schema == "obs"
}
# Publication-reserved views can never be populated outside the R2 macro gate;
# their unpopulated state is out of scope for content identity receipts.
RESERVED_GOLD_TABLES = frozenset("gold." + view for view in UNPUBLISHED_GOLD_VIEWS)
TABLES = (
    frozenset(OBS_COLUMNS) | frozenset("gold." + view for view in ORDERED_GOLD_VIEWS)
) - RESERVED_GOLD_TABLES


class ManifestError(ValueError):
    """Projection cannot establish content identity; no collected text in errors."""


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _value(value: Any) -> list[Any]:
    """Typed encoding prevents NULL, decimal, JSON and text collisions."""
    if value is None:
        return ["null"]
    if type(value) is bool:
        return ["bool", value]
    if type(value) is int:
        return ["int", str(value)]
    if type(value) is str:
        return ["text", value]
    if isinstance(value, UUID):
        return ["uuid", str(value)]
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ManifestError("manifest_nonfinite")
        # format(f) preserves every digit without ambient Decimal context rounding.
        exact = format(value, "f")
        if "." in exact:
            exact = exact.rstrip("0").rstrip(".")
        return ["decimal", "0" if value == 0 else exact]
    if type(value) is float:
        if not math.isfinite(value):
            raise ManifestError("manifest_nonfinite")
        return ["float", repr(value)]
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ManifestError("manifest_naive_datetime")
        from datetime import UTC

        return ["datetime", value.astimezone(UTC).isoformat()]
    if isinstance(value, date):
        return ["date", value.isoformat()]
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise ManifestError("manifest_invalid_json_key")
        return ["object", [[key, _value(value[key])] for key in sorted(value)]]
    if isinstance(value, (list, tuple)):
        return ["array", [_value(item) for item in value]]
    raise ManifestError("manifest_unsupported_value")


def _identifier(value: Any) -> UUID:
    try:
        result = value if isinstance(value, UUID) else UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise ManifestError("manifest_invalid_observation_id") from None
    if result.int == 0:
        raise ManifestError("manifest_invalid_observation_id")
    return result


def canonical_manifest(
    tables: Mapping[str, Sequence[Mapping[str, Any]]],
    columns: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    """Keep all values and relations; ignore only documented generated fields.

    Source/ref identifiers are intentionally retained, never blindly stripped.
    The caller must establish their inventories and Bronze identity separately.
    """
    if set(tables) != TABLES or set(columns) != TABLES:
        raise ManifestError("manifest_table_inventory_mismatch")
    schemas: dict[str, list[str]] = {}
    for table in sorted(TABLES):
        names = list(columns[table])
        if not names or any(type(name) is not str or not name for name in names):
            raise ManifestError("manifest_invalid_columns")
        if len(names) != len(set(names)):
            raise ManifestError("manifest_duplicate_column")
        if table in OBS_COLUMNS and set(names) != OBS_COLUMNS[table]:
            raise ManifestError("manifest_observation_columns_mismatch")
        if any(set(row) != set(names) for row in tables[table]):
            raise ManifestError("manifest_row_columns_mismatch")
        schemas[table] = sorted(names)

    identities: dict[tuple[str, UUID], str] = {}
    business_ids: set[tuple[str, str]] = set()
    for table in sorted(OBS_COLUMNS):
        primary = (
            "event_id"
            if table == "obs.event"
            else ("quarantine_id" if table == "obs.quarantine_ledger" else "observation_id")
        )
        for row in tables[table]:
            identity = (table, _identifier(row[primary]))
            business = {
                key: _value(value)
                for key, value in row.items()
                if key not in {primary, "ingested_at", "superseded_by", "quarantined_at"}
            }
            stable = _digest(business)
            if identity in identities or (table, stable) in business_ids:
                raise ManifestError("manifest_ambiguous_observation")
            identities[identity] = stable
            business_ids.add((table, stable))

    # A supersession must terminate. Self-links and longer cycles are not revisions.
    targets = {}
    for table in sorted(OBS_COLUMNS):
        if table == "obs.quarantine_ledger":
            continue
        for row in tables[table]:
            if row.get("superseded_by") is not None:
                targets[(table, _identifier(row["observation_id"]))] = (
                    table,
                    _identifier(row["superseded_by"]),
                )
    checked = set()
    for start in targets:
        path = set()
        current = start
        while current in targets and current not in checked:
            if current in path:
                raise ManifestError("manifest_revision_cycle")
            path.add(current)
            current = targets[current]
        checked.update(path)

    def link(table: str, value: Any) -> list[Any]:
        if value is None:
            return _value(None)
        stable = identities.get((table, _identifier(value)))
        if stable is None:
            raise ManifestError("manifest_missing_observation_target")
        return ["observation", table, stable]

    projected: dict[str, Any] = {}
    for table in sorted(TABLES):
        output = []
        for row in tables[table]:
            fields = {}
            for name, value in row.items():
                if name in {"ingested_at", "quarantined_at"} and (
                    table in OBS_COLUMNS or table == "gold.price_obs_current"
                ):
                    continue
                if table == "obs.quarantine_ledger":
                    fields[name] = _value(value)
                elif table in OBS_COLUMNS and name in {
                    "event_id",
                    "observation_id",
                    "superseded_by",
                }:
                    fields[name] = link(table, value)
                elif table == "gold.price_obs_current" and name == "observation_id":
                    fields[name] = link("obs.price_observation", value)
                else:
                    fields[name] = _value(value)
            output.append(fields)
        output.sort(key=_json)
        projected[table] = {
            "columns": schemas[table],
            "count": len(output),
            "sha256": _digest(output),
            "rows": output,
        }
    return {"version": 1, "tables": projected, "sha256": _digest(projected)}


def compare_manifests(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Return full differing rows, not just counts; reject modified receipts."""
    for document in (before, after):
        tables = document.get("tables")
        if document.get("version") != 1 or not isinstance(tables, dict) or set(tables) != TABLES:
            raise ManifestError("manifest_invalid_document")
        if document.get("sha256") != _digest(tables):
            raise ManifestError("manifest_hash_mismatch")
        for item in tables.values():
            if item["count"] != len(item["rows"]) or item["sha256"] != _digest(item["rows"]):
                raise ManifestError("manifest_table_hash_mismatch")
    changed = {}
    for table in sorted(TABLES):
        first, second = before["tables"][table], after["tables"][table]
        if first != second:
            changed[table] = {"before": first, "after": second}
    return {
        "version": 1,
        "content_identical": not changed,
        "before_sha256": before["sha256"],
        "after_sha256": after["sha256"],
        "changed_tables": changed,
    }


def capture_database(session: Session) -> dict[str, Any]:
    """SELECT only; caller owns a frozen clone/repeatable-read transaction."""
    actual = set(
        session.execute(
            text(
                "SELECT schemaname || '.' || tablename FROM pg_tables WHERE schemaname='obs' "
                "UNION ALL SELECT schemaname || '.' || matviewname FROM pg_matviews "
                "WHERE schemaname='gold'"
            )
        ).scalars()
    )
    if actual - RESERVED_GOLD_TABLES != TABLES:
        raise ManifestError("manifest_database_inventory_mismatch")
    tables, columns = {}, {}
    for table in sorted(TABLES):
        # Static allowlist, never source content or caller-provided SQL identifiers.
        result = session.execute(text("SELECT * FROM " + table))
        columns[table] = list(result.keys())
        tables[table] = [dict(row) for row in result.mappings()]
    return canonical_manifest(tables, columns)
