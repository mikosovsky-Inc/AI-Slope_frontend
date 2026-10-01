"""Creates synthetic accounts/channels: use isolated backend and frontend ONLY."""

import argparse
from uuid import uuid4

import httpx
from playwright.sync_api import expect, sync_playwright


def run(frontend, backend):
    credentials = {
        "email": f"panel-{uuid4().hex}@example.com",
        "password": "isolated-test-password",
    }
    with httpx.Client(base_url=backend) as api:
        api.post("/api/v1/auth/register", json=credentials).raise_for_status()
        token = api.post("/api/v1/auth/login", json=credentials).json()["access_token"]
        api.headers["Authorization"] = f"Bearer {token}"
        for i in range(13):
            api.post(
                "/api/v1/channels",
                json={
                    "name": f"Historia {i:02}",
                    "idea": "Polski kanał o historii i odkryciach",
                    "language": "pl",
                },
            ).raise_for_status()
        with sync_playwright() as p:
            for engine in (p.chromium, p.webkit):
                browser = engine.launch()
                context = browser.new_context(
                    viewport={"width": 1440, "height": 1000},
                    java_script_enabled=engine.name != "webkit",
                )
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(frontend + "/login")
                page.locator("#email").fill(credentials["email"])
                page.locator("#password").fill(credentials["password"])
                page.get_by_role("button", name="WEJDŹ DO STUDIA").click()
                expect(page.get_by_role("heading", name="Twoje studio.")).to_be_visible()
                expect(page.locator(".stat").first.locator("strong")).to_have_text("13")
                expect(page.get_by_text("Nie masz jeszcze filmów.")).to_be_visible()
                page.get_by_role("link", name="Kanały", exact=False).click()
                expect(page.locator(".channel")).to_have_count(12)
                page.screenshot(path=f"/tmp/ai-slop-channels-{engine.name}.png", full_page=True)
                page.get_by_role("link", name="Następna").click()
                expect(page.locator(".channel")).to_have_count(1)
                page.get_by_role("link", name="Poprzednia").click()
                expect(page.locator(".channel")).to_have_count(12)
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(
                    path=f"/tmp/ai-slop-channels-mobile-{engine.name}.png", full_page=True
                )
                page.get_by_role("link", name="Studio", exact=False).first.click()
                expect(page.get_by_role("heading", name="Twoje studio.")).to_be_visible()
                page.screenshot(
                    path=f"/tmp/ai-slop-dashboard-mobile-{engine.name}.png", full_page=True
                )
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.get_by_role("button", name="WYLOGUJ SIĘ").click()
                expect(page.locator("#auth-form")).to_be_visible()
                assert not errors, errors
                browser.close()
    print("PASS: Chromium/WebKit, real API dashboard/channels, 12+1 pagination, mobile, logout")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated-frontend-url", required=True)
    parser.add_argument("--isolated-backend-url", required=True)
    args = parser.parse_args()
    run(args.isolated_frontend_url, args.isolated_backend_url)
