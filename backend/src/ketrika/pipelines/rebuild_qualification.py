"""Real offline replay on a dedicated Unix-socket database; never an active DB.

This worker measures software replay only. Authenticity, retained S3 versions
and reproducible model training require separate evidence; status stays PARTIAL.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from ketrika.connectors.registry import get_connector_class
from ketrika.core.bronze import BronzeStore
from ketrika.core.models.db import Base, SourceRecord
from ketrika.core.rebuild_bronze import LocalBronzeClient
from ketrika.core.rebuild_manifest import OBS_COLUMNS, capture_database, compare_manifests
from ketrika.pipelines.rebuild import rebuild_database

DATABASE = "ketrika_rebuild_qualification"
SOCKET = "/run/ketrika-rebuild"


class RebuildSafetyError(ValueError):
    """Stable diagnostic, no DSN/credentials/collected content."""


def require_business_baseline(manifest: dict[str, Any]) -> None:
    if not any(manifest["tables"][table]["count"] > 0 for table in OBS_COLUMNS):
        raise RebuildSafetyError("rebuild_business_baseline_empty")


def require_network_none(
    interfaces: Path = Path("/sys/class/net"), routes: Path = Path("/proc/net/route")
) -> dict[str, Any]:
    """Kernel observations complement the orchestrator's Docker inspect receipt."""
    try:
        names = sorted(path.name for path in interfaces.iterdir())
        route_lines = routes.read_text().splitlines()
    except OSError:
        raise RebuildSafetyError("rebuild_network_evidence_unreadable") from None
    if names != ["lo"] or not route_lines or not route_lines[0].startswith("Iface"):
        raise RebuildSafetyError("rebuild_network_not_isolated")
    if any(line.split()[0] != "lo" for line in route_lines[1:] if line.strip()):
        raise RebuildSafetyError("rebuild_external_route_present")
    return {"interfaces": names, "external_ipv4_routes": 0}


def require_destination(session: Session) -> None:
    url = make_url(session.get_bind().engine.url.render_as_string(hide_password=False))
    if (
        url.drivername != "postgresql+psycopg"
        or url.database != DATABASE
        or url.username != "ketrika"
        or url.password != "qa-local-only"
        or url.host is not None
        or url.port is not None
        or dict(url.query) != {"host": SOCKET}
    ):
        raise RebuildSafetyError("rebuild_destination_not_dedicated")
    actual = session.execute(text("SELECT current_database(), inet_server_addr()")).one()
    if tuple(actual) != (DATABASE, None):
        raise RebuildSafetyError("rebuild_bound_destination_mismatch")


def protected_inventory(session: Session) -> dict[str, Any]:
    """All metadata/reference values unchanged, including their UUIDs and times."""
    names = sorted(
        name
        for name, table in Base.metadata.tables.items()
        if table.schema == "ref" or name in {"meta.source", "meta.source_record"}
    )
    result = {}
    for name in names:
        # Static ORM allowlist; exact PostgreSQL JSON text avoids float conversions.
        rows = list(session.execute(text("SELECT to_jsonb(t)::text FROM " + name + " t")).scalars())
        rows.sort()
        result[name] = {"count": len(rows), "rows": rows}
    payload = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    return {"tables": result, "sha256": hashlib.sha256(payload).hexdigest()}


def run_offline_replay(session: Session, store: BronzeStore) -> dict[str, Any]:
    """No seed, restore or subset filter; caller supplies an already prepared clone."""
    network_before = require_network_none()
    require_destination(session)
    if not isinstance(store.client, LocalBronzeClient):
        raise RebuildSafetyError("rebuild_requires_local_bronze_copy")
    session.execute(text("SET TIME ZONE 'UTC'"))
    descriptors = list(
        session.execute(
            text(
                "SELECT source_id, object_key, content_sha256 FROM meta.source_record "
                "ORDER BY fetched_at, source_record_id"
            )
        ).mappings()
    )
    if not descriptors:
        raise RebuildSafetyError("rebuild_corpus_empty")
    if any(get_connector_class(row["source_id"]) is None for row in descriptors):
        raise RebuildSafetyError("rebuild_connector_missing")
    keys = {row["object_key"] for row in descriptors}
    from ketrika.connectors.rebuild_references import resolve_snapshot_keys

    reference_keys = resolve_snapshot_keys(
        session, list(session.scalars(select(SourceRecord))), store
    )
    keys.update(key for key, _ in reference_keys.values())
    if keys != set(store.client.objects):
        raise RebuildSafetyError("rebuild_bronze_inventory_mismatch")
    for row in descriptors:
        content = store.get(row["object_key"])
        if hashlib.sha256(content).hexdigest() != row["content_sha256"]:
            raise RebuildSafetyError("rebuild_source_record_sha_mismatch")
    protected_before = protected_inventory(session)
    before = capture_database(session)
    require_business_baseline(before)
    # Rebuild always wipes/replays the whole dedicated destination, even if populated.
    stats = rebuild_database(session=session, offline=True, bronze_store=store)
    session.expire_all()
    after = capture_database(session)
    protected_after = protected_inventory(session)
    diff = compare_manifests(before, after)
    network_after = require_network_none()
    passed = (
        diff["content_identical"]
        and protected_before == protected_after
        and stats["source_records_total"] == len(descriptors)
        and stats["source_records_replayed"] == len(descriptors)
        and stats["source_records_skipped"] == 0
        and stats["records_rejected"] == 0
        and network_before == network_after
    )
    return {
        "version": 1,
        "status": "PARTIAL",
        "scope": "software replay, not authentic corpus or scientific/model qualification",
        "replay_passed": passed,
        "database": DATABASE,
        "network_before": network_before,
        "network_after": network_after,
        "before": before,
        "after": after,
        "diff": diff,
        "protected_before": protected_before,
        "protected_after": protected_after,
        "replay_stats": stats,
        "authenticity_qualified": False,
        "original_s3_versions_verified": False,
        "forecasts_recomputed": False,
    }
