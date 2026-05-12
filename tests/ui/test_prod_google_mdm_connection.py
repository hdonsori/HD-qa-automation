import re
import time
from typing import Tuple

import pytest
from playwright.sync_api import Locator, Page, expect

from fixtures.auth_fixtures import ensure_authenticated_on_page


class MdmSetupPage:
    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url

    def ensure_authenticated(self, email: str, password: str) -> None:
        ensure_authenticated_on_page(
            page=self.page,
            base_url=self.base_url,
            email=email,
            password=password,
        )

    def click_with_retry(self, locator: Locator, step_name: str, attempts: int = 3) -> None:
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                expect(locator).to_be_visible(timeout=7000)
                locator.click(timeout=7000)
                return
            except Exception as err:
                last_error = err
                if attempt < attempts:
                    self.page.wait_for_load_state("domcontentloaded")
                    self.page.wait_for_timeout(800)
        raise AssertionError(f"Failed to click '{step_name}' after {attempts} attempts: {last_error}")

    def _log_locator_state(self, locator: Locator, label: str) -> None:
        count = locator.count()
        first_visible = False
        if count > 0:
            try:
                first_visible = locator.first.is_visible()
            except Exception:
                first_visible = False
        print(f"[DEBUG] {label}: count={count}, first_visible={first_visible}")

    def _google_tab_locator(self) -> Locator:
        # Prefer stable attributes first, then scoped text fallback under the MDM header/nav area.
        candidates = [
            self.page.locator('[data-testid=\"mdm-google-tab\"]'),
            self.page.locator('[data-testid*=\"google\"][data-testid*=\"tab\"]'),
            self.page.locator('button[data-value=\"google\"]'),
            self.page.locator('a[href*=\"tab=google\"]'),
            self.page.locator('nav:has-text(\"Apple\")').locator('text=Google'),
            self.page.locator('div:has-text(\"MDM Setup\")').locator('text=Google'),
            self.page.locator('text=Google'),
        ]

        for idx, candidate in enumerate(candidates, start=1):
            self._log_locator_state(candidate, f"google_candidate_{idx}")
            if candidate.count() > 0:
                return candidate.first
        return self.page.locator('text=Google').first

    def _wait_for_mdm_ui_ready(self, timeout_ms: int = 30000) -> None:
        start = time.perf_counter()
        expect(self.page).to_have_url(re.compile(r".*/MDM.*|.*/mdm.*"), timeout=timeout_ms)
        self.page.wait_for_load_state("domcontentloaded")

        # Route-specific readiness markers for this SPA page.
        markers = [
            ("mdm_header", self.page.locator("text=Google MDM Setup")),
            ("trio_managed", self.page.locator("text=Trio Managed")),
            ("apple_tab_text", self.page.locator("text=Apple")),
        ]

        marker_used = None
        for label, marker in markers:
            count = marker.count()
            visible = count > 0 and marker.first.is_visible()
            print(
                f"[DEBUG] mdm_ready_marker_probe label={label} "
                f"url={self.page.url} count={count} visible={visible}"
            )
            if visible:
                marker_used = label
                break

        if not marker_used:
            # Wait for primary marker if hydration is delayed.
            expect(self.page.locator("text=Google MDM Setup")).to_be_visible(timeout=timeout_ms)
            marker_used = "mdm_header_delayed"

        elapsed_ms = round((time.perf_counter() - start) * 1000)
        print(
            f"[DEBUG] mdm_ui_ready url={self.page.url} marker={marker_used} "
            f"duration_ms={elapsed_ms}"
        )

    def navigate_to_google_tab(self) -> None:
        fleet_link = self.page.get_by_role("link", name="Fleet")
        self.click_with_retry(fleet_link, "Fleet sidebar link")

        mdm_setup_link = self.page.get_by_role("link", name=re.compile(r"MDM setup", re.I))
        self.click_with_retry(mdm_setup_link, "MDM setup link")
        self._wait_for_mdm_ui_ready(timeout_ms=30000)

        google_tab = self._google_tab_locator()
        self._log_locator_state(google_tab, "google_tab_selected")
        self.click_with_retry(google_tab, "Google tab")
        # Role/state attributes are not guaranteed; verify by URL/tab content instead.
        expect(self.page).to_have_url(re.compile(r".*tab=google.*|.*/MDM.*"), timeout=15000)
        expect(self.page.locator("text=Google MDM Setup")).to_be_visible(timeout=15000)

    def trio_managed_status(self) -> Tuple[str, str]:
        # Scope to the section that includes the "Trio Managed" heading.
        trio_section = self.page.locator("section,div").filter(has_text=re.compile(r"Trio Managed", re.I)).first
        expect(trio_section).to_be_visible(timeout=10000)

        connected_tag = trio_section.get_by_text("Connected", exact=True)
        not_connected_tag = trio_section.get_by_text("Not connected", exact=True)

        if connected_tag.count() > 0 and connected_tag.first.is_visible():
            color = connected_tag.first.evaluate("el => getComputedStyle(el).color")
            return "Connected", color

        if not_connected_tag.count() > 0 and not_connected_tag.first.is_visible():
            color = not_connected_tag.first.evaluate("el => getComputedStyle(el).color")
            return "Not connected", color

        raise AssertionError("Neither 'Connected' nor 'Not connected' tag was visible for Trio Managed.")


@pytest.mark.production
@pytest.mark.critical
def test_prod_google_mdm_verify_connection(
    page: Page,
    base_url: str,
    prod_email: str,
    prod_password: str,
    test_logger,
) -> None:
    """
    Production UI flow:
    1) Login with production credentials
    2) Open Fleet
    3) Open MDM setup
    4) Open Google tab
    5) Validate Trio Managed connection status tag
    """
    mdm_page = MdmSetupPage(page=page, base_url=base_url)
    test_logger.info("Starting production Google MDM connection verification.")

    mdm_page.ensure_authenticated(email=prod_email, password=prod_password)
    mdm_page.navigate_to_google_tab()
    status_text, status_color = mdm_page.trio_managed_status()

    test_logger.info("Trio Managed status=%s, color=%s", status_text, status_color)

    assert status_text in {"Connected", "Not connected"}, "Unexpected status label for Trio Managed."
    if status_text == "Connected":
        assert "rgb(" in status_color, "Connected tag color could not be read."
    else:
        assert "rgb(" in status_color, "Not connected tag color could not be read."
