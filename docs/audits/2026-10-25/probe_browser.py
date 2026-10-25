"""Observe actual pages without clicks on collection, mutation or LLM controls."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Route, sync_playwright

output = Path("/out")
report: dict[str, Any] = {
    "captured_at": datetime.now(UTC).isoformat(),
    "pages": [],
    "errors": [],
    "blocked": [],
}
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        base_url="http://web:3000", viewport={"width": 1440, "height": 1000}
    )
    page = context.new_page()
    page.on("pageerror", lambda error: report["errors"].append(str(error)))
    login = context.request.post(
        "http://api:8000/v1/auth/login",
        data={"email": "admin@ketrika.local", "password": "change-me"},
    )
    assert login.ok
    token = login.json()["token"]
    context.add_cookies(
        [
            {
                "name": "session_token",
                "value": token,
                "url": "http://web:3000",
                "httpOnly": True,
                "sameSite": "Lax",
            }
        ]
    )

    def block_reconciliation(route: Route) -> None:
        report["blocked"].append(route.request.url)
        route.abort()

    # These GETs mutate interrupted-run bookkeeping; audit avoids their execution.
    page.route("**/v1/sources/collections**", block_reconciliation)
    for path in [
        "/",
        "/prices",
        "/map",
        "/economy",
        "/climate",
        "/trade",
        "/sources",
        "/alerts",
        "/bulletins",
        "/copilot",
        "/system",
        "/admin/review",
    ]:
        try:
            response = page.goto(path, wait_until="networkidle", timeout=120000)
            body = page.locator("body").inner_text()
            item = {
                "path": path,
                "status": response.status if response else None,
                "url": page.url,
                "text": body[:16000],
                "overflow_px": page.evaluate("document.documentElement.scrollWidth - innerWidth"),
            }
            report["pages"].append(item)
            if path in ("/", "/map", "/prices", "/economy"):
                page.screenshot(
                    path=str(output / ("desktop-" + (path.strip("/") or "home") + ".png")),
                    full_page=True,
                )
        except Exception as error:
            report["pages"].append({"path": path, "error": str(error)[:300]})
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto("/", wait_until="networkidle")
    report["mobile_overflow_px"] = page.evaluate(
        "document.documentElement.scrollWidth - innerWidth"
    )
    page.screenshot(path=str(output / "mobile-home.png"), full_page=True)
    forged = browser.new_context(base_url="http://web:3000")
    forged.add_cookies(
        [{"name": "session_token", "value": "audit-invalid-token", "url": "http://web:3000"}]
    )
    forged_response = forged.request.get("/", max_redirects=0)
    report["invalid_cookie_home_status"] = forged_response.status
    report["invalid_cookie_home_contains_hardcoded_price"] = "2 850" in forged_response.text()
    browser.close()
output.joinpath("browser.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(
    json.dumps(
        {
            "pages": len(report["pages"]),
            "page_errors": report["errors"],
            "mobile_overflow_px": report.get("mobile_overflow_px"),
        }
    )
)
