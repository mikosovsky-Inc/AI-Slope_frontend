"""Browser regressions for video polling; no backend or credentials required."""

import html
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
INITIAL = dict(status="GENERATING_ASSETS", updated_at="2026-10-01", has_active_tasks=True, tasks=[])


def run():
    with sync_playwright() as p:
        for engine in (p.chromium, p.webkit):
            browser = engine.launch()
            for case in (
                "clean",
                "input",
                "change",
                "invalid",
                "unauthorized",
                "error",
                "idle",
                "unchanged",
                "bad_initial",
            ):
                page = browser.new_page()
                page.clock.install()
                calls, errors = [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                initial = INITIAL | {"has_active_tasks": case != "idle"}
                encoded = html.escape(
                    json.dumps(initial) if case != "bad_initial" else "{broken", quote=True
                )
                markup = f'''<html><head><meta charset="utf-8"></head><body>
<form><input id="edit" value="original"><select id="select"><option>A</option>
<option>B</option></select></form><section id="video-state" data-url="/status"
data-state="{encoded}"><p id="poll-message" role="status"></p></section>
<script>
window.nextPoll = 0;
const originalTimeout = window.setTimeout;
window.setTimeout = (fn, delay, ...args) => {{
  if (delay === 5000) window.nextPoll++;
  return originalTimeout(fn, delay, ...args);
}};
</script><script src="/video.js"></script></body></html>'''

                def route(request):
                    path = request.request.url.rsplit("/", 1)[-1]
                    if path == "video.js":
                        request.fulfill(
                            path=ROOT / "assets/scripts/video.js",
                            content_type="text/javascript; charset=utf-8",
                        )
                    elif path == "status":
                        calls.append(path)
                        state = (
                            INITIAL
                            if case == "unchanged"
                            else INITIAL | {"has_active_tasks": False}
                        )
                        request.fulfill(
                            status=401
                            if case == "unauthorized"
                            else 503
                            if case == "error"
                            else 200,
                            json={} if case == "invalid" else state,
                        )
                    else:
                        calls.append(path)
                        request.fulfill(body=markup, content_type="text/html; charset=utf-8")

                page.route("http://studio.test/**", route)
                page.goto("http://studio.test/video")
                if case == "input":
                    page.locator("#edit").fill("niezapisana scena")
                if case == "change":
                    page.locator("#select").evaluate(
                        "e => {e.value='B'; e.dispatchEvent(new Event('change',{bubbles:true}));}"
                    )
                page.clock.run_for(3100)
                if case in ("input", "change"):
                    expect(page.locator("#poll-message")).to_contain_text("niezapisane zmiany")
                    page.clock.run_for(10000)
                    assert calls.count("status") == 1
                    assert calls.count("video") == 1
                    if case == "input":
                        expect(page.locator("#edit")).to_have_value("niezapisana scena")
                elif case == "clean":
                    page.wait_for_function("document.readyState === 'complete'")
                    assert calls.count("video") == 2
                elif case == "unauthorized":
                    expect(page).to_have_url("http://studio.test/login")
                elif case == "idle":
                    assert calls.count("status") == 0
                elif case == "unchanged":
                    assert calls.count("video") == 1
                    page.wait_for_function("window.nextPoll === 1")
                    page.clock.run_for(5100)
                    page.wait_for_function("window.nextPoll === 2")
                    assert calls.count("status") == 2
                else:
                    expect(page.locator("#poll-message")).to_contain_text("odświeżanie zatrzymane")
                    page.clock.run_for(10000)
                    assert calls.count("video") == 1
                    assert calls.count("status") == (0 if case == "bad_initial" else 1)
                assert not errors, errors
                page.close()
            browser.close()
    print("PASS: video polling, edits, idle/active state, bad payloads, auth; Chromium/WebKit")


if __name__ == "__main__":
    run()
