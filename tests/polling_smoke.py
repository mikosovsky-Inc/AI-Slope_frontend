"""Real browser regression tests for polling with deterministic HTTP responses."""

from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def run():
    with sync_playwright() as p:
        for engine in (p.chromium, p.webkit):
            browser = engine.launch()
            for case in ("clean", "input", "change", "invalid", "unknown", "unauthorized", "error"):
                page = browser.new_page()
                page.clock.install()
                calls = []
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                html = """<html><head><meta charset="utf-8"></head><body>
<form><input id="edit" value="original">
<select id="select"><option>A</option><option>B</option></select></form>
<section id="analysis-task" data-status="running"
data-status-url="/status"><p id="task-message" role="status"></p></section>
<script src="/channel.js"></script></body></html>"""

                def route(request):
                    path = request.request.url.rsplit("/", 1)[-1]
                    if path == "channel.js":
                        request.fulfill(
                            path=ROOT / "assets/scripts/channel.js",
                            content_type="text/javascript; charset=utf-8",
                        )
                    elif path == "status":
                        calls.append("status")
                        request.fulfill(
                            status=401
                            if case == "unauthorized"
                            else 503
                            if case == "error"
                            else 200,
                            json={}
                            if case == "invalid"
                            else {"status": "future" if case == "unknown" else "succeeded"},
                        )
                    else:
                        calls.append(path)
                        request.fulfill(body=html, content_type="text/html")

                page.route("http://studio.test/**", route)
                page.goto("http://studio.test/channel")
                if case == "input":
                    page.locator("#edit").fill("niezapisana zmiana")
                if case == "change":
                    page.locator("#select").evaluate(
                        "e => {e.value='B'; e.dispatchEvent(new Event('change',{bubbles:true}));}"
                    )
                page.clock.run_for(3100)
                if case in ("input", "change"):
                    expect(page.locator("#task-message")).to_contain_text("niezapisane zmiany")
                    assert calls.count("channel") == 1
                    if case == "input":
                        expect(page.locator("#edit")).to_have_value("niezapisana zmiana")
                elif case == "clean":
                    expect(page.locator("#edit")).to_have_value("original")
                    assert calls.count("channel") == 2
                elif case == "unauthorized":
                    expect(page).to_have_url("http://studio.test/login")
                else:
                    expect(page.locator("#task-message")).to_contain_text("odświeżanie zatrzymane")
                    assert calls.count("channel") == 1
                assert not errors, errors
                page.close()
            browser.close()
    print(
        "PASS: Chromium/WebKit polling protects edits, reloads clean forms, "
        "handles bad responses and 401"
    )


if __name__ == "__main__":
    run()
