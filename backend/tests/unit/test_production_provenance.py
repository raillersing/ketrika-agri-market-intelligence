"""Production raw/revision checks; mocked writes are not SQL qualification."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from ketrika.connectors.records import ProductionRecord
from ketrika.connectors.runner import load_production_record_with_supersession
from ketrika.core.models.db import ProductionObservation


def record() -> ProductionRecord:
    return ProductionRecord(
        product_raw="synthetic maize",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        element="production_t",
        value=1.25,
        value_raw="1.2500",
        unit_raw="t",
        evidence={"synthetic": True},
    )


def test_insert_keeps_raw_and_independent_proof() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = False
    session.execute.return_value.scalar_one_or_none.return_value = None
    candidate, source = record(), uuid4()
    status, identifier = load_production_record_with_supersession(
        session, candidate, "test", source
    )
    saved = session.add.call_args.args[0]
    assert status == "inserted" and saved.observation_id == identifier
    assert saved.value == Decimal("1.2500") and saved.value_raw == "1.2500"
    assert saved.source_record_id == source
    assert saved.evidence == candidate.evidence and saved.evidence is not candidate.evidence


@pytest.mark.parametrize("raw", [None, "", "001.2500"])
def test_raw_is_not_fabricated_or_normalized(raw: str | None) -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = False
    session.execute.return_value.scalar_one_or_none.return_value = None
    load_production_record_with_supersession(
        session, record().model_copy(update={"value_raw": raw}), "test", uuid4()
    )
    assert session.add.call_args.args[0].value_raw == raw


@pytest.mark.parametrize(
    "change",
    [
        {},
        {"value_raw": "01.2500"},
        {"evidence": {"synthetic": "revision"}},
        {"extraction_method": "dual_agree"},
        {"observed_or_imputed": "imputed"},
    ],
)
def test_revised_metadata_is_not_hidden_by_equal_value(change: dict) -> None:
    candidate, source = record(), uuid4()
    old = ProductionObservation(
        observation_id=uuid4(),
        source_record_id=source,
        value=Decimal("1.25"),
        value_raw=candidate.value_raw,
        unit_raw=candidate.unit_raw,
        flag_raw=None,
        evidence=candidate.evidence,
        extraction_method=candidate.extraction_method,
        observed_or_imputed=candidate.observed_or_imputed,
    )
    session = MagicMock(spec=Session)
    session.scalar.return_value = False
    session.execute.return_value.scalar_one_or_none.return_value = old
    revised_source = uuid4() if not change else source
    status, identifier = load_production_record_with_supersession(
        session, candidate.model_copy(update=change), "test", revised_source
    )
    assert status == "superseded" and identifier != old.observation_id
    assert old.value == Decimal("1.25") and old.source_record_id == source
    statement = session.execute.call_args.args[0]
    assert set(statement.compile().params) == {"superseded_by", "observation_id_1"}
    assert session.add.call_args.args[0].value_raw == candidate.model_copy(update=change).value_raw


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 1e16, 1.23456])
def test_unrepresentable_values_fail_before_writes(value: float) -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = False
    with pytest.raises(
        ValueError, match="production_(value_not_representable|precision_not_supported)"
    ):
        load_production_record_with_supersession(
            session, record().model_copy(update={"value": value}), "test", uuid4()
        )
    session.execute.assert_not_called()
    session.add.assert_not_called()
