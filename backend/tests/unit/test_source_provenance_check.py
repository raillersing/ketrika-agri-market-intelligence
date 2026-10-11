"""Measured source checks, including an explicitly unqualified empty scope."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from ketrika.connectors.dummy_csv import DummyCsvConnector
from ketrika.core.models.db import DqResult
from ketrika.core.provenance import VerificationReport, VerificationResult
from ketrika.core.provenance_audit import AuditReceipt, audit_source_provenance
from ketrika.pipelines.factory import build_source_assets
from tests.unit.test_provenance import MemoryReader


def test_empty_source_persists_failure_without_reading_objects():
    session = MagicMock()
    session.scalars.return_value.all.return_value = []
    reader = MemoryReader({})
    receipt = audit_source_provenance(session, reader, "dummy_empty")
    assert receipt.report.total == receipt.report.valid == 0
    assert not receipt.report.passed and receipt.report.rate is None
    dq = session.add.call_args.args[0]
    assert isinstance(dq, DqResult)
    assert dq.metric is None and not dq.passed
    assert dq.source_id == "dummy_empty" and dq.asset_key == "dummy_empty__silver"
    assert dq.details["state"] == "empty"
    assert dq.details["total_records"] == dq.details["valid_provenance"] == 0
    assert session.scalars.call_count == 6
    session.commit.assert_not_called()
    for call in session.scalars.call_args_list:
        statement = str(call.args[0].compile(dialect=postgresql.dialect()))
        assert "meta.source_record.source_id =" in statement
        assert "superseded_by" not in statement
        assert "review_status" not in statement
        assert "price_mga_per_base" not in statement


@pytest.mark.parametrize("source_id", [None, "", 4])
def test_invalid_scope_refused_before_sql(source_id):
    session = MagicMock()
    with pytest.raises(ValueError, match="invalid_audit_source"):
        audit_source_provenance(session, MemoryReader({}), source_id)
    session.scalars.assert_not_called()


@pytest.mark.parametrize("outcomes", [(), (True,), (False,), (True, False)])
def test_factory_reports_actual_receipt_and_marks_check_blocking(outcomes):
    report = VerificationReport(
        "incremental",
        tuple(VerificationResult(uuid4(), uuid4(), passed, None) for passed in outcomes),
        int(bool(outcomes)),
        int(bool(outcomes)),
    )
    receipt = AuditReceipt(report, (), uuid4())
    events = []

    @contextmanager
    def transaction():
        events.append("open")
        yield MagicMock()
        events.append("committed")

    bundle = build_source_assets(DummyCsvConnector)
    check = bundle.checks[0]
    assert all(spec.blocking for spec in check.check_specs)
    with (
        patch("ketrika.pipelines.factory.get_session", transaction),
        patch("ketrika.pipelines.factory.BronzeStore"),
        patch("ketrika.pipelines.factory.audit_source_provenance", return_value=receipt) as audit,
    ):
        result = check.node_def.compute_fn.decorated_fn(MagicMock())
    assert events == ["open", "committed"]
    assert result.passed is report.passed
    assert result.metadata["total_records"].value == len(outcomes)
    assert result.metadata["valid_provenance"].value == sum(outcomes)
    assert result.metadata["dq_id"].value == str(receipt.dq_id)
    assert result.metadata["rate"].value == (float(report.rate) if outcomes else None)
    assert audit.call_args.args[2] == "dummy_csv"


def test_factory_does_not_turn_database_failure_into_success():
    check = build_source_assets(DummyCsvConnector).checks[0]
    with (
        patch("ketrika.pipelines.factory.get_session", side_effect=RuntimeError("unavailable")),
        pytest.raises(RuntimeError, match="unavailable"),
    ):
        check.node_def.compute_fn.decorated_fn(MagicMock())
