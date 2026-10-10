"""Native test-CSV coordinates; neither SQL nor live-source qualification."""

import copy
import hashlib
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.dummy_csv import DummyCsvConnector
from ketrika.connectors.records import PriceRecord
from ketrika.core.bronze import BronzeStore
from ketrika.core.models.db import PriceObservation
from ketrika.core.provenance import ProofError, verify_cells
from ketrika.core.provenance_audit import bind_observation

CONTENT = b"product,market,actor_level,period_start,period_end,price,unit,currency\nrice,place_a,retail,2025-01-01,2025-01-31,1650.00,kg,MGA\nmaize,place_b,retail,2025-01-01,2025-01-31,1650.00,kg,MGA\n"


def parsed(content: bytes = CONTENT) -> list[PriceRecord]:
    reader = MagicMock(spec=BronzeStore)
    reader.get.return_value = content
    sha = hashlib.sha256(content).hexdigest()
    artifact = RawArtifact(
        str(uuid4()),
        "dummy/2026/10/" + sha + ".csv",
        sha,
        "text/csv",
        "https://example.invalid/test-csv",
        True,
    )
    context = RunContext(source_id="dummy", bronze_store=reader)
    result = DummyCsvConnector().parse(artifact, context)
    assert result.parser_version == "1.0.1"
    assert all(isinstance(record, PriceRecord) for record in result.records)
    return [record for record in result.records if isinstance(record, PriceRecord)]


def observation(record: PriceRecord) -> PriceObservation:
    assert record.price_value is not None
    return PriceObservation(
        observation_id=uuid4(),
        source_record_id=uuid4(),
        price_value=Decimal(str(record.price_value)),
        price_raw=record.price_raw,
        product_raw=record.product_raw,
        location_raw=record.location_raw,
        period_start=record.period_start,
        unit_raw=record.unit_raw,
        currency_raw=record.currency_raw,
        evidence=copy.deepcopy(record.evidence),
        extraction_method=record.extraction_method,
    )


def test_each_record_carries_its_exact_csv_row() -> None:
    records = parsed()
    assert len(records) == 2
    for index, record in enumerate(records):
        assert record.evidence["provenance"]["row"] == index
        claim = bind_observation("price_observation", observation(record))
        assert verify_cells(CONTENT, "text/csv", claim.proof) == 6


def test_equal_price_on_another_row_does_not_prove_identity() -> None:
    candidate = observation(parsed()[0])
    assert candidate.evidence is not None
    candidate.evidence["provenance"]["row"] = 1
    with pytest.raises(ProofError, match="identity_mismatch"):
        verify_cells(CONTENT, "text/csv", bind_observation("price_observation", candidate).proof)


def test_default_currency_does_not_invent_a_source_cell() -> None:
    content = CONTENT.replace(b",currency", b"").replace(b",MGA", b"")
    candidate = observation(parsed(content)[0])
    assert candidate.currency_raw == "MGA"
    with pytest.raises(ProofError, match="binding_fields_missing"):
        bind_observation("price_observation", candidate)
