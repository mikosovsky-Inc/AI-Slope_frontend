"""Creates accounts/channels and runs analysis. Isolated mock-provider stack ONLY."""

import argparse
from uuid import uuid4

import httpx
from playwright.sync_api import expect, sync_playwright


def run(frontend, backend):
    with sync_playwright() as p:
        for engine in (p.chromium, p.webkit):
            credentials = {
                "email": f"creator-{uuid4().hex}@example.com",
                "password": "isolated-test-password",
            }
            httpx.post(backend + "/api/v1/auth/register", json=credentials).raise_for_status()
            browser = engine.launch()
            page = browser.new_page(
                viewport={"width": 1440, "height": 1000},
                java_script_enabled=engine.name != "webkit",
            )
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(frontend + "/login")
            page.locator("#email").fill(credentials["email"])
            page.locator("#password").fill(credentials["password"])
            page.get_by_role("button", name="WEJDŹ DO STUDIA").click()
            page.get_by_role("link", name="Utwórz kanał").click()
            page.locator("#idea").fill("Polski kanał o dziwnych ciekawostkach historycznych")
            page.locator("#name").fill("Historyczne odkrycia")
            page.get_by_role("button", name="UTWÓRZ KANAŁ").click()
            expect(page.get_by_role("heading", name="Historyczne odkrycia")).to_be_visible()
            page.locator("#videos_per_day").fill("3")
            page.get_by_role("button", name="ZAPISZ USTAWIENIA").click()
            expect(page.locator("#videos_per_day")).to_have_value("3")
            page.get_by_role("button", name="ANALIZUJ OPIS KANAŁU").click()
            expect(page.locator("#analysis-task")).to_be_visible()
            if engine.name == "webkit":
                page.get_by_role("link", name="Odśwież stan").click()
            expect(
                page.get_by_text("Analiza zakończona. Strategia znajduje się poniżej.")
            ).to_be_visible(timeout=60000)
            expect(page.get_by_role("heading", name="Filary tematyczne")).to_be_visible()
            expect(page.locator("#videos_per_day")).to_have_value("3")
            page.screenshot(path=f"/tmp/ai-slop-channel-{engine.name}.png", full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=f"/tmp/ai-slop-channel-mobile-{engine.name}.png", full_page=True)
            page.get_by_role("button", name="AKTYWUJ", exact=True).click()
            expect(page.get_by_role("heading", name="Stan kanału: active")).to_be_visible()
            page.get_by_role("button", name="WSTRZYMAJ", exact=True).click()
            expect(page.get_by_role("heading", name="Stan kanału: paused")).to_be_visible()
            assert not errors, errors
            browser.close()
    print("PASS: Chromium/WebKit create, save, async analysis, strategy, activate/pause, mobile")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated-frontend-url", required=True)
    parser.add_argument("--isolated-backend-url", required=True)
    args = parser.parse_args()
    run(args.isolated_frontend_url, args.isolated_backend_url)
