"""Unit tests and Golden validation for MiASA ODR connector (CC1, CC2, T4.1)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from ketrika.connectors.base import RawArtifact, RunContext
from ketrika.connectors.miasa_odr import MiasaOdrConnector
from ketrika.connectors.records import PriceRecord
from ketrika.core.bronze import BronzeStore
from ketrika.core.registry import find_repo_root
from ketrika.extraction.llm.replay import ReplayClient

FIXTURES_DIR = find_repo_root() / "backend" / "tests" / "fixtures" / "miasa_odr"
GOLDEN_DIR = find_repo_root() / "backend" / "tests" / "golden" / "miasa_odr"


@pytest.fixture
def odr_pdf_bytes_520() -> bytes:
    with open(FIXTURES_DIR / "odr_bulletin_520.pdf", "rb") as f:
        return f.read()


@pytest.fixture
def odr_pdf_bytes_710() -> bytes:
    with open(FIXTURES_DIR / "odr_bulletin_710.pdf", "rb") as f:
        return f.read()


@pytest.fixture
def odr_pdf_bytes_850() -> bytes:
    with open(FIXTURES_DIR / "odr_bulletin_850.pdf", "rb") as f:
        return f.read()


@pytest.fixture
def golden_520() -> dict[str, Any]:
    with open(GOLDEN_DIR / "odr_bulletin_520.expected.json", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
        return data


@pytest.fixture
def golden_710() -> dict[str, Any]:
    with open(GOLDEN_DIR / "odr_bulletin_710.expected.json", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
        return data


@pytest.fixture
def golden_850() -> dict[str, Any]:
    with open(GOLDEN_DIR / "odr_bulletin_850.expected.json", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
        return data


def test_miasa_odr_parse_bulletin_850(odr_pdf_bytes_850: bytes, golden_850: dict[str, Any]) -> None:
    """CC1: Unit test verifying PDF parsing on modern epoch (Bulletin 850, 2024)."""
    connector = MiasaOdrConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = odr_pdf_bytes_850
    ctx = RunContext(
        source_id="miasa_odr",
        bronze_store=mock_bronze,
        llm_client=ReplayClient(),
    )

    artifact = RawArtifact(
        source_record_id="test-rec-850",
        object_key="bronze/miasa_odr/850.pdf",
        content_sha256=golden_850["metadata"]["content_sha256"],
        mime_type="application/pdf",
        url="http://www.agriculture.gov.mg/odr/bulletin_850.pdf",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)

    assert len(result.issues) == 0
    assert len(result.records) == 60
    assert len(result.records) == golden_850["metadata"]["total_records"]

    price_records = [r for r in result.records if isinstance(r, PriceRecord)]
    assert len(price_records) == 60

    # Observation period = observation month (Jan 2024), not publication date (T4.1 rule)
    assert all(r.period_start.isoformat() == "2024-01-01" for r in price_records)
    assert all(r.period_end.isoformat() == "2024-01-31" for r in price_records)

    # All three actor levels present
    actor_levels = {r.actor_level for r in price_records}
    assert actor_levels == {"producer", "wholesale", "retail"}

    # Producer paddy records
    paddy_recs = [r for r in price_records if r.actor_level == "producer"]
    assert len(paddy_recs) == 12
    assert all(r.product_raw == "Riz paddy" for r in paddy_recs)

    # Wholesale records
    wh_recs = [r for r in price_records if r.actor_level == "wholesale"]
    assert len(wh_recs) == 24

    # Retail records
    ret_recs = [r for r in price_records if r.actor_level == "retail"]
    assert len(ret_recs) == 24


@pytest.mark.parametrize(
    ("bulletin_num", "pdf_fixture_name", "golden_fixture_name"),
    [
        (520, "odr_pdf_bytes_520", "golden_520"),
        (710, "odr_pdf_bytes_710", "golden_710"),
        (850, "odr_pdf_bytes_850", "golden_850"),
    ],
)
def test_miasa_odr_golden_evaluation(
    bulletin_num: int,
    pdf_fixture_name: str,
    golden_fixture_name: str,
    request: pytest.FixtureRequest,
) -> None:
    """CC2: Golden dataset validation on 3 epochs (exactitude >= 99%, rappel >= 98%, >= 50 values)."""
    pdf_bytes: bytes = request.getfixturevalue(pdf_fixture_name)
    golden_data: dict[str, Any] = request.getfixturevalue(golden_fixture_name)

    connector = MiasaOdrConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = pdf_bytes
    ctx = RunContext(
        source_id="miasa_odr",
        bronze_store=mock_bronze,
        llm_client=ReplayClient(),
    )

    content_sha = golden_data["metadata"]["content_sha256"]
    artifact = RawArtifact(
        source_record_id=f"test-rec-{bulletin_num}",
        object_key=f"bronze/miasa_odr/{bulletin_num}.pdf",
        content_sha256=content_sha,
        mime_type="application/pdf",
        url=f"http://www.agriculture.gov.mg/odr/bulletin_{bulletin_num}.pdf",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)
    expected_records = golden_data["records"]

    # Criterion: >= 50 values per bulletin
    assert len(expected_records) >= 50
    assert len(result.records) == len(expected_records)

    parsed_map = {
        (r.product_raw, r.location_raw, r.actor_level): r
        for r in result.records
        if isinstance(r, PriceRecord)
    }

    correct_fields = 0
    total_fields = 0

    for expected in expected_records:
        key = (expected["product_raw"], expected["location_raw"], expected["actor_level"])
        parsed = parsed_map.get(key)
        assert parsed is not None, f"Expected record with key {key} was not parsed"

        # product_raw
        total_fields += 1
        if parsed.product_raw == expected["product_raw"]:
            correct_fields += 1

        # variety
        total_fields += 1
        if parsed.variety == expected["variety"]:
            correct_fields += 1

        # actor_level
        total_fields += 1
        if parsed.actor_level == expected["actor_level"]:
            correct_fields += 1

        # location_raw
        total_fields += 1
        if parsed.location_raw == expected["location_raw"]:
            correct_fields += 1

        # price_raw
        total_fields += 1
        if parsed.price_raw == expected["price_raw"]:
            correct_fields += 1

        # price_value
        total_fields += 1
        if parsed.price_value == expected["price_value"]:
            correct_fields += 1

        # unit_raw
        total_fields += 1
        if parsed.unit_raw == expected["unit_raw"]:
            correct_fields += 1

        # currency_raw
        total_fields += 1
        if parsed.currency_raw == expected["currency_raw"]:
            correct_fields += 1

        # missing_code
        total_fields += 1
        if parsed.missing_code == expected["missing_code"]:
            correct_fields += 1

        # period_start
        total_fields += 1
        if parsed.period_start.isoformat() == expected["period_start"]:
            correct_fields += 1

        # period_end
        total_fields += 1
        if parsed.period_end.isoformat() == expected["period_end"]:
            correct_fields += 1

    accuracy = correct_fields / total_fields
    recall = len(parsed_map) / len(expected_records)

    assert accuracy >= 0.99, f"Bulletin {bulletin_num}: accuracy {accuracy:.2%} is below 99%"
    assert recall >= 0.98, f"Bulletin {bulletin_num}: recall {recall:.2%} is below 98%"


def test_miasa_odr_missing_codes_never_zero(
    odr_pdf_bytes_850: bytes, golden_850: dict[str, Any]
) -> None:
    """T4.1 strict rule: 0 valeur ND ou NA convertie en 0."""
    connector = MiasaOdrConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = odr_pdf_bytes_850
    ctx = RunContext(
        source_id="miasa_odr",
        bronze_store=mock_bronze,
        llm_client=ReplayClient(),
    )

    artifact = RawArtifact(
        source_record_id="test-rec-850",
        object_key="bronze/miasa_odr/850.pdf",
        content_sha256=golden_850["metadata"]["content_sha256"],
        mime_type="application/pdf",
        url="http://www.agriculture.gov.mg/odr/bulletin_850.pdf",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)

    missing_records = [
        r for r in result.records if isinstance(r, PriceRecord) and r.missing_code is not None
    ]
    # At least 2 missing codes in bulletin 850
    assert len(missing_records) >= 2

    for rec in missing_records:
        assert rec.missing_code in ("ND", "NA")
        assert rec.price_value is None, f"Expected None for missing code, got {rec.price_value}"
        assert rec.price_value != 0, "ND/NA must NEVER be converted to 0"


def test_miasa_odr_dual_extraction_agreement(
    odr_pdf_bytes_850: bytes, golden_850: dict[str, Any]
) -> None:
    """SPECS §11.1: Verify dual_agree extraction method and 0.99 confidence when deterministic and LLM agree."""
    connector = MiasaOdrConnector()
    mock_bronze = MagicMock(spec=BronzeStore)
    mock_bronze.get.return_value = odr_pdf_bytes_850
    ctx = RunContext(
        source_id="miasa_odr",
        bronze_store=mock_bronze,
        llm_client=ReplayClient(),
    )

    artifact = RawArtifact(
        source_record_id="test-rec-850",
        object_key="bronze/miasa_odr/850.pdf",
        content_sha256=golden_850["metadata"]["content_sha256"],
        mime_type="application/pdf",
        url="http://www.agriculture.gov.mg/odr/bulletin_850.pdf",
        is_new=True,
    )

    result = connector.parse(artifact, ctx)

    # When both deterministic and LLM replay match, extraction_method is dual_agree with 0.99 confidence
    numeric_records = [
        r for r in result.records if isinstance(r, PriceRecord) and r.price_value is not None
    ]
    assert len(numeric_records) > 0
    assert all(r.extraction_method == "dual_agree" for r in numeric_records)
    assert all(r.confidence == 0.99 for r in numeric_records)
