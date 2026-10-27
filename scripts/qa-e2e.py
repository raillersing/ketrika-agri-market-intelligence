"""Actual UI authentication on dedicated Docker targets; no injected token."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ketrika.core.qualification import validate_environment
from ketrika.core.qualification_reports import E2E_SCENARIOS, capture_binding
from playwright.sync_api import expect, sync_playwright


def seed_reading_fixtures() -> tuple[dict[str, str], list[tuple[str, uuid.UUID]]]:
    """Owned synthetic UI records only, after qualification environment validation."""
    validate_environment(os.environ)
    from ketrika.core.db import get_session
    from ketrika.core.models.db import Alert, Bulletin, Product
    from sqlalchemy import select

    ids: dict[str, str] = {}
    owned: list[tuple[str, uuid.UUID]] = []
    with get_session() as session:
        product = session.scalar(select(Product).where(Product.product_code == "rice_dq_116994"))
        if product is None:
            product = Product(
                product_id=uuid.uuid4(),
                product_code="rice_dq_116994",
                canonical_name_fr="Riz Test DQ",
                category="cereal",
                base_unit="kg",
                verified=True,
            )
            session.add(product)
            owned.append(("product", product.product_id))
        bulletin = Bulletin(
            bulletin_id=uuid.uuid4(),
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 7),
            status="draft",
            facts={
                "ui_zero": {
                    "label": "Contrôle UI — zéro",
                    "value": 0,
                    "unit": "Ar/kg",
                    "sources": ["ui_fixture"],
                },
                "ui_missing": {"label": "Contrôle UI — absence", "value": None},
                "ui_literal": {
                    "label": "Contrôle UI — texte",
                    "display": "<img src=x onerror=alert(1)>",
                },
            },
        )
        alert = Alert(
            alert_id=uuid.uuid4(),
            rule_code="UI_READING_FIXTURE",
            dedupe_key=f"ui-reading-{uuid.uuid4().hex}",
            severity="high",
            title="Contrôle UI — signal enregistré",
            state="open",
            evidence={"scope": "synthetic UI fixture, not market evidence", "zero": 0},
        )
        session.add_all([bulletin, alert])
        owned.extend([("bulletin", bulletin.bulletin_id), ("alert", alert.alert_id)])
        ids.update(bulletin=str(bulletin.bulletin_id), alert=str(alert.alert_id))
    return ids, owned


def cleanup_reading_fixtures(owned: list[tuple[str, uuid.UUID]]) -> None:
    validate_environment(os.environ)
    from ketrika.core.db import get_session
    from ketrika.core.models.db import Alert, Bulletin, Product

    models = {"alert": Alert, "bulletin": Bulletin, "product": Product}
    with get_session() as session:
        for kind, identifier in reversed(owned):
            record = session.get(models[kind], identifier)
            if record is not None:
                session.delete(record)


def main() -> int:
    validate_environment(os.environ)
    directory = Path("/app/.venv/qa-browser-results") / uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    receipt: dict = {
        "scope": "Docker browser software, synthetic QA environment",
        "passed": False,
    }
    if os.environ.get("KETRIKA_SOURCE_COMMIT"):
        receipt.update(capture_binding(Path("/workspace"), os.environ["KETRIKA_SOURCE_COMMIT"]))
    receipt["expected_checks"] = list(E2E_SCENARIOS)
    started = time.monotonic()
    errors: list[str] = []
    completed: list[str] = []
    owned: list[tuple[str, uuid.UUID]] = []
    try:
        fixture_ids, owned = seed_reading_fixtures()
        receipt["reading_fixture_scope"] = (
            "Owned synthetic Product/Alert/Bulletin only; no market observation or Bronze object"
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(base_url="http://web:3000")
            context.set_default_navigation_timeout(240000)
            expect.set_options(timeout=240000)
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            for _attempt in range(60):
                try:
                    response = context.request.get("/login", timeout=10000)
                    backend = context.request.get("http://api:8000/v1/health", timeout=10000)
                    if response.ok and backend.ok:
                        break
                except Exception:
                    pass
                time.sleep(1)
            else:
                raise RuntimeError("Dedicated frontend and API never became ready")
            for warmup_path in ("/", "/prices", "/economy", "/api/v1/auth/me"):
                try:
                    context.request.get(warmup_path, timeout=120000)
                except Exception:
                    pass
            page.emulate_media(color_scheme="light")
            page.goto("/about")
            expect(page.locator("html")).to_have_attribute("data-theme", "light")
            theme_switch = page.get_by_role("switch", name="Mode sombre", exact=True)
            theme_switch.click()
            expect(page.locator("html")).to_have_attribute("data-theme", "dark")
            page.reload()
            expect(theme_switch).to_have_attribute("aria-checked", "true")
            page.goto("/login")
            expect(page.locator("html")).to_have_attribute("data-theme", "dark")
            page.get_by_role("switch", name="Mode sombre", exact=True).click()
            page.reload()
            expect(page.locator("html")).to_have_attribute("data-theme", "light")
            completed.append("theme choice persists across reload and public pages")
            about = page.goto("/about")
            assert about is not None and about.status == 200
            expect(page.get_by_role("heading", level=1)).to_contain_text("Irooa")
            expect(page.get_by_role("heading", name="Ketrikay", exact=True)).to_be_visible()
            expect(
                page.get_by_text("Le nom Ketrikay succède à Ketrikai", exact=False)
            ).to_be_visible()
            completed.append(
                "public About identifies Irooa and Ketrikay without exposing business pages"
            )
            page.goto("/prices")
            expect(page).to_have_url(re.compile(r"http://web:3000/login(?:\?.*)?"))
            completed.append("protected UI redirects without a session")
            context.add_cookies(
                [
                    {
                        "name": "session_token",
                        "value": "arbitrary",
                        "url": "http://web:3000",
                    }
                ]
            )
            page.goto("/prices")
            expect(page).to_have_url(re.compile(r"http://web:3000/login(?:\?.*)?"))
            assert not any(cookie["name"] == "session_token" for cookie in context.cookies())
            completed.append("UI rejects and clears an arbitrary session cookie")
            page.locator('input[type="email"]').fill("admin@ketrika.local")
            page.locator('input[type="password"]').fill("change-me")
            page.locator('form button[type="submit"]').click()
            expect(page).to_have_url("http://web:3000/", timeout=240000)
            cookies = context.cookies()
            assert any(
                cookie["name"] == "session_token" and cookie["httpOnly"] for cookie in cookies
            )
            assert not any(cookie["name"] == "ketrika_token" for cookie in cookies)
            session_cookie = next(cookie for cookie in cookies if cookie["name"] == "session_token")
            completed.append("form login establishes HttpOnly session")
            for warmup_path in ("/prices", "/economy"):
                try:
                    context.request.get(warmup_path, timeout=120000)
                except Exception:
                    pass
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
            navigation = page.get_by_role("navigation", name="Navigation principale")
            expect(navigation.locator('[aria-current="page"]')).to_have_count(1)
            expect(navigation.locator('[aria-current="page"]')).to_have_attribute("href", "/")
            management = navigation.get_by_role("button", name="Gestion des données", exact=True)
            expect(management).to_have_attribute("aria-expanded", "false")
            management.click()
            expect(navigation.get_by_role("link", name="À vérifier", exact=True)).to_be_visible()
            management.focus()
            page.keyboard.press("Space")
            expect(management).to_have_attribute("aria-expanded", "false")
            completed.append(
                "desktop navigation groups management links and marks the current page"
            )
            search = page.get_by_role("button", name="Rechercher une page", exact=True)
            search.click()
            dialog = page.get_by_role("dialog", name="Aller à une page", exact=True)
            field = dialog.get_by_role("combobox", name="Rechercher une page", exact=True)
            expect(field).to_be_focused()
            field.fill("ECONOMIE")
            expect(dialog.get_by_role("option")).to_have_count(1)
            expect(dialog.get_by_role("option")).to_contain_text("Économie")
            page.keyboard.press("Escape")
            expect(dialog).not_to_be_visible()
            expect(search).to_be_focused()
            page.keyboard.press("Control+k")
            expect(field).to_be_focused()
            field.fill("prix vivriers")
            page.keyboard.press("Enter")
            expect(page).to_have_url("http://web:3000/prices", timeout=120000)
            expect(dialog).not_to_be_visible()
            completed.append("page search navigates real destinations and restores keyboard focus")
            page.goto("/prices")
            expect(page.get_by_text("Explorateur des prix vivriers", exact=True)).to_be_visible()
            page.screenshot(path=str(directory / "prices.png"), full_page=True)
            completed.append("price explorer renders")

            # DP-1: existing contracts and real isolated SQL fixtures, never active data.
            product_select = page.get_by_role("combobox", name="Produit", exact=True)
            expect(product_select).to_be_enabled()
            references = context.request.get("/api/v1/products")
            assert references.ok and any(
                item["product_code"] == "rice_dq_116994" for item in references.json()
            )
            assert "rice_dq_116994" not in product_select.locator("option").evaluate_all(
                "nodes => nodes.map(node => node.value)"
            )
            dq_requests: list[str] = []

            def record_dq_request(request) -> None:
                url = urlparse(request.url)
                if url.path == "/api/v1/prices" and parse_qs(url.query).get("product") == [
                    "rice_dq_116994"
                ]:
                    dq_requests.append(url.path)

            page.on("request", record_dq_request)
            page.goto("/prices?product=rice_dq_116994")
            expect(
                page.get_by_text(
                    "Cette référence est réservée aux essais de qualité. Choisissez un produit du catalogue métier.",
                    exact=True,
                ).first
            ).to_be_visible()
            assert "product=rice_dq_116994" in page.url and not dq_requests
            page.reload()
            expect(page.get_by_role("combobox", name="Produit", exact=True)).to_have_value("")
            assert not dq_requests
            page.remove_listener("request", record_dq_request)
            completed.append(
                "business filters exclude known DQ references without remapping the URL"
            )

            page.goto("/prices?product=UI_NO_SUCH_PRODUCT&actor=unknown")
            expect(page.get_by_role("combobox", name="Stade de vente", exact=True)).to_have_value(
                "unknown"
            )
            expect(page.get_by_role("combobox", name="Produit", exact=True)).to_have_value(
                "UI_NO_SUCH_PRODUCT"
            )
            expect(
                page.get_by_role(
                    "heading",
                    name="Aucun point de prix pour cette sélection",
                    exact=True,
                )
            ).to_be_visible()
            page.reload()
            expect(page.get_by_role("combobox", name="Stade de vente", exact=True)).to_have_value(
                "unknown"
            )
            completed.append("sale stage unknown and empty product keep explicit selections")

            def catalog_outage(route) -> None:
                route.fulfill(
                    status=503,
                    content_type="application/json",
                    body='{"detail":"synthetic catalog outage"}',
                )

            page.route("**/api/v1/products", catalog_outage)
            page.goto("/prices?product=UI_NO_SUCH_PRODUCT")
            expect(
                page.get_by_text(
                    "Catalogue indisponible. Les données et la sélection ne sont pas remplacées.",
                    exact=True,
                )
            ).to_be_visible()
            expect(page.get_by_role("combobox", name="Produit", exact=True)).to_have_value(
                "UI_NO_SUCH_PRODUCT"
            )
            page.unroute("**/api/v1/products", catalog_outage)
            for path in ("/economy", "/alerts", "/bulletins"):
                page.goto(path)
                expect(
                    page.get_by_role("region", name="Filtres de cette page", exact=True)
                ).to_have_count(0)
            completed.append(
                "reference outage preserves selection without redundant global filters"
            )

            page.goto("/map")
            expect(
                page.get_by_role("heading", name="Carte géographique en préparation", exact=True)
            ).to_be_visible()
            expect(
                page.get_by_role("heading", name="Derniers points par zone", exact=True)
            ).to_be_visible()
            expect(page.get_by_role("combobox", name="Produit", exact=True)).to_be_visible()
            expect(page.get_by_role("combobox", name="Zone", exact=True)).to_have_count(0)
            expect(page.get_by_text(re.compile(r"Surcoût de transport estimé"))).to_have_count(0)
            completed.append("territory view is tabular and states missing geography")

            bulletin_response = page.goto(f"/bulletins/{fixture_ids['bulletin']}")
            if bulletin_response is not None and bulletin_response.status == 503:
                assert bulletin_response.json() == {
                    "detail": "Vérification de session indisponible. Réessayez dans un instant."
                }, "Unexpected bulletin navigation error"
                assert context.request.get("/api/v1/auth/me").status == 200, (
                    "Session verification remains unavailable"
                )
                receipt["session_readiness_recoveries"] = [
                    {"scenario": "first bulletin navigation", "initial_status": 503, "reloads": 1}
                ]
                retry_response = page.reload()
                assert retry_response is not None and retry_response.status == 200, (
                    "Bulletin navigation failed after its single readiness reload"
                )
            expect(page.get_by_text("0 Ar/kg", exact=True)).to_be_visible()
            expect(page.get_by_text("Valeur non renseignée", exact=True)).to_be_visible()
            expect(page.get_by_text("<img src=x onerror=alert(1)>", exact=True)).to_be_visible()
            expect(page.locator('img[src="x"]')).to_have_count(0)
            expect(
                page.get_by_text(
                    re.compile(
                        "demeurent réguliers|conformes aux normales saisonnières|Extraction déterministe certifiée"
                    )
                )
            ).to_have_count(0)
            expect(page.get_by_role("link", name="Télécharger le PDF", exact=True)).to_have_count(0)
            page.get_by_role("button", name="Approuver le bulletin", exact=True).click()
            expect(
                page.get_by_text(
                    "Approbation enregistrée. Cette action n’envoie pas le bulletin.",
                    exact=True,
                )
            ).to_be_visible()
            approval = context.request.get(f"/api/v1/bulletins/{fixture_ids['bulletin']}")
            assert approval.status == 200, f"Approval reread HTTP {approval.status}"
            assert approval.json()["status"] == "approved", "Bulletin approval was not persisted"
            completed.append(
                "recorded bulletin facts preserve zero missingness and approval without invented narrative"
            )

            page.goto("/alerts")
            page.get_by_role("combobox", name="État de l’alerte", exact=True).select_option("open")
            fixture_button = page.get_by_role("button").filter(
                has_text="Contrôle UI — signal enregistré"
            )
            expect(fixture_button).to_be_visible()
            expect(fixture_button).to_contain_text("Priorité élevée")
            fixture_button.click()
            page.get_by_role("button", name="Prendre en compte", exact=True).click()
            expect(
                page.get_by_text("Le suivi de l’alerte a été mis à jour.", exact=True)
            ).to_be_visible()
            expect(fixture_button).to_have_count(0)
            page.get_by_role("combobox", name="État de l’alerte", exact=True).select_option(
                "acknowledged"
            )
            expect(fixture_button).to_be_visible()
            expect(fixture_button).to_contain_text("Prise en compte")
            completed.append("alert states are French and updated selection follows active filter")

            for theme in ("light", "dark"):
                page.evaluate("theme => localStorage.setItem('irooa.theme', theme)", theme)
                for path in (
                    "/prices",
                    "/map",
                    "/trade",
                    "/alerts",
                    "/economy",
                    f"/bulletins/{fixture_ids['bulletin']}",
                ):
                    page.set_viewport_size({"width": 320, "height": 844})
                    page.goto(path)
                    expect(page.get_by_role("main").get_by_role("heading", level=1)).to_be_visible()
                    for loading_message in (
                        "Chargement des points de prix…",
                        "Chargement des prix par territoire…",
                        "Chargement des échanges…",
                        "Chargement des alertes…",
                        "Chargement du bulletin…",
                    ):
                        expect(page.get_by_text(loading_message, exact=True)).not_to_be_visible()
                    expect(page.locator("html")).to_have_attribute("data-theme", theme)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                        theme,
                        path,
                        "320px",
                    )
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.add_style_tag(content="html {font-size:200%}")
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                        theme,
                        path,
                        "text200%",
                    )
            page.set_viewport_size({"width": 1280, "height": 800})
            completed.append("first-lot views fit 320px and 200 percent text in both themes")

            # R2.10: Economy observatory navigation, dimensions and responsive checks
            eco_res = context.request.get("/api/v1/economic/dashboard")
            assert eco_res.status == 503, f"Unqualified macro must fail closed: {eco_res.status}"
            assert eco_res.json()["detail"] == "economic_data_not_qualified"
            page.goto("/economy")
            expect(
                page.get_by_text("Observatoire Économique & Conjoncture", exact=True)
            ).to_be_visible()
            unavailable = page.get_by_text(
                "Données économiques non qualifiées ou temporairement indisponibles.",
                exact=True,
            )
            expect(unavailable).to_be_visible()
            expect(
                page.get_by_text(
                    "Aucune donnée disponible pour cette dimension économique.",
                    exact=True,
                )
            ).to_have_count(0)
            page.reload()
            expect(unavailable).to_be_visible()
            page.screenshot(path=str(directory / "economy.png"), full_page=True)
            completed.append("economy explicitly reports unqualified data after reload")

            # R2.10: Mobile responsive check at 390px width (SPECS §22)
            page.set_viewport_size({"width": 390, "height": 844})
            expect(
                page.get_by_text("Observatoire Économique & Conjoncture", exact=True)
            ).to_be_visible()
            expect(unavailable).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            content = page.get_by_role("main").first.bounding_box()
            assert content is not None and content["width"] >= 360 and content["x"] <= 16
            message = unavailable.bounding_box()
            assert message is not None and message["x"] >= 0
            assert message["x"] + message["width"] <= 390
            navigation = page.locator("#primary-navigation")
            expect(navigation).not_to_be_visible()
            page.get_by_role("button", name="Ouvrir la navigation", exact=True).click()
            expect(navigation).to_be_visible()
            page.keyboard.press("Escape")
            expect(navigation).not_to_be_visible()
            expect(
                page.get_by_role("button", name="Ouvrir la navigation", exact=True)
            ).to_be_focused()
            page.get_by_role("button", name="Ouvrir la navigation", exact=True).click()
            drawer = page.get_by_role("dialog", name="Navigation Irooa", exact=True)
            expect(drawer.locator('[aria-current="page"]')).to_be_focused()
            logout_button = drawer.get_by_role("button", name="Se déconnecter", exact=True)
            logout_button.focus()
            page.keyboard.press("Tab")
            expect(
                drawer.get_by_role("button", name="Fermer la navigation", exact=True)
            ).to_be_focused()
            page.get_by_role("navigation", name="Navigation principale").get_by_role(
                "link", name="Économie", exact=True
            ).click()
            expect(navigation).not_to_be_visible()
            completed.append("mobile navigation opens, closes with Escape and with its link")
            expect(page.get_by_text("100% Provenance vérifiée", exact=True)).to_have_count(0)
            page.screenshot(path=str(directory / "economy_mobile_390px.png"), full_page=True)
            completed.append("economy uses full content width at 390px without clipped message")

            # Restore desktop viewport
            page.set_viewport_size({"width": 1280, "height": 800})

            page.get_by_title("Se déconnecter", exact=True).click()
            expect(page).to_have_url("http://web:3000/login")
            assert not any(cookie["name"] == "session_token" for cookie in context.cookies())
            completed.append("UI logout removes session")
            unauthenticated = context.request.get("/api/v1/auth/me")
            assert unauthenticated.status in (401, 403)
            completed.append("API rejects access after logout")
            revoked = context.request.get(
                "/api/v1/prices",
                headers={"Authorization": f"Bearer {session_cookie['value']}"},
            )
            assert revoked.status == 401
            completed.append("API rejects reuse of the logged-out token")
            context.add_cookies(
                [
                    {
                        "name": session_cookie["name"],
                        "value": session_cookie["value"],
                        "domain": session_cookie["domain"],
                        "path": session_cookie["path"],
                        "httpOnly": session_cookie["httpOnly"],
                        "secure": session_cookie["secure"],
                        "sameSite": session_cookie["sameSite"],
                        "expires": session_cookie["expires"],
                    }
                ]
            )
            page.goto("/prices")
            expect(page).to_have_url(re.compile(r"http://web:3000/login(?:\?.*)?"))
            assert not any(cookie["name"] == "session_token" for cookie in context.cookies())
            completed.append("UI rejects and clears a restored revoked cookie")
            completed.append("UI remains protected after logout")
            assert not errors, f"Browser runtime errors: {errors}"
            context.tracing.stop(path=str(directory / "trace.zip"))
            browser.close()
            receipt.update(passed=True, unauthenticated_status=unauthenticated.status)
    except Exception as exc:
        receipt["reason"] = re.sub(
            r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
            "[redacted-token]",
            str(exc),
        )
    finally:
        try:
            cleanup_reading_fixtures(owned)
            receipt["owned_reading_fixtures_cleaned"] = True
        except Exception:
            receipt["passed"] = False
            receipt["owned_reading_fixtures_cleaned"] = False
            receipt.setdefault("reason", "Owned synthetic UI fixture cleanup failed")
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
