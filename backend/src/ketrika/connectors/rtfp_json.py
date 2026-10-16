"""Bounded close-estimate parser; context must come from the durable batch."""

import calendar
import hashlib
import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from ketrika.connectors.base import ParseResult, RawArtifact
from ketrika.connectors.records import PriceRecord
from ketrika.core.provenance import (
    MAX_CONTENT_BYTES,
    ArtifactReader,
    ArtifactReference,
    JsonNumberToken,
    ObservationClaim,
    ProofError,
    ProvenanceVerifier,
    _check_json_depth,
    _reject_constant,
    _unique_json_object,
)
from ketrika.core.provenance_rtfp import FIELDS

PARSER_VERSION = "2.0.0"


def parse_persisted(session: Session, primary: RawArtifact, reader: ArtifactReader) -> ParseResult:
    """Resolve context from the verified immutable ledger, never caller metadata."""
    from ketrika.core.models.ingestion_batch import IngestionBatchMember

    document = _document(reader, primary)
    is_context = (
        isinstance(document, dict) and "study_desc" in document and "additional" in document
    )
    run_ids = list(
        session.scalars(
            select(IngestionBatchMember.run_id)
            .where(IngestionBatchMember.source_record_id == UUID(primary.source_record_id))
            .limit(1 if is_context else 1001)
        )
    )
    if not run_ids or len(run_ids) > 1000:
        raise ProofError("rtfp_batch_ambiguous_or_missing")
    contexts: list[RawArtifact] = []
    for run_id in run_ids:
        context = _persisted_context(session, run_id, primary, reader, is_context=is_context)
        if is_context:
            return ParseResult(records=[], parser_version=PARSER_VERSION)
        if contexts and _artifact_descriptor(context) != _artifact_descriptor(contexts[0]):
            raise ProofError("rtfp_context_ambiguous_or_missing")
        contexts.append(context)
    return parse_close_estimates(primary, contexts[0], reader)


def _artifact_descriptor(artifact: RawArtifact) -> tuple[object, ...]:
    return tuple(
        getattr(artifact, field)
        for field in (
            "source_record_id",
            "object_key",
            "content_sha256",
            "mime_type",
            "url",
            "published_at",
        )
    )


def _persisted_context(
    session: Session,
    run_id: UUID,
    primary: RawArtifact,
    reader: ArtifactReader,
    *,
    is_context: bool,
) -> RawArtifact:
    from ketrika.connectors.batch_ledger import read_bronze_batch

    batch = read_bronze_batch(session, run_id)
    if (
        batch.ingestion_run_id != run_id
        or batch.source_id != "wb_rtfp_mdg"
        or batch.parser_version != PARSER_VERSION
        or not 2 <= len(batch.artifacts) <= 16
    ):
        raise ProofError("rtfp_batch_invalid")
    matches = [
        item for item in batch.artifacts if item.source_record_id == primary.source_record_id
    ]
    if len(matches) != 1 or any(
        getattr(matches[0], field) != getattr(primary, field)
        for field in ("object_key", "content_sha256", "mime_type", "url", "published_at")
    ):
        raise ProofError("rtfp_batch_reference_mismatch")
    if is_context:
        return matches[0]
    contexts = []
    for artifact in batch.artifacts:
        document = _document(reader, artifact)
        if isinstance(document, dict) and "study_desc" in document and "additional" in document:
            contexts.append(artifact)
    if len(contexts) != 1:
        raise ProofError("rtfp_context_ambiguous_or_missing")
    return contexts[0]


def _document(reader: ArtifactReader, artifact: RawArtifact):
    content = reader.get(artifact.object_key)
    if (
        len(content) > MAX_CONTENT_BYTES
        or hashlib.sha256(content).hexdigest() != artifact.content_sha256
    ):
        raise ProofError("rtfp_artifact_invalid")
    try:
        text = content.decode("utf-8-sig")
        _check_json_depth(text)
        return json.loads(
            text,
            parse_int=JsonNumberToken,
            parse_float=JsonNumberToken,
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_json_object,
        )
    except (UnicodeError, ValueError, RecursionError):
        raise ProofError("rtfp_document_invalid") from None


