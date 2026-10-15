"""Recompute KPI numerators from bounded internal evidence, without SQL or HTTP."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import sqlglot
from sqlglot import exp

from ketrika.copilot.sql_guard import validate_and_sanitize_sql
from ketrika.core.provenance import ArtifactReference, ProofError, ProvenanceVerifier
from ketrika.core.provenance_audit import POLICIES, bind_observation
from ketrika.core.qualification import QualificationSafetyError
from ketrika.core.qualification_reports import evidence_path
from ketrika.core.registry import REQUIRED_SOURCES


def rows(document: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    result = document.get(key)
    if not isinstance(result, list) or not result or len(result) > 100000:
        raise QualificationSafetyError("metric_rows_missing")
    if any(not isinstance(row, dict) for row in result):
        raise QualificationSafetyError("metric_row_invalid")
    return result


def integer(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise QualificationSafetyError("metric_invalid_count")
    return value


def number(value: Any) -> float:
    if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        raise QualificationSafetyError("metric_invalid_number")
    return float(value)


def measurement(
    numerator: int | float, denominator: int, passed: bool, **details: Any
) -> dict[str, Any]:
    return {"numerator": numerator, "denominator": denominator, "passed": passed, **details}


def _observation(table: str, values: dict[str, Any]) -> Any:
    policy = POLICIES.get(table)
    if policy is None:
        raise QualificationSafetyError("metric_unknown_observation")
    columns = {column.name: column for column in policy.model.__table__.columns}
    if not values or set(values) - columns.keys():
        raise QualificationSafetyError("metric_unknown_field")
    converted = copy.deepcopy(values)
    for name, value in values.items():
        if value is None:
            continue
        kind = columns[name].type.python_type
        if kind in (UUID, Decimal, date, datetime):
            if not isinstance(value, str):
                raise QualificationSafetyError("metric_exact_value_required")
            converted[name] = kind.fromisoformat(value) if kind in (date, datetime) else kind(value)
        elif kind in (bool, int, str) and type(value) is not kind:
            raise QualificationSafetyError("metric_invalid_scalar")
    return policy.model(**converted)


def provenance(document: dict[str, Any], root: Path) -> dict[str, Any]:
    objects = rows(document, "references")
    references: dict[UUID, ArtifactReference] = {}
    paths: dict[str, Path] = {}
    for item in objects:
        reference = ArtifactReference(
            UUID(item["source_record_id"]),
            item["source_id"],
            item["object_key"],
            item["content_sha256"],
            item["mime_type"],
        )
        path = evidence_path(root, item["file"])
        if reference.source_record_id in references or (
            reference.object_key in paths and paths[reference.object_key] != path
        ):
            raise QualificationSafetyError("metric_duplicate_reference")
        references[reference.source_record_id] = reference
        paths[reference.object_key] = path
    observations = rows(document, "observations")
    claims = []
    llm_observations: list[UUID] = []
    binding_failures: Counter[str] = Counter()
    for item in observations:
        value = _observation(item["table"], item["values"])
        method = getattr(value, "extraction_method", "") or ""
        if method.startswith("llm") or method == "dual_agree":
            llm_observations.append(value.observation_id)
        try:
            claims.append(bind_observation(item["table"], value))
        except ProofError as error:
            binding_failures[str(error)] += 1

    class Reader:
        def get(self, object_key: str) -> bytes:
            return paths[object_key].read_bytes()

    report = ProvenanceVerifier(Reader(), references).verify(claims)
    valid_ids = {result.observation_id for result in report.results if result.passed}
    failed = Counter(result.reason for result in report.results if not result.passed)
    failed.update(binding_failures)
    return measurement(
        report.valid,
        len(observations),
        report.valid == len(observations),
        percent=100 * report.valid / len(observations),
        llm_unverified=sum(identity not in valid_ids for identity in llm_observations),
        objects_read=report.objects_read,
        failure_reasons=dict(failed),
    )


def source_counts(
    document: dict[str, Any], registry: dict[str, Any], root: Path, now: datetime
) -> dict[str, Any]:
    observed = rows(document, "sources")
    index = {item["source_id"]: item for item in observed}
    if len(index) != len(observed) or set(index) - set(REQUIRED_SOURCES):
        raise QualificationSafetyError("metric_duplicate_or_unknown_source")
    qualified = []
    details = {}
    for source_id in REQUIRED_SOURCES:
        definition = registry.get(source_id)
        item = index.get(source_id)
        status = getattr(definition, "status", "missing")
        accepted = bool(
            item
            and status in ("active", "degraded")
            and item.get("status") == status
            and item.get("source_record_ids")
            and item.get("acquisition_receipt")
            and item.get("permission_receipt")
            and any(
                entry.verified_at is not None for entry in getattr(definition, "entrypoints", [])
            )
            and (status != "degraded" or item.get("blocker_id"))
        )
        if accepted and item:
            acquisition = json.loads(evidence_path(root, item["acquisition_receipt"]).read_bytes())
            permission = json.loads(evidence_path(root, item["permission_receipt"]).read_bytes())
            identities = [UUID(value) for value in item["source_record_ids"]]
            fetched_at = datetime.fromisoformat(acquisition["fetched_at"])
            age = (now - fetched_at).total_seconds()
            accepted = (
                len(identities) == len(set(identities))
                and acquisition.get("source_id") == source_id
                and acquisition.get("http_status") == 200
                and acquisition.get("source_record_ids") == item["source_record_ids"]
                and acquisition.get("runtime_observed") is True
                and 0 <= age <= getattr(definition, "freshness_sla_days", 0) * 86400
                and permission.get("source_id") == source_id
                and permission.get("crawl_permission")
                == getattr(definition, "crawl_permission", None)
                and permission.get("status") == "approved"
            )
        if accepted:
            qualified.append(source_id)
        details[source_id] = {
            "registry_status": status,
            "receipt_present": item is not None,
            "qualified_in_receipt": accepted,
        }
    return measurement(
        len(qualified),
        len(REQUIRED_SOURCES),
        len(qualified) == len(REQUIRED_SOURCES),
        sources=details,
        target=9,
    )


def parsing(document: dict[str, Any]) -> dict[str, Any]:
    runs = rows(document, "runs")
    seen = set()
    total = parsed = 0
    rates = []
    for run in runs:
        identity = UUID(run["run_id"])
        if identity in seen:
            raise QualificationSafetyError("metric_duplicate_run")
        seen.add(identity)
        count = integer(run["n_candidates"])
        valid = integer(run["n_parsed"])
        if not count or valid > count or run["status"] != "success":
            raise QualificationSafetyError("metric_incomplete_run")
        total += count
        parsed += valid
        rates.append(100 * valid / count)
    return measurement(
        parsed,
        total,
        min(rates) >= 99,
        percent=100 * parsed / total,
        minimum_run_percent=min(rates),
    )


def golden(document: dict[str, Any]) -> dict[str, Any]:
    fields = rows(document, "fields")
    grouped: dict[str, list[bool]] = defaultdict(list)
    sources = set()
    for field in fields:
        source = field["source_id"]
        if source not in ("miasa_odr", "mincc_ppn"):
            raise QualificationSafetyError("metric_unknown_golden_source")
        sources.add(source)
        grouped[source + ":" + field["field"]].append(
            type(field["actual"]) is type(field["expected"])
            and field["actual"] == field["expected"]
        )
    rates = {
        key: {
            "numerator": sum(values),
            "denominator": len(values),
            "percent": 100 * sum(values) / len(values),
        }
        for key, values in grouped.items()
    }
    matched = sum(item["numerator"] for item in rates.values())
    return measurement(
        matched,
        len(fields),
        sources == {"miasa_odr", "mincc_ppn"}
        and all(item["percent"] >= 99 for item in rates.values()),
        fields=rates,
        annotated_sources=sorted(sources),
    )


def rebuild(document: dict[str, Any]) -> dict[str, Any]:
    before = rows(document, "before")
    after = rows(document, "after")

    def encode(values: list[dict[str, Any]]) -> bytes:
        return json.dumps(
            sorted(
                json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                for row in values
            ),
            separators=(",", ":"),
        ).encode()

    first, second = (
        hashlib.sha256(encode(before)).hexdigest(),
        hashlib.sha256(encode(after)).hexdigest(),
    )
    requests = integer(document["network_requests"])
    changed = abs(len(before) - len(after))
    return measurement(
        changed,
        len(before),
        first == second and requests == 0,
        before_count=len(before),
        after_count=len(after),
        before_sha256=first,
        after_sha256=second,
        network_requests=requests,
        content_identical=first == second,
    )


def forecasts(document: dict[str, Any]) -> dict[str, Any]:
    series = rows(document, "series")
    seen = set()
    valid = 0
    for item in series:
        identity = item["series_id"]
        if not isinstance(identity, str) or not identity or identity in seen:
            raise QualificationSafetyError("metric_duplicate_series")
        seen.add(identity)
        wape = number(item["wape"])
        accepted = (
            integer(item["forecast_count"]) > 0
            and integer(item["backtest_windows"]) > 0
            and item.get("leakage_detected") is False
            and isinstance(item.get("training_snapshot_sha256"), str)
            and len(item["training_snapshot_sha256"]) == 64
        )
        valid += accepted
        if wape < 0:
            raise QualificationSafetyError("metric_invalid_wape")
    return measurement(valid, len(series), valid >= 10, target=10)


def api_latency(document: dict[str, Any]) -> dict[str, Any]:
    groups: dict[str, list[float]] = defaultdict(list)
    for sample in rows(document, "samples"):
        if sample["status_code"] != 200:
            raise QualificationSafetyError("metric_api_error")
        groups[sample["endpoint"]].append(number(sample["elapsed_ms"]))
    percentiles = {}
    for endpoint, samples in groups.items():
        ordered = sorted(samples)
        rank = 0.95 * (len(ordered) - 1)
        lower = int(rank)
        p95 = ordered[lower] + (ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower]) * (
            rank - lower
        )
        percentiles[endpoint] = {"samples": len(ordered), "p95_ms": p95}
    required = {
        "/v1/prices",
        "/v1/prices/latest",
        "/v1/stocks",
        "/v1/trade",
        "/v1/kpis/market-health",
        "/v1/weather/anomalies",
    }
    passed = required <= set(groups) and all(
        item["samples"] >= 200 and item["p95_ms"] < 1000 for item in percentiles.values()
    )
    return measurement(
        sum(item["samples"] for item in percentiles.values()),
        len(groups),
        passed,
        endpoints=percentiles,
    )


def copilot(document: dict[str, Any]) -> dict[str, Any]:
    questions = rows(document, "questions")
    correct = forbidden = 0
    seen = set()
    for question in questions:
        if question["question_id"] in seen:
            raise QualificationSafetyError("metric_duplicate_question")
        seen.add(question["question_id"])
        try:
            sql = validate_and_sanitize_sql(question["sql"])
            tables = {table.name for table in sqlglot.parse_one(sql).find_all(exp.Table)}
            correct += question["expected_view"].removeprefix("gold.") in tables
        except ValueError:
            forbidden += 1
    rate = 100 * correct / len(questions)
    return measurement(
        correct, len(questions), rate >= 80 and forbidden == 0, percent=rate, forbidden=forbidden
    )


def bulletin(document: dict[str, Any]) -> dict[str, Any]:
    values = rows(document, "numbers")
    facts = document.get("facts")
    if not isinstance(facts, dict):
        raise QualificationSafetyError("metric_bulletin_facts_missing")
    unreferenced = 0
    for item in values:
        fact = facts.get(item["fact_id"])
        if not isinstance(fact, dict) or not fact.get("citation"):
            unreferenced += 1
            continue
        try:
            actual, expected = Decimal(item["value"]), Decimal(fact["value"])
            unreferenced += not actual.is_finite() or not expected.is_finite() or actual != expected
        except (ValueError, ArithmeticError):
            unreferenced += 1
    return measurement(unreferenced, len(values), unreferenced == 0)
