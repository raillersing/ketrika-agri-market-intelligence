"""Read-only product proof on dedicated QA services, after the frozen full check."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from playwright.sync_api import expect, sync_playwright

from ketrika.core.qualification import validate_environment


def main() -> None:
    validate_environment(os.environ)
    directory = Path("/app/.venv/safe-facts-browser")
    directory.mkdir(exist_ok=True)
    receipt: dict[str, Any] = {
        "scope": "isolated software and synthetic data only",
        "passed": False,
    }
    errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(base_url="http://web:3000")
        context.set_default_timeout(60000)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("/login")
        page.locator('input[type="email"]').fill("admin@ketrika.local")
        page.locator('input[type="password"]').fill("change-me")
        page.locator('form button[type="submit"]').click()
        expect(page).to_have_url("http://web:3000/", timeout=120000)
        query = "product=rice_milled&region=MG11&actor=retail"
        response = context.request.get(
            "/api/v1/prices?product=rice_milled&location=MG11&actor_level=retail"
        )
        assert response.ok
        rows = response.json()
        assert rows, "Positive proof requires actual seeded prices, not an empty UI"
        receipt["prices"] = rows
        page.goto(f"/?{query}")
        expect(page.get_by_text("Chargement des données…", exact=True)).not_to_be_visible()
        card = page.get_by_text("Dernier point disponible", exact=True).locator("../..")
        latest = sorted(rows, key=lambda row: row["month"])[-1]
        expected_value = page.evaluate(
            "value => value.toLocaleString('fr-FR')", latest["median_price"]
        )
        expect(card).to_contain_text(expected_value)
        expect(card).to_contain_text(latest["location_name"])
        expect(card).to_contain_text(latest["actor_level"])
        count = page.get_by_text("Points mensuels disponibles", exact=True).locator("../..")
        expect(count).to_contain_text(str(len(rows)))
        expect(page.get_by_text("Prix médian national", exact=True)).not_to_be_visible()
        page.reload()
        expect(card).to_contain_text(expected_value)
        chart = page.locator("canvas").first
        expect(chart).to_be_visible()
        chart_bounds = chart.bounding_box()
        assert chart_bounds and chart_bounds["height"] >= 200 and chart_bounds["width"] >= 200
        receipt["chart_bounds"] = chart_bounds
        page.screenshot(path=str(directory / "overview-desktop.png"), full_page=True)
        receipt["reload_matches_api"] = True
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(directory / "overview-mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.goto("/?product=__EMPTY_AUDIT__")
        expect(
            page.get_by_text("Aucune donnée disponible pour ces filtres.", exact=True)
        ).to_be_visible()
        empty = page.get_by_text("Dernier point disponible", exact=True).locator("../..")
        expect(empty).to_contain_text("—")
        receipt["empty_selection"] = True
        page.route(
            "**/api/v1/prices?**",
            lambda route: route.fulfill(status=503, json={"detail": "test unavailable"}),
        )
        page.reload()
        expect(page.get_by_role("alert").filter(has_text="Prix indisponibles")).to_be_visible()
        expect(empty).to_contain_text("—")
        receipt["error_visible_without_stale_value"] = True
        page.unroute("**/api/v1/prices?**")
        locations_response = context.request.get("/api/v1/locations?level=1")
        assert locations_response.ok
        for location in locations_response.json():
            if not location["pcode"]:
                continue
            summary_response = context.request.get(
                f"/api/v1/climate/summary?location={location['pcode']}"
            )
            assert summary_response.ok, summary_response.text()
            summary = summary_response.json()
            if summary["forecast_next_72h_precip_mm"] is None:
                page.goto("/climate")
                selector = (
                    page.locator("select")
                    .filter(has=page.locator(f'option[value="{location["pcode"]}"]'))
                    .last
                )
                expect(selector).to_be_visible()
                selector.select_option(location["pcode"])
                expect(page.get_by_text("Modèle : Indisponible", exact=True)).to_be_visible()
                expect(page.get_by_text("Risque non évalué", exact=True)).to_be_visible()
                page.screenshot(path=str(directory / "climate-mobile.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                receipt["climate"] = summary
                break
        else:
            raise AssertionError("No empty forecast case available for this proof")
        assert not errors, errors
        receipt["browser_errors"] = errors
        receipt["passed"] = True
        browser.close()
    (directory / "receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False))
    print(json.dumps({"passed": True, "directory": str(directory)}))


if __name__ == "__main__":
    main()
