"""Mock transaction intent, not SQL locks or actual normalization evidence."""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from ketrika.core.reference_lock import lock_reference_manifest
from ketrika.core.reference_manifest import build_reference_manifest


def test_lock_precedes_manifest_in_same_session_without_commit():
    session = Mock(spec=Session)
    events = []
    session.execute.side_effect = lambda statement: events.append(str(statement))
    expected = build_reference_manifest([])

    def read(actual):
        assert actual is session
        events.append("read")
        return expected

    with patch("ketrika.core.reference_lock.read_reference_manifest", side_effect=read):
        assert lock_reference_manifest(session) is expected
    assert events == [
        "SET LOCAL lock_timeout = '5s'",
        "LOCK TABLE ref.location, ref.location_alias, ref.product, ref.product_alias, ref.unit_conversion IN SHARE MODE",
        "read",
    ]
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


@pytest.mark.parametrize("operation", ["timeout", "lock", "read"])
def test_failure_never_returns_success_or_commits(operation):
    session = Mock(spec=Session)
    error = RuntimeError("inert failure")
    session.execute.side_effect = (
        [error] if operation == "timeout" else [Mock(), error] if operation == "lock" else None
    )
    with patch("ketrika.core.reference_lock.read_reference_manifest", side_effect=error) as read:
        with pytest.raises(RuntimeError, match="inert failure"):
            lock_reference_manifest(session)
    if operation != "read":
        read.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
