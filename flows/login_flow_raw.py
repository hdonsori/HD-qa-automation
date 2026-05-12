import re
from playwright.sync_api import Page, expect


def test_example(page: Page) -> None:
    page.goto("https://a99.trio-dev.us.bcpapers.ca/auth/login")
    page.locator("input[name=\"email\"]").click()
    page.locator("input[name=\"email\"]").fill("a+99@sternx.de")
    page.locator("input[name=\"email\"]").press("Tab")
    page.locator("input[name=\"password\"]").fill("Trio@123")
    page.get_by_role("checkbox").check()
    page.locator("iframe[src=\"https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/g/turnstile/f/ov2/av0/rch/u2305/0x4AAAAAADJfqlrgrJlm1qdE/light/fbE/new/flexible?lang=auto\"]").content_frame.locator("body").click()
    page.locator("iframe[src=\"https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/g/turnstile/f/ov2/av0/rch/u2305/0x4AAAAAADJfqlrgrJlm1qdE/light/fbE/new/flexible?lang=auto\"]").content_frame.locator("body").click()
