"""Unknown quarantine state and unselected rebuild destinations fail closed."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from ketrika.core.quarantine import require_eligible_source, require_no_active_quarantine
from ketrika.pipelines import rebuild, rebuild_qualification


@pytest.mark.parametrize("state,reason", [(True, "preservation_required"), (None, "unavailable")])
def test_wipe_refuses_before_mutation_or_refresh(monkeypatch, state, reason):
    session = MagicMock()
    session.scalar.return_value = state
    refresh = MagicMock()
    monkeypatch.setattr(rebuild, "refresh_gold_views", refresh)
    with pytest.raises(ValueError, match=reason):
        rebuild.wipe_silver_gold_tables(session)
    session.execute.assert_not_called()
    refresh.assert_not_called()


@pytest.mark.parametrize("state,reason", [(True, "quarantined"), (None, "unavailable")])
def test_quarantined_or_unknown_source_is_refused(state, reason):
    session = MagicMock()
    session.scalar.return_value = state
    with pytest.raises(ValueError, match=reason):
        require_eligible_source(session, uuid4())
    session.add.assert_not_called()


def test_source_identity_is_required_before_query():
    session = MagicMock()
    with pytest.raises(ValueError, match="identity_required"):
        require_eligible_source(session, None)
    session.scalar.assert_not_called()


def test_explicitly_unquarantined_state_is_allowed():
    session = MagicMock()
    session.scalar.return_value = False
    require_eligible_source(session, uuid4())
    require_no_active_quarantine(session)


def test_cli_rebuild_never_reaches_replay_on_unselected_destination(monkeypatch):
    def refuse(session):
        raise rebuild_qualification.RebuildSafetyError("rebuild_destination_not_dedicated")

    replay = MagicMock()
    monkeypatch.setattr(rebuild, "get_session", MagicMock())
    monkeypatch.setattr(rebuild, "rebuild_database", replay)
    monkeypatch.setattr(rebuild_qualification, "require_destination", refuse)
    monkeypatch.setattr(
        rebuild_qualification,
        "require_network_none",
        lambda: pytest.fail("Destination must be checked first"),
    )
    with pytest.raises(SystemExit) as exit_info:
        rebuild.main()
    assert exit_info.value.code == 1
    replay.assert_not_called()
