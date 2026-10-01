"""Operations against an explicitly isolated backend with mock providers."""

import argparse
import time

from playwright.sync_api import expect
from video_smoke import run


def verify(page, api, video_id, channel_id, engine):
    origin = page.url.split("/videos/")[0]
    page.goto(origin + f"/channels/{channel_id}/costs")
    expect(page.get_by_role("heading", name="Cała historia kanału")).to_be_visible()
    page.goto(origin + f"/videos/{video_id}/budget")
    expect(page.get_by_role("heading", name="Budżet według backendu")).to_be_visible()
    page.goto(origin + "/jobs")
    expect(page.get_by_role("heading", name="Liczniki")).to_be_visible()
    page.get_by_role("button", name="FILTRUJ").click()
    expect(page.get_by_role("heading", name="Liczniki")).to_be_visible()
    page.goto(origin + f"/videos/{video_id}/revisions")
    if engine == "chromium":
        page.get_by_role("button", name="UTWÓRZ REWIZJĘ").click()
        expect(page.get_by_role("heading", name="Wersja 2 · draft")).to_be_visible()
        page.locator("summary").first.click()
        page.locator("select[name=camera_motion]").first.select_option("pan_left")
        page.get_by_role("button", name="ZAPISZ SCENĘ REWIZJI").first.click()
        page.get_by_role("button", name="PRODUKUJ REWIZJĘ").click()
        for _ in range(240):
            versions = api.get(f"/api/v1/videos/{video_id}/revisions").json()
            if any(v["number"] == 2 and v["status"] == "ready" for v in versions):
                break
            time.sleep(0.5)
        assert any(v["number"] == 2 and v["status"] == "ready" for v in versions)
        assert any(v["number"] == 1 and v["final_asset_id"] for v in versions)
        page.reload()
        page.get_by_role("button", name="UTWÓRZ REWIZJĘ").click()
        page.locator("input[name=confirmed]").check()
        page.get_by_role("button", name="ANULUJ REWIZJĘ").click()
        expect(page.get_by_role("heading", name="Wersja 3 · cancelled")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=f"/tmp/ai-slop-operations-{engine}.png", full_page=True)
    task = api.get(f"/api/v1/videos/{video_id}/status").json()["tasks"][0]
    page.goto(origin + "/tasks/" + task["id"])
    expect(page.get_by_role("heading", name="Historia odzyskiwania")).to_be_visible()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated-frontend-url", required=True)
    parser.add_argument("--isolated-backend-url", required=True)
    args = parser.parse_args()
    run(args.isolated_frontend_url, args.isolated_backend_url, verify=verify)
    print("PASS: costs, budget, admin filters, task details, revision edit/produce/cancel")
