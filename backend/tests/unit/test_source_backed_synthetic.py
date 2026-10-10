"""Generator checks with simulated stores; never SQL/live qualification."""

import hashlib
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from ketrika.core.bronze import BronzeArtifact
from ketrika.core.models.db import PriceObservation, SourceRecord
from ketrika.core.provenance import ProofError, verify_cells
from ketrika.core.provenance_audit import bind_observation
from tests.e2e_data.source_backed_synthetic import attach_new_synthetic_proof


def price(raw: str | None = "1650.00") -> PriceObservation:
    return PriceObservation(
        observation_id=uuid4(),
        source_record_id=uuid4(),
        price_value=Decimal("1650.00"),
        price_raw=raw,
        product_raw="synthetic rice",
        location_raw="synthetic location",
        period_start=date(2024, 1, 1),
        unit_raw="kg",
        currency_raw="MGA",
    )


@pytest.mark.parametrize("raw", ["1650.00", None])
def test_generated_cells_match_before_any_observation_insert(raw) -> None:
    session, reader = MagicMock(spec=Session), MagicMock()
    reference = SourceRecord(source_record_id=uuid4(), source_id="synthetic")
    session.get.side_effect = [reference, None]
    reader.bucket = "ketrika-qa-bronze"
    contents: list[bytes] = []

    def put(**kwargs):
        content = kwargs["content"]
        contents.append(content)
        sha = hashlib.sha256(content).hexdigest()
        return BronzeArtifact(
            "synthetic/2024/03/" + sha + ".json",
            sha,
            "application/json",
            kwargs["url"],
            kwargs["fetched_at"],
            True,
            len(content),
        )

    reader.put.side_effect = put
    observation = price(raw)
    old_reference = observation.source_record_id
    with (
        patch("tests.e2e_data.source_backed_synthetic.require_synthetic_test_database") as safety,
        patch("tests.e2e_data.source_backed_synthetic.BronzeStore", return_value=reader),
    ):
        attach_new_synthetic_proof(session, observation)
    safety.assert_called_once()
    assert observation.source_record_id != old_reference
    assert observation.price_raw == "1650.00"
    assert observation.evidence is not None
    assert observation.evidence["authenticity"] == "synthetic"
    assert observation.evidence["verified"] is False
    verify_cells(
        contents[0], "application/json", bind_observation("price_observation", observation).proof
    )
    assert reader.put.call_args.kwargs["http_status"] == 0
    assert reader.put.call_args.kwargs["retrieved_via"] == "manual_upload"
    assert isinstance(session.add.call_args.args[0], SourceRecord)
    session.commit.assert_not_called()


def test_contradictory_raw_fails_before_bronze_or_silver_write() -> None:
    session, reader = MagicMock(spec=Session), MagicMock()
    session.get.return_value = SourceRecord(source_id="synthetic")
    reader.bucket = "ketrika-qa-bronze"
    with (
        patch("tests.e2e_data.source_backed_synthetic.require_synthetic_test_database"),
        patch("tests.e2e_data.source_backed_synthetic.BronzeStore", return_value=reader),
    ):
        with pytest.raises(ProofError, match="value_mismatch"):
            attach_new_synthetic_proof(session, price("9999"))
    reader.put.assert_not_called()
    session.add.assert_not_called()


def test_wrong_bucket_fails_before_any_write() -> None:
    session, reader = MagicMock(spec=Session), MagicMock()
    session.get.return_value = SourceRecord(source_id="synthetic")
    reader.bucket = "bronze"
    with (
        patch("tests.e2e_data.source_backed_synthetic.require_synthetic_test_database"),
        patch("tests.e2e_data.source_backed_synthetic.BronzeStore", return_value=reader),
    ):
        with pytest.raises(ValueError, match="synthetic_bronze_destination_refused"):
            attach_new_synthetic_proof(session, price())
    reader.put.assert_not_called()
    session.add.assert_not_called()


def test_pending_observation_cannot_be_retrofitted() -> None:
    session, reader = MagicMock(spec=Session), MagicMock()
    observation = price()
    with Session() as holder:
        holder.add(observation)
        with (
            patch("tests.e2e_data.source_backed_synthetic.require_synthetic_test_database"),
            patch("tests.e2e_data.source_backed_synthetic.BronzeStore", return_value=reader),
        ):
            with pytest.raises(
                ValueError, match="synthetic_proof_requires_new_transient_observation"
            ):
                attach_new_synthetic_proof(session, observation)
    session.get.assert_not_called()
    reader.put.assert_not_called()


def test_float_is_not_a_verified_input_to_the_proof_generator() -> None:
    session, reader = MagicMock(spec=Session), MagicMock()
    session.get.return_value = SourceRecord(source_id="synthetic")
    reader.bucket = "ketrika-qa-bronze"
    observation = price()
    observation.price_value = 1650.0
    with (
        patch("tests.e2e_data.source_backed_synthetic.require_synthetic_test_database"),
        patch("tests.e2e_data.source_backed_synthetic.BronzeStore", return_value=reader),
    ):
        with pytest.raises(ProofError, match="invalid_bound_number"):
            attach_new_synthetic_proof(session, observation)
    reader.put.assert_not_called()
    session.add.assert_not_called()
