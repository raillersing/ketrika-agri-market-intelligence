"""Prepared metadata session semantics; no SQL or pipeline receipt claimed."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from ketrika.connectors.durable_runs import (
    DurableRunReference,
    bind_running_run,
    create_durable_ingestion_run,
    persist_durable_run_failure,
    read_running_run_reference,
)
from ketrika.core.models.db import IngestionRun


def prepare_session(monkeypatch):
    session, events = MagicMock(), []

    @contextmanager
    def independent():
        events.append("open")
        yield session
        events.append("committed")

    monkeypatch.setattr("ketrika.connectors.durable_runs.get_session", independent)
    return session, events


def reference_and_run():
    reference = DurableRunReference(uuid4(), "dummy_durable", datetime.now(UTC), str(uuid4()))
    run = IngestionRun(
        run_id=reference.run_id,
        source_id=reference.source_id,
        started_at=reference.started_at,
        dagster_run_id=reference.dagster_run_id,
        status="running",
    )
    return reference, run


def test_bind_locks_exact_owner_without_committing(monkeypatch):
    session, events = prepare_session(monkeypatch)
    reference, run = reference_and_run()
    session.scalar.return_value = run
    assert bind_running_run(session, reference) is run
    assert "FOR UPDATE" in str(session.scalar.call_args.args[0])
    assert events == []
    session.commit.assert_not_called()
    session.add.assert_not_called()


@pytest.mark.parametrize("field", ["source_id", "started_at", "dagster_run_id"])
def test_bind_rejects_owner_mismatch(field, monkeypatch):
    session, _ = prepare_session(monkeypatch)
    reference, run = reference_and_run()
    setattr(run, field, None)
    session.scalar.return_value = run
    with pytest.raises(ValueError, match="reference_mismatch"):
        bind_running_run(session, reference)
    session.flush.assert_not_called()


@pytest.mark.parametrize("status", ["success", "failed", "cancelled"])
def test_bind_refuses_terminal_owner(status, monkeypatch):
    session, _ = prepare_session(monkeypatch)
    reference, run = reference_and_run()
    run.status = status
    session.scalar.return_value = run
    with pytest.raises(ValueError, match="not_running"):
        bind_running_run(session, reference)


def test_read_owner_uses_real_metadata_not_caller_dates(monkeypatch):
    session, events = prepare_session(monkeypatch)
    reference, run = reference_and_run()
    session.get.return_value = run
    assert read_running_run_reference(reference.run_id, reference.source_id) == reference
    assert events == ["open", "committed"]
    session.add.assert_not_called()
    session.flush.assert_not_called()


@pytest.mark.parametrize("variant", ["missing", "wrong_source", "finished", "success"])
def test_read_owner_refuses_missing_mismatched_or_terminal(variant, monkeypatch):
    session, _ = prepare_session(monkeypatch)
    reference, run = reference_and_run()
    if variant == "wrong_source":
        run.source_id = "dummy_other"
    if variant == "finished":
        run.finished_at = datetime.now(UTC)
    if variant == "success":
        run.status = "success"
    session.get.return_value = None if variant == "missing" else run
    with pytest.raises(ValueError, match="reference_mismatch|not_running"):
        read_running_run_reference(reference.run_id, reference.source_id)
    session.add.assert_not_called()


def test_create_returns_after_independent_transaction(monkeypatch):
    session, events = prepare_session(monkeypatch)
    reference = create_durable_ingestion_run("dummy_durable", str(uuid4()))
    run = session.add.call_args.args[0]
    assert events == ["open", "committed"]
    assert isinstance(run, IngestionRun) and run.status == "running"
    assert (run.run_id, run.source_id, run.started_at, run.dagster_run_id) == (
        reference.run_id,
        reference.source_id,
        reference.started_at,
        reference.dagster_run_id,
    )
    assert reference.started_at.tzinfo is UTC
    session.flush.assert_called_once()
    session.commit.assert_not_called()


def test_create_does_not_manufacture_or_activate_source(monkeypatch):
    session, events = prepare_session(monkeypatch)
    session.get.return_value = None
    with pytest.raises(ValueError, match="source_not_persisted"):
        create_durable_ingestion_run("dummy_missing")
    assert events == ["open"]
    session.add.assert_not_called()
    session.flush.assert_not_called()


@pytest.mark.parametrize("source_id", [None, "", "bad SOURCE", "x" * 129])
def test_invalid_source_refused_before_session(source_id, monkeypatch):
    session, events = prepare_session(monkeypatch)
    with pytest.raises(ValueError, match="invalid_source"):
        create_durable_ingestion_run(source_id)
    assert events == []
    session.get.assert_not_called()


@pytest.mark.parametrize("dagster_id", ["", "not-a-uuid", "00000000-0000-0000-0000-000000000000"])
def test_invalid_dagster_id_refused_before_session(dagster_id, monkeypatch):
    _, events = prepare_session(monkeypatch)
    with pytest.raises(ValueError, match="invalid_dagster_id"):
        create_durable_ingestion_run("dummy_durable", dagster_id)
    assert events == []


def test_failure_only_changes_run_metadata_after_verified_identity(monkeypatch):
    session, events = prepare_session(monkeypatch)
    reference, run = reference_and_run()
    session.scalar.return_value = run
    result = persist_durable_run_failure(reference, RuntimeError)
    assert result == run.run_id and events == ["open", "committed"]
    assert run.status == "failed" and run.error == "RuntimeError"
    assert run.finished_at is not None and run.finished_at.tzinfo is UTC
    sql = str(session.scalar.call_args.args[0])
    assert "FOR UPDATE" in sql and "ingestion_run.run_id =" in sql
    session.flush.assert_called_once()
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_same_failure_retry_keeps_first_finish_time(monkeypatch):
    session, events = prepare_session(monkeypatch)
    reference, run = reference_and_run()
    finished = datetime(2026, 1, 1, tzinfo=UTC)
    run.status, run.error, run.finished_at = "failed", "RuntimeError", finished
    session.scalar.return_value = run
    assert persist_durable_run_failure(reference, RuntimeError) == reference.run_id
    assert events == ["open", "committed"] and run.finished_at == finished
    session.flush.assert_not_called()


@pytest.mark.parametrize("status", ["success", "partial", "cancelled"])
def test_terminal_run_not_rewritten(status, monkeypatch):
    session, events = prepare_session(monkeypatch)
    reference, run = reference_and_run()
    run.status = status
    session.scalar.return_value = run
    with pytest.raises(ValueError, match="already_terminal"):
        persist_durable_run_failure(reference, RuntimeError)
    assert run.status == status and run.error is None and events == ["open"]
    session.flush.assert_not_called()


def test_reference_mismatch_refused_without_rewrite(monkeypatch):
    session, events = prepare_session(monkeypatch)
    reference, run = reference_and_run()
    session.scalar.return_value = run
    with pytest.raises(ValueError, match="reference_mismatch"):
        persist_durable_run_failure(replace(reference, source_id="dummy_other"), RuntimeError)
    assert run.status == "running" and events == ["open"]
    session.flush.assert_not_called()


@pytest.mark.parametrize("cause", ["RUN_TOOL_NOW", RuntimeError("untrusted body"), None])
def test_error_instances_or_strings_never_accepted(cause, monkeypatch):
    _, events = prepare_session(monkeypatch)
    reference, _ = reference_and_run()
    with pytest.raises(ValueError, match="invalid_error_class"):
        persist_durable_run_failure(reference, cause)
    assert events == []
