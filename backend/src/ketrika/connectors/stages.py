"""Exact Bronze receipts consumed by Silver without source discovery or fetch."""

from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from ketrika.connectors.base import Connector, RawArtifact, RunContext
from ketrika.connectors.durable_runs import DurableRunReference, bind_running_run
from ketrika.core.artifact_identity import ArtifactProcessingIdentity
from ketrika.core.bronze import BronzeArtifact, BronzeStore
from ketrika.core.http import FetchResult, PoliteHttpClient
from ketrika.core.models.db import IngestionRun, ReviewItem, SourceRecord
from ketrika.core.policy import OfflineError, PolicyStop
from ketrika.core.provenance import ArtifactReference, _validate_reference
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.qualification import QualificationSafetyError, validate_environment
from ketrika.core.registry import get_source


@dataclass(frozen=True)
class BronzeBatch:
    source_id: str
    ingestion_run_id: uuid.UUID
    parser_version: str
    artifacts: tuple[RawArtifact, ...]


class _OfflineHttpClient(PoliteHttpClient):
    def get(self, url: str, *args: Any, **kwargs: Any) -> FetchResult:
        raise OfflineError(url)

    def _execute_request(self, method: str, url: str, *args: Any, **kwargs: Any) -> Any:
        raise OfflineError(url)

    def fetch_robots_txt(self, domain: str) -> None:
        raise OfflineError(domain)


class _VerifiedBronzeStore(BronzeStore):
    """Only the already-verified current object's bytes are available to parse."""

    def __init__(self, object_key: str, content: bytes) -> None:
        self._object_key, self._content = object_key, content

    def get(self, object_key: str) -> bytes:
        if object_key != self._object_key:
            raise ValueError("silver_object_outside_batch")
        return self._content

    def put(self, *args: Any, **kwargs: Any) -> BronzeArtifact:
        raise ValueError("silver_bronze_write_forbidden")


def authorize_collection(connector: Connector, ctx: RunContext) -> None:
    """The existing registry/fixture policy, before starting a durable run."""
    if ctx.source_id != connector.source_id:
        raise ValueError("connector_context_source_mismatch")
    try:
        definition = get_source(connector.source_id)
    except KeyError:
        from ketrika.connectors.registry import get_connector_class

        registered = get_connector_class(connector.source_id)
        if (
            not connector.source_id.startswith(("dummy_", "fixture_"))
            or registered is None
            or not isinstance(connector, registered)
        ):
            raise PolicyStop("source_not_registered") from None
        try:
            validate_environment(os.environ)
        except QualificationSafetyError:
            raise PolicyStop("fixture_collection_outside_qa") from None
        definition = None
    if definition is not None and (
        definition.status == "disabled" or definition.crawl_permission == "forbidden"
    ):
        raise PolicyStop("source_collection_disabled")
    if ctx.http_client is None:
        ctx.http_client = PoliteHttpClient(policy_engine=ctx.policy_engine)
    if isinstance(ctx.http_client, PoliteHttpClient):
        ctx.http_client.bind_source(
            connector.source_id,
            definition.daily_request_budget if definition is not None else 500,
            definition.max_rps if definition is not None else 0.2,
        )


def collect_connector_bronze(
    connector: Connector,
    ctx: RunContext,
    session: Session,
    *,
    durable_run: DurableRunReference | None = None,
) -> BronzeBatch:
    """Persist exact references; optional owner never comes from collected data."""
    from ketrika.connectors.runner import ensure_ingestion_run_started, record_bronze_artifact

    ctx.run_id = None
    authorize_collection(connector, ctx)
    if durable_run is None:
        run = ensure_ingestion_run_started(
            session, connector.source_id, ctx.metadata.get("dagster_run_id")
        )
    else:
        if (
            not isinstance(durable_run, DurableRunReference)
            or durable_run.source_id != connector.source_id
        ):
            raise ValueError("durable_run_reference_mismatch")
        run = bind_running_run(session, durable_run)
    ctx.run_id = run.run_id
    artifacts: list[RawArtifact] = []
    for item in connector.discover(ctx):
        raw = connector.fetch(item, ctx)
        reference, is_new = record_bronze_artifact(
            session, connector.source_id, raw, connector.parser_version
        )
        session.refresh(reference)
        if (reference.object_key, reference.content_sha256, reference.mime_type) != (
            raw.object_key,
            raw.content_sha256,
            raw.mime_type,
        ):
            raise ValueError("bronze_reference_mismatch")
        artifacts.append(
            replace(
                raw,
                source_record_id=str(reference.source_record_id),
                is_new=is_new,
                url=reference.source_url,
                published_at=reference.published_at,
            )
        )
        run.n_fetched += 1
        run.n_new_artifacts += int(is_new)
    session.flush()
    return BronzeBatch(connector.source_id, run.run_id, connector.parser_version, tuple(artifacts))


