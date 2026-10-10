"""Assert historical Silver replay AND mandatory Gold refusal, never certify it."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.gold.provenance_gate import GoldProvenanceRejected
from ketrika.gold.refresh import ORDERED_GOLD_VIEWS
from ketrika.pipelines.rebuild import rebuild_database


def rejected_legacy_rebuild(
    session: Session, source_id: str, *, allow_empty: bool = False
) -> dict[str, Any]:
    """Real pipeline statistics from the propagated error, not a success result."""
    try:
        stats = rebuild_database(session=session, offline=True, source_id=source_id)
    except GoldProvenanceRejected as failure:
        return failure_statistics(failure)
    assert allow_empty, "unexpected_legacy_publication_success"
    assert stats["gold_publication_state"] == "empty"
    assert stats["source_observations_total"] == stats["source_observations_valid"] == 0
    assert stats["source_cell_rate"] is None
    assert stats["provenance_scope"] == "source_cells_not_authenticity_conversions_or_model"
    for view in ORDERED_GOLD_VIEWS:
        if view != "source_health":
            assert session.scalar(text(f"SELECT count(*) FROM gold.{view}")) == 0
    return stats


def failure_statistics(failure: GoldProvenanceRejected) -> dict[str, Any]:
    receipt = failure.receipt
    assert not receipt.report.passed
    assert 0 <= receipt.report.valid < receipt.report.total
    stats = failure.replay_stats
    assert stats is not None
    assert stats["gold_publication_state"] == "refused"
    assert stats["gold_views_refreshed"] == 0
    return stats