def parse_close_estimates(
    primary: RawArtifact, context: RawArtifact, reader: ArtifactReader
) -> ParseResult:
    """No unit defaults, no CSV interpretation and no observed-price inference."""
    data, metadata = _document(reader, primary), _document(reader, context)
    try:
        rows, tickers = data["data"], metadata["additional"]["ticker_info"]
    except (TypeError, KeyError):
        raise ProofError("rtfp_document_invalid") from None
    if (
        not isinstance(rows, list)
        or not 0 < len(rows) <= 1000
        or not isinstance(tickers, list)
        or not 0 < len(tickers) <= 128
    ):
        raise ProofError("rtfp_document_outside_bounds")
    references = {
        UUID(item.source_record_id): ArtifactReference(
            UUID(item.source_record_id),
            "wb_rtfp_mdg",
            item.object_key,
            item.content_sha256,
            item.mime_type,
        )
        for item in (primary, context)
    }
    records, claims = [], []
    for row_index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("ISO3") != "MDG":
            raise ProofError("rtfp_country_invalid")
        for field, ticker in FIELDS.items():
            raw = row.get(field)
            if raw is None or raw == "":
                continue
            raw_price = raw.raw if isinstance(raw, JsonNumberToken) else raw
            if not isinstance(raw_price, str) or len(raw_price) > 128:
                raise ProofError("invalid_number")
            try:
                value = Decimal(raw_price)
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
            matches = [
                (index, item)
                for index, item in enumerate(tickers)
                if isinstance(item, dict)
                and item.get("iso3") == "MDG"
                and item.get("ticker") == ticker
            ]
            if len(matches) != 1:
                raise ProofError("rtfp_context_ambiguous_or_missing")
            ticker_index, item = matches[0]
            try:
                start = date.fromisoformat(row["price_date"])
                if start.day != 1:
                    raise ValueError
                end = date(start.year, start.month, calendar.monthrange(start.year, start.month)[1])
                location = row["mkt_name"]
                product, unit, currency = item["full_name"], item["units"], row["currency"]
                if any(
                    not isinstance(v, str) or not v for v in (location, product, unit, currency)
                ):
                    raise ValueError
            except (TypeError, ValueError, KeyError):
                raise ProofError("rtfp_identity_invalid") from None
            proof = {
                "version": 2,
                "format": "rtfp_json_v1",
                "context_source_record_id": context.source_record_id,
                "row": row_index,
                "ticker_index": ticker_index,
                "price_field": field,
                "location_field": "mkt_name",
            }
            if isinstance(raw, JsonNumberToken):
                proof["raw_encoding"] = "json_number_lexeme"
            expected = {
                "price_value": str(value),
                "price_raw": raw_price,
                "product_raw": product,
                "unit_raw": unit,
                "currency_raw": currency,
                "period_start": start.isoformat(),
                "location_raw": location,
            }
            claims.append(
                ObservationClaim(
                    uuid5(UUID(primary.source_record_id), f"{row_index}:{field}"),
                    UUID(primary.source_record_id),
                    dict(proof, expected=expected),
                )
            )
            records.append(
                PriceRecord(
                    product_raw=product,
                    location_raw=location,
                    actor_level="unknown",
                    period_start=start,
                    period_end=end,
                    price_raw=raw_price,
                    price_value=float(value),
                    unit_raw=unit,
                    currency_raw=currency,
                    observed_or_imputed="imputed",
                    value_kind="point",
                    extraction_method="deterministic",
                    evidence={"provenance": proof},
                    published_at=primary.published_at,
                )
            )
    report = ProvenanceVerifier(reader, references).verify(claims)
    if not report.passed:
        raise ProofError("rtfp_provenance_rejected")
    return ParseResult(records=records, parser_version=PARSER_VERSION)
