"""Preview presentation/safety tests; SQL persistence is checked separately."""

import runpy
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PREVIEW = runpy.run_path(str(Path(__file__).parents[2] / "scripts" / "price_preview.py"))


def test_preview_discloses_historical_imputed_and_pending_status():
    page = PREVIEW["render"]([])
    assert "historiques" in page
    assert "Estimations imputées" in page
    assert "pas des relevés observés ni des prix actuels" in page
    assert "normalisation à revoir" in page
    assert "/api/prices" in page


def test_collected_content_is_escaped_not_executed():
    item = dict.fromkeys(
        ("period", "product", "market", "price_raw", "currency", "unit", "kind", "review"),
        '<script>alert("source")</script>',
    )
    page = PREVIEW["render"]([item])
    assert "<script>" not in page
    assert "&lt;script&gt;" in page


def test_existing_database_is_refused_before_migration_or_write():
    session = MagicMock()
    session.scalar.return_value = "meta.source_record"
    # Functions loaded by runpy retain their own globals mapping.
    function = PREVIEW["prepare"]
    with patch.dict(
        function.__globals__, require_network_none=MagicMock(), require_destination=MagicMock()
    ):
        with pytest.raises(ValueError, match="already_initialized_no_overwrite"):
            function(session)
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_read_query_begins_readonly_transaction():
    session = MagicMock()
    session.execute.side_effect = [None, MagicMock(all=lambda: [])]
    assert PREVIEW["read_prices"](session) == []
    assert str(session.execute.call_args_list[0].args[0]) == "SET TRANSACTION READ ONLY"
    session.commit.assert_not_called()
