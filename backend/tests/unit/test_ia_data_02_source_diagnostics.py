"""Unit tests for IA-DATA-02: Source DataOps diagnostics and health classification.

Normative requirements:
1. 8 canonical DataOps operational states:
   - downloaded, parsed, normalized, published, no_data, policy_blocked, schema_drift, failed, idle.
2. Sanitization & secrecy: No raw passwords, connection strings, auth tokens or filesystem paths
   may ever leak into diagnostic_code or diagnostic_message.
3. Stable diagnostic codes: Standardized uppercase identifiers (e.g. POLICY_STOP_ROBOTS, UPSTREAM_TIMEOUT).
4. API contracts: SourceItem, SourceHealthItem, and SourceRunItem must expose diagnostic metadata.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ketrika.api.main import app
from ketrika.core.db import get_db
from ketrika.core.diagnostics import (
    classify_run_diagnostic,
    sanitize_diagnostic_error,
)

pytestmark = pytest.mark.usefixtures("authenticated_unit_reader")


def test_sanitize_diagnostic_error_all_categories() -> None:
    """Test sanitization of errors into deterministic status, code, and user message."""
    # 1. Null / empty
    status, code, msg, cat = sanitize_diagnostic_error(None)
    assert status == "failed"
    assert code == "COLLECTION_FAILED"
    assert cat == "unknown"

    status, code, msg, cat = sanitize_diagnostic_error("")
    assert status == "failed"
    assert code == "COLLECTION_FAILED"

    # 2. Policy stopped: robots.txt
    status, code, msg, cat = sanitize_diagnostic_error("Disallowed by robots.txt policy rule")
    assert status == "policy_blocked"
    assert code == "POLICY_STOP_ROBOTS"
    assert cat == "policy"
    assert "robots.txt" in msg

    # 3. Policy stopped: rate / budget
    status, code, msg, cat = sanitize_diagnostic_error(
        "HTTP 429 Too Many Requests: Rate limit exceeded"
    )
    assert status == "policy_blocked"
    assert code == "POLICY_STOP_RATE_LIMIT"
    assert cat == "policy"

    # 4. Policy stopped: auth required
    status, code, msg, cat = sanitize_diagnostic_error("HTTP 403 Forbidden: credentials missing")
    assert status == "policy_blocked"
    assert code == "POLICY_STOP_AUTH_REQUIRED"
    assert cat == "policy"

    # 5. Policy stopped: general policy stop
    status, code, msg, cat = sanitize_diagnostic_error(
        "PolicyStop: source disabled by administrator"
    )
    assert status == "policy_blocked"
    assert code == "POLICY_STOP_BLOCKED"
    assert cat == "policy"

    # 6. Schema drift: mismatch
    status, code, msg, cat = sanitize_diagnostic_error(
        "SchemaDrift: column 'price_ariary' unexpected shape"
    )
    assert status == "schema_drift"
    assert code == "SCHEMA_DRIFT_MISMATCH"
    assert cat == "schema"

    # 7. Schema drift: contract absent
    status, code, msg, cat = sanitize_diagnostic_error(
        "contract_absent: no registered schema for format"
    )
    assert status == "schema_drift"
    assert code == "SCHEMA_CONTRACT_ABSENT"
    assert cat == "schema"

    # 8. Network: connect error
    status, code, msg, cat = sanitize_diagnostic_error(
        "httpx.ConnectError: [Errno 111] Connection refused"
    )
    assert status == "failed"
    assert code == "UPSTREAM_CONNECT_ERROR"
    assert cat == "network"

    # 9. Network: timeout
    status, code, msg, cat = sanitize_diagnostic_error(
        "httpx.ReadTimeout: The read operation timed out"
    )
    assert status == "failed"
    assert code == "UPSTREAM_TIMEOUT"
    assert cat == "network"

    # 10. Upstream server: 5xx
    status, code, msg, cat = sanitize_diagnostic_error("HTTP 502 Bad Gateway from upstream host")
    assert status == "failed"
    assert code == "UPSTREAM_HTTP_500"
    assert cat == "upstream"

    # 11. Upstream 404
    status, code, msg, cat = sanitize_diagnostic_error("HTTP 404 Not Found: dataset removed")
    assert status == "failed"
    assert code == "UPSTREAM_HTTP_404"
    assert cat == "upstream"


def test_sanitize_diagnostic_error_strictly_protects_secrets() -> None:
    """Ensure that database passwords, auth tokens, and server paths are never leaked."""
    sensitive_error = (
        "Fatal error connecting to postgresql://ketrika_admin:SuperSecretPass123!@db-prod.internal:5432/ketrika_db "
        "with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token_payload.secret_signature "
        "at /home/raillersing/projects/hahitantsoa-titan-erp/backend/src/secret_worker.py:42"
    )
    status, code, msg, cat = sanitize_diagnostic_error(sensitive_error)
    assert status == "failed"
    assert code == "COLLECTION_FAILED"
    # Verify zero leakage
    for forbidden in [
        "SuperSecretPass123",
        "ketrika_admin",
        "eyJhbGci",
        "db-prod.internal",
        "/home/raillersing",
    ]:
        assert forbidden not in code
        assert forbidden not in msg


def test_classify_run_diagnostic_all_operational_states() -> None:
    """Test full matrix of 8 canonical DataOps operational states."""
    # 1. Idle (never run)
    diag = classify_run_diagnostic(status=None)
    assert diag.diagnostic_status == "idle"
    assert diag.diagnostic_code == "IDLE_NOT_RUN"

    # 2. Running
    diag = classify_run_diagnostic(status="running")
    assert diag.diagnostic_status == "downloaded"
    assert diag.diagnostic_code == "IN_PROGRESS"

    # 3. No data: 0 records, 0 fetched
    diag = classify_run_diagnostic(status="success", n_records=0, n_fetched=0)
    assert diag.diagnostic_status == "no_data"
    assert diag.diagnostic_code == "NO_NEW_DATA"

    # 4. No data: fetched docs but 0 observations parsed
    diag = classify_run_diagnostic(status="success", n_records=0, n_fetched=2)
    assert diag.diagnostic_status == "no_data"
    assert diag.diagnostic_code == "NO_OBSERVATIONS_PARSED"

    # 5. Published: verified in Gold
    diag = classify_run_diagnostic(
        status="success", n_records=850, n_fetched=1, has_published_gold=True
    )
    assert diag.diagnostic_status == "published"
    assert diag.diagnostic_code == "PUBLISHED_GOLD"
    assert "850 obs" in diag.diagnostic_message

    # 6. Normalized: Silver with review items
    diag = classify_run_diagnostic(
        status="success",
        n_records=300,
        n_fetched=1,
        has_published_gold=False,
        open_review_items=4,
    )
    assert diag.diagnostic_status == "normalized"
    assert diag.diagnostic_code == "REVIEW_REQUIRED"
    assert diag.error_category == "review"
    assert "4 élément(s) en attente" in diag.diagnostic_message

    # 7. Normalized: Silver clean
    diag = classify_run_diagnostic(
        status="success",
        n_records=300,
        n_fetched=1,
        has_published_gold=False,
        open_review_items=0,
    )
    assert diag.diagnostic_status == "normalized"
    assert diag.diagnostic_code == "NORMALIZED_SILVER"

    # 8. Failed: Network timeout
    diag = classify_run_diagnostic(status="failed", error="ConnectTimeout: host unreachable")
    assert diag.diagnostic_status == "failed"
    assert diag.diagnostic_code in ("UPSTREAM_CONNECT_ERROR", "UPSTREAM_TIMEOUT")

    # 9. Policy blocked: Explicit blocked status
    diag = classify_run_diagnostic(status="blocked")
    assert diag.diagnostic_status == "policy_blocked"
    assert diag.diagnostic_code == "POLICY_STOP_BLOCKED"

    # 10. Schema drift via failed error
    diag = classify_run_diagnostic(
        status="failed", error="contract_absent: schema validation failed"
    )
    assert diag.diagnostic_status == "schema_drift"
    assert diag.diagnostic_code == "SCHEMA_CONTRACT_ABSENT"


def test_api_sources_list_exposes_diagnostics() -> None:
    """Verify GET /v1/sources returns diagnostic fields for each source."""
    client = TestClient(app)
    mock_session = MagicMock()

    # Mock DB query in list_sources:
    # 0: source_id, 1: name, 2: priority, 3: status, 4: freshness_sla_days,
    # 5: freshness_days, 6: is_stale, 7: latest_run_status, 8: last_run_started_at,
    # 9: n_records, 10: n_fetched, 11: error, 12: open_review_items, 13: n_records_30d
    mock_rows = [
        (
            "wb_rtfp_mdg",
            "World Bank RTFP",
            "P0",
            "active",
            30,
            5,
            False,
            "success",
            None,
            96,
            1,
            None,
            0,
            96,
        ),
        (
            "faostat_blocked",
            "FAOSTAT Price Index",
            "P1",
            "disabled",
            60,
            None,
            None,
            "failed",
            None,
            0,
            0,
            "PolicyStop: rate limit exceeded",
            0,
            0,
        ),
    ]
    mock_session.execute.return_value.fetchall.return_value = mock_rows

    with patch("ketrika.api.routers.sources.get_db", return_value=mock_session):
        app.dependency_overrides[get_db] = lambda: mock_session
        try:
            resp = client.get("/v1/sources")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 2

            wb = next(s for s in data if s["source_id"] == "wb_rtfp_mdg")
            assert wb["diagnostic_status"] == "published"
            assert wb["diagnostic_code"] == "PUBLISHED_GOLD"
            assert "96 obs" in wb["diagnostic_message"]

            fao = next(s for s in data if s["source_id"] == "faostat_blocked")
            assert fao["diagnostic_status"] == "policy_blocked"
            assert fao["diagnostic_code"] == "POLICY_STOP_RATE_LIMIT"
        finally:
            app.dependency_overrides.pop(get_db, None)


def test_api_source_health_exposes_diagnostics() -> None:
    """Verify GET /v1/sources/{source_id}/health returns diagnostic fields."""
    client = TestClient(app)
    mock_session = MagicMock()

    # Mock health cache check via session.scalar
    mock_session.scalar.return_value = True

    # Mock health row:
    # 0: source_id, 1: name, 2: priority, 3: sla, 4: freshness_days, 5: is_stale,
    # 6: latest_run_status, 7: last_run_started_at, 8: n_records_30d, 9: parse_rate,
    # 10: open_review, 11: lr_records, 12: lr_fetched, 13: lr_error
    mock_health_row = (
        "miasa_odr",
        "ODR Miasa",
        "P0",
        15,
        2,
        False,
        "success",
        datetime.now(UTC),
        820,
        1.0,
        0,
        820,
        1,
        None,
    )
    mock_session.execute.return_value.fetchone.return_value = mock_health_row

    with patch("ketrika.api.routers.sources.get_db", return_value=mock_session):
        app.dependency_overrides[get_db] = lambda: mock_session
        try:
            resp = client.get("/v1/sources/miasa_odr/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["source_id"] == "miasa_odr"
            assert data["diagnostic_status"] == "published"
            assert data["diagnostic_code"] == "PUBLISHED_GOLD"
        finally:
            app.dependency_overrides.pop(get_db, None)


def test_api_source_runs_exposes_sanitized_diagnostics() -> None:
    """Verify GET /v1/sources/runs returns sanitized diagnostic outcomes."""
    client = TestClient(app)
    mock_session = MagicMock()

    now = datetime.now(UTC)

    # Mock rows for list_recent_runs:
    # 0: run_id, 1: source_id, 2: name, 3: status, 4: started_at, 5: finished_at,
    # 6: duration_seconds, 7: n_records, 8: n_fetched, 9: error
    mock_runs = [
        (
            "run-12345",
            "miasa_odr",
            "ODR Miasa",
            "failed",
            now,
            now,
            1.25,
            0,
            0,
            "httpx.ConnectError: [Errno 111] Connection refused",
        ),
        (
            "run-12346",
            "wb_rtfp_mdg",
            "World Bank RTFP",
            "success",
            now,
            now,
            4.5,
            0,
            0,
            None,
        ),
    ]
    mock_session.execute.return_value.fetchall.return_value = mock_runs

    with patch("ketrika.api.routers.sources.get_db", return_value=mock_session):
        app.dependency_overrides[get_db] = lambda: mock_session
        try:
            resp = client.get("/v1/sources/runs")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 2

            run_fail = data[0]
            assert run_fail["diagnostic_status"] == "failed"
            assert run_fail["diagnostic_code"] == "UPSTREAM_CONNECT_ERROR"
            assert "incident réseau" in run_fail["diagnostic_message"]

            run_empty = data[1]
            assert run_empty["diagnostic_status"] == "no_data"
            assert run_empty["diagnostic_code"] == "NO_NEW_DATA"
        finally:
            app.dependency_overrides.pop(get_db, None)
