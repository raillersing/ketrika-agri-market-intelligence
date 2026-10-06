"""Execution engine and silver loading with supersession for Ketrika connectors (SPECS §8.1, §9)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ketrika.connectors.base import (
    Connector,
    ParseResult,
    RawArtifact,
    RunContext,
)
from ketrika.connectors.records import (
    PriceRecord,
)
from ketrika.core.models.db import (
    IngestionRun,
    PriceObservation,
    Source,
    SourceRecord,
)


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
    nk = record.compute_natural_key(source_id)

    # 1. Check for active current row (superseded_by IS NULL)
    stmt = select(PriceObservation).where(
        PriceObservation.natural_key == nk,
        PriceObservation.superseded_by.is_(None),
    )
    current_obs = session.execute(stmt).scalar_one_or_none()

    price_val = record.price_value
    if price_val is None:
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
            extraction_method=record.extraction_method,
            evidence=record.evidence,
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
        extraction_method=record.extraction_method,
        evidence=record.evidence,
        confidence=record.confidence,
        review_status="accepted",
        superseded_by=None,
    )
    session.add(new_obs)
    session.flush()

    return "superseded", new_obs.observation_id


def execute_connector_pipeline(
    connector: Connector,
    ctx: RunContext,
    session: Session,
) -> dict[str, Any]:
    """Execute full Bronze -> Silver lifecycle for a connector."""
    source_id = connector.source_id
    ingestion_run = ensure_ingestion_run_started(session, source_id)

    stats: dict[str, int] = {
        "n_fetched": 0,
        "n_new_artifacts": 0,
        "n_inserted": 0,
        "n_superseded": 0,
        "n_skipped": 0,
    }

    try:
        # Phase 1: Bronze
        discovered = list(connector.discover(ctx))
        stats["n_fetched"] = len(discovered)

        artifacts: list[tuple[RawArtifact, uuid.UUID]] = []
        for item in discovered:
            raw_art = connector.fetch(item, ctx)
            db_record, is_new = record_bronze_artifact(
                session=session,
                source_id=source_id,
                artifact=raw_art,
                parser_version=connector.parser_version,
            )
            if is_new:
                stats["n_new_artifacts"] += 1
            artifacts.append((raw_art, db_record.source_record_id))

        # Phase 2: Silver
        for raw_art, s_rec_id in artifacts:
            # Reconstruct RawArtifact with actual DB source_record_id
            bound_artifact = RawArtifact(
                source_record_id=str(s_rec_id),
                object_key=raw_art.object_key,
                content_sha256=raw_art.content_sha256,
                mime_type=raw_art.mime_type,
                url=raw_art.url,
                is_new=raw_art.is_new,
                published_at=raw_art.published_at,
            )
            parse_res: ParseResult = connector.parse(bound_artifact, ctx)

            for rec in parse_res.records:
                if isinstance(rec, PriceRecord):
                    action, _ = load_price_record_with_supersession(
                        session=session,
                        record=rec,
                        source_id=source_id,
                        source_record_id=s_rec_id,
                    )
                    if action == "inserted":
                        stats["n_inserted"] += 1
                    elif action == "superseded":
                        stats["n_superseded"] += 1
                    else:
                        stats["n_skipped"] += 1

            # Mark source_record parsed
            mark_stmt = (
                update(SourceRecord)
                .where(SourceRecord.source_record_id == s_rec_id)
                .values(extraction_status="parsed")
            )
            session.execute(mark_stmt)

        ingestion_run.status = "success"
        ingestion_run.finished_at = datetime.now(UTC)
        ingestion_run.n_fetched = stats["n_fetched"]
        ingestion_run.n_new_artifacts = stats["n_new_artifacts"]
        ingestion_run.n_records = stats["n_inserted"] + stats["n_superseded"]
        session.flush()

        return stats

    except Exception as e:
        ingestion_run.status = "failed"
        ingestion_run.finished_at = datetime.now(UTC)
        ingestion_run.error = str(e)
        session.flush()
        raise
