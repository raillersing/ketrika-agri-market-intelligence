"""Explicit source definition inventory; construction never qualifies acquisition."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from dagster import AssetChecksDefinition, AssetKey, AssetsDefinition, ScheduleDefinition

from ketrika.connectors.base import Connector
from ketrika.connectors.registry import list_registered_connectors
from ketrika.core.models.source import SourceDefinition
from ketrika.core.registry import get_source
from ketrika.pipelines.factory import SourceAssets, build_source_assets


class SourceDefinitionsError(ValueError):
    """Stable construction error, without registry bodies or exception text."""


@dataclass(frozen=True)
class SourceInventoryEntry:
    source_id: str
    status: str | None
    included: bool
    reason: str
    assets: int
    checks: int
    schedules: int


@dataclass(frozen=True)
class SourceDefinitions:
    assets: tuple[AssetsDefinition, ...]
    checks: tuple[Any, ...]
    schedules: tuple[ScheduleDefinition, ...]
    inventory: tuple[SourceInventoryEntry, ...]


def build_registered_source_definitions(
    connectors: Mapping[str, type[Connector]] | None = None,
    *,
    resolve: Callable[[str], SourceDefinition] | None = None,
    build: Callable[[type[Connector]], SourceAssets] | None = None,
) -> SourceDefinitions:
    registered = list_registered_connectors() if connectors is None else dict(connectors)
    resolver, builder = resolve or get_source, build or build_source_assets
    assets: list[AssetsDefinition] = []
    checks: list[Any] = []
    schedules: list[ScheduleDefinition] = []
    inventory: list[SourceInventoryEntry] = []
    for source_id in sorted(registered):
        if not re.fullmatch(r"[a-z0-9_]+", source_id):
            raise SourceDefinitionsError("invalid_registered_source_id")
        if source_id.startswith(("dummy_", "fixture_")):
            inventory.append(SourceInventoryEntry(source_id, None, False, "fixture", 0, 0, 0))
            continue
        connector = registered[source_id]
        if not isinstance(connector, type) or not all(
            callable(getattr(connector, method, None)) for method in ("discover", "fetch", "parse")
        ):
            raise SourceDefinitionsError(f"invalid_connector_definition:{source_id}")
        if getattr(connector, "source_id", None) != source_id:
            raise SourceDefinitionsError(f"connector_identity_mismatch:{source_id}")
        try:
            definition = resolver(source_id)
        except Exception as exc:
            raise SourceDefinitionsError(
                f"source_resolution_failed:{source_id}:{type(exc).__name__}"
            ) from None
        if not isinstance(definition, SourceDefinition) or definition.source_id != source_id:
            raise SourceDefinitionsError(f"source_definition_mismatch:{source_id}")
        reason = (
            "forbidden"
            if definition.crawl_permission == "forbidden"
            else definition.status
            if definition.status in ("planned", "disabled")
            else None
        )
        if reason is not None:
            inventory.append(
                SourceInventoryEntry(source_id, definition.status, False, reason, 0, 0, 0)
            )
            continue
        try:
            bundle = builder(connector)
            expected_checks = {
                (AssetKey(f"{source_id}__silver"), f"{source_id}__{name}")
                for name in ("provenance_complete", "schema_drift")
            }
            if len(bundle.checks) != 2 or not all(
                isinstance(check, AssetChecksDefinition) for check in bundle.checks
            ):
                raise ValueError("invalid_source_checks")
            specs = [spec for check in bundle.checks for spec in check.check_specs]
            if (
                len(specs) != 2
                or {(spec.asset_key, spec.name) for spec in specs} != expected_checks
                or not all(spec.blocking for spec in specs)
            ):
                raise ValueError("invalid_source_checks")
            if (
                bundle.source_id != source_id
                or bundle.bronze_asset.key.path != [f"{source_id}__bronze"]
                or bundle.silver_asset.key.path != [f"{source_id}__silver"]
            ):
                raise ValueError("invalid_source_bundle")
        except Exception as exc:
            raise SourceDefinitionsError(
                f"source_construction_failed:{source_id}:{type(exc).__name__}"
            ) from None
        assets.extend((bundle.bronze_asset, bundle.silver_asset))
        checks.extend(bundle.checks)
        if bundle.schedule is not None:
            schedules.append(bundle.schedule)
        inventory.append(
            SourceInventoryEntry(
                source_id,
                definition.status,
                True,
                "constructed",
                2,
                len(bundle.checks),
                int(bundle.schedule is not None),
            )
        )
    return SourceDefinitions(tuple(assets), tuple(checks), tuple(schedules), tuple(inventory))
