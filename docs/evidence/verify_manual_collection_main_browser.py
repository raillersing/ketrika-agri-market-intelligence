"""Read-only owner-lock click/reload diagnostic, not live acquisition proof."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from ketrika.connectors.manual_collection import LOCK_SQL
from ketrika.core.qualification_reports import capture_binding
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import text

from ketrika.core.db import get_session
from ketrika.core.qualification import validate_environment


def budget_total() -> int:
    with get_session() as session:
        return int(
            session.scalar(
                text("SELECT coalesce(sum(request_count),0) FROM meta.http_daily_budget")
            )
        )


def main() -> int:
    expect.set_options(timeout=60000)
    validate_environment(os.environ)
    output = Path("/app/.venv/qa-browser-results") / ("collection-" + uuid.uuid4().hex)
    output.mkdir(parents=True)
    receipt = {
        **capture_binding(Path("/workspace"), os.environ["KETRIKA_SOURCE_COMMIT"]),
        "scope": "read-only owner-lock, real UI/API; no live source qualification",
        "passed": False,
        "fixture": "transient SQL advisory lock, no source policy or observed data changed",
    }
    errors: list[str] = []
    try:
        before = budget_total()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(base_url="http://localhost:3000")
            context.set_default_timeout(60000)
            context.set_default_navigation_timeout(120000)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto("/login")
            page.locator('input[type="email"]').fill("admin@ketrika.local")
            page.locator('input[type="password"]').fill("change-me")
            page.locator('form button[type="submit"]').click()
            expect(page).to_have_url("http://localhost:3000/", timeout=120000)
            assert any(c["name"] == "session_token" and c["httpOnly"] for c in context.cookies())
            history = context.request.get("/api/v1/sources/collections")
            assert history.ok and history.json()
            previous = history.json()[0]
            marker = "Reçu persistant : " + previous["request_id"]
            page.goto("/sources")
            assert page.evaluate("window.isSecureContext") is True
            expect(page.get_by_text(marker, exact=True)).to_be_visible()
            page.get_by_role(
                "textbox", name="Rechercher une source, une institution ou un produit"
            ).fill("wb_rtfp_mdg")
            button = page.get_by_role("button", name="Collecter", exact=True)
            expect(button).to_be_enabled()
            # Simulate a concurrent owner without creating a fake job or a durable stop.
            with get_session() as owner:
                assert owner.scalar(text(LOCK_SQL)) is True
                with page.expect_response(
                    lambda response: (
                        response.request.method == "POST"
                        and response.url.endswith("/api/v1/sources/collect")
                    ),
                    timeout=120000,
                ) as response_info:
                    button.click()
                response = response_info.value
                assert response.status == 409
                assert response.json()["detail"] == "collection_busy"
                request_body = response.request.post_data_json
                assert request_body["source_id"] == "wb_rtfp_mdg"
                expect(
                    page.get_by_text(
                        "Une collecte est déjà en cours, ou cette source n’est pas autorisée. Consultez le suivi.",
                        exact=True,
                    )
                ).to_be_visible()
                page.screenshot(path=str(output / "sources_desktop.png"), full_page=True)
            # Lock is released; the refused click must not have created a receipt.
            with get_session() as session:
                count = session.scalar(
                    text("SELECT count(*) FROM meta.collection_request WHERE request_id=:id"),
                    {"id": request_body["request_id"]},
                )
                assert count == 0
            page.reload()
            expect(page.get_by_text(marker, exact=True)).to_be_visible()
            stored = context.request.get("/api/v1/sources/collections/" + previous["request_id"])
            assert stored.ok and stored.json() == previous
            page.set_viewport_size({"width": 390, "height": 844})
            expect(page.get_by_text(marker, exact=True)).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            box = page.get_by_role("main").first.bounding_box()
            assert box and box["width"] >= 360
            page.screenshot(path=str(output / "sources_mobile.png"), full_page=True)
            assert not errors
            after = budget_total()
            assert after == before
            receipt.update(
                passed=True,
                rejected_request=request_body,
                response_status=409,
                prior_receipt=previous,
                budget_before=before,
                budget_after=after,
                no_new_receipt=True,
                secure_context=True,
                reload_matches=True,
                mobile_width=box["width"],
            )
            browser.close()
    except Exception as error:
        receipt["reason"] = str(error)
    receipt["browser_errors"] = errors
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"output": str(output), **receipt}))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
