"""Execution engine and silver loading with supersession for Ketrika connectors (SPECS §8.1, §9)."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from ketrika.alerts.notifier import send_pipeline_failure_email
from ketrika.connectors.base import (
    Connector,
    RawArtifact,
    RunContext,
)
from ketrika.connectors.records import (
    CpiRecord,
    EventRecord,
    MacroRecord,
    PriceRecord,
    ProductionRecord,
    RecordBase,
    StockRecord,
    TradeFlowRecord,
    WeatherForecastRecord,
    WeatherRecord,
)
from ketrika.core.logging import bind_context, clear_context
from ketrika.core.models.db import (
    CpiObservation,
    Event,
    IngestionRun,
    Location,
    MacroObservation,
    PriceObservation,
    ProductionObservation,
    Source,
    SourceRecord,
    StockObservation,
    TradeFlow,
    WeatherForecast,
    WeatherObservation,
)
from ketrika.core.quarantine import require_eligible_observation, require_eligible_source
from ketrika.normalize.price_bridge import identity_evidence, resolve_price_identity


def ensure_ingestion_run_started(
    session: Session, source_id: str, dagster_run_id: str | None = None
) -> IngestionRun:
    """Ensure source exists and create a new meta.ingestion_run record in running state."""
    src_check = session.execute(
        select(Source.source_id).where(Source.source_id == source_id)
    ).scalar_one_or_none()
    if src_check is None:
        new_src = Source(source_id=source_id, spec={"name": source_id}, status="active")
        session.add(new_src)
        session.flush()

    run = IngestionRun(
        run_id=uuid.uuid4(),
        source_id=source_id,
        dagster_run_id=dagster_run_id,
        started_at=datetime.now(UTC),
        status="running",
        n_fetched=0,
        n_new_artifacts=0,
        n_records=0,
        n_rejected=0,
        n_review=0,
    )
    session.add(run)
    session.flush()
    return run


def record_bronze_artifact(
    session: Session,
    source_id: str,
    artifact: RawArtifact,
    parser_version: str,
    retrieved_via: str = "direct",
    http_status: int = 200,
) -> tuple[SourceRecord, bool]:
    """Upsert or retrieve meta.source_record for the given artifact SHA-256."""
    stmt = select(SourceRecord).where(
        SourceRecord.source_id == source_id,
        SourceRecord.content_sha256 == artifact.content_sha256,
    )
    existing = session.execute(stmt).scalar_one_or_none()
    if existing is not None:
        return existing, False

    source_record = SourceRecord(
        source_record_id=uuid.UUID(artifact.source_record_id)
        if artifact.source_record_id
        else uuid.uuid4(),
        source_id=source_id,
        source_url=artifact.url,
        retrieved_via=retrieved_via,
        object_key=artifact.object_key,
        content_sha256=artifact.content_sha256,
        mime_type=artifact.mime_type,
        http_status=http_status,
        fetched_at=datetime.now(UTC),
        published_at=artifact.published_at,
        parser_version=parser_version,
        extraction_status="pending",
    )
    session.add(source_record)
    session.flush()
    return source_record, True


def load_price_record_with_supersession(
    session: Session,
    record: PriceRecord,
    source_id: str,
    source_record_id: uuid.UUID,
) -> tuple[str, uuid.UUID]:
    """Load PriceRecord into obs.price_observation with SPECS §8.1 supersession logic.

    Returns: (action, observation_id) where action is 'inserted', 'idempotent_skipped', or 'superseded'.
    """
    require_eligible_source(session, source_record_id)
    resolution = resolve_price_identity(session, record, source_id, source_record_id)
    if resolution.review_id is not None:
        return "review_required", resolution.review_id
    nk = record.compute_natural_key(source_id)
    evidence = deepcopy(record.evidence)
    evidence["price_identity"] = identity_evidence(record, source_id)

    # 1. Check for active current row (superseded_by IS NULL)
    stmt = select(PriceObservation).where(
        PriceObservation.natural_key == resolution.lookup_key,
        PriceObservation.superseded_by.is_(None),
    )
    current_obs = session.execute(stmt).scalar_one_or_none()
    if current_obs is not None:
        require_eligible_observation(session, PriceObservation, current_obs.observation_id)

    price_val = record.price_value
    missing_code = record.missing_code
    price_raw_clean = str(record.price_raw).strip().upper()
    if missing_code or price_raw_clean in ("ND", "NA", "-", "N.D.", "N.A.", "", "NONE"):
        price_val = None
        if not missing_code:
            missing_code = price_raw_clean if price_raw_clean in ("ND", "NA") else "ND"
    elif price_val is None:
        try:
            clean_str = record.price_raw.replace(" ", "").replace(",", ".")
            price_val = float(clean_str)
        except ValueError:
            price_val = None

    if current_obs is None:
        # Case A: No current observation -> INSERT
        new_obs = PriceObservation(
            observation_id=uuid.uuid4(),
            source_record_id=source_record_id,
            natural_key=nk,
            product_raw=record.product_raw,
            variety=record.variety,
            location_raw=record.location_raw,
            actor_level=record.actor_level,
            period_start=record.period_start,
            period_end=record.period_end,
            published_at=record.published_at,
            price_raw=record.price_raw,
            price_value=price_val,
            unit_raw=record.unit_raw,
            currency_raw=record.currency_raw,
            conversion_status="exact",
            observed_or_imputed=record.observed_or_imputed,
            missing_code=missing_code,
            extraction_method=record.extraction_method,
            evidence=evidence,
            confidence=record.confidence,
            review_status="accepted",
            superseded_by=None,
        )
        session.add(new_obs)
        session.flush()
        return "inserted", new_obs.observation_id

    # Check if identical (Case B: Idempotence)
    current_val = float(current_obs.price_value) if current_obs.price_value is not None else None
    if (
        current_obs.price_raw == record.price_raw
        and current_val == price_val
        and current_obs.unit_raw == record.unit_raw
        and current_obs.observed_or_imputed == record.observed_or_imputed
        and current_obs.missing_code == missing_code
        and current_obs.variety == record.variety
    ):
        return "idempotent_skipped", current_obs.observation_id

    # Case C: Values differ -> Supersede
    # In single transaction: UPDATE old row SET superseded_by = new.observation_id, then INSERT new row
    new_obs_id = uuid.uuid4()
    update_stmt = (
        update(PriceObservation)
        .where(PriceObservation.observation_id == current_obs.observation_id)
        .values(superseded_by=new_obs_id)
    )
    session.execute(update_stmt)
    session.flush()

    new_obs = PriceObservation(
        observation_id=new_obs_id,
        source_record_id=source_record_id,
        natural_key=nk,
        product_raw=record.product_raw,
        variety=record.variety,
        location_raw=record.location_raw,
        actor_level=record.actor_level,
        period_start=record.period_start,
        period_end=record.period_end,
        published_at=record.published_at,
        price_raw=record.price_raw,
        price_value=price_val,
        unit_raw=record.unit_raw,
        currency_raw=record.currency_raw,
        conversion_status="exact",
        observed_or_imputed=record.observed_or_imputed,
        missing_code=missing_code,
        extraction_method=record.extraction_method,
        evidence=evidence,
        confidence=record.confidence,
        review_status="accepted",
        superseded_by=None,
    )
    session.add(new_obs)
    session.flush()

    return "superseded", new_obs.observation_id


def load_stock_record_with_supersession(
    session: Session,
    record: StockRecord,
    source_id: str,
    source_record_id: uuid.UUID,
) -> tuple[str, uuid.UUID]:
    """Load StockRecord into obs.stock_observation with supersession."""
    require_eligible_source(session, source_record_id)
    nk = record.compute_natural_key(source_id)
    stmt = select(StockObservation).where(
        StockObservation.natural_key == nk,
        StockObservation.superseded_by.is_(None),
    )
    current_obs = session.execute(stmt).scalar_one_or_none()
    if current_obs is not None:
        require_eligible_observation(session, StockObservation, current_obs.observation_id)

    q_val = record.quantity_value
    if q_val is None and record.quantity_raw:
        try:
            q_val = float(record.quantity_raw.replace(" ", "").replace(",", "."))
        except ValueError:
            q_val = None

    target_val = record.target or "stock_inventory"
    measurement_mode_val = record.measurement_mode or "declared_trader"

    if current_obs is None:
        new_obs = StockObservation(
            observation_id=uuid.uuid4(),
            source_record_id=source_record_id,
            natural_key=nk,
            product_raw=record.product_raw,
            location_raw=record.location_raw,
            period_start=record.period_start,
            period_end=record.period_end,
            published_at=record.published_at,
            quantity_raw=record.quantity_raw,
            quantity_value=q_val,
            unit_raw=record.unit_raw,
            stock_status=record.stock_status,
            coverage_days=record.coverage_days,
            target=target_val,
            measurement_mode=measurement_mode_val,
            market_type=record.market_type,
            market_code=record.market_code,
            extraction_method=record.extraction_method,
            evidence=record.evidence,
            confidence=record.confidence,
            review_status="accepted",
            superseded_by=None,
        )
        session.add(new_obs)
        session.flush()
        return "inserted", new_obs.observation_id

    current_val = (
        float(current_obs.quantity_value) if current_obs.quantity_value is not None else None
    )
    if (
        current_obs.quantity_raw == record.quantity_raw
        and current_val == q_val
        and current_obs.unit_raw == record.unit_raw
        and current_obs.stock_status == record.stock_status
        and getattr(current_obs, "target", None) == target_val
        and getattr(current_obs, "measurement_mode", None) == measurement_mode_val
        and getattr(current_obs, "market_code", None) == record.market_code
    ):
        return "idempotent_skipped", current_obs.observation_id

    new_id = uuid.uuid4()
    session.execute(
        update(StockObservation)
        .where(StockObservation.observation_id == current_obs.observation_id)
        .values(superseded_by=new_id)
    )
    session.flush()

    new_obs = StockObservation(
        observation_id=new_id,
        source_record_id=source_record_id,
        natural_key=nk,
        product_raw=record.product_raw,
        location_raw=record.location_raw,
        period_start=record.period_start,
        period_end=record.period_end,
        published_at=record.published_at,
        quantity_raw=record.quantity_raw,
        quantity_value=q_val,
        unit_raw=record.unit_raw,
        stock_status=record.stock_status,
        coverage_days=record.coverage_days,
        target=target_val,
        measurement_mode=measurement_mode_val,
        market_type=record.market_type,
        market_code=record.market_code,
        extraction_method=record.extraction_method,
        evidence=record.evidence,
        confidence=record.confidence,
        review_status="accepted",
        superseded_by=None,
    )
    session.add(new_obs)
    session.flush()
    return "superseded", new_id


def load_trade_flow_with_supersession(
    session: Session,
    record: TradeFlowRecord,
    source_id: str,
    source_record_id: uuid.UUID,
) -> tuple[str, uuid.UUID]:
    """Load TradeFlowRecord into obs.trade_flow with supersession."""
    require_eligible_source(session, source_record_id)
    nk = record.compute_natural_key(source_id)
    stmt = select(TradeFlow).where(
        TradeFlow.natural_key == nk,
        TradeFlow.superseded_by.is_(None),
    )
    current_obs = session.execute(stmt).scalar_one_or_none()
    if current_obs is not None:
        require_eligible_observation(session, TradeFlow, current_obs.observation_id)

    if current_obs is None:
        new_obs = TradeFlow(
            observation_id=uuid.uuid4(),
            source_record_id=source_record_id,
            natural_key=nk,
            flow=record.flow,
            hs_code=record.hs_code,
            product_raw=record.product_raw,
            partner_raw=record.partner_raw,
            partner_iso3=record.partner_iso3,
            period_start=record.period_start,
            period_end=record.period_end,
            published_at=record.published_at,
            value_raw=record.value_raw,
            value_mga=record.value_mga,
            value_usd=record.value_usd,
            weight_raw=record.weight_raw,
            weight_kg=record.weight_kg,
            extraction_method=record.extraction_method,
            evidence=record.evidence,
            confidence=record.confidence,
            review_status="accepted",
            superseded_by=None,
        )
        session.add(new_obs)
        session.flush()
        return "inserted", new_obs.observation_id

    curr_mga = float(current_obs.value_mga) if current_obs.value_mga is not None else None
    curr_kg = float(current_obs.weight_kg) if current_obs.weight_kg is not None else None
    if (
        current_obs.value_raw == record.value_raw
        and curr_mga == record.value_mga
        and curr_kg == record.weight_kg
    ):
        return "idempotent_skipped", current_obs.observation_id

    new_id = uuid.uuid4()
    session.execute(
        update(TradeFlow)
        .where(TradeFlow.observation_id == current_obs.observation_id)
        .values(superseded_by=new_id)
    )
    session.flush()

    new_obs = TradeFlow(
        observation_id=new_id,
        source_record_id=source_record_id,
        natural_key=nk,
        flow=record.flow,
        hs_code=record.hs_code,
        product_raw=record.product_raw,
        partner_raw=record.partner_raw,
        partner_iso3=record.partner_iso3,
        period_start=record.period_start,
        period_end=record.period_end,
        published_at=record.published_at,
        value_raw=record.value_raw,
        value_mga=record.value_mga,
        value_usd=record.value_usd,
        weight_raw=record.weight_raw,
        weight_kg=record.weight_kg,
        extraction_method=record.extraction_method,
        evidence=record.evidence,
        confidence=record.confidence,
        review_status="accepted",
        superseded_by=None,
    )
    session.add(new_obs)
    session.flush()
    return "superseded", new_id


def load_production_record_with_supersession(
    session: Session,
    record: ProductionRecord,
    source_id: str,
    source_record_id: uuid.UUID,
) -> tuple[str, uuid.UUID]:
    """Load ProductionRecord into obs.production_observation with supersession."""
    value = Decimal(str(record.value)) if record.value is not None else None
    if value is not None:
        if not value.is_finite() or abs(value) > Decimal("9999999999999999.9999"):
            raise ValueError("production_value_not_representable")
        if value.quantize(Decimal("0.0001")) != value:
            raise ValueError("production_precision_not_supported")
    require_eligible_source(session, source_record_id)
    nk = record.compute_natural_key(source_id)
    stmt = select(ProductionObservation).where(
        ProductionObservation.natural_key == nk,
        ProductionObservation.superseded_by.is_(None),
    )
    current_obs = session.execute(stmt).scalar_one_or_none()
    if current_obs is not None:
        require_eligible_observation(session, ProductionObservation, current_obs.observation_id)

    if current_obs is None:
        new_obs = ProductionObservation(
            observation_id=uuid.uuid4(),
            source_record_id=source_record_id,
            natural_key=nk,
            product_raw=record.product_raw,
            element=record.element,
            period_start=record.period_start,
            period_end=record.period_end,
            published_at=record.published_at,
            value=value,
            value_raw=record.value_raw,
            unit_raw=record.unit_raw,
            flag_raw=record.flag_raw,
            observed_or_imputed=record.observed_or_imputed,
            extraction_method=record.extraction_method,
            evidence=deepcopy(record.evidence),
            confidence=record.confidence,
            superseded_by=None,
        )
        session.add(new_obs)
        session.flush()
        return "inserted", new_obs.observation_id

    if (
        current_obs.unit_raw == record.unit_raw
        and current_obs.value == value
        and current_obs.flag_raw == record.flag_raw
        and current_obs.value_raw == record.value_raw
        and current_obs.source_record_id == source_record_id
        and current_obs.evidence == record.evidence
        and current_obs.extraction_method == record.extraction_method
        and current_obs.observed_or_imputed == record.observed_or_imputed
    ):
        return "idempotent_skipped", current_obs.observation_id

    new_id = uuid.uuid4()
    session.execute(
        update(ProductionObservation)
        .where(ProductionObservation.observation_id == current_obs.observation_id)
        .values(superseded_by=new_id)
    )
    session.flush()

    new_obs = ProductionObservation(
        observation_id=new_id,
        source_record_id=source_record_id,
        natural_key=nk,
        product_raw=record.product_raw,
        element=record.element,
        period_start=record.period_start,
        period_end=record.period_end,
        published_at=record.published_at,
        value=value,
        value_raw=record.value_raw,
        unit_raw=record.unit_raw,
        flag_raw=record.flag_raw,
        observed_or_imputed=record.observed_or_imputed,
        extraction_method=record.extraction_method,
        evidence=deepcopy(record.evidence),
        confidence=record.confidence,
        superseded_by=None,
    )
    session.add(new_obs)
    session.flush()
    return "superseded", new_id


def load_cpi_record_with_supersession(
    session: Session,
    record: CpiRecord,
    source_id: str,
    source_record_id: uuid.UUID,
) -> tuple[str, uuid.UUID]:
    """Load CpiRecord into obs.cpi_observation with supersession."""
    require_eligible_source(session, source_record_id)
    nk = record.compute_natural_key(source_id)
    stmt = select(CpiObservation).where(
        CpiObservation.natural_key == nk,
        CpiObservation.superseded_by.is_(None),
    )
    current_obs = session.execute(stmt).scalar_one_or_none()
    if current_obs is not None:
        require_eligible_observation(session, CpiObservation, current_obs.observation_id)

    if current_obs is None:
        new_obs = CpiObservation(
            observation_id=uuid.uuid4(),
            source_record_id=source_record_id,
            natural_key=nk,
            series_code=record.series_code,
            series_label=record.series_label,
            geo_scope=record.geo_scope,
            period_start=record.period_start,
            period_end=record.period_end,
            index_value=record.index_value,
            base_period=record.base_period,
            published_at=record.published_at,
            extraction_method=record.extraction_method,
            evidence=record.evidence,
            confidence=record.confidence,
            superseded_by=None,
        )
        session.add(new_obs)
        session.flush()
        return "inserted", new_obs.observation_id

    curr_val = float(current_obs.index_value) if current_obs.index_value is not None else None
    if curr_val == record.index_value:
        return "idempotent_skipped", current_obs.observation_id

    new_id = uuid.uuid4()
    session.execute(
        update(CpiObservation)
        .where(CpiObservation.observation_id == current_obs.observation_id)
        .values(superseded_by=new_id)
    )
    session.flush()

    new_obs = CpiObservation(
        observation_id=new_id,
        source_record_id=source_record_id,
        natural_key=nk,
        series_code=record.series_code,
        series_label=record.series_label,
        geo_scope=record.geo_scope,
        period_start=record.period_start,
        period_end=record.period_end,
        index_value=record.index_value,
        base_period=record.base_period,
        published_at=record.published_at,
        extraction_method=record.extraction_method,
        evidence=record.evidence,
        confidence=record.confidence,
        superseded_by=None,
    )
    session.add(new_obs)
    session.flush()
    return "superseded", new_id


def load_weather_record_with_supersession(
    session: Session,
    record: WeatherRecord,
    source_id: str,
    source_record_id: uuid.UUID,
) -> tuple[str, uuid.UUID]:
    """Preserve weather revisions and supplied proof; never fabricate raw values."""
    require_eligible_source(session, source_record_id)
    if record.raster_source_record_id is not None:
        require_eligible_source(session, record.raster_source_record_id)
    loc_stmt = select(Location).where(
        or_(
            Location.pcode == record.location_raw,
            Location.name == record.location_raw,
        )
    )
    location = session.execute(loc_stmt).scalars().first()
    if location is None:
        try:
            loc_uuid = uuid.UUID(record.location_raw)
            location = session.get(Location, loc_uuid)
        except ValueError:
            pass

    if location is None:
        raise ValueError(
            f"Could not resolve location_id for weather record location_raw='{record.location_raw}'"
        )

    stmt = select(WeatherObservation).where(
        WeatherObservation.provider == record.provider,
        WeatherObservation.location_id == location.location_id,
        WeatherObservation.date == record.date,
        WeatherObservation.variable == record.variable,
        WeatherObservation.superseded_by.is_(None),
    )
    current_obs = session.execute(stmt).scalar_one_or_none()
    if current_obs is not None:
        require_eligible_observation(session, WeatherObservation, current_obs.observation_id)
    # Refuse silent NUMERIC(10,3) rounding; raw evidence stays source supplied.
    source_value = Decimal(str(record.value))
    if not source_value.is_finite() or abs(source_value) > Decimal("9999999.999"):
        raise ValueError("weather_value_not_representable")
    stored_value = source_value.quantize(Decimal("0.001"))
    if stored_value != source_value:
        raise ValueError("weather_precision_not_supported")
    if current_obs is not None and (
        current_obs.value == stored_value
        and current_obs.method == record.method
        and current_obs.source_record_id == source_record_id
        and current_obs.location_raw == record.location_raw
        and current_obs.value_raw == record.value_raw
        and current_obs.stage == getattr(record, "stage", "final")
        and current_obs.spatial_resolution == getattr(record, "spatial_resolution", None)
        and current_obs.coverage_ratio == getattr(record, "coverage_ratio", None)
        and current_obs.raster_source_record_id == getattr(record, "raster_source_record_id", None)
        and current_obs.extraction_method == record.extraction_method
        and current_obs.evidence == record.evidence
    ):
        return "idempotent_skipped", current_obs.observation_id
    new_id = uuid.uuid4()
    if current_obs is not None:
        session.execute(
            update(WeatherObservation)
            .where(WeatherObservation.observation_id == current_obs.observation_id)
            .values(superseded_by=new_id)
        )
        session.flush()
    new_obs = WeatherObservation(
        observation_id=new_id,
        source_record_id=source_record_id,
        location_id=location.location_id,
        location_raw=record.location_raw,
        date=record.date,
        variable=record.variable,
        value=stored_value,
        value_raw=record.value_raw,
        method=record.method,
        provider=record.provider,
        stage=getattr(record, "stage", "final"),
        spatial_resolution=getattr(record, "spatial_resolution", None),
        coverage_ratio=getattr(record, "coverage_ratio", None),
        raster_source_record_id=getattr(record, "raster_source_record_id", None),
        evidence=deepcopy(record.evidence),
        extraction_method=record.extraction_method,
    )
    session.add(new_obs)
    session.flush()
    return "superseded" if current_obs is not None else "inserted", new_id


def load_macro_record_with_supersession(
    session: Session,
    record: MacroRecord,
    source_id: str,
    source_record_id: uuid.UUID,
) -> tuple[str, uuid.UUID]:
    """Load MacroRecord into obs.macro_observation with supersession (ADR-069)."""
    require_eligible_source(session, source_record_id)
    nk = record.compute_natural_key(source_id)
    stmt = select(MacroObservation).where(
        MacroObservation.natural_key == nk,
        MacroObservation.superseded_by.is_(None),
    )
    current_obs = session.execute(stmt).scalar_one_or_none()
    if current_obs is not None:
        require_eligible_observation(session, MacroObservation, current_obs.observation_id)

    # C2 : first_available_at cannot be None, fallback conservative to fetched_at or now
    first_avail = record.first_available_at
    if first_avail is None:
        sr = session.get(SourceRecord, source_record_id)
        first_avail = sr.fetched_at if sr is not None else datetime.now(UTC)

    v_val = record.value
    if v_val is None and record.value_raw:
        try:
            v_val = float(record.value_raw.replace(" ", "").replace(",", "."))
        except ValueError:
            v_val = None

    if current_obs is None:
        new_obs = MacroObservation(
            observation_id=uuid.uuid4(),
            source_record_id=source_record_id,
            natural_key=nk,
            indicator_code=record.indicator_code,
            indicator_name=record.indicator_name,
            frequency=record.frequency,
            unit=record.unit,
            base_period=record.base_period,
            geo_scope=record.geo_scope,
            period_start=record.period_start,
            period_end=record.period_end,
            published_at=record.published_at,
            first_available_at=first_avail,
            vintage=record.vintage,
            value=v_val,
            value_raw=record.value_raw,
            observed_or_imputed=record.observed_or_imputed,
            extraction_method=record.extraction_method,
            evidence=record.evidence,
            confidence=record.confidence,
            review_status="accepted",
            superseded_by=None,
        )
        session.add(new_obs)
        session.flush()
        return "inserted", new_obs.observation_id

    curr_val = float(current_obs.value) if current_obs.value is not None else None
    if curr_val == v_val and current_obs.vintage == record.vintage:
        return "idempotent_skipped", current_obs.observation_id

    new_id = uuid.uuid4()
    session.execute(
        update(MacroObservation)
        .where(MacroObservation.observation_id == current_obs.observation_id)
        .values(superseded_by=new_id)
    )
    session.flush()

    new_obs = MacroObservation(
        observation_id=new_id,
        source_record_id=source_record_id,
        natural_key=nk,
        indicator_code=record.indicator_code,
        indicator_name=record.indicator_name,
        frequency=record.frequency,
        unit=record.unit,
        base_period=record.base_period,
        geo_scope=record.geo_scope,
        period_start=record.period_start,
        period_end=record.period_end,
        published_at=record.published_at,
        first_available_at=first_avail,
        vintage=record.vintage,
        value=v_val,
        value_raw=record.value_raw,
        observed_or_imputed=record.observed_or_imputed,
        extraction_method=record.extraction_method,
        evidence=record.evidence,
        confidence=record.confidence,
        review_status="accepted",
        superseded_by=None,
    )
    session.add(new_obs)
    session.flush()
    return "superseded", new_id


def load_event_record_with_supersession(
    session: Session,
    record: EventRecord,
    source_id: str,
    source_record_id: uuid.UUID,
) -> tuple[str, uuid.UUID]:
    """Load EventRecord into obs.event."""
    require_eligible_source(session, source_record_id)
    product_ids: list[uuid.UUID] = []
    location_ids: list[uuid.UUID] = []

    if record.location_raw:
        from ketrika.core.models.db import LocationAlias

        loc_alias = session.execute(
            select(LocationAlias.location_id).where(
                LocationAlias.alias_norm == record.location_raw.strip().lower()
            )
        ).scalar_one_or_none()
        if loc_alias is not None:
            location_ids.append(loc_alias)

    if record.product_raw:
        from ketrika.core.models.db import ProductAlias

        prod_alias = session.execute(
            select(ProductAlias.product_id).where(
                ProductAlias.alias_norm == record.product_raw.strip().lower()
            )
        ).scalar_one_or_none()
        if prod_alias is not None:
            product_ids.append(prod_alias)

    stmt = select(Event).where(
        Event.source_record_id == source_record_id,
        Event.title == record.title,
        Event.event_type == record.event_type,
    )
    existing_event = session.execute(stmt).scalar_one_or_none()
    if existing_event is not None:
        return "idempotent_skipped", existing_event.event_id

    ev_data = deepcopy(record.evidence) if record.evidence else {}
    ev_data["is_projected"] = record.is_projected
    if record.location_raw:
        ev_data["location_raw"] = record.location_raw
    if record.product_raw:
        ev_data["product_raw"] = record.product_raw
    if record.period_start:
        ev_data["period_start"] = record.period_start.isoformat()
    if record.period_end:
        ev_data["period_end"] = record.period_end.isoformat()

    new_id = uuid.uuid4()
    new_event = Event(
        event_id=new_id,
        source_record_id=source_record_id,
        event_type=record.event_type,
        title=record.title,
        summary=record.summary,
        product_ids=product_ids,
        location_ids=location_ids,
        event_date=record.event_date,
        severity=record.severity,
        extraction_method=record.extraction_method,
        evidence=ev_data,
        confidence=record.confidence,
    )
    session.add(new_event)
    session.flush()
    return "inserted", new_id


def load_weather_forecast_record_with_supersession(
    session: Session,
    record: WeatherForecastRecord,
    source_id: str,
    source_record_id: uuid.UUID,
) -> tuple[str, uuid.UUID]:
    require_eligible_source(session, source_record_id)
    loc_stmt = select(Location).where(
        or_(
            Location.pcode == record.location_raw,
            Location.name == record.location_raw,
        )
    )
    location = session.execute(loc_stmt).scalars().first()
    if location is None:
        try:
            loc_uuid = uuid.UUID(record.location_raw)
            location = session.get(Location, loc_uuid)
        except ValueError:
            pass

    loc_id: uuid.UUID = location.location_id if location is not None else uuid.uuid4()

    stmt = select(WeatherForecast).where(
        WeatherForecast.location_id == loc_id,
        WeatherForecast.issued_at == record.issued_at,
        WeatherForecast.horizon_hours == record.horizon_hours,
        WeatherForecast.variable == record.variable,
        WeatherForecast.model_name == record.model_name,
        WeatherForecast.superseded_by.is_(None),
    )
    current_fc = session.execute(stmt).scalar_one_or_none()

    if (
        current_fc is not None
        and current_fc.predicted_value == record.predicted_value
        and current_fc.predicted_p10 == record.predicted_p10
        and current_fc.predicted_p90 == record.predicted_p90
        and current_fc.source_record_id == source_record_id
    ):
        return "idempotent_skipped", current_fc.forecast_id

    new_id = uuid.uuid4()
    if current_fc is not None:
        session.execute(
            update(WeatherForecast)
            .where(WeatherForecast.forecast_id == current_fc.forecast_id)
            .values(superseded_by=new_id)
        )
        session.flush()

    new_fc = WeatherForecast(
        forecast_id=new_id,
        source_record_id=source_record_id,
        location_id=loc_id,
        issued_at=record.issued_at,
        valid_from=record.valid_from,
        valid_to=record.valid_to,
        horizon_hours=record.horizon_hours,
        variable=record.variable,
        model_name=record.model_name,
        predicted_value=record.predicted_value,
        predicted_p10=record.predicted_p10,
        predicted_p90=record.predicted_p90,
        method=record.method,
        spatial_resolution=record.spatial_resolution,
        unit=record.unit,
        evidence=deepcopy(record.evidence) if record.evidence else None,
        superseded_by=None,
    )
    session.add(new_fc)
    session.flush()
    return "superseded" if current_fc is not None else "inserted", new_id


def load_record_with_supersession(
    session: Session,
    record: RecordBase,
    source_id: str,
    source_record_id: uuid.UUID,
) -> tuple[str, uuid.UUID]:
    """Unified loader dispatching typed record to its corresponding table with supersession."""
    if isinstance(record, PriceRecord):
        return load_price_record_with_supersession(session, record, source_id, source_record_id)
    elif isinstance(record, StockRecord):
        return load_stock_record_with_supersession(session, record, source_id, source_record_id)
    elif isinstance(record, TradeFlowRecord):
        return load_trade_flow_with_supersession(session, record, source_id, source_record_id)
    elif isinstance(record, ProductionRecord):
        return load_production_record_with_supersession(
            session, record, source_id, source_record_id
        )
    elif isinstance(record, CpiRecord):
        return load_cpi_record_with_supersession(session, record, source_id, source_record_id)
    elif isinstance(record, WeatherRecord):
        return load_weather_record_with_supersession(session, record, source_id, source_record_id)
    elif isinstance(record, MacroRecord):
        return load_macro_record_with_supersession(session, record, source_id, source_record_id)
    elif isinstance(record, EventRecord):
        return load_event_record_with_supersession(session, record, source_id, source_record_id)
    elif isinstance(record, WeatherForecastRecord):
        return load_weather_forecast_record_with_supersession(
            session, record, source_id, source_record_id
        )
    else:
        raise ValueError(f"Unsupported record type: {type(record)}")


def execute_connector_pipeline(
    connector: Connector,
    ctx: RunContext,
    session: Session,
) -> dict[str, Any]:
    """Compose exact Bronze collection and offline Silver consumption."""
    from ketrika.connectors.stages import collect_connector_bronze, consume_connector_silver

    bind_context(source_id=connector.source_id)
    batch = None
    try:
        batch = collect_connector_bronze(connector, ctx, session)
        bind_context(run_id=str(batch.ingestion_run_id))
        return consume_connector_silver(connector, ctx, session, batch)
    except Exception as exc:
        failed_run_id = batch.ingestion_run_id if batch is not None else ctx.run_id
        if failed_run_id is not None and session.is_active:
            run = session.get(IngestionRun, failed_run_id)
            if run is not None and run.source_id == connector.source_id:
                from ketrika.core.diagnostics import sanitize_diagnostic_error

                _st, diag_code, _msg, _cat = sanitize_diagnostic_error(type(exc).__name__)
                run.status = "failed"
                run.finished_at = datetime.now(UTC)
                run.error = diag_code
                session.flush()
        send_pipeline_failure_email(
            job_name=f"connector_{connector.source_id}",
            run_id=str(failed_run_id) if failed_run_id is not None else "bronze_collection",
            error_message=type(exc).__name__,
        )
        raise
    finally:
        clear_context()
