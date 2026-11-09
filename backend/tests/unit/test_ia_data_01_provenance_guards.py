"""Tests for IA-DATA-01: Provenance guards, synthetic isolation, and quarantine ledger.

Normative requirements:
1. Provenance totale: Every observation published to Gold must have valid Bronze cell proof.
2. Synthetic isolation: Synthetic extractions, fixture URLs, and dummy source records must be rejected.
3. No auto-acceptance: Manual imports or unverified observations must not auto-publish to Gold.
4. Quarantine ledger: Unverified observations are quarantined without altering Bronze artifacts.
5. Bronze immutability: Deletion or mutation of immutable Bronze metadata is strictly forbidden.
"""

from __future__ import annotations

import hashlib
import uuid
from decimal import Decimal
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from ketrika.core.models.db import (
    PriceObservation,
    SourceRecord,
)
from ketrika.core.provenance import (
    ArtifactReader,
)
from ketrika.core.provenance_audit import (
    ObservationTarget,
    audit_observation_provenance,
)
from ketrika.gold.provenance_gate import (
    GoldProvenanceRejected,
    require_gold_provenance,
)


class DummyReader(ArtifactReader):
    """In-memory reader for isolated unit tests."""

    def __init__(self, data: dict[str, bytes] | None = None) -> None:
        self.data = data or {}
        self.reads = 0

    def get(self, object_key: str) -> bytes:
        self.reads += 1
        if object_key not in self.data:
            raise KeyError(f"object_not_found: {object_key}")
        return self.data[object_key]


def _make_source_record(
    source_id: str = "wb_rtfp_mdg",
    retrieved_via: str = "direct",
    source_url: str = "https://microdata.worldbank.org/rtfp.json",
    content_bytes: bytes = b"test content",
) -> tuple[SourceRecord, bytes]:
    sha = hashlib.sha256(content_bytes).hexdigest()
    rec = SourceRecord(
        source_record_id=uuid.uuid4(),
        source_id=source_id,
        source_url=source_url,
        retrieved_via=retrieved_via,
        object_key=f"{source_id}/2026/10/{sha}.csv",
        content_sha256=sha,
        mime_type="text/csv",
        extraction_status="parsed",
    )
    return rec, content_bytes


def test_synthetic_extraction_method_rejected_by_provenance_audit():
    """Observations with extraction_method='synthetic' must be rejected."""
    rec, content = _make_source_record()
    reader = DummyReader({rec.object_key: content})

    obs = Mock(spec=PriceObservation)
    obs.observation_id = uuid.uuid4()
    obs.source_record_id = rec.source_record_id
    obs.extraction_method = "synthetic"
    obs.price_value = Decimal("2500.00")
    obs.product_id = uuid.uuid4()
    obs.location_id = uuid.uuid4()
    obs.missing_code = None
    obs.evidence = {"provenance": {"cells": [{"field": "price_value", "role": "value"}]}}

    session = Mock(spec=Session)
    session.get.return_value = obs
    session.scalars.return_value.all.return_value = [rec]

    target = ObservationTarget("price_observation", obs.observation_id)
    receipt = audit_observation_provenance(session, reader, mode="incremental", targets=[target])

    assert not receipt.report.passed
    assert receipt.report.results[0].passed is False
    assert receipt.report.results[0].reason == "extraction_proof_not_supported"


