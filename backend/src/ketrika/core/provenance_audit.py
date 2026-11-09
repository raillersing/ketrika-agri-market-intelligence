"""Explicit SQL binding and transactional DQ receipts (ADR-017).

The Gold publication gate uses this audit. It does not validate conversions or
discover sources. Legacy rows without supported evidence fail rather than disappear.
"""

from __future__ import annotations

import copy
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ketrika.core.models.db import (
    CpiObservation,
    DqResult,
    PriceObservation,
    ProductionObservation,
    SourceRecord,
    StockObservation,
    TradeFlow,
    WeatherObservation,
)
from ketrika.core.provenance import (
    ArtifactReader,
    ArtifactReference,
    ObservationClaim,
    ProofError,
    ProvenanceVerifier,
    VerificationReport,
)


@dataclass(frozen=True)
class BindingPolicy:
    model: Any
    values: tuple[str, ...]
    identities: tuple[str, ...]
    raw_fields: Mapping[str, str]


POLICIES: dict[str, BindingPolicy] = {
    "price_observation": BindingPolicy(
        PriceObservation,
        ("price_value",),
        ("product_raw", "location_raw", "period_start", "unit_raw", "currency_raw"),
        {"price_value": "price_raw"},
    ),
    "stock_observation": BindingPolicy(
        StockObservation,
        ("quantity_value", "coverage_days", "stock_status"),
        ("product_raw", "location_raw", "period_start", "unit_raw"),
        {"quantity_value": "quantity_raw"},
    ),
    "trade_flow": BindingPolicy(
        TradeFlow,
        ("value_mga", "value_usd", "weight_kg"),
        ("product_raw", "period_start", "flow", "hs_code", "partner_raw"),
        {"weight_kg": "weight_raw"},
    ),
    "production_observation": BindingPolicy(
        ProductionObservation,
        ("value",),
        ("product_raw", "period_start", "element", "unit_raw"),
        {"value": "value_raw"},
    ),
    "weather_observation": BindingPolicy(
        WeatherObservation,
        ("value",),
        ("date", "variable", "provider", "location_raw", "method"),
        {"value": "value_raw"},
    ),
    "cpi_observation": BindingPolicy(
        CpiObservation,
        ("index_value",),
        ("series_code", "series_label", "geo_scope", "period_start", "base_period"),
        {},
    ),
}


def _expected(value: Any, kind: str) -> str:
    if kind == "number":
        if type(value) not in (int, Decimal) or not Decimal(value).is_finite():
            raise ProofError("invalid_bound_number")
        return str(value)
    if kind == "text":
        if type(value) is date:
            return value.isoformat()
        if isinstance(value, str):
            return value
    raise ProofError("invalid_bound_identity")


