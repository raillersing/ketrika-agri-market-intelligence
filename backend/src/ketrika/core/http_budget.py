"""Atomic, fail-closed HTTP admission; runtime never creates SQL tables."""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from ketrika.core.policy import PolicyStop


@dataclass(frozen=True)
class Admission:
    source_id: str
    domain: str
    origin: str
    source_limit: int
    domain_limit: int
    max_rps: float

    def validate(self) -> None:
        if any(
            not value or len(value) > 512 for value in (self.source_id, self.domain, self.origin)
        ):
            raise PolicyStop("http_invalid_identity")
        if any(
            type(value) is not int or value < 0 for value in (self.source_limit, self.domain_limit)
        ):
            raise PolicyStop("http_invalid_budget")
        if not math.isfinite(self.max_rps) or not 0 < self.max_rps <= 1000:
            raise PolicyStop("http_invalid_rate")


class BudgetBackend(Protocol):
    def check(self, source_id: str, origin: str) -> None:
        """Recheck stops after pacing wait, without consuming another quota."""

    def reserve(self, admission: Admission, now: datetime) -> float:
        """Commit quota and pacing together, return seconds before emission."""

    def stop(self, source_id: str, origin: str, status_code: int) -> None:
        """Persist challenge independently of the collection transaction."""


def _utc(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise PolicyStop("http_clock_timezone_missing")
    return now.astimezone(UTC)


class SqlBudgetBackend:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def check(self, source_id: str, origin: str) -> None:
        try:
            with self.engine.connect() as connection:
                stopped = connection.execute(
                    text("""
                    SELECT 1 FROM meta.http_policy_stop
                    WHERE (scope='source' AND scope_key=:source)
                       OR (scope='origin' AND scope_key=:origin)
                    UNION ALL SELECT 1 FROM meta.source WHERE source_id=:source AND status='disabled'
                    LIMIT 1
                    """),
                    {"source": source_id, "origin": origin},
                ).first()
            if stopped:
                raise PolicyStop("http_source_disabled")
        except SQLAlchemyError:
            raise PolicyStop("http_budget_storage_unavailable") from None

    def reserve(self, admission: Admission, now: datetime) -> float:
        admission.validate()
        now = _utc(now)
        denied = False
        delay = 0.0
        try:
            with self.engine.begin() as connection:
                # Serialize policy-stop writers and admissions for this source.
                connection.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                    {"key": "http-source:" + admission.source_id},
                )
                stopped = connection.execute(
                    text("""
                    SELECT 1 FROM meta.http_policy_stop
                    WHERE (scope='source' AND scope_key=:source)
                       OR (scope='origin' AND scope_key=:origin)
                    UNION ALL SELECT 1 FROM meta.source WHERE source_id=:source AND status='disabled'
                    LIMIT 1
                    """),
                    {"source": admission.source_id, "origin": admission.origin},
                ).first()
                if stopped:
                    raise PolicyStop("http_source_disabled")
                rows = [
                    ("domain", admission.domain, min(500, admission.domain_limit)),
                    ("source", admission.source_id, admission.source_limit),
                ]
                keys = []
                for scope, key, limit in rows:
                    params = {"scope": scope, "key": key, "day": now.date(), "limit": limit}
                    connection.execute(
                        text("""
                        INSERT INTO meta.http_daily_budget(scope, scope_key, day_utc, budget_limit)
                        VALUES (:scope, :key, :day, :limit)
                        ON CONFLICT (scope, scope_key, day_utc)
                        DO UPDATE SET budget_limit=LEAST(meta.http_daily_budget.budget_limit, EXCLUDED.budget_limit)
                        """),
                        params,
                    )
                    count, cap = connection.execute(
                        text("""
                        SELECT request_count, budget_limit FROM meta.http_daily_budget
                        WHERE scope=:scope AND scope_key=:key AND day_utc=:day FOR UPDATE
                        """),
                        params,
                    ).one()
                    denied |= count >= cap
                    keys.append(params)
                # Commit lower ceilings even on rejection, without consuming either counter.
                if not denied:
                    connection.execute(
                        text("""
                        INSERT INTO meta.http_domain_pacing(domain, next_allowed_at, max_rps)
                        VALUES (:domain, :now, :rate)
                        ON CONFLICT (domain) DO UPDATE
                        SET max_rps=LEAST(meta.http_domain_pacing.max_rps, EXCLUDED.max_rps)
                        """),
                        {"domain": admission.domain, "now": now, "rate": admission.max_rps},
                    )
                    next_at, rate = connection.execute(
                        text(
                            "SELECT next_allowed_at, max_rps FROM meta.http_domain_pacing WHERE domain=:domain FOR UPDATE"
                        ),
                        {"domain": admission.domain},
                    ).one()
                    slot = max(now, next_at)
                    delay = (slot - now).total_seconds()
                    connection.execute(
                        text(
                            "UPDATE meta.http_domain_pacing SET next_allowed_at=:next WHERE domain=:domain"
                        ),
                        {"domain": admission.domain, "next": slot + timedelta(seconds=1 / rate)},
                    )
                    for params in keys:
                        connection.execute(
                            text("""
                            UPDATE meta.http_daily_budget SET request_count=request_count+1
                            WHERE scope=:scope AND scope_key=:key AND day_utc=:day
                            """),
                            params,
                        )
        except SQLAlchemyError:
            raise PolicyStop("http_budget_storage_unavailable") from None
        if denied:
            raise PolicyStop("http_daily_budget_exhausted")
        return delay

    def stop(self, source_id: str, origin: str, status_code: int) -> None:
        try:
            with self.engine.begin() as connection:
                connection.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                    {"key": "http-source:" + source_id},
                )
                for scope, key in (("source", source_id), ("origin", origin)):
                    connection.execute(
                        text("""
                        INSERT INTO meta.http_policy_stop(scope, scope_key, reason_code, status_code)
                        VALUES (:scope, :key, 'challenge', :status) ON CONFLICT DO NOTHING
                        """),
                        {"scope": scope, "key": key, "status": status_code},
                    )
                # Never wait on an outer collection transaction holding the source row.
                connection.execute(
                    text("""
                    UPDATE meta.source SET status='disabled' WHERE source_id IN
                    (SELECT source_id FROM meta.source WHERE source_id=:source FOR UPDATE SKIP LOCKED)
                    """),
                    {"source": source_id},
                )
        except SQLAlchemyError:
            raise PolicyStop("http_stop_storage_unavailable") from None


