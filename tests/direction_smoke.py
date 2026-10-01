"""Visual plan from an isolated real pipeline, with mock providers only."""

import argparse

from playwright.sync_api import expect
from video_smoke import run


def verify(page, api, video_id, channel_id, engine):
    assert "/api/v1/videos/{video_id}/direction" in api.get("/openapi.json").json()["paths"]
    response = api.get(f"/api/v1/videos/{video_id}/direction")
    response.raise_for_status()
    plan = response.json()
    page.get_by_role("link", name="Plan wizualny", exact=True).click()
    expect(page.get_by_role("heading", name="Plan wizualny filmu")).to_be_visible()
    expect(
        page.get_by_text("Szacowany koszt obrazu: " + plan["estimated_cost_usd"] + " USD")
    ).to_be_visible()
    assert page.locator("article.panel").count() == len(plan["scenes"])
    page.get_by_text("Stawki użyte do planowania", exact=True).click()
    page.get_by_text("Opis obrazu", exact=True).first.click()
    expect(page.locator(".source-content").first).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=f"/tmp/ai-slop-direction-{engine}.png", full_page=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated-frontend-url", required=True)
    parser.add_argument("--isolated-backend-url", required=True)
    args = parser.parse_args()
    run(args.isolated_frontend_url, args.isolated_backend_url, verify=verify)
    print("PASS: real visual plan, exact estimates, scenes, Chromium/WebKit, mobile")
