"""Fresh source-cell gate used before materialized Gold refresh.

This gate checks source cells, not authenticity, conversions or model lineage.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ketrika.core.provenance import ArtifactReader
from ketrika.core.provenance_audit import (
    POLICIES,
    AuditReceipt,
    ObservationTarget,
    audit_observation_provenance,
)

VIEW_TABLES: dict[str, frozenset[str]] = {
    "price_obs_current": frozenset({"price_observation"}),
    "price_monthly": frozenset({"price_observation"}),
    "price_monthly_best": frozenset({"price_observation"}),
    "price_changes": frozenset({"price_observation"}),
    "stock_latest": frozenset({"stock_observation"}),
    "trade_monthly": frozenset({"trade_flow"}),
    "import_dependency": frozenset({"trade_flow", "production_observation"}),
    "weather_monthly": frozenset({"weather_observation"}),
    "cpi_food": frozenset({"cpi_observation"}),
    "market_health": frozenset({"price_observation", "stock_observation", "weather_observation"}),
    "source_health": frozenset(),
    "market_coverage": frozenset({"price_observation"}),
    # Price cells are necessary but insufficient for qualifying forecasts.
    "forecast_latest": frozenset({"price_observation"}),
    "economic_dashboard": frozenset(),
}


class GoldProvenanceRejected(ValueError):
    """No collected text or sensitive value in this exception."""

    def __init__(self, receipt: AuditReceipt) -> None:
        self.receipt = receipt
        self.replay_stats: dict[str, Any] | None = None
        super().__init__("gold_provenance_rejected")


@dataclass(frozen=True)
class PublicationCheck:
    state: str
    tables: tuple[str, ...]
    receipt: AuditReceipt | None
    candidate_record_ids: tuple[UUID, ...] = ()


def tables_for_views(views: Sequence[str]) -> tuple[str, ...]:
    if not views or any(not isinstance(view, str) or view not in VIEW_TABLES for view in views):
        raise ValueError("unsupported_gold_view")
    if "economic_dashboard" in views:
        raise ValueError("macro_publication_not_qualified")
    return tuple(sorted(set().union(*(VIEW_TABLES[view] for view in views))))


def require_gold_provenance(
    session: Session, reader: ArtifactReader, views: Sequence[str]
) -> PublicationCheck:
    """Fresh check under transaction-held locks; caller must not commit mid-refresh."""
    tables = tables_for_views(views)
    if not tables:
        return PublicationCheck("metadata_only", tables, None)
    identifiers = ["meta.source_record", *("obs." + table for table in tables)]
    session.execute(text("SET LOCAL lock_timeout = '5s'"))
    session.execute(text("LOCK TABLE " + ", ".join(identifiers) + " IN SHARE MODE"))
    from ketrika.core.models.db import QuarantineLedger

    targets: list[ObservationTarget] = []
    candidate_ids: set[UUID] = set()
    quarantined_source_record_ids = select(QuarantineLedger.source_record_id).where(
        QuarantineLedger.table_name == "meta.source_record",
        QuarantineLedger.revoked_at.is_(None),
    )
    for table in tables:
        model = POLICIES[table].model
        quarantined_ids = select(QuarantineLedger.observation_id).where(
            QuarantineLedger.table_name == f"obs.{table}",
            QuarantineLedger.revoked_at.is_(None),
        )
        query = select(model).where(
            model.superseded_by.is_(None),
            model.observation_id.not_in(quarantined_ids),
            model.source_record_id.not_in(quarantined_source_record_ids),
        )
        if table == "price_observation":
            query = query.where(
                model.review_status == "accepted", model.price_mga_per_base.is_not(None)
            )
        elif table == "stock_observation":
            query = query.where(model.product_id.is_not(None), model.location_id.is_not(None))
        elif table == "production_observation":
            query = query.where(model.element == "production_t")
        rows = session.scalars(query.order_by(model.observation_id)).all()
        targets.extend(ObservationTarget(table, row.observation_id) for row in rows)
        candidate_ids.update(row.source_record_id for row in rows)
    if not targets:
        return PublicationCheck("empty", tables, None)
    receipt = audit_observation_provenance(session, reader, mode="incremental", targets=targets)
    if not receipt.report.passed:
        raise GoldProvenanceRejected(receipt)
    # Auxiliary metadata must pass the same structural gate as primary data.
    # Read references only after the fresh cell audit has validated the proof.
    from ketrika.core.provenance_rtfp import context_reference, is_context_proof
    from ketrika.core.provenance_wb_archive import is_archive_proof

    for target in targets:
        row = session.get(POLICIES[target.table].model, target.observation_id)
        if row is None:
            raise RuntimeError("gold_candidate_disappeared_after_audit")
        proof = (row.evidence or {}).get("provenance", {})
        if is_context_proof(proof) or is_archive_proof(proof):
            candidate_ids.add(context_reference(proof))
    return PublicationCheck("cells_verified", tables, receipt, tuple(sorted(candidate_ids)))
