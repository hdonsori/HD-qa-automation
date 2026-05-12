import re

import pytest
from playwright.sync_api import Page

from pages.login_flow_page import LoginFlowPage


def _long_text(length: int = 5000) -> str:
    return "A" * length


@pytest.mark.production
def test_login_valid_credentials(fresh_page: Page, base_url: str, prod_email: str, prod_password: str, test_logger):
    login = LoginFlowPage(fresh_page, base_url)
    login.goto_login()
    login.fill_credentials(prod_email, prod_password)
    response = login.submit_with_optional_auth_capture()
    login.wait_after_submit()

    if response is not None:
        test_logger.info("Valid login auth status=%s", response.status)
        assert 200 <= response.status < 300
    login.wait_authenticated_shell()


@pytest.mark.production
def test_login_storage_state_reuse(page: Page, base_url: str, test_logger):
    login = LoginFlowPage(page, base_url)
    page.goto(f"{base_url}/", wait_until="domcontentloaded")
    test_logger.info("Storage-state reuse URL=%s", page.url)
    assert login.is_authenticated(), f"Expected authenticated route via storageState, got: {page.url}"
    login.wait_authenticated_shell()


@pytest.mark.production
def test_login_session_persistence_after_refresh(page: Page, base_url: str, test_logger):
    login = LoginFlowPage(page, base_url)
    page.goto(f"{base_url}/", wait_until="domcontentloaded")
    login.wait_authenticated_shell()
    page.reload(wait_until="domcontentloaded")
    assert login.is_authenticated(), f"Session lost after refresh: {page.url}"
    page.goto(f"{base_url}/fleet/mdm-setup", wait_until="domcontentloaded")
    assert login.is_authenticated(), f"Session lost after navigation: {page.url}"
    test_logger.info("Session persistence URL=%s", page.url)


@pytest.mark.production
def test_login_logout_after_success(fresh_page: Page, base_url: str, prod_email: str, prod_password: str, test_logger):
    login = LoginFlowPage(fresh_page, base_url)
    login.goto_login()
    login.fill_credentials(prod_email, prod_password)
    _ = login.submit_with_optional_auth_capture()
    login.wait_after_submit()
    login.wait_authenticated_shell()

    logged_out = login.try_logout()
    if not logged_out:
        pytest.skip("Logout control is not exposed for this tenant/runtime context.")
    assert "/auth/login" in fresh_page.url
    test_logger.info("Logout successful URL=%s", fresh_page.url)


@pytest.mark.production
@pytest.mark.parametrize(
    "email,password",
    [
        ("invalid.user@example.com", "Trio@123"),
        ("hd.onsori+2@gmail.com", "WrongPass!234"),
        ("invalid.user@example.com", "WrongPass!234"),
    ],
)
def test_login_invalid_credential_combinations(
    fresh_page: Page, base_url: str, email: str, password: str, test_logger
):
    login = LoginFlowPage(fresh_page, base_url)
    login.goto_login()
    login.fill_credentials(email, password)
    response = login.submit_with_optional_auth_capture()
    login.wait_after_submit()
    test_logger.info("Invalid combo URL=%s status=%s", fresh_page.url, None if response is None else response.status)

    assert "/auth/login" in fresh_page.url
    error_text = login.error_text().lower()
    assert "not valid" in error_text or "error" in error_text


@pytest.mark.production
def test_login_empty_email(fresh_page: Page, base_url: str):
    login = LoginFlowPage(fresh_page, base_url)
    login.goto_login()
    login.fill_credentials("", "Trio@123")
    _ = login.submit_with_optional_auth_capture(timeout_ms=12000)
    login.wait_after_submit(ms=1200)
    # Behavior-driven auth outcome validation (no hard requirement for visible inline errors).
    assert "/auth/login" in fresh_page.url
    assert not login.is_authenticated()
    assert not login.has_auth_tokens()
    assert login.protected_route_denied("/fleet/mdm-setup")
    assert not login.authenticated_markers_visible()