@pytest.mark.parametrize(
    "source_id,retrieved_via,source_url",
    [
        ("dummy_fixture_01", "direct", "https://example.com/test.csv"),
        ("fixture_source", "direct", "https://example.com/test.csv"),
        ("wb_rtfp_mdg", "synthetic", "https://microdata.worldbank.org/test.csv"),
        ("wb_rtfp_mdg", "direct", "fixture://synthetic_test_data.csv"),
    ],
)
def test_synthetic_source_record_rejected_by_provenance_audit(
    source_id: str, retrieved_via: str, source_url: str
):
    """Source records marked as synthetic, fixture, or dummy must be rejected."""
    rec, content = _make_source_record(
        source_id=source_id, retrieved_via=retrieved_via, source_url=source_url
    )
    reader = DummyReader({rec.object_key: content})

    obs = Mock(spec=PriceObservation)
    obs.observation_id = uuid.uuid4()
    obs.source_record_id = rec.source_record_id
    obs.extraction_method = "deterministic"
    obs.price_value = Decimal("2500.00")
    obs.product_id = uuid.uuid4()
    obs.location_id = uuid.uuid4()
    obs.missing_code = None
    obs.evidence = {
        "provenance": {
            "cells": [
                {"field": "price_value", "role": "value", "raw_expected": "2500.00"},
                {"field": "product_id", "role": "identity"},
                {"field": "location_id", "role": "identity"},
            ]
        }
    }

    session = Mock(spec=Session)
    session.get.return_value = obs
    session.scalars.return_value.all.return_value = [rec]

    target = ObservationTarget("price_observation", obs.observation_id)
    receipt = audit_observation_provenance(session, reader, mode="incremental", targets=[target])

    assert not receipt.report.passed
    assert receipt.report.results[0].passed is False
    assert receipt.report.results[0].reason == "synthetic_source_record_forbidden"


def test_missing_cell_evidence_rejected_by_provenance_audit():
    """Observations lacking Bronze cell proof must be rejected."""
    rec, content = _make_source_record()
    reader = DummyReader({rec.object_key: content})

    obs = Mock(spec=PriceObservation)
    obs.observation_id = uuid.uuid4()
    obs.source_record_id = rec.source_record_id
    obs.extraction_method = "deterministic"
    obs.price_value = Decimal("2500.00")
    obs.evidence = None  # No evidence

    session = Mock(spec=Session)
    session.get.return_value = obs
    session.scalars.return_value.all.return_value = [rec]

    target = ObservationTarget("price_observation", obs.observation_id)
    receipt = audit_observation_provenance(session, reader, mode="incremental", targets=[target])

    assert not receipt.report.passed
    assert receipt.report.results[0].passed is False
    assert receipt.report.results[0].reason == "binding_proof_missing"


def test_missing_bronze_object_fails_verification():
    """If the Bronze artifact is not in object storage, verification must fail."""
    rec, content = _make_source_record()
    reader = DummyReader()  # Empty reader: object is absent

    obs = Mock(spec=PriceObservation)
    obs.observation_id = uuid.uuid4()
    obs.source_record_id = rec.source_record_id
    obs.extraction_method = "deterministic"
    obs.price_value = Decimal("2500.00")
    obs.product_id = uuid.uuid4()
    obs.location_id = uuid.uuid4()
    obs.missing_code = None
    obs.evidence = {
        "provenance": {
            "cells": [
                {"field": "price_value", "role": "value"},
                {"field": "product_id", "role": "identity"},
                {"field": "location_id", "role": "identity"},
            ]
        }
    }

    session = Mock(spec=Session)
    session.get.return_value = obs
    session.scalars.return_value.all.return_value = [rec]

    target = ObservationTarget("price_observation", obs.observation_id)
    receipt = audit_observation_provenance(session, reader, mode="incremental", targets=[target])

    assert not receipt.report.passed
    assert receipt.report.results[0].passed is False


def test_require_gold_provenance_raises_when_audit_fails():
    """require_gold_provenance must raise GoldProvenanceRejected when audit fails."""
    session = Mock(spec=Session)
    reader = DummyReader()

    obs_id = uuid.uuid4()
    sr_id = uuid.uuid4()
    obs = Mock(spec=PriceObservation)
    obs.observation_id = obs_id
    obs.source_record_id = sr_id
    obs.extraction_method = "synthetic"  # Invalid
    obs.evidence = None

    rec = SourceRecord(
        source_record_id=sr_id,
        source_id="dummy_test",
        source_url="fixture://dummy",
        retrieved_via="synthetic",
        object_key="dummy_test/2026/10/sha.csv",
        content_sha256="a" * 64,
        extraction_status="parsed",
    )

    session.scalars.return_value.all.side_effect = [[obs], [rec]]
    session.get.return_value = obs

    with pytest.raises(GoldProvenanceRejected):
        require_gold_provenance(session, reader, ["price_obs_current"])
