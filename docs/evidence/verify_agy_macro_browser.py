"""QA-only synthetic Silver inspection; not source or macro Gold qualification.

Run only after the frozen check and official E2E, in their isolated browser image.
Adds its own clearly synthetic source/record/observation and immutable Bronze object.
Never changes/deletes existing objects, observations or publication views.
"""

import hashlib
import json
import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.models.db import MacroObservation, Source, SourceRecord
from ketrika.core.qualification import validate_environment


def main() -> None:
    validate_environment(os.environ)
    source_id = "synthetic_browser_macro_" + uuid4().hex
    observation_id, record_id = uuid4(), uuid4()
    payload = {"dataset": "synthetic", "value_raw": "123,25", "value_kind": "imputed"}
    content = json.dumps(payload, sort_keys=True).encode()
    store = BronzeStore()
    assert store.bucket == "ketrika-qa-bronze"
    artifact = store.put(
        source_id=source_id,
        content=content,
        mime_type="application/json",
        url="https://example.invalid/synthetic-browser-macro",
        retrieved_via="manual_upload",
        http_status=0,
        http_headers={"x-ketrika-dataset": "synthetic;verified=false"},
    )
    assert store.get(artifact.object_key) == content
    assert artifact.content_sha256 == hashlib.sha256(content).hexdigest()
    with get_session() as session:
        session.add(Source(source_id=source_id, status="disabled", spec={"synthetic": True}))
        session.flush()
        session.add(
            SourceRecord(
                source_record_id=record_id,
                source_id=source_id,
                source_url=artifact.url,
                object_key=artifact.object_key,
                content_sha256=artifact.content_sha256,
                mime_type="application/json",
                fetched_at=datetime.now(UTC),
                parser_version="synthetic-inspection-v1",
                extraction_status="parsed",
                retrieved_via="manual_upload",
                http_status=0,
            )
        )
        session.flush()
        session.add(
            MacroObservation(
                observation_id=observation_id,
                source_record_id=record_id,
                natural_key=hashlib.sha256(source_id.encode()).hexdigest(),
                indicator_code="SYNTHETIC_BROWSER_INSPECTION",
                indicator_name="Synthetic only",
                frequency="monthly",
                unit="index_points",
                geo_scope="synthetic",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
                first_available_at=datetime.now(UTC),
                value=Decimal("123.25"),
                value_raw=payload["value_raw"],
                observed_or_imputed="imputed",
                extraction_method="deterministic",
                evidence=payload,
                confidence=Decimal("1"),
                review_status="accepted",
            )
        )
    with get_session() as session:
        reread = session.get(MacroObservation, observation_id)
        assert reread is not None and reread.value == Decimal("123.25")
        assert reread.source_record_id == record_id
    directory = Path("/app/.venv/qa-browser-results") / ("macro-" + uuid4().hex)
    directory.mkdir(parents=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(base_url="http://web:3000")
        page = context.new_page()
        page.set_default_navigation_timeout(120000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("/login")
        page.locator('input[type="email"]').fill("admin@ketrika.local")
        page.locator('input[type="password"]').fill("change-me")
        page.locator('form button[type="submit"]').click()
        expect(page).to_have_url("http://web:3000/", timeout=120000)
        response = context.request.get(f"/api/v1/macro/{observation_id}/provenance")
        assert response.status == 200
        data = response.json()
        assert data["observation_id"] == str(observation_id)
        assert data["source_record_id"] == str(record_id)
        assert data["value"] == 123.25 and data["value_raw"] == "123,25"
        assert data["value_kind"] == "imputed"
        assert data["qualification_state"] == "not_qualified"
        assert data["content_sha256"] == artifact.content_sha256
        page.goto(f"/macro/observations/{observation_id}")
        for viewport in [None, {"width": 390, "height": 844}]:
            if viewport:
                page.set_viewport_size(viewport)
            page.reload()
            expect(page.get_by_role("heading", name="SYNTHETIC_BROWSER_INSPECTION")).to_be_visible()
            values = page.locator("dd").all_text_contents()
            assert "123.25 index_points" in values and "123,25" in values
            assert str(record_id) in values and artifact.object_key in values
            assert artifact.content_sha256 in values
            assert "non qualifiée" in page.get_by_role("status").inner_text()
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            if viewport:
                box = page.get_by_role("main").first.bounding_box()
                assert box is not None and box["width"] >= 360 and box["x"] <= 16
        page.screenshot(path=str(directory / "macro-inspection-390.png"), full_page=True)
        assert not errors, errors
        browser.close()
    receipt = {
        "passed": True,
        "scope": "synthetic QA Silver inspection only; not macro Gold",
        "observation_id": str(observation_id),
        "source_record_id": str(record_id),
        "object_key": artifact.object_key,
        "sha256": artifact.content_sha256,
        "qualification_state": "not_qualified",
        "value_kind": "imputed",
        "checks": [
            "Bronze reread",
            "SQL reread",
            "authenticated HTTP API",
            "native value and lineage in UI",
            "reload",
            "390px no overflow",
        ],
    }
    (directory / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
