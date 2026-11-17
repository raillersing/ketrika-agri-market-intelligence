"""Real SQL/phase/S3 receipts; mocked HTTP bytes do NOT qualify a live source."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text

from ketrika.connectors import manual_collection as manual
from ketrika.core.db import get_session
from ketrika.core.http import PoliteHttpClient
from ketrika.core.registry import find_repo_root

pytestmark = pytest.mark.integration


def test_real_phases_and_receipts_no_repeat_on_same_request(monkeypatch):
    request_id = uuid4()
    fixture = find_repo_root() / "backend/tests/fixtures/authentic/world_bank_rtfp"
    wire = []

    def transport(request):
        wire.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        filename = (
            "mdg_study_20261005.json"
            if "/metadata/" in request.url.path
            else "mdg_close_estimates_20261015.json"
        )
        document = json.loads((fixture / filename).read_bytes())
        document["_ketrika_test"] = {"scope": "synthetic-http-envelope", "request": str(request_id)}
        return httpx.Response(200, json=document)

    monkeypatch.setattr(
        manual,
        "PoliteHttpClient",
        lambda **kwargs: PoliteHttpClient(**kwargs, transport=httpx.MockTransport(transport)),
    )
    # Publication is real too: synthetic historical QA may legitimately be withheld.
    result = manual.collect(request_id, "wb_rtfp_mdg")
    assert result["status"] in {"succeeded", "partial"}
    assert len(result["outcomes"]) == 1
    outcome = result["outcomes"][0]
    assert outcome["status"] == "success"
    assert outcome["scope"] == "bounded_recent_modeled_rice_estimates_not_full_market"
    data_url = next(url for url in wire if "/api/tables/data/" in url)
    selection = parse_qs(urlsplit(data_url).query)
    assert selection["limit"] == ["120"]
    assert selection["c[price_date]"]
    assert outcome["n_fetched"] == 2
    assert outcome["n_rejected"] == 0
    assert outcome["run_id"]
    assert result["publication"] in {"succeeded", "failed"}
    before = len(wire)
    assert before >= 2
    assert manual.collect(request_id, "wb_rtfp_mdg") == result
    assert len(wire) == before
    with get_session() as session:
        assert (
            session.scalar(
                text("""
            SELECT count(*) FROM meta.ingestion_run WHERE dagster_run_id=:id
        """),
                {"id": str(request_id)},
            )
            == 1
        )
        assert (
            session.scalar(
                text("""
            SELECT count(*) FROM meta.ingestion_batch_member WHERE run_id=:id
        """),
                {"id": outcome["run_id"]},
            )
            == 2
        )
    with pytest.raises(manual.CollectionError, match="idempotency_conflict"):
        manual.collect(request_id, None)


def test_concurrent_clicks_and_live_poll_do_not_recover_active_owner(monkeypatch):
    started, release = Event(), Event()
    request_id = uuid4()
    monkeypatch.setattr(manual, "eligible_sources", lambda: ["miasa_odr"])

    def hold(sid, identifier, outcomes):
        started.set()
        assert release.wait(20)
        return {"source_id": sid, "status": "failed"}

    monkeypatch.setattr(manual, "_collect_source", hold)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(manual.collect, request_id, None)
        try:
            assert started.wait(10)
            assert manual.read_collection(request_id)["status"] == "running"
            assert manual.collect(request_id, None)["status"] == "running"
            with pytest.raises(manual.CollectionError, match="collection_busy"):
                manual.collect(uuid4(), None)
        finally:
            release.set()
        assert future.result(timeout=20)["status"] == "failed"


def test_orphan_is_interrupted_never_automatically_recollected(monkeypatch):
    request_id = uuid4()
    with get_session() as session:
        session.execute(
            text("""
            INSERT INTO meta.collection_request(request_id,status,stage,source_ids)
            VALUES (:id,'running','bronze:miasa_odr','["miasa_odr"]')
        """),
            {"id": request_id},
        )
    monkeypatch.setattr(manual, "_collect_source", lambda *args: pytest.fail("ambiguous retry"))
    result = manual.read_collection(request_id)
    assert result["status"] == "interrupted" and result["finished_at"]
    assert manual.collect(request_id, None) == result


@pytest.mark.parametrize(
    "sid", ["wfp_hdx_mdg", "nasa_power", "chirps", "dummy_csv", "not_registered"]
)
def test_ineligible_sources_never_reach_phase_owner(monkeypatch, sid):
    monkeypatch.setattr(manual, "eligible_sources", lambda: [])
    monkeypatch.setattr(manual, "_collect_source", lambda *args: pytest.fail("ineligible wire"))
    with pytest.raises(manual.CollectionError, match="not_eligible"):
        manual.collect(uuid4(), sid)


def test_source_failure_does_not_abort_independent_sources_and_gold_refusal_is_partial(monkeypatch):
    monkeypatch.setattr(manual, "eligible_sources", lambda: ["first", "second"])
    monkeypatch.setattr(
        manual,
        "_collect_source",
        lambda sid, *args: {
            "source_id": sid,
            "status": "failed" if sid == "first" else "success",
            "n_records": 0,
        },
    )

    def refuse(*args, **kwargs):
        raise ValueError("private-source-content")

    monkeypatch.setattr(manual, "refresh_gold_views", refuse)
    result = manual.collect(uuid4(), None)
    assert result["status"] == "partial" and result["publication"] == "failed"
    assert len(result["outcomes"]) == 2 and "private" not in str(result)