class MemoryBudgetBackend:
    """Explicit inert-test injection, never the production/default fallback."""

    def __init__(self) -> None:
        self.counts: dict[tuple[str, str, date], int] = {}
        self.limits: dict[tuple[str, str, date], int] = {}
        self.pacing: dict[str, tuple[datetime, float]] = {}
        self.stops: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    def reserve(self, admission: Admission, now: datetime) -> float:
        admission.validate()
        now = _utc(now)
        with self._lock:
            if ("source", admission.source_id) in self.stops or (
                "origin",
                admission.origin,
            ) in self.stops:
                raise PolicyStop("http_source_disabled")
            rows = [
                (("domain", admission.domain, now.date()), min(500, admission.domain_limit)),
                (("source", admission.source_id, now.date()), admission.source_limit),
            ]
            for key, cap in rows:
                self.limits[key] = min(cap, self.limits.get(key, cap))
            if any(self.counts.get(key, 0) >= self.limits[key] for key, _ in rows):
                raise PolicyStop("http_daily_budget_exhausted")
            previous, rate = self.pacing.get(admission.domain, (now, admission.max_rps))
            rate = min(rate, admission.max_rps)
            slot = max(now, previous)
            self.pacing[admission.domain] = (slot + timedelta(seconds=1 / rate), rate)
            for key, _ in rows:
                self.counts[key] = self.counts.get(key, 0) + 1
            return (slot - now).total_seconds()

    def check(self, source_id: str, origin: str) -> None:
        with self._lock:
            if ("source", source_id) in self.stops or ("origin", origin) in self.stops:
                raise PolicyStop("http_source_disabled")

    def stop(self, source_id: str, origin: str, status_code: int) -> None:
        with self._lock:
            self.stops.update({("source", source_id), ("origin", origin)})
