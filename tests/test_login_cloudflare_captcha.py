import os
import re

from playwright.sync_api import expect, sync_playwright


BASE_URL = os.getenv("BASE_URL", "https://a99.trio-dev.us.bcpapers.ca")
TRIO_EMAIL = os.getenv("TRIO_EMAIL", "a+99@sternx.de")
TRIO_PASSWORD = os.getenv("TRIO_PASSWORD", "Trio@123")
BROWSER_CHANNEL = os.getenv("BROWSER_CHANNEL", "chrome")
SLOW_MO_MS = int(os.getenv("SLOW_MO_MS", "250"))
CAPTCHA_TIMEOUT_MS = int(os.getenv("CAPTCHA_TIMEOUT_MS", "180000"))
LOGIN_API_PATTERN = re.compile(r"/v2/auth/login(?:$|[?#])")
SUCCESS_URL_PATTERN = re.compile(r"/(dashboard|home|identity|directory)(?:$|[/?#])")
SUCCESS_TEXT_PATTERN = re.compile(r"Good (morning|afternoon|evening)|Dashboard|Identity")


def test_login_flow_with_cloudflare_captcha_headed() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel=BROWSER_CHANNEL,
            headless=False,
            slow_mo=SLOW_MO_MS,
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir="artifacts/videos",
        )
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()

        try:
            page.goto(f"{BASE_URL.rstrip('/')}/auth/login", wait_until="domcontentloaded")

            page.locator('input[name="email"]').fill(TRIO_EMAIL)
            page.locator('input[name="email"]').press("Tab")
            page.locator('input[name="password"]').fill(TRIO_PASSWORD)
            page.get_by_role("checkbox").check()
            page.screenshot(path="artifacts/screenshots/login-filled-before-captcha.png", full_page=True)

            continue_button = page.get_by_role("button", name="Continue")
            expect(continue_button).to_be_enabled(timeout=CAPTCHA_TIMEOUT_MS)

            with page.expect_response(
                lambda response: bool(LOGIN_API_PATTERN.search(response.url))
                and response.request.method == "POST",
                timeout=60000,
            ) as login_response_info:
                continue_button.click()

            login_response = login_response_info.value
            assert login_response.status == 201, f"Expected login API status 201, got {login_response.status}"

            page.wait_for_url(SUCCESS_URL_PATTERN, timeout=60000)
            expect(page.locator("body")).to_contain_text(SUCCESS_TEXT_PATTERN, timeout=30000)
            page.screenshot(path="artifacts/screenshots/login-success.png", full_page=True)
        finally:
            context.tracing.stop(path="artifacts/traces/login-flow-with-cloudflare.zip")
            context.close()
            browser.close()
