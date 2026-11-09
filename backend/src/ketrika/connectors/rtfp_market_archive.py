"""Historical multi-commodity and market-level WB close estimates from original ZIPs (IA-DATA-04).

Covers:
- All geo-referenced markets and national average
- Three primary food staples: Rice (local), Sugar, and Wheat flour
- Full historical depth starting in 2007
- Direct observation vs spatial interpolation attribution
- 100% verified cell provenance against original ZIP bytes
"""

from __future__ import annotations

import calendar
import hashlib
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from ketrika.connectors.base import ParseResult, RawArtifact
from ketrika.connectors.records import PriceRecord
from ketrika.connectors.rtfp_json import _artifact_descriptor, _document
from ketrika.core.provenance import (
    ArtifactReader,
    ArtifactReference,
    ObservationClaim,
    ProofError,
    ProvenanceVerifier,
)
from ketrika.core.provenance_wb_market import (
    ALLOWED_PRICE_FIELDS,
    FORMAT,
    MIMES,
)
from ketrika.core.schema_wb_archive import COLUMNS, archive_member
from ketrika.core.wb_archive import ArchiveError, rows

PARSER_VERSION = "4.0.0"
SOURCE = "wb_rtfp_mdg"


def parse_persisted(
    session: Session,
    primary: RawArtifact,
    reader: ArtifactReader,
    limit: int | None = None,
) -> ParseResult:
    """Resolve the study context exclusively from the immutable batch ledger."""
    from ketrika.connectors.batch_ledger import read_bronze_batch
    from ketrika.core.models.ingestion_batch import IngestionBatchMember

    run_ids = list(
        session.scalars(
            select(IngestionBatchMember.run_id)
            .where(IngestionBatchMember.source_record_id == UUID(primary.source_record_id))
            .limit(1001)
        )
    )
    if not run_ids or len(run_ids) > 1000:
        raise ProofError("rtfp_batch_ambiguous_or_missing")

    contexts: list[RawArtifact] = []
    for run_id in run_ids:
        batch = read_bronze_batch(session, run_id)
        if (
            batch.source_id != SOURCE
            or batch.parser_version != PARSER_VERSION
            or not 2 <= len(batch.artifacts) <= 16
        ):
            raise ProofError("rtfp_batch_invalid")

        matches = [
            item for item in batch.artifacts if item.source_record_id == primary.source_record_id
        ]
        if len(matches) != 1 or _artifact_descriptor(matches[0]) != _artifact_descriptor(primary):
            raise ProofError("rtfp_batch_reference_mismatch")

        candidates = []
        for artifact in batch.artifacts:
            if artifact.mime_type.split(";")[0].strip().lower() != "application/json":
                continue
            document = _document(reader, artifact)
            if isinstance(document, dict) and "study_desc" in document and "additional" in document:
                candidates.append(artifact)

        if len(candidates) != 1:
            raise ProofError("rtfp_context_ambiguous_or_missing")
        if contexts and _artifact_descriptor(candidates[0]) != _artifact_descriptor(contexts[0]):
            raise ProofError("rtfp_context_ambiguous_or_missing")
        contexts.append(candidates[0])

    if primary.mime_type.split(";")[0].strip().lower() == "application/json":
        if _artifact_descriptor(primary) != _artifact_descriptor(contexts[0]):
            raise ProofError("rtfp_context_ambiguous_or_missing")
        return ParseResult(records=[], parser_version=PARSER_VERSION)

    return parse_market_estimates(primary, contexts[0], reader, limit=limit)


