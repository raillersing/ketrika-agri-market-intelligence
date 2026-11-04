"""Synthetic trajectories must not become official market artifacts."""

from datetime import date
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from ketrika.core.schema_audit import audit_source_schema
from ketrika.gold import parity_pricing
from tests.unit.test_schema_audit import example


def test_synthetic_writer_refuses_before_session_or_bronze_access(monkeypatch):
    session = Mock(spec=Session)
    bronze = Mock(side_effect=AssertionError("unexpected_bronze_access"))
    monkeypatch.setattr("ketrika.core.bronze.BronzeStore.put", bronze)
    with pytest.raises(
        parity_pricing.UnverifiedPricingInputs,
        match="verified_economic_pricing_inputs_required",
    ):
        parity_pricing.generate_and_load_econometric_prices(session)
    assert session.mock_calls == []
    bronze.assert_not_called()


def test_cli_refuses_before_opening_database(monkeypatch):
    connect = Mock(side_effect=AssertionError("unexpected_database_access"))
    monkeypatch.setattr("ketrika.core.db.get_session", connect)
    with pytest.raises(parity_pricing.UnverifiedPricingInputs):
        parity_pricing.main()
    connect.assert_not_called()


@pytest.mark.parametrize("source", ["douanes_stats", "miasa_odr"])
def test_generated_csv_is_not_admitted_as_official_source_schema(source):
    session, reader, record = example()
    record.source_id = source
    record.object_key = record.object_key.replace("dummy_schema/", source + "/", 1)
    record.parser_version = "1.0.0"
    record.mime_type = "text/csv"
    receipt = audit_source_schema(session, reader, source, record_ids=(record.source_record_id,))
    assert receipt.report.valid_artifacts == 0
    assert receipt.report.results[0]["state"] == "unknown"
    assert receipt.report.results[0]["binding_contract_sha256"] is None
    session.commit.assert_not_called()


def test_scenarios_are_explicitly_unqualified_and_have_no_factual_citation():
    period = date(2026, 10, 1)
    macro = parity_pricing.get_macro_benchmarks(period)
    imported = parity_pricing.compute_import_parity_price("WHEAT_FLOUR", period, macro)
    local = parity_pricing.compute_substitution_price("MAIZE_GRAIN", period, 2800.0, macro)
    assert imported["qualification"] == local["qualification"] == "synthetic_unverified"
    assert imported["source_citation"] is None
