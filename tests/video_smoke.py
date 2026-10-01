"""Creates and renders a synthetic STORY; isolated stack with mock providers ONLY."""

import argparse
import re
import time
from uuid import uuid4

import httpx
from playwright.sync_api import expect, sync_playwright


def wait_task(api, result):
    if "kind" not in result:
        return
    for _ in range(120):
        task = api.get("/api/v1/tasks/" + result["id"]).json()
        if task["status"] == "succeeded":
            return
        assert task["status"] not in ("failed", "needs_review"), task["status"]
        time.sleep(0.5)
    raise AssertionError("Preparation task timeout")


def run(frontend, backend, verify=None):
    credentials = {
        "email": f"video-{uuid4().hex}@example.com",
        "password": "isolated-test-password",
    }
    with httpx.Client(base_url=backend, timeout=30) as api:
        paths = api.get("/openapi.json").json()["paths"]
        assert "/api/v1/videos/{video_id}/produce" in paths
        api.post("/api/v1/auth/register", json=credentials).raise_for_status()
        token = api.post("/api/v1/auth/login", json=credentials).json()["access_token"]
        api.headers["Authorization"] = "Bearer " + token
        channel = api.post(
            "/api/v1/channels",
            json={
                "idea": "Fikcyjne historie z zaskakującym finałem",
                "language": "pl",
                "budget_per_video_usd": "10",
            },
        ).json()
        base = "/api/v1/channels/" + channel["id"]
        wait_task(api, api.post(base + "/analyze").json())
        channel = api.get(base).json()
        config = channel["blueprint"]["configuration"]
        config["formats"] = {"top5": 0, "story": 1}
        config["video_style"]["duration_target"] = 45
        api.patch(
            base,
            json={
                "blueprint": {
                    "configuration": config,
                    "content_pillars": [
                        {"name": p["name"], "description": p["description"]}
                        for p in channel["blueprint"]["content_pillars"]
                    ],
                }
            },
        ).raise_for_status()
        wait_task(api, api.post(base + "/ideas/generate").json())
        idea = api.get(base + "/ideas").json()["items"][0]
        api.post("/api/v1/ideas/" + idea["id"] + "/approve").raise_for_status()
        with sync_playwright() as p:
            video_id = None
            for engine in (p.chromium, p.webkit):
                browser = engine.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                page.goto(frontend + "/login")
                page.locator("#email").fill(credentials["email"])
                page.locator("#password").fill(credentials["password"])
                page.get_by_role("button", name="WEJDŹ DO STUDIA").click()
                if video_id is None:
                    page.goto(frontend + "/channels/" + channel["id"] + "/ideas?status=approved")
                    page.get_by_role("button", name="UTWÓRZ FILM", exact=True).click()
                    expect(page).to_have_url(re.compile(r"/videos/[a-f0-9-]+$"))
                    video_id = page.url.rsplit("/", 1)[-1]
                    # Eager test backends need explicit script/production actions.
                    if page.get_by_role("button", name="PRZYGOTUJ SCENARIUSZ", exact=True).count():
                        page.get_by_role("button", name="PRZYGOTUJ SCENARIUSZ", exact=True).click()
                        page.get_by_role("button", name="URUCHOM PRODUKCJĘ").click()
                    for _ in range(240):
                        state = api.get("/api/v1/videos/" + video_id + "/status").json()
                        assert state["status"] != "FAILED", [
                            (t["kind"], t["status"], t["error_category"]) for t in state["tasks"]
                        ]
                        assert not any(t["status"] == "needs_review" for t in state["tasks"]), (
                            "Task needs review"
                        )
                        if state["status"] == "READY":
                            break
                        time.sleep(0.5)
                    assert state["status"] == "READY", state["status"]
                page.goto(frontend + "/videos/" + video_id)
                expect(page.get_by_role("heading", name="Stan: READY", exact=True)).to_be_visible()
                assets = api.get("/api/v1/videos/" + video_id + "/assets").json()
                final = next(a for a in reversed(assets) if a["type"] == "final_video")
                player = page.locator('video[src="/media/' + final["id"] + '"]')
                expect(player).to_be_visible()
                player.evaluate("v => {v.muted=true; v.load();}")
                page.wait_for_function(
                    "id => {const v=document.querySelector('video[src=\"/media/'+id+'\"]'); "
                    "return v.readyState >= 2 && v.duration > 0;}",
                    arg=final["id"],
                    timeout=60000,
                )
                player.evaluate("v => v.play()")
                page.wait_for_function(
                    "id => document.querySelector('video[src=\"/media/'+id+'\"]').currentTime > 0",
                    arg=final["id"],
                    timeout=30000,
                )
                response = page.request.get(
                    frontend + "/media/" + final["id"], headers={"Range": "bytes=0-31"}
                )
                assert response.status == 206 and len(response.body()) == 32
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(path=f"/tmp/ai-slop-video-{engine.name}.png", full_page=True)
                if verify:
                    verify(page, api, video_id, channel["id"], engine.name)
                browser.close()
    print("PASS: real pipeline READY, Chromium/WebKit video playback, Range, mobile")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated-frontend-url", required=True)
    parser.add_argument("--isolated-backend-url", required=True)
    args = parser.parse_args()
    run(args.isolated_frontend_url, args.isolated_backend_url)
