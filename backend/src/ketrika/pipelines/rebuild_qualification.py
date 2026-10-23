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

# Documented technical exclusion (uuid of the immutable run lineage); times live
# outside the compared result, in the persisted ml rows only.
EXCLUDED_RUN_TECHNICAL = ("model_run_id",)

_MODEL_RUN_COLUMNS = (
    "task",
    "model_name",
    "model_version",
    "data_cutoff",
    "params",
    "metrics",
)

_FORECAST_COLUMNS = (
    "series_key",
    "product_id",
    "location_id",
    "actor_level",
    "target_period",
    "horizon",
    "p10",
    "p50",
    "p90",
    "model_requested",
    "model_effective",
    "is_baseline",
    "is_calibrated",
    "calibration_sample_size",
    "status",
    "fallback_reason",
    "currency",
    "unit",
    "interval_width",
    "coverage_rate_80",
)


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


def bronze_inventory_fingerprint(store: BronzeStore) -> dict[str, Any]:
    """Re-read every declared object and bind its actual bytes to the inventory."""
    if not isinstance(store.client, LocalBronzeClient):
        raise RebuildSafetyError("rebuild_requires_local_bronze_copy")
    for key in sorted(store.client.objects):
        # get performs a fresh bounded read, size/SHA and path safety checks.
        store.get(key)
    objects = sorted(
        (
            {"key": key, "sha256": digest, "size_bytes": size}
            for key, (digest, size) in store.client.objects.items()
        ),
        key=lambda descriptor: str(descriptor["key"]),
    )
    payload = json.dumps(objects, sort_keys=True, separators=(",", ":")).encode()
    return {"count": len(objects), "sha256": hashlib.sha256(payload).hexdigest()}


def compare_versioned_recompute(
    run_a: dict[str, Any], run_b: dict[str, Any], model_rows: tuple, forecast_rows: tuple
) -> bool:
    """Business outputs only; the documented technical exclusion never hides a diff."""

    def business(run: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in run.items() if key not in EXCLUDED_RUN_TECHNICAL}

    return (
        business(run_a) == business(run_b)
        and model_rows[0] == model_rows[1]
        and forecast_rows[0] == forecast_rows[1]
    )


def versioned_recompute_receipt(
    session: Session,
    *,
    horizon: int = 3,
    min_points: int = 36,
    cohort: str = "mixed",
) -> dict[str, Any]:
    """Separate versioned recompute step (plan R0.8 item 4), never inside replay.

    Two executions against the same versioned dataset fingerprint on a dedicated
    destination; business outputs compared; committed to persist the receipts.
    Offline clones publish Gold separately, so refresh_gold stays False.
    """
    require_network_none()
    require_destination(session)
    data_cutoff = session.execute(
        text("SELECT max(period_start)::date FROM obs.price_observation")
    ).scalar_one()
    from ketrika.ml.forecast import run_price_forecasting_pipeline

    runs: list[dict[str, Any]] = [
        run_price_forecasting_pipeline(
            session=session,
            data_cutoff=data_cutoff,
            horizon=horizon,
            min_points=min_points,
            cohort=cohort,
            refresh_gold=False,
        )
        for _ in range(2)
    ]
    model_rows: list[tuple] = []
    forecast_rows: list[list] = []
    for run in runs:
        model_run_id = run.get("model_run_id")
        if model_run_id is None:
            model_rows.append(())
            forecast_rows.append([])
            continue
        model_row = session.execute(
            text(
                "SELECT " + ", ".join(_MODEL_RUN_COLUMNS) + " "
                "FROM ml.model_run WHERE model_run_id = :id"
            ),
            {"id": model_run_id},
        ).one()
        model_rows.append(tuple(model_row))
        forecast_rows.append(
            [
                tuple(row)
                for row in session.execute(
                    text(
                        "SELECT " + ", ".join(_FORECAST_COLUMNS) + " "
                        "FROM ml.forecast WHERE model_run_id = :id "
                        "ORDER BY series_key, target_period, horizon"
                    ),
                    {"id": model_run_id},
                ).all()
            ]
        )
    recompute_equal = compare_versioned_recompute(
        runs[0], runs[1], tuple(model_rows), tuple(forecast_rows)
    )
    session.commit()
    return {
        "version": 1,
        "scope": "versioned recompute on a dedicated destination; no model qualification claim",
        "data_cutoff": data_cutoff.isoformat(),
        "horizon": horizon,
        "cohort": cohort,
        "min_points_required": min_points,
        "dataset_fingerprint": runs[0]["dataset_fingerprint"],
        "eligible_series": runs[0]["n_series"],
        "forecasts_generated": [run["forecasts_generated"] for run in runs],
        "n_abstentions": [run["n_abstentions"] for run in runs],
        "recompute_equal": recompute_equal,
        "forecasts_recomputed": bool(recompute_equal and runs[0]["n_series"] > 0),
        "excluded_technical": ["model_run_id", "trained_at", "generated_at", "forecast_id"],
        "runs": [
            {key: value for key, value in run.items() if key not in EXCLUDED_RUN_TECHNICAL}
            for run in runs
        ],
    }


def run_offline_replay(session: Session, store: BronzeStore) -> dict[str, Any]:
    """No seed, restore or subset filter; caller supplies an already prepared clone."""
    network_before = require_network_none()
    require_destination(session)
    if not isinstance(store.client, LocalBronzeClient):
        raise RebuildSafetyError("rebuild_requires_local_bronze_copy")
    session.execute(text("SET TIME ZONE 'UTC'"))
    inventory_before = bronze_inventory_fingerprint(store)
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
    inventory_after = bronze_inventory_fingerprint(store)
    network_after = require_network_none()
    passed = (
        diff["content_identical"]
        and protected_before == protected_after
        and stats["source_records_total"] == len(descriptors)
        and stats["source_records_replayed"] == len(descriptors)
        and stats["source_records_skipped"] == 0
        and stats["records_rejected"] == 0
        and network_before == network_after
        and inventory_before == inventory_after
    )
    return {
        "version": 2,
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
        "bronze_inventory_before": inventory_before,
        "bronze_inventory_after": inventory_after,
        "bronze_inventory_verified": inventory_before == inventory_after,
        "authenticity_qualified": False,
        "original_s3_versions_verified": False,
        "forecasts_recomputed": False,
    }
