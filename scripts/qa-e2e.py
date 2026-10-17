"""Actual UI authentication on dedicated Docker targets; no injected token."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from ketrika.core.qualification import validate_environment
from ketrika.core.qualification_reports import E2E_SCENARIOS, capture_binding


def main() -> int:
    validate_environment(os.environ)
    directory = Path("/app/.venv/qa-browser-results") / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    receipt: dict = {"scope": "Docker browser software, synthetic QA environment", "passed": False}
    if os.environ.get("KETRIKA_SOURCE_COMMIT"):
        receipt.update(capture_binding(Path("/workspace"), os.environ["KETRIKA_SOURCE_COMMIT"]))
    receipt["expected_checks"] = list(E2E_SCENARIOS)
    started = time.monotonic()
    errors: list[str] = []
    completed: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(base_url="http://web:3000")
            context.set_default_navigation_timeout(120000)
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            for _attempt in range(60):
                try:
                    response = context.request.get("/login", timeout=10000)
                    if response.ok:
                        break
                except Exception:
                    pass
                time.sleep(1)
            else:
                raise RuntimeError("Dedicated frontend never became ready")
            page.goto("/prices")
            expect(page).to_have_url(re.compile(r"http://web:3000/login(?:\?.*)?"))
            completed.append("protected UI redirects without a session")
            page.locator('input[type="email"]').fill("admin@ketrika.local")
            page.locator('input[type="password"]').fill("change-me")
            page.locator('form button[type="submit"]').click()
            expect(page).to_have_url("http://web:3000/", timeout=120000)
            cookies = context.cookies()
            assert any(
                cookie["name"] == "session_token" and cookie["httpOnly"] for cookie in cookies
            )
            assert not any(cookie["name"] == "ketrika_token" for cookie in cookies)
            completed.append("form login establishes HttpOnly session")
            page.reload()
            expect(page).to_have_url("http://web:3000/")
            completed.append("reload retains authentication")
            profile = context.request.get("/api/v1/auth/me")
            assert profile.ok and profile.json()["role"] == "admin"
            completed.append("protected profile authenticates the browser session")
            response = context.request.get("/api/v1/prices?limit=5")
            assert response.ok, f"Authenticated same-origin prices: {response.status}"
            receipt["prices_status"] = response.status
            completed.append("authenticated same-origin prices API")
            page.goto("/prices")
            expect(page.get_by_text("Explorateur des prix vivriers", exact=True)).to_be_visible()
            page.screenshot(path=str(directory / "prices.png"), full_page=True)
            completed.append("price explorer renders")

            # R2.10: Economy observatory navigation, dimensions and responsive checks
            eco_res = context.request.get("/api/v1/economic/dashboard")
            assert eco_res.ok, f"Authenticated same-origin economic dashboard: {eco_res.status}"
            page.goto("/economy")
            expect(page.get_by_text("Observatoire Économique & Conjoncture", exact=True)).to_be_visible()
            expect(page.get_by_text("ADR-070", exact=True)).to_be_visible()
            page.screenshot(path=str(directory / "economy.png"), full_page=True)
            completed.append("economy observatory renders")

            # R2.10: Mobile responsive check at 390px width (SPECS §22)
            page.set_viewport_size({"width": 390, "height": 844})
            expect(page.get_by_text("Observatoire Économique & Conjoncture", exact=True)).to_be_visible()
            page.screenshot(path=str(directory / "economy_mobile_390px.png"), full_page=True)
            completed.append("economy mobile 390px responsive view")

            # Restore desktop viewport
            page.set_viewport_size({"width": 1280, "height": 800})

            page.get_by_title("Se déconnecter", exact=True).click()
            expect(page).to_have_url("http://web:3000/login")
            assert not any(cookie["name"] == "session_token" for cookie in context.cookies())
            completed.append("UI logout removes session")
            unauthenticated = context.request.get("/api/v1/auth/me")
            assert unauthenticated.status in (401, 403)
            completed.append("API rejects access after logout")
            page.goto("/prices")
            expect(page).to_have_url(re.compile(r"http://web:3000/login(?:\?.*)?"))
            completed.append("UI remains protected after logout")
            assert not errors, f"Browser runtime errors: {errors}"
            context.tracing.stop(path=str(directory / "trace.zip"))
            browser.close()
            receipt.update(passed=True, unauthenticated_status=unauthenticated.status)
    except Exception as exc:
        receipt["reason"] = str(exc)
    receipt.update(
        duration_seconds=round(time.monotonic() - started, 3),
        browser_errors=errors,
        completed_checks=completed,
        checks=len(completed),
    )
    if (directory / "trace.zip").is_file():
        receipt["trace"] = {
            "path": "trace.zip",
            "sha256": hashlib.sha256((directory / "trace.zip").read_bytes()).hexdigest(),
        }
    (directory / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
