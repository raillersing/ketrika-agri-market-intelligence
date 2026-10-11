"""Prepared measured structural checks, not source or SQL qualification."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from dagster import AssetCheckSeverity

from ketrika.core.schema_audit import CSVSchemaContract, SourceSchemaReceipt, SourceSchemaReport
from ketrika.pipelines.schema_check import build_source_schema_check


@pytest.mark.parametrize("total,valid", [(0, 0), (1, 1), (1, 0), (2, 1)])
def test_schema_check_reports_receipt_after_transaction_completes(total, valid):
    contract = CSVSchemaContract("fixture-v1", ("value",))
    report = SourceSchemaReport(total, valid, int(bool(total)), int(bool(total)), ())
    receipt = SourceSchemaReceipt(report, uuid4())
    events = []

    @contextmanager
    def transaction():
        events.append("open")
        yield MagicMock()
        events.append("committed")

    check = build_source_schema_check("dummy_schema", contract)
    assert all(spec.blocking for spec in check.check_specs)
    with (
        patch("ketrika.pipelines.schema_check.get_session", transaction),
        patch("ketrika.pipelines.schema_check.BronzeStore"),
        patch("ketrika.pipelines.schema_check.audit_source_schema", return_value=receipt) as audit,
    ):
        result = check.node_def.compute_fn.decorated_fn(MagicMock())
    assert events == ["open", "committed"]
    assert result.passed is report.passed
    assert result.severity is AssetCheckSeverity.ERROR
    assert result.metadata["total_artifacts"].value == total
    assert result.metadata["valid_schema_artifacts"].value == valid
    assert result.metadata["state"].value == report.state
    assert result.metadata["dq_id"].value == str(receipt.dq_id)
    assert audit.call_args.args[2:] == ("dummy_schema", contract)


def test_schema_check_propagates_database_failure_without_positive_receipt():
    check = build_source_schema_check("dummy_schema", None)
    with (
        patch(
            "ketrika.pipelines.schema_check.get_session", side_effect=RuntimeError("unavailable")
        ),
        pytest.raises(RuntimeError, match="unavailable"),
    ):
        check.node_def.compute_fn.decorated_fn(MagicMock())