@pytest.mark.production
def test_login_empty_password(fresh_page: Page, base_url: str):
    login = LoginFlowPage(fresh_page, base_url)
    login.goto_login()
    login.fill_credentials("hd.onsori+2@gmail.com", "")
    _ = login.submit_with_optional_auth_capture(timeout_ms=12000)
    login.wait_after_submit(ms=1200)
    assert "/auth/login" in fresh_page.url
    assert not login.is_authenticated()
    assert not login.has_auth_tokens()
    assert login.protected_route_denied("/fleet/mdm-setup")
    assert not login.authenticated_markers_visible()


@pytest.mark.production
def test_login_empty_email_and_password(fresh_page: Page, base_url: str):
    login = LoginFlowPage(fresh_page, base_url)
    login.goto_login()
    login.fill_credentials("", "")
    _ = login.submit_with_optional_auth_capture(timeout_ms=12000)
    login.wait_after_submit(ms=1200)
    assert "/auth/login" in fresh_page.url
    assert not login.is_authenticated()
    assert not login.has_auth_tokens()
    assert login.protected_route_denied("/fleet/mdm-setup")
    assert not login.authenticated_markers_visible()


@pytest.mark.production
def test_login_invalid_email_format(fresh_page: Page, base_url: str):
    login = LoginFlowPage(fresh_page, base_url)
    login.goto_login()
    login.fill_credentials("invalid-format", "AnyPass!123")
    if login.continue_enabled():
        _ = login.submit_with_optional_auth_capture()
        login.wait_after_submit()
        assert "/auth/login" in fresh_page.url
    else:
        assert not login.continue_enabled()


@pytest.mark.production
@pytest.mark.parametrize(
    "email,password",
    [
        ("' OR '1'='1", "' OR '1'='1"),
        ("admin@example.com' --", "password' OR '1'='1"),
    ],
)
def test_login_sql_injection_attempts(fresh_page: Page, base_url: str, email: str, password: str):
    login = LoginFlowPage(fresh_page, base_url)
    login.goto_login()
    login.fill_credentials(email, password)
    _ = login.submit_with_optional_auth_capture()
    login.wait_after_submit()
    assert "/auth/login" in fresh_page.url


@pytest.mark.production
@pytest.mark.parametrize(
    "email,password",
    [
        ('<script>alert("x")</script>@example.com', "Trio@123"),
        ("hd.onsori+2@gmail.com", '<img src=x onerror=alert("x")>'),
    ],
)
def test_login_xss_injection_attempts(fresh_page: Page, base_url: str, email: str, password: str):
    login = LoginFlowPage(fresh_page, base_url)
    login.goto_login()
    login.fill_credentials(email, password)
    _ = login.submit_with_optional_auth_capture()
    login.wait_after_submit()
    assert "/auth/login" in fresh_page.url


@pytest.mark.production
def test_login_extremely_long_input_values(fresh_page: Page, base_url: str):
    login = LoginFlowPage(fresh_page, base_url)
    login.goto_login()
    login.fill_credentials(f"{_long_text()}@example.com", _long_text())
    _ = login.submit_with_optional_auth_capture(timeout_ms=10000)
    login.wait_after_submit(ms=1000)
    assert "/auth/login" in fresh_page.url


@pytest.mark.production
def test_login_leading_trailing_spaces_in_credentials(
    fresh_page: Page, base_url: str, prod_email: str, prod_password: str
):
    login = LoginFlowPage(fresh_page, base_url)
    login.goto_login()
    login.fill_credentials(f"  {prod_email}  ", f"  {prod_password}  ")
    _ = login.submit_with_optional_auth_capture()
    login.wait_after_submit()

    # Accept either behavior: app trims and logs in, or rejects and stays at login.
    assert login.is_authenticated() or "/auth/login" in fresh_page.url


@pytest.mark.production
def test_login_multiple_failed_attempts_safe(fresh_page: Page, base_url: str, test_logger):
    login = LoginFlowPage(fresh_page, base_url)
    login.goto_login()

    for attempt in range(1, 4):
        login.fill_credentials("invalid.user@example.com", f"WrongPass!{attempt}23")
        response = login.submit_with_optional_auth_capture()
        login.wait_after_submit(ms=900)
        error_text = login.error_text().lower()
        test_logger.info(
            "Safe failed-attempt #%s url=%s status=%s error=%s",
            attempt,
            fresh_page.url,
            None if response is None else response.status,
            error_text[:120],
        )
        assert "/auth/login" in fresh_page.url
        assert "not valid" in error_text or "error" in error_text
