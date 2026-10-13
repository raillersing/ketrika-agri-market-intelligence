"""Pure receipt bounds; not database/crash proof."""

from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest

from ketrika.connectors.silver_attempts import (
    SilverRunBusy,
    advisory_key,
    exclusive_silver_run,
    validate_native_stats,
    validate_stats,
)


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        [],
        {"n_inserted": True},
        {"n_inserted": -1},
        {"n_inserted": 2**63},
        {"n_inserted": 1.0},
        {"untrusted_text": 1},
        {"n_skipped": "3"},
    ],
)
def test_invalid_receipt_counters_refused(value):
    with pytest.raises(ValueError, match="silver_attempt_invalid_stats"):
        validate_stats(value)


def test_stats_are_copied_without_new_numbers():
    original = {"n_inserted": 0, "n_superseded": 4, "n_skipped": 2**63 - 1}
    result = validate_stats(original)
    assert result == original and result is not original


def test_native_phase_counter_shape_is_preserved():
    stats = {
        "n_fetched": 1,
        "n_new_artifacts": 1,
        "n_inserted": 3,
        "n_superseded": 0,
        "n_skipped": 0,
        "n_review": 2,
    }
    assert validate_stats(stats) == stats
    assert validate_native_stats(stats) == stats


@pytest.mark.parametrize(
    "missing", ["n_fetched", "n_new_artifacts", "n_inserted", "n_superseded", "n_skipped"]
)
def test_native_receipt_missing_counter_is_not_a_success(missing):
    stats = {
        "n_fetched": 1,
        "n_new_artifacts": 1,
        "n_inserted": 3,
        "n_superseded": 0,
        "n_skipped": 0,
    }
    del stats[missing]
    with pytest.raises(ValueError, match="silver_attempt_stats_incomplete"):
        validate_native_stats(stats)


def test_lock_key_deterministic_and_signed_bigint():
    identifier = uuid4()
    assert advisory_key(identifier) == advisory_key(identifier)
    assert -(2**63) <= advisory_key(identifier) < 2**63
    assert advisory_key(identifier) != advisory_key(uuid4())


@pytest.mark.parametrize("identifier", [None, "not-a-run", UUID(int=0)])
def test_lock_invalid_identity_refused(identifier):
    with pytest.raises(ValueError, match="silver_attempt_invalid_run"):
        advisory_key(identifier)


@pytest.mark.parametrize("failure", ["acquire", "commit", "unlock", "body"])
def test_pinned_connection_lock_is_released_or_invalidated(monkeypatch, failure):
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    engine = Mock()
    engine.connect.return_value = connection
    monkeypatch.setattr("ketrika.connectors.silver_attempts.get_engine", Mock(return_value=engine))
    connection.scalar.side_effect = [True, True]
    if failure == "acquire":
        connection.scalar.side_effect = OSError("database unavailable")
    elif failure == "commit":
        connection.commit.side_effect = OSError("commit unavailable")
    elif failure == "unlock":
        connection.scalar.side_effect = [True, False]
    expected = RuntimeError if failure in ("unlock", "body") else OSError
    with pytest.raises(expected):
        with exclusive_silver_run(uuid4()):
            if failure == "body":
                raise RuntimeError("worker failed")
    if failure == "body":
        assert connection.scalar.call_count == 2
        connection.invalidate.assert_not_called()
    else:
        connection.invalidate.assert_called()


def test_busy_lock_is_not_unlocked_or_claimed(monkeypatch):
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    connection.scalar.return_value = False
    engine = Mock()
    engine.connect.return_value = connection
    monkeypatch.setattr("ketrika.connectors.silver_attempts.get_engine", Mock(return_value=engine))
    with pytest.raises(SilverRunBusy):
        with exclusive_silver_run(uuid4()):
            pytest.fail("busy lock must not yield")
    assert connection.scalar.call_count == 1
    connection.invalidate.assert_not_called()
