"""Publication parse gate preserves the per-batch 99% threshold."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from ketrika.gold.dq import GoldDqRejected, check_publication_parse_success


def test_empty_publication_has_no_invented_success_percentage():
    session = MagicMock()
    result = check_publication_parse_success(session, ())
    assert result.passed
    assert result.details == {"state": "empty", "rate": None, "groups": []}
    assert result.metric != 100
    session.execute.assert_not_called()


def test_every_batch_must_meet_threshold_not_aggregate_survivors():
    session = MagicMock()
    session.execute.return_value.all.return_value = [
        ("large", 10000, 10000, 10000),
        ("small", 2, 1, 2),
    ]
    result = check_publication_parse_success(session, (uuid4(),))
    assert not result.passed
    assert result.metric == 50
    assert result.threshold == 99


def test_exact_99_percent_remains_accepted():
    session = MagicMock()
    session.execute.return_value.all.return_value = [("batch", 100, 99, 100)]
    result = check_publication_parse_success(session, (uuid4(),))
    assert result.passed and result.metric == 99


def test_missing_parse_scope_fails_closed():
    session = MagicMock()
    session.execute.return_value.all.return_value = []
    with pytest.raises(GoldDqRejected, match="publication_parse_scope_missing"):
        check_publication_parse_success(session, (uuid4(),))


def test_incomplete_batch_cannot_appear_successful():
    session = MagicMock()
    session.execute.return_value.all.return_value = [("incomplete", 1, 1, 2)]
    with pytest.raises(GoldDqRejected, match="publication_parse_counts_invalid"):
        check_publication_parse_success(session, (uuid4(),))
