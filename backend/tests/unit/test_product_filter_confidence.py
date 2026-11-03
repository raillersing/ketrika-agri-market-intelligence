"""API product filters never silently assign a weak alias to a canonical scope."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from ketrika.api.routers import prices


@pytest.mark.parametrize("endpoint", ["history", "latest"])
@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("Rice", None),
        ("rice_milled", None),
        ("RICE_WHITE_LOCAL", None),
        ("Rice (local)", "RICE_WHITE_LOCAL"),
        ("vary gasy", "RICE_WHITE_LOCAL"),
        ("rice_imported", "RICE_WHITE_IMPORTED"),
    ],
)
def test_filter_scope_requires_confident_alias(monkeypatch, endpoint, raw, canonical):
    # SQL admission is covered separately on PostgreSQL; this unit verifies the
    # actual taxonomy and API query binding without mocking product resolution.
    monkeypatch.setattr(prices, "require_gold_view", lambda *_args: None)
    session = MagicMock(spec=Session)
    session.execute.return_value.fetchall.return_value = []
    if endpoint == "history":
        result = prices.get_prices(
            product=raw,
            location=None,
            actor_level=None,
            from_date=None,
            to_date=None,
            granularity="month",
            source=None,
            format="json",
            session=session,
        )
    else:
        result = prices.get_prices_latest(product=raw, level=1, session=session)
    assert result == []
    session.execute.assert_called_once()
    statement, parameters = session.execute.call_args.args
    assert parameters.get("product", parameters.get("prod")) == raw
    if canonical is None:
        assert "canonical" not in parameters
        assert ":canonical" not in str(statement)
    else:
        assert parameters["canonical"] == canonical
        assert ":canonical" in str(statement)