def consume_connector_silver(
    connector: Connector,
    ctx: RunContext,
    session: Session,
    batch: BronzeBatch,
    *,
    processing_identities: list[ArtifactProcessingIdentity] | None = None,
) -> dict[str, Any]:
    """Parse only verified Bronze bytes; does not discover/fetch/commit."""
    from ketrika.connectors.records import PriceRecord
    from ketrika.connectors.runner import load_record_with_supersession
    from ketrika.normalize.price_loader import load_normalized_price
    from ketrika.normalize.reference_snapshot import prepare_reference_snapshot

    if (
        not isinstance(batch, BronzeBatch)
        or batch.source_id != connector.source_id
        or ctx.source_id != batch.source_id
    ):
        raise ValueError("silver_batch_source_mismatch")
    native_rtfp = batch.source_id == "wb_rtfp_mdg" and batch.parser_version == "2.0.0"
    if batch.parser_version != connector.parser_version and not native_rtfp:
        raise ValueError("silver_batch_parser_mismatch")
    run = session.get(IngestionRun, batch.ingestion_run_id)
    if run is None or run.source_id != batch.source_id:
        raise ValueError("silver_batch_run_mismatch")
    if ctx.bronze_store is None:
        raise ValueError("silver_bronze_store_required")
    if len({artifact.source_record_id for artifact in batch.artifacts}) != len(batch.artifacts):
        raise ValueError("silver_batch_duplicate_reference")
    stats = {
        "n_fetched": run.n_fetched,
        "n_new_artifacts": run.n_new_artifacts,
        "n_inserted": 0,
        "n_superseded": 0,
        "n_skipped": 0,
        "n_rejected": 0,
    }
    reader = BronzeProofReader(ctx.bronze_store)
    reference_snapshot = None
    with _OfflineHttpClient() as offline_http:
        for artifact in batch.artifacts:
            try:
                reference_id = uuid.UUID(artifact.source_record_id)
            except (ValueError, TypeError, AttributeError):
                raise ValueError("silver_reference_id_invalid") from None
            reference = session.get(SourceRecord, reference_id)
            if reference is None or (
                reference.source_id,
                reference.object_key,
                reference.content_sha256,
                reference.mime_type,
                reference.source_url,
                reference.published_at,
            ) != (
                batch.source_id,
                artifact.object_key,
                artifact.content_sha256,
                artifact.mime_type,
                artifact.url,
                artifact.published_at,
            ):
                raise ValueError("silver_reference_mismatch")
            digest = _validate_reference(
                ArtifactReference(
                    reference_id,
                    batch.source_id,
                    artifact.object_key,
                    artifact.content_sha256,
                    artifact.mime_type,
                )
            )
            content = reader.get(artifact.object_key)
            if hashlib.sha256(content).hexdigest() != digest:
                raise ValueError("silver_object_sha256_mismatch")
            parse_context = replace(
                ctx,
                offline=True,
                http_client=offline_http,
                bronze_store=_VerifiedBronzeStore(artifact.object_key, content),
                run_id=batch.ingestion_run_id,
                metadata=dict(ctx.metadata),
            )
            if native_rtfp:
                from ketrika.connectors.rtfp_json import parse_persisted

                result = parse_persisted(session, artifact, reader)
            else:
                result = connector.parse(artifact, parse_context)
            if result.parser_version != batch.parser_version:
                raise ValueError("silver_parse_version_mismatch")
            used_price_normalizer = False
            for record in result.records:
                if isinstance(record, PriceRecord):
                    used_price_normalizer = True
                    if reference_snapshot is None:
                        reference_snapshot = prepare_reference_snapshot(session, ctx.bronze_store)
                    loaded = load_normalized_price(
                        session,
                        record,
                        batch.source_id,
                        reference_id,
                        reference_snapshot=reference_snapshot,
                    )
                    action = loaded.action
                    stats["n_review"] = stats.get("n_review", 0) + loaded.review_items
                else:
                    action, _ = load_record_with_supersession(
                        session, record, batch.source_id, reference_id
                    )
                if action == "inserted":
                    stats["n_inserted"] += 1
                elif action == "superseded":
                    stats["n_superseded"] += 1
                elif action == "idempotent_skipped":
                    stats["n_skipped"] += 1
                elif action == "review_required":
                    stats["n_rejected"] += 1
                else:
                    raise ValueError("silver_loader_action_invalid")
            if used_price_normalizer and processing_identities is not None:
                if reference_snapshot is None:
                    raise ValueError("silver_reference_snapshot_missing")
                processing_identities.append(
                    ArtifactProcessingIdentity(
                        batch.source_id,
                        reference_id,
                        artifact.content_sha256,
                        batch.parser_version,
                        "price_normalizer_v2",
                        reference_snapshot.manifest.sha256,
                    )
                )
            for issue in result.issues:
                session.add(
                    ReviewItem(
                        review_id=uuid.uuid4(),
                        kind=issue.get("kind", "extraction_conflict"),
                        source_record_id=reference_id,
                        payload=issue.get("payload", issue),
                        status="open",
                    )
                )
                stats["n_review"] = stats.get("n_review", 0) + 1
            session.execute(
                update(SourceRecord)
                .where(SourceRecord.source_record_id == reference_id)
                .values(extraction_status="parsed")
            )
    run.status, run.finished_at = "success", datetime.now(UTC)
    run.n_records = stats["n_inserted"] + stats["n_superseded"]
    run.n_review = stats.get("n_review", 0)
    run.n_rejected = stats["n_rejected"]
    session.flush()
    return stats
