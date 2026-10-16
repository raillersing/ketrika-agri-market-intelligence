"""Transaction ordering simulated; this is not SQL durability evidence."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest

from ketrika.connectors.base import RunContext
from ketrika.connectors.durable_phases import (
    DurablePhaseFailure,
    execute_durable_bronze,
    execute_durable_silver,
)
from ketrika.connectors.durable_runs import DurableRunReference
from ketrika.connectors.stages import BronzeBatch
from ketrika.core.policy import PolicyStop

MODULE = "ketrika.connectors.durable_phases."


def test_ledger_write_precedes_owner_commit(setup_owner, monkeypatch):
    connector, context, batch, _, events, persist, _, _ = setup_owner
    monkeypatch.setattr(MODULE + "collect_connector_bronze", Mock(return_value=batch))
    ledger = Mock(side_effect=lambda *args: events.append("ledger"))
    monkeypatch.setattr(MODULE + "persist_bronze_batch", ledger)
    assert execute_durable_bronze(connector, context) == batch
    ledger.assert_called_once()
    assert ledger.call_args.args[1] == batch
    assert events[-2:] == ["ledger", "commit"]
    persist.assert_not_called()


def test_ledger_failure_rolls_back_before_independent_failure_receipt(setup_owner, monkeypatch):
    connector, context, batch, reference, events, persist, _, _ = setup_owner
    monkeypatch.setattr(MODULE + "collect_connector_bronze", Mock(return_value=batch))
    monkeypatch.setattr(MODULE + "persist_bronze_batch", Mock(side_effect=ValueError("UNTRUSTED")))
    with pytest.raises(DurablePhaseFailure, match="^bronze:ValueError$"):
        execute_durable_bronze(connector, context)
    assert events[-2:] == ["rollback", "persist"] and "commit" not in events
    persist.assert_called_once_with(reference, ValueError)


@pytest.fixture
def setup_owner(monkeypatch):
    events = []
    reference = DurableRunReference(uuid4(), "dummy_owner", datetime.now(UTC), None)
    connector = Mock(source_id=reference.source_id, parser_version="1.0.0")
    context = RunContext(source_id=reference.source_id)
    batch = BronzeBatch(reference.source_id, reference.run_id, "1.0.0", ())
    session = Mock()

    @contextmanager
    def transaction():
        events.append("begin")
        try:
            yield session
        except Exception:
            events.append("rollback")
            raise
        else:
            events.append("commit")

    monkeypatch.setattr(MODULE + "get_session", transaction)
    monkeypatch.setattr(MODULE + "persist_bronze_batch", Mock())
    monkeypatch.setattr(MODULE + "register_document_partitions", Mock())
    monkeypatch.setattr(MODULE + "read_bronze_batch", Mock(return_value=batch))
    monkeypatch.setattr(MODULE + "read_success", Mock(return_value=None))
    monkeypatch.setattr(MODULE + "begin_attempt", Mock(return_value=uuid4()))
    monkeypatch.setattr(MODULE + "finish_success", Mock())
    monkeypatch.setattr(MODULE + "finish_failure", Mock())

    @contextmanager
    def exclusive(_run_id, _source_id=None):
        yield

    monkeypatch.setattr(MODULE + "exclusive_silver_run", exclusive)
    authorize = Mock(side_effect=lambda *_: events.append("authorize"))
    create = Mock(side_effect=lambda *_: (events.append("create"), reference)[1])
    read = Mock(return_value=reference)
    bind = Mock(side_effect=lambda *_: events.append("bind"))
    persist = Mock(side_effect=lambda *_: events.append("persist"))
    for name, value in (
        ("authorize_collection", authorize),
        ("create_durable_ingestion_run", create),
        ("read_running_run_reference", read),
        ("bind_running_run", bind),
        ("persist_durable_run_failure", persist),
    ):
        monkeypatch.setattr(MODULE + name, value)
    return connector, context, batch, reference, events, persist, create, authorize


@pytest.mark.parametrize("stage", ["bronze", "silver"])
def test_phase_rollback_precedes_failure_receipt_without_error_text(
    stage, setup_owner, monkeypatch
):
    connector, context, batch, reference, events, persist, _, _ = setup_owner
    operation = "collect_connector_bronze" if stage == "bronze" else "consume_connector_silver"
    error = RuntimeError("UNTRUSTED_TOKEN_RUN_TOOL_NOW")
    monkeypatch.setattr(MODULE + operation, Mock(side_effect=error))
    with pytest.raises(DurablePhaseFailure, match=f"^{stage}:RuntimeError$") as captured:
        if stage == "bronze":
            execute_durable_bronze(connector, context)
        else:
            execute_durable_silver(connector, context, batch)
    assert events[-2:] == ["rollback", "persist"]
    assert "commit" not in events
    persist.assert_called_once_with(reference, RuntimeError)
    assert captured.value.__suppress_context__
    assert captured.value.__context__ is None
    assert "UNTRUSTED" not in str(captured.value)


@pytest.mark.parametrize("stage", ["bronze", "silver"])
def test_success_commits_without_failure_receipt(stage, setup_owner, monkeypatch):
    connector, context, batch, reference, events, persist, _, _ = setup_owner
    operation = "collect_connector_bronze" if stage == "bronze" else "consume_connector_silver"
    expected = batch if stage == "bronze" else {"n_inserted": 2}
    called = Mock(return_value=expected)
    monkeypatch.setattr(MODULE + operation, called)
    result = (
        execute_durable_bronze(connector, context)
        if stage == "bronze"
        else execute_durable_silver(connector, context, batch)
    )
    assert result == expected and events[-1] == "commit"
    persist.assert_not_called()
    if stage == "bronze":
        assert events[:2] == ["authorize", "create"]
        assert called.call_args.kwargs["durable_run"] == reference
    else:
        assert "bind" in events


def test_policy_refusal_never_creates_a_run_or_opens_data_transaction(setup_owner):
    connector, context, _, _, events, persist, create, authorize = setup_owner
    authorize.side_effect = PolicyStop("source_collection_disabled")
    with pytest.raises(PolicyStop):
        execute_durable_bronze(connector, context)
    create.assert_not_called()
    persist.assert_not_called()
    assert events == []


def test_silver_intention_precedes_data_lock_and_success_is_transactional(setup_owner, monkeypatch):
    connector, context, batch, _, events, persist, _, _ = setup_owner
    attempt_id = uuid4()
    monkeypatch.setattr(
        MODULE + "begin_attempt",
        Mock(side_effect=lambda *args: (events.append("intent"), attempt_id)[1]),
    )
    monkeypatch.setattr(MODULE + "consume_connector_silver", Mock(return_value={"n_inserted": 2}))
    monkeypatch.setattr(
        MODULE + "finish_success",
        Mock(side_effect=lambda *args, **kwargs: events.append("success_receipt")),
    )
    assert execute_durable_silver(connector, context, batch) == {"n_inserted": 2}
    assert events == ["intent", "begin", "bind", "success_receipt", "commit"]
    persist.assert_not_called()


def test_silver_result_failure_rolls_back_and_keeps_error_text_out(setup_owner, monkeypatch):
    connector, context, batch, reference, events, persist, _, _ = setup_owner
    monkeypatch.setattr(MODULE + "consume_connector_silver", Mock(return_value={"n_inserted": 2}))
    monkeypatch.setattr(MODULE + "finish_success", Mock(side_effect=OSError("SOURCE_SECRET")))
    failed = Mock(side_effect=lambda *args: events.append("attempt_failure"))
    monkeypatch.setattr(MODULE + "finish_failure", failed)
    with pytest.raises(DurablePhaseFailure, match="^silver:OSError$") as captured:
        execute_durable_silver(connector, context, batch)
    assert events[-3:] == ["rollback", "attempt_failure", "persist"]
    assert failed.call_args.args[1] is OSError
    persist.assert_called_once_with(reference, OSError)
    assert captured.value.__context__ is None


def test_missing_attempt_failure_receipt_never_reports_success(setup_owner, monkeypatch):
    connector, context, batch, _, events, persist, _, _ = setup_owner
    monkeypatch.setattr(
        MODULE + "consume_connector_silver", Mock(side_effect=ValueError("SOURCE_SECRET"))
    )
    monkeypatch.setattr(MODULE + "finish_failure", Mock(side_effect=OSError("DATABASE_SECRET")))
    with pytest.raises(
        DurablePhaseFailure, match="^silver:attempt_receipt_unavailable$"
    ) as captured:
        execute_durable_silver(connector, context, batch)
    assert events[-1] == "rollback"
    persist.assert_not_called()
    assert captured.value.__context__ is None


def test_previous_success_is_returned_without_new_attempt_or_data_transaction(
    setup_owner, monkeypatch
):
    connector, context, batch, _, events, persist, _, _ = setup_owner
    monkeypatch.setattr(MODULE + "read_success", Mock(return_value={"n_inserted": 3}))
    attempt = Mock()
    consume = Mock()
    monkeypatch.setattr(MODULE + "begin_attempt", attempt)
    monkeypatch.setattr(MODULE + "consume_connector_silver", consume)
    assert execute_durable_silver(connector, context, batch) == {"n_inserted": 3}
    attempt.assert_not_called()
    consume.assert_not_called()
    persist.assert_not_called()
    assert events == []


def test_changed_parser_cannot_reuse_an_old_success_receipt(setup_owner, monkeypatch):
    connector, context, batch, _, events, _, _, _ = setup_owner
    connector.parser_version = "different-v2"
    read = Mock()
    monkeypatch.setattr(MODULE + "read_success", read)
    with pytest.raises(ValueError, match="silver_batch_parser_mismatch"):
        execute_durable_silver(connector, context, batch)
    read.assert_not_called()
    assert events == []


@pytest.mark.parametrize(
    "source,version,allowed",
    [
        ("wb_rtfp_mdg", "2.0.0", True),
        ("wb_rtfp_mdg", "2.1.0", False),
        ("other_source", "2.0.0", False),
    ],
)
def test_native_parser_exception_is_exactly_scoped(
    source, version, allowed, setup_owner, monkeypatch
):
    connector, context, batch, _, events, _, _, _ = setup_owner
    connector.source_id = context.source_id = source
    batch = replace(batch, source_id=source, parser_version=version)
    read = Mock(return_value={"n_inserted": 15})
    monkeypatch.setattr(MODULE + "read_success", read)
    if allowed:
        assert execute_durable_silver(connector, context, batch) == {"n_inserted": 15}
    else:
        with pytest.raises(ValueError, match="silver_batch_parser_mismatch"):
            execute_durable_silver(connector, context, batch)
        read.assert_not_called()
    assert events == []


@pytest.mark.parametrize("reason", ["ingestion_batch_missing", "ingestion_batch_digest_mismatch"])
def test_silver_registered_batch_guard_prevents_parse(setup_owner, monkeypatch, reason):
    connector, context, batch, _, events, _, _, _ = setup_owner
    monkeypatch.setattr(MODULE + "read_bronze_batch", Mock(side_effect=ValueError(reason)))
    consume = Mock()
    monkeypatch.setattr(MODULE + "consume_connector_silver", consume)
    with pytest.raises(DurablePhaseFailure, match="^silver:ValueError$"):
        execute_durable_silver(connector, context, batch)
    consume.assert_not_called()
    assert "rollback" in events and "commit" not in events


def test_receipt_write_failure_is_not_reported_as_durable_success(setup_owner, monkeypatch):
    connector, context, _, _, events, persist, _, _ = setup_owner
    monkeypatch.setattr(
        MODULE + "collect_connector_bronze", Mock(side_effect=ValueError("SOURCE_SECRET"))
    )
    persist.side_effect = OSError("DATABASE_SECRET")
    with pytest.raises(
        DurablePhaseFailure, match="^bronze:failure_receipt_unavailable$"
    ) as captured:
        execute_durable_bronze(connector, context)
    assert "rollback" in events and "commit" not in events
    assert captured.value.__suppress_context__
    assert captured.value.__context__ is None
    assert "SECRET" not in str(captured.value)


def test_silver_wrong_source_refuses_before_read_or_transaction(setup_owner, monkeypatch):
    connector, context, batch, _, events, persist, _, _ = setup_owner
    read = Mock()
    monkeypatch.setattr(MODULE + "read_running_run_reference", read)
    context.source_id = "dummy_wrong"
    with pytest.raises(ValueError, match="silver_batch_source_mismatch"):
        execute_durable_silver(connector, context, batch)
    read.assert_not_called()
    persist.assert_not_called()
    assert events == []