def bind_observation(table: str, observation: Any) -> ObservationClaim:
    """Replace all supplied expectations with allowlisted stored field values."""
    policy = POLICIES.get(table)
    if policy is None or not isinstance(observation, policy.model):
        raise ProofError("unsupported_observation")
    from ketrika.core.provenance_rtfp import bind_rtfp_observation, is_context_proof

    source_proof = (getattr(observation, "evidence", None) or {}).get("provenance", {})
    from ketrika.core.provenance_wb_archive import bind_archive_observation, is_archive_proof
    from ketrika.core.provenance_wb_market import (
        bind_market_archive_observation,
        is_market_archive_proof,
    )

    if (
        table == "price_observation"
        and isinstance(source_proof, dict)
        and is_archive_proof(source_proof)
    ):
        return bind_archive_observation(observation, source_proof)
    if (
        table == "price_observation"
        and isinstance(source_proof, dict)
        and is_market_archive_proof(source_proof)
    ):
        return bind_market_archive_observation(observation, source_proof)
    if (
        table == "price_observation"
        and isinstance(source_proof, dict)
        and is_context_proof(source_proof)
    ):
        return bind_rtfp_observation(observation, source_proof)
    evidence = getattr(observation, "evidence", None)
    proof = evidence.get("provenance") if isinstance(evidence, dict) else None
    if not isinstance(proof, dict) or not isinstance(proof.get("cells"), list):
        raise ProofError("binding_proof_missing")
    method = getattr(observation, "extraction_method", None)
    if method not in ("deterministic", "llm_verified", "dual_agree"):
        raise ProofError("extraction_proof_not_supported")
    if method in ("llm_verified", "dual_agree") and not isinstance(proof.get("llm_evidence"), dict):
        raise ProofError("extraction_proof_not_supported")
    bound = copy.deepcopy(proof)
    required_values = {field for field in policy.values if getattr(observation, field) is not None}
    if table == "price_observation" and observation.missing_code is not None:
        if observation.price_value is not None or observation.price_mga_per_base is not None:
            raise ProofError("binding_missingness_conflict")
        raw = observation.price_raw
        if not isinstance(raw, str) or len(raw) > 128:
            raise ProofError("binding_missing_marker_invalid")
        marker = unicodedata.normalize("NFKC", raw).strip().upper()
        code = "ND" if marker in {"", "-"} else marker
        if code not in {"ND", "NA"} or observation.missing_code != code:
            raise ProofError("binding_missing_marker_invalid")
        required_values = {"price_raw"}
    required_identities = {
        field for field in policy.identities if getattr(observation, field) is not None
    }
    if not required_values or not required_identities:
        raise ProofError("binding_value_or_identity_missing")
    seen: set[str] = set()
    for cell in bound["cells"]:
        if not isinstance(cell, dict):
            raise ProofError("invalid_proof")
        field = cell.get("field")
        if not isinstance(field, str) or field in seen:
            raise ProofError("invalid_bound_field")
        seen.add(field)
        if field in required_values:
            role = "value"
            kind = "text" if field in {"stock_status", "price_raw"} else "number"
        elif field in required_identities:
            role, kind = "identity", "text"
        else:
            raise ProofError("invalid_bound_field")
        if cell.get("role") != role or cell.get("kind") != kind:
            raise ProofError("invalid_bound_role")
        cell["expected"] = _expected(getattr(observation, field), kind)
        cell.pop("raw_expected", None)
        raw_field = policy.raw_fields.get(field)
        if raw_field is not None:
            raw_value = getattr(observation, raw_field)
            if not isinstance(raw_value, str):
                raise ProofError("binding_raw_value_missing")
            cell["raw_expected"] = raw_value
    if seen != required_values | required_identities:
        raise ProofError("binding_fields_missing")
    return ObservationClaim(observation.observation_id, observation.source_record_id, bound)


@dataclass(frozen=True)
class ObservationTarget:
    table: str
    observation_id: UUID


@dataclass(frozen=True)
class AuditReceipt:
    report: VerificationReport
    targets: tuple[ObservationTarget, ...]
    dq_id: UUID


