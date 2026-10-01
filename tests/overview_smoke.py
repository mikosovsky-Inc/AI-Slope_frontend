"""Read-only overview UI after creating a synthetic channel on an isolated stack."""

import argparse
from uuid import uuid4

import httpx
from playwright.sync_api import expect, sync_playwright


def run(frontend, backend):
    credentials = dict(
        email=f"overview-{uuid4().hex}@example.com", password="isolated-test-password"
    )
    with httpx.Client(base_url=backend, timeout=30) as api:
        assert "/api/v1/channels/{channel_id}/overview" in api.get("/openapi.json").json()["paths"]
        api.post("/api/v1/auth/register", json=credentials).raise_for_status()
        token = api.post("/api/v1/auth/login", json=credentials).json()["access_token"]
        api.headers["Authorization"] = "Bearer " + token
        result = api.post("/api/v1/channels", json={"idea": "Historie testowe", "language": "pl"})
        result.raise_for_status()
        channel = result.json()["id"]
        expected = api.get(f"/api/v1/channels/{channel}/overview")
        expected.raise_for_status()
        assert expected.json()["latest_plan"] is None
        with sync_playwright() as p:
            for engine in (p.chromium, p.webkit):
                browser = engine.launch()
                context = browser.new_context(java_script_enabled=engine.name == "chromium")
                page = context.new_page()
                page.goto(frontend + "/login")
                page.locator("#email").fill(credentials["email"])
                page.locator("#password").fill(credentials["password"])
                page.get_by_role("button", name="WEJDŹ DO STUDIA").click()
                page.wait_for_url(frontend + "/app")
                page.goto(frontend + f"/channels/{channel}")
                page.get_by_role("link", name="Podsumowanie", exact=True).click()
                expect(page.get_by_role("heading", name="Podsumowanie kanału")).to_be_visible()
                expect(
                    page.get_by_text("Backend nie zapisał jeszcze planu dla tego kanału.")
                ).to_be_visible()
                for width in (1440, 390):
                    page.set_viewport_size({"width": width, "height": 900})
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(path=f"/tmp/ai-slop-overview-{engine.name}.png", full_page=True)
                page.get_by_role("link", name="Sprawdź zdarzenia kosztowe").click()
                expect(page.get_by_role("heading", name="Koszty kanału")).to_be_visible()
                browser.close()
    print("PASS: real overview contract, navigation, Chromium, WebKit without JS, mobile")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated-frontend-url", required=True)
    parser.add_argument("--isolated-backend-url", required=True)
    args = parser.parse_args()
    run(args.isolated_frontend_url, args.isolated_backend_url)
