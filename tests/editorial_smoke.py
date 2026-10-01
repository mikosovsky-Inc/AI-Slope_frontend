"""Use isolated backend with mock LLM and worker; creates accounts and content."""

import argparse
import time
from uuid import uuid4

import httpx
from playwright.sync_api import expect, sync_playwright


def run(frontend, backend):
    with httpx.Client(base_url=backend, timeout=30) as api:
        # Verify deployed endpoints before changing the isolated fixture.
        paths = api.get("/openapi.json").json()["paths"]
        assert "/api/v1/channels/{channel_id}/competitor-research" in paths
        assert "/api/v1/channels/{channel_id}/ideas/generate" in paths
        with sync_playwright() as p:
            for engine in (p.chromium, p.webkit):
                credentials = {
                    "email": f"ideas-{uuid4().hex}@example.com",
                    "password": "isolated-test-password",
                }
                api.headers.pop("Authorization", None)
                api.post("/api/v1/auth/register", json=credentials).raise_for_status()
                token = api.post("/api/v1/auth/login", json=credentials).json()["access_token"]
                api.headers["Authorization"] = "Bearer " + token
                channel = api.post(
                    "/api/v1/channels",
                    json={"idea": "Polski kanał o historii i odkryciach", "language": "pl"},
                ).json()
                base = "/channels/" + channel["id"]
                result = api.post("/api/v1" + base + "/analyze").json()
                if "kind" in result:
                    for _ in range(30):
                        status = api.get("/api/v1/tasks/" + result["id"]).json()["status"]
                        if status == "succeeded":
                            break
                        time.sleep(0.2)
                    assert status == "succeeded"
                browser = engine.launch()
                page = browser.new_page(
                    viewport={"width": 1440, "height": 1000},
                    java_script_enabled=engine.name != "webkit",
                )
                page.goto(frontend + "/login")
                page.locator("#email").fill(credentials["email"])
                page.locator("#password").fill(credentials["password"])
                page.get_by_role("button", name="WEJDŹ DO STUDIA").click()
                page.goto(frontend + base + "/ideas")
                page.locator("#count").fill("12")
                page.get_by_role("button", name="GENERUJ POMYSŁY").click()
                expect(page.locator("#analysis-task")).to_be_visible()
                if engine.name == "webkit":
                    page.get_by_role("link", name="Odśwież stan").click()
                expect(page.locator("#task-message")).to_contain_text("succeeded", timeout=60000)
                expect(page.locator(".editorial-card")).to_have_count(10)
                page.get_by_role("link", name="Następna").click()
                expect(page.locator(".editorial-card")).to_have_count(2)
                page.get_by_role("link", name="Poprzednia").click()
                page.get_by_role("button", name="ZATWIERDŹ").first.click()
                page.locator("#status").select_option("approved")
                page.get_by_role("button", name="FILTRUJ").click()
                expect(page.locator(".editorial-card")).to_have_count(1)
                page.get_by_role("button", name="ODRZUĆ").click()
                expect(page.get_by_role("heading", name="Brak wyników.")).to_be_visible()
                page.locator("#status").select_option("rejected")
                page.get_by_role("button", name="FILTRUJ").click()
                expect(page.locator(".editorial-card")).to_have_count(1)
                page.screenshot(path=f"/tmp/ai-slop-ideas-{engine.name}.png", full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(path=f"/tmp/ai-slop-ideas-mobile-{engine.name}.png", full_page=True)
                page.get_by_role("link", name="Konkurenci", exact=True).click()
                page.get_by_role("button", name="ZBADAJ KONKURENCJĘ").click()
                expect(page.locator("#analysis-task")).to_be_visible()
                if engine.name == "webkit":
                    page.get_by_role("link", name="Odśwież stan").click()
                expect(page.locator("#task-message")).to_contain_text("succeeded", timeout=60000)
                expect(page.get_by_role("heading", name="Brak wyników.")).to_be_visible()
                browser.close()
    print("PASS: Chromium/WebKit, 12 ideas, pagination, decisions, filters, research, no-JS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated-frontend-url", required=True)
    parser.add_argument("--isolated-backend-url", required=True)
    args = parser.parse_args()
    run(args.isolated_frontend_url, args.isolated_backend_url)