def audit_observation_provenance(
    session: Session,
    reader: ArtifactReader,
    *,
    mode: Literal["complete", "incremental"] = "complete",
    targets: Sequence[ObservationTarget] | None = None,
) -> AuditReceipt:
    """Audit/persist; caller controls commit. Never mutates observed or Bronze data."""
    if mode not in ("complete", "incremental"):
        raise ValueError("Unsupported verification mode")
    if (mode == "complete" and targets is not None) or (mode == "incremental" and not targets):
        raise ValueError("Complete audit forbids targets; incremental audit requires targets")
    selected: list[tuple[ObservationTarget, Any]] = []
    if mode == "complete":
        for table, policy in POLICIES.items():
            rows = session.scalars(select(policy.model).order_by(policy.model.observation_id)).all()
            selected.extend((ObservationTarget(table, row.observation_id), row) for row in rows)
    else:
        for target in targets or ():
            if target.table not in POLICIES:
                raise ValueError("Unsupported observation table")
            selected.append(
                (target, session.get(POLICIES[target.table].model, target.observation_id))
            )
    claims = []
    binding_errors: dict[int, str] = {}
    for index, (target, row) in enumerate(selected):
        try:
            if row is None:
                raise ProofError("observation_missing")
            claim = bind_observation(target.table, row)
        except ProofError as exc:
            binding_errors[index] = str(exc)
            claim = ObservationClaim(
                target.observation_id, getattr(row, "source_record_id", None), {}
            )
        claims.append(claim)
    record_ids = {claim.source_record_id for claim in claims if claim.source_record_id}
    from ketrika.core.provenance_rtfp import context_reference, is_context_proof
    from ketrika.core.provenance_wb_archive import is_archive_proof
    from ketrika.core.provenance_wb_market import is_market_archive_proof

    record_ids.update(
        context_reference(claim.proof)
        for claim in claims
        if is_context_proof(claim.proof)
        or is_archive_proof(claim.proof)
        or is_market_archive_proof(claim.proof)
    )
    records = (
        session.scalars(
            select(SourceRecord).where(SourceRecord.source_record_id.in_(record_ids))
        ).all()
        if record_ids
        else []
    )
    synthetic_ids = {
        row.source_record_id
        for row in records
        if row.retrieved_via == "synthetic"
        or (row.source_url and row.source_url.startswith("fixture:"))
        or (row.source_id and row.source_id.startswith(("dummy_", "fixture_")))
    }
    for index, claim in enumerate(claims):
        if claim.source_record_id and claim.source_record_id in synthetic_ids:
            binding_errors[index] = "synthetic_source_record_forbidden"
    references = {
        row.source_record_id: ArtifactReference(
            row.source_record_id,
            row.source_id,
            row.object_key,
            row.content_sha256,
            row.mime_type or "",
        )
        for row in records
        if row.source_record_id not in synthetic_ids
    }
    report = ProvenanceVerifier(reader, references).verify(claims, mode)
    results = tuple(
        replace(
            result, passed=False, reason=binding_errors[index], object_key=None, content_sha256=None
        )
        if index in binding_errors
        else result
        for index, result in enumerate(report.results)
    )
    report = replace(report, results=results)
    dq = DqResult(
        check_name="provenance_bytes_and_cells",
        asset_key="obs.*",
        passed=report.passed,
        metric=report.rate,
        threshold=Decimal(100),
        details={
            "mode": mode,
            "scope": "all_observations" if mode == "complete" else "explicit_targets",
            "tables": list(POLICIES)
            if mode == "complete"
            else sorted({t.table for t, _ in selected}),
            "total_records": report.total,
            "valid_provenance": report.valid,
            "objects_read": report.objects_read,
            "object_read_attempts": report.object_read_attempts,
            "results": [
                {
                    "table": target.table,
                    "observation_id": str(result.observation_id),
                    "source_record_id": str(result.source_record_id)
                    if result.source_record_id
                    else None,
                    "passed": result.passed,
                    "reason": result.reason,
                    "object_key": result.object_key,
                    "content_sha256": result.content_sha256,
                }
                for (target, _), result in zip(selected, report.results, strict=True)
            ],
        },
    )
    session.add(dq)
    session.flush()
    return AuditReceipt(report, tuple(target for target, _ in selected), dq.dq_id)


def audit_source_provenance(
    session: Session, reader: ArtifactReader, source_id: str
) -> AuditReceipt:
    """Measure every source-attributable row, including historical/rejected rows."""
    if not isinstance(source_id, str) or not source_id:
        raise ValueError("invalid_audit_source")
    targets: list[ObservationTarget] = []
    for table, policy in POLICIES.items():
        model = policy.model
        ids = session.scalars(
            select(model.observation_id)
            .join(SourceRecord, model.source_record_id == SourceRecord.source_record_id)
            .where(SourceRecord.source_id == source_id)
            .order_by(model.observation_id)
        ).all()
        targets.extend(ObservationTarget(table, observation_id) for observation_id in ids)
    if targets:
        receipt = audit_observation_provenance(session, reader, mode="incremental", targets=targets)
        dq = session.get(DqResult, receipt.dq_id)
        if dq is None:
            raise ValueError("source_audit_receipt_missing")
        dq.details = dict(dq.details or {}) | {"scope": "all_source_observations"}
    else:
        report = VerificationReport("incremental", (), 0, 0)
        dq = DqResult(
            check_name="provenance_bytes_and_cells",
            passed=False,
            metric=None,
            threshold=Decimal(100),
            details={
                "mode": "incremental",
                "scope": "all_source_observations",
                "tables": list(POLICIES),
                "total_records": 0,
                "valid_provenance": 0,
                "objects_read": 0,
                "object_read_attempts": 0,
                "results": [],
            },
        )
        session.add(dq)
        session.flush()
        receipt = AuditReceipt(report, (), dq.dq_id)
    dq.source_id = source_id
    dq.asset_key = f"{source_id}__silver"
    dq.details = dict(dq.details or {}) | {
        "state": "empty"
        if not receipt.report.total
        else "verified"
        if receipt.report.passed
        else "failed"
    }
    session.flush()
    return receipt
