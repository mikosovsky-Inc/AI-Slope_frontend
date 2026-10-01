"""Run ONLY against an isolated empty backend: creates two synthetic accounts."""

import argparse

from playwright.sync_api import expect, sync_playwright


def run(url):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for index, javascript in enumerate((False, True)):
            context = browser.new_context(
                java_script_enabled=javascript, viewport={"width": 1440, "height": 1000}
            )
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url)
            if index:
                page.get_by_role("link", name="Załóż konto").click()
            expect(page.locator("#confirm-password")).to_be_visible()
            if not index:
                expect(
                    page.get_by_text("Pierwsze konto otrzyma rolę administratora.")
                ).to_be_visible()
                page.screenshot(path="/tmp/ai-slop-ssr-desktop.png", full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path="/tmp/ai-slop-ssr-mobile.png", full_page=True)
            email = f"smoke{index}@example.com"
            page.locator("#email").fill(email)
            page.locator("#password").fill("isolated-test-password")
            page.locator("#confirm-password").fill("isolated-test-password")
            page.get_by_role("button", name="UTWÓRZ KONTO").click()
            expect(page.get_by_text("Konto utworzone. Możesz się zalogować.")).to_be_visible()
            page.locator("#email").fill(email)
            page.locator("#password").fill("isolated-test-password")
            page.get_by_role("button", name="WEJDŹ DO STUDIA").click()
            expect(page.get_by_text(email, exact=True)).to_be_visible()
            expect(page.locator("dd").last).to_have_text("admin" if index == 0 else "user")
            assert "isolated-test-password" not in page.content()
            page.reload()
            expect(page.get_by_text(email, exact=True)).to_be_visible()
            page.get_by_role("button", name="WYLOGUJ SIĘ").click()
            expect(page.locator("#auth-form")).to_be_visible()
            assert not errors
            context.close()
        browser.close()
    print("PASS: real backend auth, roles, reload, logout, JS on/off, mobile overflow")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated-frontend-url", required=True)
    run(parser.parse_args().isolated_frontend_url)
