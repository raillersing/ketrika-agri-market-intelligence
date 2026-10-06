"""Unit tests for SQLAlchemy ORM models and database helpers in ketrika.core."""

import uuid
from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

import pytest

from ketrika.core.db import (
    check_db_connection,
    get_engine,
    get_sessionmaker,
    transaction,
    verify_observation_provenance,
)
from ketrika.core.models.db import (
    Alert,
    ApiKey,
    Bulletin,
    CpiObservation,
    DqResult,
    Event,
    IngestionRun,
    LlmCall,
    Location,
    PriceObservation,
    Product,
    ProductAlias,
    ProductionObservation,
    ReviewItem,
    Source,
    SourceRecord,
    StockObservation,
    TradeFlow,
    UserAccount,
    WeatherObservation,
)
from ketrika.core.registry import sync_sources_to_db


def test_orm_models_instantiation():
    """Verify that all ORM models can be instantiated with valid attributes matching SPECS §8."""
    # 1. Source & IngestionRun & SourceRecord
    src = Source(source_id="test_src", spec={"name": "test"}, status="active")
    assert src.source_id == "test_src"

    run = IngestionRun(
        source_id="test_src",
        started_at=datetime.now(UTC),
        status="running",
    )
    assert run.source_id == "test_src"

    rec = SourceRecord(
        source_id="test_src",
        source_url="https://example.com/test",
        object_key="test_src/2026/01/abc.csv",
        content_sha256="abc",
        fetched_at=datetime.now(UTC),
    )
    assert rec.content_sha256 == "abc"

    # 2. LLM Call
    llm = LlmCall(
        provider="gemini",
        model="gemini-2.5-flash",
        purpose="extract",
        prompt_version="v1",
        cache_key="key123",
        status="ok",
    )
    assert llm.model == "gemini-2.5-flash"

    # 3. Product & Aliases
    prod = Product(
        product_code="RICE_WHITE_LOCAL",
        canonical_name_fr="Riz blanc local",
        category="cereal",
        base_unit="kg",
    )
    assert prod.product_code == "RICE_WHITE_LOCAL"

    alias = ProductAlias(
        alias_norm="vary gasy",
        alias_display="Vary gasy",
        lang="mg",
        product_id=uuid.uuid4(),
        confidence=0.9,
        origin="seed",
    )
    assert alias.lang == "mg"

    # 4. Location & Aliases
    loc = Location(
        admin_level=1,
        pcode="MDG11",
        name="Analamanga",
        boundary_version="cod-ab-2024",
    )
    assert loc.name == "Analamanga"

    # 5. Price Observation
    obs = PriceObservation(
        source_record_id=uuid.uuid4(),
        natural_key="nat_key_123",
        product_raw="Riz",
        actor_level="retail",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
        price_raw="2500",
        price_value=2500.0,
        unit_raw="kg",
        conversion_status="exact",
        observed_or_imputed="observed",
        extraction_method="deterministic",
        confidence=1.0,
    )
    assert obs.price_value == 2500.0

    # 6. Stock, Trade, Production, Weather, CPI, Event
    stock = StockObservation(
        source_record_id=uuid.uuid4(),
        natural_key="nat_stock",
        product_raw="Riz",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
        extraction_method="deterministic",
        confidence=1.0,
    )
    trade = TradeFlow(
        source_record_id=uuid.uuid4(),
        natural_key="nat_trade",
        flow="import",
        product_raw="Riz",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
        extraction_method="deterministic",
        confidence=1.0,
    )
    prod_obs = ProductionObservation(
        source_record_id=uuid.uuid4(),
        natural_key="nat_prod",
        product_raw="Riz",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
        element="production_t",
        observed_or_imputed="observed",
        extraction_method="deterministic",
        confidence=1.0,
    )
    weather = WeatherObservation(
        source_record_id=uuid.uuid4(),
        location_id=uuid.uuid4(),
        date=date(2025, 1, 1),
        variable="precip_mm",
        value=15.2,
        method="point_centroid",
        provider="nasa_power",
    )
    cpi = CpiObservation(
        source_record_id=uuid.uuid4(),
        natural_key="nat_cpi",
        series_code="food",
        series_label="Alimentation",
        geo_scope="national",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
        extraction_method="deterministic",
        confidence=1.0,
    )
    event = Event(
        source_record_id=uuid.uuid4(),
        event_type="market_disruption",
        title="Cyclone impact",
        extraction_method="deterministic",
        confidence=1.0,
    )
    assert stock.product_raw == "Riz"
    assert trade.flow == "import"
    assert prod_obs.element == "production_t"
    assert weather.variable == "precip_mm"
    assert cpi.series_code == "food"
    assert event.event_type == "market_disruption"

    # 7. ReviewItem, DqResult, Alert, Bulletin
    rev = ReviewItem(
        kind="unknown_product",
        payload={"raw": "unmapped"},
    )
    dq = DqResult(
        check_name="provenance_complete",
        passed=True,
    )
    alert = Alert(
        rule_code="PRICE_SPIKE",
        dedupe_key="spike_rice_2025_01",
        severity="high",
        title="Spike in rice price",
        evidence={"ratio": 1.25},
    )
    bulletin = Bulletin(
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 7),
        status="draft",
        facts={"summary": "prices stable"},
    )
    assert rev.kind == "unknown_product"
    assert dq.passed is True
    assert alert.severity == "high"
    assert bulletin.status == "draft"

    # 8. UserAccount, ApiKey
    user = UserAccount(
        email="test@example.com",
        password_hash="hash",
        role="client",
    )
    key = ApiKey(
        user_id=uuid.uuid4(),
        prefix="kt_",
        key_hash="argon2hash",
    )
    assert user.role == "client"
    assert key.prefix == "kt_"


def test_verify_observation_provenance():
    """Verify verify_observation_provenance correctly checks Bronze source_record existence."""
    mock_session = MagicMock()
    valid_id = uuid.uuid4()
    mock_session.execute.return_value.scalar_one_or_none.return_value = valid_id

    assert verify_observation_provenance(mock_session, valid_id) is True

    mock_session.execute.return_value.scalar_one_or_none.return_value = None
    assert verify_observation_provenance(mock_session, uuid.uuid4()) is False


def test_db_engine_and_sessionmaker():
    """Verify database engine and sessionmaker singleton creation."""
    engine = get_engine()
    assert engine is not None
    factory = get_sessionmaker()
    assert factory is not None


def test_sync_sources_to_db():
    """Verify sync_sources_to_db syncs all registry sources via session.execute."""
    mock_session = MagicMock()
    count = sync_sources_to_db(mock_session)
    # Should sync at least 10 sources
    assert count >= 10
    assert mock_session.execute.call_count == count


def test_transaction_context_manager():
    """Verify transaction context manager commits on success and rolls back on exception."""
    mock_session = MagicMock()
    with patch("ketrika.core.db.get_sessionmaker") as mock_factory:
        mock_factory.return_value = MagicMock(return_value=mock_session)

        # Success case
        with transaction() as s:
            assert s is mock_session
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

        # Exception case
        mock_session.reset_mock()
        with pytest.raises(ValueError, match="Boom"):
            with transaction() as s:
                raise ValueError("Boom")
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()


def test_check_db_connection():
    """Verify check_db_connection handles success and failure."""
    with patch("ketrika.core.db.get_engine") as mock_get_engine:
        # Success
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine
        assert check_db_connection() is True

        # Failure
        mock_engine.connect.side_effect = Exception("DB Down")
        assert check_db_connection() is False
