"""Prototype gate intent; mocks never prove real publication/locking."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from ketrika.core.provenance import VerificationReport, VerificationResult
from ketrika.core.provenance_audit import AuditReceipt
from ketrika.gold.provenance_gate import (
    GoldProvenanceRejected,
    require_gold_provenance,
    tables_for_views,
)


@pytest.mark.parametrize(
    "views",
    [
        [],
        ["unknown"],
        ["weather_monthly; DROP TABLE obs.price_observation"],
        ["weather_monthly", "unknown"],
        [None],
        [[]],
    ],
)
def test_unknown_views_refused_before_database_or_object_reads(views) -> None:
    session, reader = MagicMock(spec=Session), MagicMock()
    with pytest.raises(ValueError, match="unsupported_gold_view"):
        require_gold_provenance(session, reader, views)
    session.execute.assert_not_called()
    reader.get.assert_not_called()


def test_dependency_union_is_sorted_and_deduplicated() -> None:
    assert tables_for_views(["market_health", "price_monthly"]) == (
        "price_observation",
        "stock_observation",
        "weather_observation",
    )


def test_source_health_is_metadata_not_cell_certification() -> None:
    session = MagicMock(spec=Session)
    result = require_gold_provenance(session, MagicMock(), ["source_health"])
    assert result.state == "metadata_only" and result.receipt is None
    session.execute.assert_not_called()


def test_empty_inputs_never_fabricate_a_success_receipt() -> None:
    session = MagicMock(spec=Session)
    session.scalars.return_value.all.return_value = []
    with patch("ketrika.gold.provenance_gate.audit_observation_provenance") as audit:
        result = require_gold_provenance(session, MagicMock(), ["weather_monthly"])
    assert result.state == "empty" and result.receipt is None
    audit.assert_not_called()
    assert str(session.execute.call_args.args[0]) == (
        "LOCK TABLE meta.source_record, obs.weather_observation IN SHARE MODE"
    )
    query = str(session.scalars.call_args.args[0])
    assert "superseded_by IS NULL" in query
    assert "source_id" not in query
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "view,fragments",
    [
        ("price_monthly", ("review_status =", "price_mga_per_base IS NOT NULL")),
        ("stock_latest", ("product_id IS NOT NULL", "location_id IS NOT NULL")),
        ("import_dependency", ("element =",)),
    ],
)
def test_queries_keep_consumed_rows_without_filtering_by_source(view, fragments) -> None:
    session = MagicMock(spec=Session)
    session.scalars.return_value.all.return_value = []
    require_gold_provenance(session, MagicMock(), [view])
    queries = [str(call.args[0]) for call in session.scalars.call_args_list]
    assert all("source_id" not in query for query in queries)
    for fragment in fragments:
        assert any(fragment in query for query in queries)
    assert str(session.execute.call_args_list[0].args[0]) == "SET LOCAL lock_timeout = '5s'"


def test_lock_failure_never_reads_objects_or_claims_success() -> None:
    session, reader = MagicMock(spec=Session), MagicMock()
    session.execute.side_effect = [MagicMock(), RuntimeError("simulated lock timeout")]
    with pytest.raises(RuntimeError, match="simulated lock timeout"):
        require_gold_provenance(session, reader, ["weather_monthly"])
    session.scalars.assert_not_called()
    reader.get.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.parametrize("valid", [True, False])
def test_fresh_audit_required_without_success_cache(valid: bool) -> None:
    session, reader = MagicMock(spec=Session), MagicMock()
    identifier = uuid4()
    session.scalars.return_value.all.return_value = [MagicMock(observation_id=identifier)]
    report = VerificationReport(
        "incremental",
        (VerificationResult(identifier, uuid4(), valid, None if valid else "cell_mismatch"),),
        1,
        1,
    )
    receipt = AuditReceipt(report, (), uuid4())
    with patch(
        "ketrika.gold.provenance_gate.audit_observation_provenance", return_value=receipt
    ) as audit:
        if valid:
            result = require_gold_provenance(session, reader, ["weather_monthly"])
            assert result.receipt is receipt and result.state == "cells_verified"
            require_gold_provenance(session, reader, ["weather_monthly"])
            assert audit.call_count == 2
        else:
            with pytest.raises(GoldProvenanceRejected) as error:
                require_gold_provenance(session, reader, ["weather_monthly"])
            assert str(error.value) == "gold_provenance_rejected"
            assert error.value.receipt is receipt
            assert audit.call_count == 1
    session.commit.assert_not_called()
