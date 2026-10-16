"""Data Quality (DQ) checks engine and stale alert automation (SPECS §14, §15, MVP_EXECUTION_PLAN T5.3)."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ketrika.core.models.db import Alert, DqResult, SourceRecord

logger = logging.getLogger("ketrika.dq")


class GoldDqRejected(ValueError):
    """Raised when a blocking Data Quality check fails, stopping Gold publication (SPECS §14, R2.3)."""


@dataclass(frozen=True)
class PublicationDenominators:
    """Exact accounting denominators for Gold publication (SPECS §14, R2.3).

    Strict invariant: candidate_rows == accepted_rows + rejected_rows + review_rows.
    """

    candidate_files: int
    parsed_files: int
    failed_files: int
    review_files: int
    pending_files: int

    candidate_rows: int
    accepted_rows: int
    rejected_rows: int
    review_rows: int

    def validate_invariants(self) -> None:
        """Validate exact mathematical consistency of publication accounting."""
        expected_rows = self.accepted_rows + self.rejected_rows + self.review_rows
        if self.candidate_rows != expected_rows:
            raise ValueError(
                f"publication_denominators_inconsistent: candidate_rows ({self.candidate_rows}) "
                f"!= accepted ({self.accepted_rows}) + rejected ({self.rejected_rows}) + review ({self.review_rows})"
            )
        expected_files = (
            self.parsed_files + self.failed_files + self.review_files + self.pending_files
        )
        if self.candidate_files != expected_files:
            raise ValueError(
                f"file_denominators_inconsistent: candidate_files ({self.candidate_files}) != "
                f"parsed ({self.parsed_files}) + failed ({self.failed_files}) + review ({self.review_files}) + pending ({self.pending_files})"
            )


@dataclass(frozen=True)
class DqCheckResult:
    """Result of a single DQ asset check."""

    check_name: str
    source_id: str | None
    asset_key: str
    passed: bool
    metric: float
    threshold: float
    details: dict[str, Any]


def check_provenance_complete(session: Session, source_id: str | None = None) -> DqCheckResult:
    """Check that 100% of observations have a valid source_record_id (SPECS §14)."""
    # Check across price observations
    if source_id is not None:
        sql = text(
            """
            SELECT
                count(*)::integer AS total,
                count(CASE WHEN po.source_record_id IS NOT NULL AND sr.source_record_id IS NOT NULL THEN 1 END)::integer AS valid_prov
            FROM obs.price_observation po
            LEFT JOIN meta.source_record sr ON po.source_record_id = sr.source_record_id
            WHERE sr.source_id = :sid;
            """
        )
        row = session.execute(sql, {"sid": source_id}).fetchone()
    else:
        sql = text(
            """
            SELECT
                count(*)::integer AS total,
                count(CASE WHEN po.source_record_id IS NOT NULL AND sr.source_record_id IS NOT NULL THEN 1 END)::integer AS valid_prov
            FROM obs.price_observation po
            LEFT JOIN meta.source_record sr ON po.source_record_id = sr.source_record_id;
            """
        )
        row = session.execute(sql).fetchone()

    total = row[0] if row else 0
    valid = row[1] if row else 0

    rate = (valid / total * 100.0) if total > 0 else 100.0
    passed = rate >= 100.0

    return DqCheckResult(
        check_name="provenance_complete",
        source_id=source_id,
        asset_key="obs.price_observation",
        passed=passed,
        metric=round(rate, 2),
        threshold=100.0,
        details={"total_records": total, "valid_provenance": valid},
    )


def check_parse_success_rate(session: Session, source_id: str | None = None) -> DqCheckResult:
    """Check that extraction parse success rate is >= 99% (SPECS §14)."""
    stmt = select(SourceRecord)
    if source_id:
        stmt = stmt.where(SourceRecord.source_id == source_id)
    records = list(session.execute(stmt).scalars().all())

    total = len(records)
    parsed = sum(1 for r in records if r.extraction_status == "parsed")
    rate = (parsed / total * 100.0) if total > 0 else 100.0
    passed = rate >= 99.0

    return DqCheckResult(
        check_name="parse_success_rate",
        source_id=source_id,
        asset_key="meta.source_record",
        passed=passed,
        metric=round(rate, 2),
        threshold=99.0,
        details={"total_artifacts": total, "parsed_artifacts": parsed},
    )


def check_price_range_sanity(session: Session, source_id: str | None = None) -> DqCheckResult:
    """Check that observed prices fall within reasonable boundaries [100, 200000] MGA/base (SPECS §14)."""
    if source_id is not None:
        sql = text(
            """
            SELECT count(*)::integer
            FROM obs.price_observation po
            JOIN meta.source_record sr ON po.source_record_id = sr.source_record_id
            WHERE sr.source_id = :sid
              AND po.superseded_by IS NULL
              AND po.price_mga_per_base IS NOT NULL
              AND (po.price_mga_per_base < 100.0 OR po.price_mga_per_base > 200000.0);
            """
        )
        violations = session.execute(sql, {"sid": source_id}).scalar() or 0
    else:
        sql = text(
            """
            SELECT count(*)::integer
            FROM obs.price_observation po
            WHERE po.superseded_by IS NULL
              AND po.price_mga_per_base IS NOT NULL
              AND (po.price_mga_per_base < 100.0 OR po.price_mga_per_base > 200000.0);
            """
        )
        violations = session.execute(sql).scalar() or 0

    passed = violations == 0

    return DqCheckResult(
        check_name="price_range_sanity",
        source_id=source_id,
        asset_key="obs.price_observation",
        passed=passed,
        metric=float(violations),
        threshold=0.0,
        details={"out_of_bounds_prices": violations},
    )


def check_freshness_and_manage_alerts(
    session: Session, source_id: str | None = None
) -> list[DqCheckResult]:
    """Check freshness vs SLA from gold.source_health and generate DATA_STALE alerts (SPECS §14, §15, T5.3)."""
    if source_id is not None:
        sql = text(
            """
            SELECT source_id, freshness_sla_days, freshness_days, is_stale, last_fetched_at
            FROM gold.source_health
            WHERE source_id = :sid;
            """
        )
        rows = session.execute(sql, {"sid": source_id}).fetchall()
    else:
        sql = text(
            """
            SELECT source_id, freshness_sla_days, freshness_days, is_stale, last_fetched_at
            FROM gold.source_health;
            """
        )
        rows = session.execute(sql).fetchall()
    results: list[DqCheckResult] = []

    for r in rows:
        s_id = r[0]
        sla_days = r[1]
        freshness_days = r[2]
        is_stale = bool(r[3])
        last_fetched = r[4]

        # Metric is freshness_days (or 999 if never fetched)
        metric_val = float(freshness_days) if freshness_days is not None else 999.0
        thresh_val = float(sla_days) if sla_days is not None else 30.0
        passed = not is_stale

        results.append(
            DqCheckResult(
                check_name="freshness",
                source_id=s_id,
                asset_key=f"source.{s_id}",
                passed=passed,
                metric=metric_val,
                threshold=thresh_val,
                details={
                    "sla_days": sla_days,
                    "freshness_days": freshness_days,
                    "last_fetched_at": str(last_fetched) if last_fetched else None,
                    "is_stale": is_stale,
                },
            )
        )

        dedupe_key = f"DATA_STALE_{s_id}"
        alert_stmt = select(Alert).where(Alert.dedupe_key == dedupe_key)
        existing_alert = session.execute(alert_stmt).scalar_one_or_none()

        if is_stale:
            # Trigger or update open DATA_STALE alert
            if existing_alert is None:
                new_alert = Alert(
                    alert_id=uuid.uuid4(),
                    rule_code="DATA_STALE",
                    dedupe_key=dedupe_key,
                    severity="high" if s_id in ("miasa_odr", "wfp_hdx_mdg") else "medium",
                    title=f"Source '{s_id}' est hors SLA ({metric_val:.0f}j > SLA {thresh_val:.0f}j)",
                    evidence={
                        "source_id": s_id,
                        "freshness_days": metric_val,
                        "sla_days": thresh_val,
                        "last_fetched_at": str(last_fetched) if last_fetched else None,
                    },
                    state="open",
                    first_seen_at=datetime.now(UTC),
                    last_seen_at=datetime.now(UTC),
                )
                session.add(new_alert)
                logger.warning("Created DATA_STALE alert for source %s", s_id)
            else:
                existing_alert.last_seen_at = datetime.now(UTC)
                existing_alert.state = "open"
                existing_alert.evidence = {
                    "source_id": s_id,
                    "freshness_days": metric_val,
                    "sla_days": thresh_val,
                    "last_fetched_at": str(last_fetched) if last_fetched else None,
                }
        else:
            # Resolve existing alert if source is back within SLA
            if existing_alert is not None and existing_alert.state == "open":
                existing_alert.state = "resolved"
                existing_alert.last_seen_at = datetime.now(UTC)
                logger.info("Resolved DATA_STALE alert for source %s", s_id)

    session.flush()
    return results


def check_llm_unverified_in_gold(session: Session, source_id: str | None = None) -> DqCheckResult:
    """Check that 0 unverified LLM extractions enter Gold (SPECS §11, §14).

    Any LLM-extracted value in Gold must carry mechanical provenance evidence
    (page + excerpt) and have review_status = 'accepted'.
    """
    if source_id is not None:
        sql = text(
            """
            SELECT count(*)::integer
            FROM obs.price_observation po
            JOIN meta.source_record sr ON po.source_record_id = sr.source_record_id
            WHERE sr.source_id = :sid
              AND po.superseded_by IS NULL
              AND po.review_status = 'accepted'
              AND po.price_mga_per_base IS NOT NULL
              AND (
                  po.extraction_method IN ('llm', 'llm_unverified')
                  OR (
                      po.extraction_method IN ('llm_verified', 'dual_agree')
                      AND (
                          po.evidence IS NULL
                          OR po.evidence->'provenance'->'llm_evidence' IS NULL
                          OR po.evidence->'provenance'->'llm_evidence'->>'page' IS NULL
                          OR po.evidence->'provenance'->'llm_evidence'->>'text' IS NULL
                      )
                  )
              );
            """
        )
        violations = session.execute(sql, {"sid": source_id}).scalar() or 0
    else:
        sql = text(
            """
            SELECT count(*)::integer
            FROM obs.price_observation po
            WHERE po.superseded_by IS NULL
              AND po.review_status = 'accepted'
              AND po.price_mga_per_base IS NOT NULL
              AND (
                  po.extraction_method IN ('llm', 'llm_unverified')
                  OR (
                      po.extraction_method IN ('llm_verified', 'dual_agree')
                      AND (
                          po.evidence IS NULL
                          OR po.evidence->'provenance'->'llm_evidence' IS NULL
                          OR po.evidence->'provenance'->'llm_evidence'->>'page' IS NULL
                          OR po.evidence->'provenance'->'llm_evidence'->>'text' IS NULL
                      )
                  )
              );
            """
        )
        violations = session.execute(sql).scalar() or 0

    passed = violations == 0

    return DqCheckResult(
        check_name="llm_unverified_in_gold",
        source_id=source_id,
        asset_key="obs.price_observation",
        passed=passed,
        metric=float(violations),
        threshold=0.0,
        details={"unverified_llm_records": violations},
    )


def get_publication_denominators(
    session: Session, source_id: str | None = None
) -> PublicationDenominators:
    """Compute and validate exact accounting denominators for publication (SPECS §14, R2.3)."""
    if source_id is not None:
        file_sql = text(
            """
            SELECT
                count(*)::integer AS total_files,
                count(CASE WHEN extraction_status = 'parsed' THEN 1 END)::integer AS parsed,
                count(CASE WHEN extraction_status = 'failed' THEN 1 END)::integer AS failed,
                count(CASE WHEN extraction_status = 'review' THEN 1 END)::integer AS review,
                count(CASE WHEN extraction_status = 'pending' THEN 1 END)::integer AS pending
            FROM meta.source_record
            WHERE source_id = :sid;
            """
        )
        f_row = session.execute(file_sql, {"sid": source_id}).fetchone()
        row_sql = text(
            """
            SELECT
                count(*)::integer AS candidate_rows,
                count(CASE WHEN po.review_status = 'accepted' THEN 1 END)::integer AS accepted,
                count(CASE WHEN po.review_status = 'rejected' THEN 1 END)::integer AS rejected,
                count(CASE WHEN po.review_status = 'pending' THEN 1 END)::integer AS review
            FROM obs.price_observation po
            JOIN meta.source_record sr ON po.source_record_id = sr.source_record_id
            WHERE sr.source_id = :sid
              AND po.superseded_by IS NULL;
            """
        )
        r_row = session.execute(row_sql, {"sid": source_id}).fetchone()
    else:
        file_sql = text(
            """
            SELECT
                count(*)::integer AS total_files,
                count(CASE WHEN extraction_status = 'parsed' THEN 1 END)::integer AS parsed,
                count(CASE WHEN extraction_status = 'failed' THEN 1 END)::integer AS failed,
                count(CASE WHEN extraction_status = 'review' THEN 1 END)::integer AS review,
                count(CASE WHEN extraction_status = 'pending' THEN 1 END)::integer AS pending
            FROM meta.source_record;
            """
        )
        f_row = session.execute(file_sql).fetchone()
        row_sql = text(
            """
            SELECT
                count(*)::integer AS candidate_rows,
                count(CASE WHEN review_status = 'accepted' THEN 1 END)::integer AS accepted,
                count(CASE WHEN review_status = 'rejected' THEN 1 END)::integer AS rejected,
                count(CASE WHEN review_status = 'pending' THEN 1 END)::integer AS review
            FROM obs.price_observation
            WHERE superseded_by IS NULL;
            """
        )
        r_row = session.execute(row_sql).fetchone()

    total_files = f_row[0] if f_row else 0
    parsed_files = f_row[1] if f_row else 0
    failed_files = f_row[2] if f_row else 0
    review_files = f_row[3] if f_row else 0
    pending_files = f_row[4] if f_row else 0

    candidate_rows = r_row[0] if r_row else 0
    accepted_rows = r_row[1] if r_row else 0
    rejected_rows = r_row[2] if r_row else 0
    review_rows = r_row[3] if r_row else 0

    denominators = PublicationDenominators(
        candidate_files=total_files,
        parsed_files=parsed_files,
        failed_files=failed_files,
        review_files=review_files,
        pending_files=pending_files,
        candidate_rows=candidate_rows,
        accepted_rows=accepted_rows,
        rejected_rows=rejected_rows,
        review_rows=review_rows,
    )
    denominators.validate_invariants()
    return denominators


def check_blocking_dq_gate(
    session: Session, source_id: str | None = None
) -> list[DqCheckResult]:
    """Execute blocking DQ gate checks and refuse publication if any fails (SPECS §14, R2.3).

    Blocking checks (SPECS §14):
    1. provenance_complete: 100% of observations must have valid source_record_id.
    2. parse_success_rate: >= 99% parse success rate per source run.
    3. llm_unverified_in_gold: 0 unverified LLM extractions allowed in Gold.
    """
    checks: list[DqCheckResult] = []

    # 1. Provenance complete (threshold 100.0%)
    prov_check = check_provenance_complete(session, source_id)
    checks.append(prov_check)
    if not prov_check.passed:
        raise GoldDqRejected(
            f"blocking_dq_provenance_incomplete: rate={prov_check.metric}% < threshold={prov_check.threshold}%"
        )

    # 2. Parse success rate (threshold 99.0%)
    parse_check = check_parse_success_rate(session, source_id)
    checks.append(parse_check)
    if not parse_check.passed:
        raise GoldDqRejected(
            f"blocking_dq_parse_rate_low: rate={parse_check.metric}% < threshold={parse_check.threshold}%"
        )

    # 3. LLM unverified in Gold (threshold 0)
    llm_check = check_llm_unverified_in_gold(session, source_id)
    checks.append(llm_check)
    if not llm_check.passed:
        raise GoldDqRejected(
            f"blocking_dq_llm_unverified_in_gold: violations={llm_check.metric} > threshold={llm_check.threshold}"
        )

    return checks


def run_all_dq_checks(session: Session, persist: bool = True) -> list[DqCheckResult]:
    """Execute full battery of Data Quality checks and persist results to ops.dq_result (SPECS §14)."""
    checks: list[DqCheckResult] = []

    # 1. Global / source checks
    checks.append(check_provenance_complete(session))
    checks.append(check_parse_success_rate(session))
    checks.append(check_price_range_sanity(session))
    checks.append(check_llm_unverified_in_gold(session))

    # 2. Freshness and staleness checks per source
    freshness_checks = check_freshness_and_manage_alerts(session)
    checks.extend(freshness_checks)

    # 3. Persist to ops.dq_result
    if persist:
        for c in checks:
            record = DqResult(
                dq_id=uuid.uuid4(),
                check_name=c.check_name,
                source_id=c.source_id,
                asset_key=c.asset_key,
                passed=c.passed,
                metric=c.metric,
                threshold=c.threshold,
                details=c.details,
                checked_at=datetime.now(UTC),
            )
            session.add(record)
        session.flush()

    return checks
