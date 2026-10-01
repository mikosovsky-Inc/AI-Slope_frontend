"""Quality history for a real rendered film on an isolated mock-provider stack."""

import argparse

from playwright.sync_api import expect
from video_smoke import run


def verify(page, api, video_id, channel_id, engine):
    reports = api.get(f"/api/v1/videos/{video_id}/quality-checks")
    reports.raise_for_status()
    assert reports.json()[-1]["status"] == "passed"
    page.get_by_role("link", name="Kontrola jakości", exact=True).click()
    expect(page.get_by_role("heading", name="Kontrola jakości filmu")).to_be_visible()
    expect(page.get_by_text("Pominięta", exact=True).first).to_be_visible()
    expect(page.get_by_role("link", name="Pobierz sprawdzony plik")).to_have_attribute(
        "href", "/media/" + reports.json()[-1]["final_asset_id"] + "?attachment=true"
    )
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=f"/tmp/ai-slop-quality-{engine}.png", full_page=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated-frontend-url", required=True)
    parser.add_argument("--isolated-backend-url", required=True)
    args = parser.parse_args()
    run(args.isolated_frontend_url, args.isolated_backend_url, verify=verify)
    print("PASS: real quality reports and checked asset links, Chromium/WebKit")
