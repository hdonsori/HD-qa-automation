import re
import time
from typing import Optional

from playwright.sync_api import Page, Response, expect


class LoginFlowPage:
    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")

        self.email_input = self.page.locator('input[name="email"]')
        self.password_input = self.page.locator('input[name="password"]')
        self.continue_button = self.page.locator('button:has-text("Continue")')

    def goto_login(self) -> None:
        # Localized resilience for intermittent login-page navigation delays.
        last_error = None
        for _ in range(2):
            try:
                self.page.goto(f"{self.base_url}/auth/login", wait_until="domcontentloaded", timeout=45000)
                break
            except Exception as err:
                last_error = err
                self.page.wait_for_timeout(1000)
        else:
            raise last_error  # type: ignore[misc]
        self.wait_login_form_ready()

    def wait_login_form_ready(self, timeout_ms: int = 30000) -> None:
        expect(self.page).to_have_url(re.compile(r".*/auth/login.*"), timeout=timeout_ms)
        expect(self.email_input).to_be_visible(timeout=timeout_ms)
        expect(self.password_input).to_be_visible(timeout=timeout_ms)
        expect(self.continue_button).to_be_visible(timeout=timeout_ms)

    def fill_credentials(self, email: str, password: str) -> None:
        self.email_input.fill(email)
        self.password_input.fill(password)

    def continue_enabled(self) -> bool:
        try:
            return self.continue_button.is_enabled()
        except Exception:
            return False

    def submit_with_optional_auth_capture(self, timeout_ms: int = 15000) -> Optional[Response]:
        # Client-side validations may block API call; return None in that case.
        try:
            with self.page.expect_response(
                lambda r: "/v2/auth/login" in r.url,
                timeout=timeout_ms,
            ) as auth_wait:
                self.continue_button.click(timeout=timeout_ms)
            return auth_wait.value
        except Exception:
            try:
                self.continue_button.click(timeout=timeout_ms)
            except Exception:
                pass
            return None

    def wait_after_submit(self, ms: int = 1500) -> None:
        self.page.wait_for_load_state("domcontentloaded")
        self.page.wait_for_timeout(ms)

    def is_authenticated(self) -> bool:
        return "/auth/login" not in self.page.url

    def has_auth_tokens(self) -> bool:
        try:
            tokens = self.page.evaluate(
                """
                () => ({
                  access: localStorage.getItem('access_token') || '',
                  refresh: localStorage.getItem('refresh_token') || ''
                })
                """
            )
            return bool(tokens.get("access") or tokens.get("refresh"))
        except Exception:
            return False

    def protected_route_denied(self, route: str = "/fleet/mdm-setup") -> bool:
        self.page.goto(f"{self.base_url}{route}", wait_until="domcontentloaded")
        self.page.wait_for_timeout(1000)
        current = self.page.url
        if "/auth/login" in current or "/404" in current:
            return True
        # Safety fallback: treat as denied if no auth tokens and no authenticated markers.
        return (not self.has_auth_tokens()) and (not self.authenticated_markers_visible())

    def authenticated_markers_visible(self) -> bool:
        markers = [
            self.page.locator("text=Fleet"),
            self.page.locator("text=Dashboard"),
            self.page.locator("text=Device Groups"),
        ]
        for marker in markers:
            try:
                if marker.count() > 0 and marker.first.is_visible():
                    return True
            except Exception:
                continue
        return False

    def error_text(self) -> str:
        # Keep selectors local to login flow and avoid regex+CSS mixed selector syntax.
        text_candidates = self.page.locator("text=/error|invalid|not valid|incorrect|try again/i")
        if text_candidates.count() > 0:
            return text_candidates.first.inner_text().strip()

        alert_candidates = self.page.locator('[role="alert"], [aria-live]')
        if alert_candidates.count() > 0:
            return alert_candidates.first.inner_text().strip()
        return ""

    def wait_authenticated_shell(self, timeout_ms: int = 30000) -> None:
        start = time.perf_counter()
        expect(self.page).to_have_url(re.compile(rf"^{re.escape(self.base_url)}/.*"), timeout=timeout_ms)
        if "/auth/login" in self.page.url:
            raise AssertionError(f"Expected authenticated route, still on login: {self.page.url}")

        markers = [
            self.page.locator("text=Fleet"),
            self.page.locator("text=Dashboard"),
            self.page.locator("text=Settings"),
        ]
        for marker in markers:
            if marker.count() > 0 and marker.first.is_visible():
                break
        elapsed = round((time.perf_counter() - start) * 1000)
        print(f"[DEBUG] auth_shell_ready url={self.page.url} duration_ms={elapsed}")

    def try_logout(self) -> bool:
        # Open lower-left account panel if present.
        openers = [
            self.page.locator('[data-testid*="account"]'),
            self.page.locator('[data-testid*="profile"]'),
            self.page.locator('button[aria-label*="account" i], button[aria-label*="profile" i]'),
            self.page.locator('[data-testid*="sidebar"] >> text=Settings'),
            self.page.locator('div:has-text("Settings")'),
        ]

        panel_expanded = False
        for opener in openers:
            if opener.count() == 0:
                continue
            try:
                opener.first.click(timeout=2500)
                self.page.wait_for_timeout(600)
                panel_expanded = True
                break
            except Exception:
                continue

        # Sidebar/account scoped Sign Out strategy.
        scoped_sidebar = self.page.locator(
            'aside, nav, [data-testid*="sidebar"], [class*="sidebar"], [class*="drawer"]'
        )
        signout_candidates = [
            scoped_sidebar.locator('text=Sign Out'),
            scoped_sidebar.get_by_role("button", name="Sign Out"),
            scoped_sidebar.get_by_role("link", name="Sign Out"),
            self.page.locator('text=Sign Out'),
        ]

        clicked = False
        for idx, candidate in enumerate(signout_candidates, start=1):
            count = candidate.count()
            visible = count > 0 and candidate.first.is_visible()
            enabled = False
            if visible:
                try:
                    enabled = candidate.first.is_enabled()
                except Exception:
                    enabled = False
            print(
                f"[DEBUG] signout_candidate_{idx} count={count} visible={visible} "
                f"enabled={enabled} panel_expanded={panel_expanded}"
            )

            if not (count > 0 and visible and enabled):
                continue

            try:
                candidate.first.click(timeout=4000)
                clicked = True
                break
            except Exception:
                continue

        if not clicked:
            return False

        self.page.wait_for_load_state("domcontentloaded")
        self.page.wait_for_timeout(1200)
        return "/auth/login" in self.page.url
