"""Every direct observation loader refuses quarantined rows before any revision.

All records are explicitly synthetic SQL regressions, never source qualification.
"""

import hashlib
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text

from ketrika.connectors import records, runner
from ketrika.core.db import get_session
from ketrika.core.models import db
from ketrika.core.qualification import require_synthetic_test_database
from tests.integration.test_quarantine_integration import _ensure_test_source_and_record

KINDS = ("price", "stock", "trade", "production", "cpi", "weather", "macro")


def case(session, kind):
    name = "synthetic_quarantine_" + uuid4().hex
    period = {
        "period_start": date(2026, 10, 1),
        "period_end": date(2026, 10, 1),
        "evidence": {"synthetic": True, "scope": "SQL guard regression only"},
    }
    if kind == "price":
        record = records.PriceRecord(
            **period,
            product_raw=name,
            location_raw=name,
            price_raw="1.25",
            price_value=1.25,
            unit_raw="kg",
        )
        return (
            record,
            runner.load_price_record_with_supersession,
            db.PriceObservation,
            {"price_raw": "2.5", "price_value": 2.5},
        )
    if kind == "stock":
        record = records.StockRecord(
            **period, product_raw=name, quantity_raw="1.25", quantity_value=1.25, unit_raw="kg"
        )
        return (
            record,
            runner.load_stock_record_with_supersession,
            db.StockObservation,
            {"quantity_raw": "2.5", "quantity_value": 2.5},
        )
    if kind == "trade":
        record = records.TradeFlowRecord(
            **period, flow="import", product_raw=name, weight_raw="1.25", weight_kg=1.25
        )
        return (
            record,
            runner.load_trade_flow_with_supersession,
            db.TradeFlow,
            {"weight_raw": "2.5", "weight_kg": 2.5},
        )
    if kind == "production":
        record = records.ProductionRecord(
            **period,
            product_raw=name,
            element="production_t",
            value_raw="1.25",
            value=1.25,
            unit_raw="t",
        )
        return (
            record,
            runner.load_production_record_with_supersession,
            db.ProductionObservation,
            {"value_raw": "2.5", "value": 2.5},
        )
    if kind == "cpi":
        record = records.CpiRecord(
            **period, series_code=name, series_label=name, index_value_raw="1.25", index_value=1.25
        )
        return (
            record,
            runner.load_cpi_record_with_supersession,
            db.CpiObservation,
            {"index_value_raw": "2.5", "index_value": 2.5},
        )
    if kind == "weather":
        location = db.Location(
            location_id=uuid4(),
            name=name,
            admin_level=2,
            boundary_version="synthetic-guard-fixture",
        )
        session.add(location)
        session.flush()
        record = records.WeatherRecord(
            **period,
            location_raw=name,
            date=date(2026, 10, 1),
            variable="precip_mm",
            provider="synthetic",
            value_raw="1.250",
            value=1.25,
        )
        return (
            record,
            runner.load_weather_record_with_supersession,
            db.WeatherObservation,
            {"value_raw": "2.500", "value": 2.5},
        )
    record = records.MacroRecord(
        **period,
        indicator_code=name,
        indicator_name=name,
        unit="index",
        value_raw="1.25",
        value=1.25,
        first_available_at=datetime(2026, 10, 2, tzinfo=UTC),
    )
    return (
        record,
        runner.load_macro_record_with_supersession,
        db.MacroObservation,
        {"value_raw": "2.5", "value": 2.5},
    )


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("actor_role", ("owner", "application"))
@pytest.mark.parametrize("scenario", ("observation_equal", "observation_revised", "source"))
def test_direct_loader_never_reuses_or_revises_quarantined_history(kind, scenario, actor_role):
    with get_session() as session:
        require_synthetic_test_database(session.bind.url.host, session.bind.url.database)
        source_id, reference = _ensure_test_source_and_record(session)
        reference = UUID(reference)
        record, loader, model, changed = case(session, kind)
        if actor_role == "application":
            session.execute(text("SET LOCAL ROLE ketrika_app"))
            assert session.scalar(text("SELECT current_user")) == "ketrika_app"
        action, identifier = loader(session, record, source_id, reference)
        assert action == "inserted"
        table = model.__table__.fullname
        snapshot = text(f"SELECT to_jsonb(t)::text FROM {table} t WHERE observation_id=:id")
        before = session.scalar(snapshot, {"id": identifier})
        incoming = reference
        if scenario == "source":
            incoming = uuid4()
            digest = hashlib.sha256(incoming.bytes).hexdigest()
            session.add(
                db.SourceRecord(
                    source_record_id=incoming,
                    source_id=source_id,
                    source_url="https://example.invalid/synthetic-only",
                    retrieved_via="direct",
                    object_key="synthetic/" + digest,
                    content_sha256=digest,
                    mime_type="application/json",
                    parser_version="synthetic-test",
                    fetched_at=datetime.now(UTC),
                )
            )
            session.flush()
        session.add(
            db.QuarantineLedger(
                quarantine_id=uuid4(),
                table_name="meta.source_record" if scenario == "source" else table,
                observation_id=incoming if scenario == "source" else identifier,
                source_record_id=incoming,
                reason_code="TEST_FIXTURE_ISOLATION",
                details={"synthetic": True, "scope": "SQL guard regression only"},
                operator="pytest",
            )
        )
        session.flush()
        candidate = record.model_copy(update=changed) if scenario != "observation_equal" else record
        reason = "source_quarantined" if scenario == "source" else "quarantined_identity_reserved"
        with pytest.raises(ValueError, match=reason):
            loader(session, candidate, source_id, incoming)
        assert session.scalar(snapshot, {"id": identifier}) == before
        assert (
            len(
                list(
                    session.scalars(
                        select(model).where(model.source_record_id.in_({reference, incoming}))
                    )
                )
            )
            == 1
        )
        session.rollback()