def parse_market_estimates(
    primary: RawArtifact,
    context: RawArtifact,
    reader: ArtifactReader,
    limit: int | None = None,
) -> ParseResult:
    """Parse market-level and multi-commodity estimates with verified provenance."""
    if primary.mime_type.split(";")[0].strip().lower() not in MIMES:
        raise ProofError("unsupported_format")

    content = reader.get(primary.object_key)
    if hashlib.sha256(content).hexdigest() != primary.content_sha256:
        raise ProofError("rtfp_artifact_invalid")

    try:
        member = archive_member(content)
    except ArchiveError as exc:
        raise ProofError(str(exc)) from None

    url = urlsplit(primary.url)
    if (
        url.scheme != "https"
        or url.hostname != "microdata.worldbank.org"
        or url.username
        or url.password
        or url.port not in (None, 443)
        or url.fragment
        or not url.path.startswith("/api/downloads/download/MDG_2021_RTFP_v02_M/")
        or not url.path.rsplit("/", 1)[-1].isdigit()
        or parse_qs(url.query) != {"filename": [member[:-4] + ".zip"]}
        or context.url != "https://microdata.worldbank.org/metadata/export/8240/json"
    ):
        raise ProofError("wb_archive_source_url_invalid")

    metadata = _document(reader, context)
    try:
        tickers = metadata["additional"]["ticker_info"]
    except (TypeError, KeyError):
        raise ProofError("rtfp_document_invalid") from None

    if not isinstance(tickers, list) or not 0 < len(tickers) <= 128:
        raise ProofError("rtfp_document_outside_bounds")

    ticker_map: dict[str, tuple[int, dict[str, Any]]] = {}
    for price_field, field_def in ALLOWED_PRICE_FIELDS.items():
        target_ticker = field_def["ticker"]
        matching = [
            (index, item)
            for index, item in enumerate(tickers)
            if isinstance(item, dict)
            and item.get("iso3") == "MDG"
            and item.get("ticker") == target_ticker
        ]
        if len(matching) != 1:
            raise ProofError("rtfp_context_ambiguous_or_missing")
        ticker_index, ticker = matching[0]
        if not ticker.get("full_name") or ticker.get("units") != "KG":
            raise ProofError("wb_archive_context_outside_received_scope")
        ticker_map[price_field] = (ticker_index, ticker)

    records: list[PriceRecord] = []
    claims: list[ObservationClaim] = []
    vintage = date.fromisoformat(member[-14:-4]).replace(day=1)

    try:
        for index, row in rows(content, member):
            if tuple(row) != COLUMNS:
                raise ProofError("wb_archive_schema_drift")

            if row["ISO3"] != "MDG" or row["currency"] != "MGA":
                raise ProofError("wb_archive_identity_invalid")

            if not row["geo_id"] or not row["mkt_name"]:
                continue

            start = date.fromisoformat(row["price_date"])
            if not date(2007, 1, 1) <= start <= vintage:
                continue

            is_interpolated = row.get("spatially_interpolated") == "1"
            observed_status = "imputed" if is_interpolated else "observed"
            val_kind = "imputed" if is_interpolated else "point"

            for price_field, (ticker_index, ticker) in ticker_map.items():
                raw = row[price_field]
                if raw == "":
                    continue

                if len(raw) > 128:
                    raise ProofError("wb_archive_value_or_currency_invalid")

                try:
                    value = Decimal(raw)
                    if not value.is_finite() or value <= 0:
                        raise InvalidOperation

                    with localcontext() as arithmetic:
                        arithmetic.prec = 64
                        value = value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

                    if (
                        value <= 0
                        or value >= Decimal("100000000000000")
                        or Decimal(str(float(value))) != value
                    ):
                        raise InvalidOperation
                except InvalidOperation:
                    raise ProofError("invalid_number") from None

                proof = {
                    "version": 2,
                    "format": FORMAT,
                    "member": member,
                    "row": index,
                    "ticker_index": ticker_index,
                    "price_field": price_field,
                    "location_field": "mkt_name",
                    "context_source_record_id": context.source_record_id,
                }
                expected = {
                    "price_value": str(value),
                    "price_raw": raw,
                    "product_raw": ticker["full_name"],
                    "unit_raw": ticker["units"],
                    "currency_raw": row["currency"],
                    "period_start": start.isoformat(),
                    "location_raw": row["mkt_name"],
                }

                claims.append(
                    ObservationClaim(
                        uuid5(UUID(primary.source_record_id), f"{index}:{price_field}"),
                        UUID(primary.source_record_id),
                        dict(proof, expected=expected),
                    )
                )

                records.append(
                    PriceRecord(
                        product_raw=ticker["full_name"],
                        location_raw=row["mkt_name"],
                        actor_level="unknown",
                        period_start=start,
                        period_end=date(
                            start.year,
                            start.month,
                            calendar.monthrange(start.year, start.month)[1],
                        ),
                        price_raw=raw,
                        price_value=float(value),
                        unit_raw=ticker["units"],
                        currency_raw=row["currency"],
                        observed_or_imputed=observed_status,
                        value_kind=val_kind,
                        extraction_method="deterministic",
                        evidence={"provenance": proof},
                        published_at=primary.published_at,
                    )
                )

                if limit is not None and len(records) >= limit:
                    break
            if limit is not None and len(records) >= limit:
                break

    except ArchiveError as exc:
        raise ProofError(str(exc)) from None

    if not records:
        raise ProofError("wb_market_archive_selected_scope_empty")

    references = {
        UUID(item.source_record_id): ArtifactReference(
            UUID(item.source_record_id),
            SOURCE,
            item.object_key,
            item.content_sha256,
            item.mime_type,
        )
        for item in (primary, context)
    }

    if not ProvenanceVerifier(reader, references).verify(claims).passed:
        raise ProofError("rtfp_provenance_rejected")

    return ParseResult(records=records, parser_version=PARSER_VERSION)
