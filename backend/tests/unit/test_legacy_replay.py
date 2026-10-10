"""Helper refuses fake historical certification; mocks are not source evidence."""

from unittest.mock import MagicMock, patch

import pytest

from ketrika.gold.provenance_gate import GoldProvenanceRejected
from tests.legacy_replay import rejected_legacy_rebuild


def failure():
    receipt = MagicMock()
    receipt.report.passed = False
    receipt.report.total = 2
    receipt.report.valid = 1
    error = GoldProvenanceRejected(receipt)
    error.replay_stats = {
        "gold_publication_state": "refused",
        "gold_views_refreshed": 0,
        "source_records_replayed": 1,
    }
    return error


def test_actual_failure_statistics_are_returned_only_after_negative_receipt() -> None:
    error = failure()
    with patch("tests.legacy_replay.rebuild_database", side_effect=error) as pipeline:
        assert rejected_legacy_rebuild(MagicMock(), "legacy")["source_records_replayed"] == 1
    assert pipeline.call_args.kwargs["offline"] is True


def test_unexpected_success_is_not_accepted() -> None:
    with patch("tests.legacy_replay.rebuild_database", return_value={}):
        with pytest.raises(AssertionError):
            rejected_legacy_rebuild(MagicMock(), "legacy")


@pytest.mark.parametrize("bad", ["missing_stats", "positive_receipt"])
def test_missing_stats_or_positive_receipt_is_not_accepted(bad) -> None:
    error = failure()
    if bad == "missing_stats":
        error.replay_stats = None
    else:
        error.receipt.report = MagicMock(passed=True, total=2, valid=2)
    with patch("tests.legacy_replay.rebuild_database", side_effect=error):
        with pytest.raises(AssertionError):
            rejected_legacy_rebuild(MagicMock(), "legacy")


def empty_statistics():
    return {
        "gold_publication_state": "empty",
        "source_observations_total": 0,
        "source_observations_valid": 0,
        "source_cell_rate": None,
        "provenance_scope": "source_cells_not_authenticity_conversions_or_model",
    }


def test_explicit_empty_requires_actual_empty_numeric_views_and_no_rate() -> None:
    session = MagicMock()
    session.scalar.return_value = 0
    stats = empty_statistics()
    with patch("tests.legacy_replay.rebuild_database", return_value=stats):
        assert rejected_legacy_rebuild(session, "legacy", allow_empty=True) == stats
    assert session.scalar.call_count == 11


@pytest.mark.parametrize("bad", ["qualified", "rate", "rows", "counts"])
def test_explicit_empty_cannot_hide_nonempty_or_qualified_data(bad) -> None:
    session = MagicMock()
    session.scalar.return_value = 1 if bad == "rows" else 0
    stats = empty_statistics()
    if bad == "qualified":
        stats["gold_publication_state"] = "cells_verified"
    elif bad == "rate":
        stats["source_cell_rate"] = "100"
    elif bad == "counts":
        stats["source_observations_total"] = 1
    with patch("tests.legacy_replay.rebuild_database", return_value=stats):
        with pytest.raises(AssertionError):
            rejected_legacy_rebuild(session, "legacy", allow_empty=True)
