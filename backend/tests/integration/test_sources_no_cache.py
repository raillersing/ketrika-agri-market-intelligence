"""Isolated DataOps HTTP/SQL; prepared only, not concurrent with main check."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from ketrika.api.main import app
from ketrika.core.db import get_session
from ketrika.core.models.db import IngestionRun, Source
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.gold.refresh import refresh_gold_views


def price_signature(session):
    return session.execute(
        text(
            "SELECT count(*), md5(coalesce(string_agg(to_jsonb(p)::text, ',' "
            "ORDER BY observation_id), '')) FROM obs.price_observation p"
        )
    ).one()


@pytest.mark.integration
@pytest.mark.parametrize("populated", [False, True], ids=["unpublished", "stale-cache"])
def test_source_api_uses_meta_runs_without_publishing_prices(request, populated):
    source_id = f"dummy_source_api_{uuid4().hex}"
    old_started = datetime(2026, 1, 1, tzinfo=UTC)
    new_started = datetime(2026, 1, 2, tzinfo=UTC)
    with get_session() as session:
        target = session.get_bind().engine.url
        require_synthetic_test_database(target.host, target.database)
        before_prices = price_signature(session)
        before_views = session.execute(
            text(
                "SELECT matviewname, ispopulated FROM pg_matviews WHERE schemaname='gold' "
                "AND matviewname LIKE 'price_%' ORDER BY matviewname"
            )
        ).all()
        session.add(
            Source(
                source_id=source_id,
                status="disabled",
                spec={"name": "Synthetic metadata only", "verified": False, "priority": "P2"},
            )
        )
        session.flush()
        session.add(
            IngestionRun(
                run_id=uuid4(),
                source_id=source_id,
                started_at=old_started,
                finished_at=old_started,
                status="success",
            )
        )
    with get_session() as session:
        if populated:
            metadata = refresh_gold_views(session, views=["source_health"])
            assert metadata["views_refreshed"] == ["source_health"]
            assert metadata["source_observations_total"] == 0
        else:
            # Exact guarded disposable metadata cache only; no Bronze or
            # Silver reset and no modification of numerical Gold caches.
            session.execute(text("REFRESH MATERIALIZED VIEW gold.source_health WITH NO DATA"))
        session.add(
            IngestionRun(
                run_id=uuid4(),
                source_id=source_id,
                started_at=new_started,
                finished_at=new_started,
                status="failed",
                error="RuntimeError",
            )
        )
    try:
        with TestClient(app) as client:
            response = client.get("/v1/sources")
            assert response.status_code == 200
            item = next(row for row in response.json() if row["source_id"] == source_id)
            assert item["latest_run_status"] == "failed"
            assert datetime.fromisoformat(item["last_run_started_at"]) == new_started
            if not populated:
                assert item["freshness_days"] is None and item["is_stale"] is None
            health = client.get(f"/v1/sources/{source_id}/health")
            if populated:
                assert health.status_code == 200
                assert health.json()["latest_run_status"] == "failed"
                assert datetime.fromisoformat(health.json()["last_run_started_at"]) == new_started
            else:
                assert health.status_code == 503
                assert health.headers["content-type"].startswith("application/problem+json")
                assert health.json()["status"] == 503 and health.json()["type"] == "about:blank"
                assert "parse_success_rate" not in health.json()
        with get_session() as session:
            state = session.scalar(
                text(
                    "SELECT ispopulated FROM pg_matviews WHERE schemaname='gold' "
                    "AND matviewname='source_health'"
                )
            )
            assert state is populated
            current = session.scalar(
                select(IngestionRun.status).where(
                    IngestionRun.source_id == source_id, IngestionRun.started_at == new_started
                )
            )
            assert current == "failed"
            if populated:
                cached = session.scalar(
                    text("SELECT latest_run_status FROM gold.source_health WHERE source_id=:sid"),
                    {"sid": source_id},
                )
                assert cached == "success"
            assert price_signature(session) == before_prices
            assert (
                session.execute(
                    text(
                        "SELECT matviewname, ispopulated FROM pg_matviews WHERE schemaname='gold' "
                        "AND matviewname LIKE 'price_%' ORDER BY matviewname"
                    )
                ).all()
                == before_views
            )
            request.node.user_properties.append(
                (
                    "ketrika.sources.no_cache",
                    json.dumps(
                        {
                            "source_id": source_id,
                            "cache_populated": populated,
                            "meta_latest_run": "failed",
                            "price_signature_unchanged": True,
                            "numerical_gold_not_refreshed": True,
                            "scope": "synthetic metadata SQL/API only; no source, market or DQ metric qualification",
                        }
                    ),
                )
            )
    finally:
        if not populated:
            with get_session() as session:
                refresh_gold_views(session, views=["source_health"])
