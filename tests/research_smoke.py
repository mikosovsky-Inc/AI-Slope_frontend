"""Isolated eager backend with mock LLM and explicit fictional source documents only."""

import argparse
from uuid import uuid4

import httpx
from playwright.sync_api import expect, sync_playwright


def run(frontend, backend):
    credentials = dict(
        email=f"research-{uuid4().hex}@example.com", password="isolated-test-password"
    )
    with httpx.Client(base_url=backend, timeout=30) as api:
        assert "/api/v1/videos/{video_id}/research" in api.get("/openapi.json").json()["paths"]
        api.post("/api/v1/auth/register", json=credentials).raise_for_status()
        token = api.post("/api/v1/auth/login", json=credentials).json()["access_token"]
        api.headers["Authorization"] = "Bearer " + token
        result = api.post(
            "/api/v1/channels", json={"idea": "Historical discoveries and facts", "language": "en"}
        )
        result.raise_for_status()
        base = "/api/v1/channels/" + result.json()["id"]
        api.post(base + "/analyze").raise_for_status()
        generated = api.post(base + "/ideas/generate")
        generated.raise_for_status()
        idea = next(i for i in generated.json()["items"] if i["format"] == "top5")
        path = "/api/v1/ideas/" + idea["id"]
        api.post(path + "/approve").raise_for_status()
        video = api.post(path + "/create-video")
        video.raise_for_status()
        video_id = video.json()["id"]
        path = "/api/v1/videos/" + video_id
        research = api.post(path + "/research")
        research.raise_for_status()
        assert len(research.json()["documents"]) == 2
        script = api.post(path + "/top5-script/generate")
        script.raise_for_status()
        assert len(script.json()["citations"]) == 5
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
                page.goto(frontend + "/videos/" + video_id)
                page.get_by_role("link", name="Źródła i fakty", exact=True).click()
                expect(
                    page.get_by_role("heading", name="Fakty użyte w scenariuszu")
                ).to_be_visible()
                assert page.locator("article[id^=document-]").count() == 2
                assert page.get_by_text("Ocena pewności modelu:", exact=False).count() == 6
                page.get_by_text("Przeczytaj zapisany dokument", exact=True).first.click()
                expect(page.locator(".source-content").first).to_be_visible()
                for width in (1440, 390):
                    page.set_viewport_size({"width": width, "height": 900})
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(path=f"/tmp/ai-slop-research-{engine.name}.png", full_page=True)
                browser.close()
    print("PASS: real TOP5 research, 2 documents, 6 facts, 5 citations, Chromium/WebKit without JS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated-frontend-url", required=True)
    parser.add_argument("--isolated-backend-url", required=True)
    args = parser.parse_args()
    run(args.isolated_frontend_url, args.isolated_backend_url)
