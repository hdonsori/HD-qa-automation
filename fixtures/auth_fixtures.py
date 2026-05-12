import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, expect

from config.settings import AUTH_FILE, BASE_URL


AUTH_STATE_PATH = Path(os.getenv("AUTH_FILE", AUTH_FILE))


def ensure_auth_state_dir(path: Path = AUTH_STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def is_session_active(page: Page, base_url: str) -> bool:
    page.goto(f"{base_url}/", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    return "/auth/login" not in page.url


def is_authenticated_context(context: BrowserContext, base_url: str) -> bool:
    probe = context.new_page()
    probe.set_default_timeout(int(os.getenv("DEFAULT_TIMEOUT_MS", "30000")))
    try:
        probe.goto(f"{base_url}/", wait_until="domcontentloaded")
        probe.wait_for_load_state("networkidle")
        return "/auth/login" not in probe.url
    finally:
        probe.close()


def has_login_form(page: Page) -> bool:
    email_input = page.locator('input[name="email"]')
    password_input = page.locator('input[name="password"]')
    return email_input.count() > 0 and password_input.count() > 0


def _capture_bootstrap_failure_artifacts(page: Page, reason: str) -> None:
    artifacts_root = Path("artifacts")
    screenshots_dir = artifacts_root / "screenshots"
    logs_dir = artifacts_root / "logs"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_reason = reason.lower().replace(" ", "_")
    screenshot_path = screenshots_dir / f"auth_bootstrap_{safe_reason}_{stamp}.png"
    html_path = logs_dir / f"auth_bootstrap_{safe_reason}_{stamp}.html"
    url_path = logs_dir / f"auth_bootstrap_{safe_reason}_{stamp}.txt"

    try:
        if not page.is_closed():
            page.screenshot(path=str(screenshot_path), full_page=True)
            html_path.write_text(page.content(), encoding="utf-8")
            url_path.write_text(f"URL: {page.url}\n", encoding="utf-8")
    except Exception:
        # Never raise from artifact capture during auth fallback handling.
        pass


def _read_local_storage_snapshot(page: Page) -> dict:
    try:
        return page.evaluate(
            """
            () => {
              const out = {};
              for (let i = 0; i < localStorage.length; i++) {
                const k = localStorage.key(i);
                out[k] = localStorage.getItem(k);
              }
              return out;
            }
            """
        )
    except Exception:
        return {}


def _wait_for_authenticated_readiness(page: Page, base_url: str, logger=None, timeout_ms: int = 45000) -> tuple[bool, str]:
    """
    Stage auth readiness beyond immediate submit:
    - redirect stabilization
    - authenticated route
    - visible authenticated UI marker
    """
    start = time.perf_counter()
    page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        # Some apps keep long-polling connections; do not hard-fail on networkidle.
        pass

    # If still on login route, give SPA/router state extra time.
    for _ in range(4):
        if "/auth/login" not in page.url:
            break
        page.wait_for_timeout(1500)

    if "/auth/login" in page.url:
        elapsed = round((time.perf_counter() - start) * 1000)
        if logger:
            logger.warning("Auth readiness failed: still on login route after %sms.", elapsed)
        return False, f"still_on_login_after_{elapsed}ms"

    # Authenticated UI markers (broad but stable for this app shell).
    markers = [
        page.locator("text=Fleet"),
        page.locator("text=Dashboard"),
        page.locator("text=Device Groups"),
    ]
    marker_visible = False
    for marker in markers:
        try:
            if marker.first.count() > 0 and marker.first.is_visible():
                marker_visible = True
                break
        except Exception:
            continue

    elapsed = round((time.perf_counter() - start) * 1000)
    if logger:
        logger.info("Auth readiness check finished in %sms | marker_visible=%s | url=%s", elapsed, marker_visible, page.url)

    if not marker_visible:
        # The route is authenticated; UI marker lag should not invalidate auth session.
        return True, f"authenticated_route_marker_pending_{elapsed}ms"
    return True, f"authenticated_ready_{elapsed}ms"


def login_and_save_state(
    browser: Browser,
    base_url: str = BASE_URL,
    email: str | None = None,
    password: str | None = None,
    auth_state_path: Path = AUTH_STATE_PATH,
    logger=None,
) -> None:
    login_email = email or os.getenv("TRIO_PROD_EMAIL", "").strip()
    login_password = password or os.getenv("TRIO_PROD_PASSWORD", "").strip()

    if not login_email or not login_password:
        raise RuntimeError("TRIO_PROD_EMAIL or TRIO_PROD_PASSWORD is missing.")

    ensure_auth_state_dir(auth_state_path)

    context = browser.new_context(viewport={"width": 1600, "height": 900}, ignore_https_errors=True)
    page = context.new_page()
    page.set_default_timeout(int(os.getenv("DEFAULT_TIMEOUT_MS", "30000")))

    try:
        entry_url = f"{base_url}/auth/login"
        page.goto(entry_url, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        if logger:
            logger.info("Auth bootstrap entry URL: %s", page.url)

        # If already authenticated due app/session behavior, save and return.
        if "/auth/login" not in page.url:
            context.storage_state(path=str(auth_state_path))
            if logger:
                logger.info("Auth bootstrap skipped form submit; already authenticated at entry.")
            return

        # Login form can be delayed; retry short SPA stabilization cycles.
        for _ in range(3):
            if has_login_form(page):
                break
            page.wait_for_timeout(1500)
            page.wait_for_load_state("domcontentloaded")

        if not has_login_form(page):
            _capture_bootstrap_failure_artifacts(page, "missing_login_form")
            raise RuntimeError(f"Login form is not visible at expected login URL. Current URL: {page.url}")

        pre_cookies_count = len(context.cookies())
        pre_ls = _read_local_storage_snapshot(page)
        if logger:
            logger.info(
                "Pre-submit auth state | cookies=%s | localStorage_keys=%s",
                pre_cookies_count,
                list(pre_ls.keys())[:10],
            )

        page.locator('input[name="email"]').fill(login_email, timeout=20000)
        page.locator('input[name="password"]').fill(login_password, timeout=20000)

        submit_started = time.perf_counter()
        with page.expect_response(lambda r: "/v2/auth/login" in r.url, timeout=60000) as login_resp_wait:
            page.locator('button:has-text("Continue")').click(timeout=20000)
        login_resp = login_resp_wait.value
        login_status = login_resp.status
        if logger:
            logger.info("Auth API response | url=%s | status=%s", login_resp.url, login_status)
        if login_status < 200 or login_status >= 300:
            _capture_bootstrap_failure_artifacts(page, f"auth_api_{login_status}")
            raise RuntimeError(f"Auth API returned non-success status: {login_status}")

        ready, readiness_note = _wait_for_authenticated_readiness(page, base_url, logger=logger, timeout_ms=60000)
        if logger:
            logger.info(
                "Post-submit timing | submit_to_ready_ms=%s | readiness_note=%s",
                round((time.perf_counter() - submit_started) * 1000),
                readiness_note,
            )
        if not ready:
            _capture_bootstrap_failure_artifacts(page, "readiness_timeout")
            raise RuntimeError(f"Auth readiness failed after successful API login: {readiness_note}")

        if "/auth/login" in page.url:
            _capture_bootstrap_failure_artifacts(page, "login_stuck")
            raise RuntimeError(f"Login appears to have failed. Current URL: {page.url}")

        post_cookies_count = len(context.cookies())
        post_ls = _read_local_storage_snapshot(page)
        if logger:
            logger.info(
                "Post-submit auth state | cookies=%s (delta=%s) | localStorage_keys=%s | final_url=%s",
                post_cookies_count,
                post_cookies_count - pre_cookies_count,
                list(post_ls.keys())[:10],
                page.url,
            )

        context.storage_state(path=str(auth_state_path))
        if logger:
            logger.info("Storage state regenerated at: %s", auth_state_path)
    finally:
        context.close()


def validate_or_refresh_storage_state(
    browser: Browser,
    base_url: str,
    email: str,
    password: str,
    auth_state_path: Path = AUTH_STATE_PATH,
    logger=None,
) -> Path:
    """
    Validate current storageState and self-heal it when stale/expired.
    """
    ensure_auth_state_dir(auth_state_path)
    should_reauth = not auth_state_path.exists()

    if not should_reauth:
        probe_context = browser.new_context(storage_state=str(auth_state_path), ignore_https_errors=True)
        try:
            should_reauth = not is_authenticated_context(probe_context, base_url)
            if logger:
                logger.info("Auth probe (existing state): authenticated=%s", not should_reauth)
        except Exception as exc:
            should_reauth = True
            if logger:
                logger.warning("Auth probe failed, forcing reauth: %s", exc)
        finally:
            probe_context.close()

    if should_reauth:
        if logger:
            logger.info("Storage state invalid/missing. Regenerating auth state.")
        last_error = None
        for attempt in range(1, 3):
            try:
                if logger:
                    logger.info("Fallback auth attempt %s/2 started.", attempt)
                login_and_save_state(
                    browser=browser,
                    base_url=base_url,
                    email=email,
                    password=password,
                    auth_state_path=auth_state_path,
                    logger=logger,
                )

                # Validate regenerated state with light retry for delayed SPA auth init.
                validated = False
                for verify_round in range(1, 3):
                    verify_context = browser.new_context(storage_state=str(auth_state_path), ignore_https_errors=True)
                    try:
                        validated = is_authenticated_context(verify_context, base_url)
                        if logger:
                            logger.info(
                                "Post-regeneration auth probe round %s/2: authenticated=%s",
                                verify_round,
                                validated,
                            )
                    finally:
                        verify_context.close()

                    if validated:
                        break

                if validated:
                    if logger:
                        logger.info("Auth state regenerated and verified successfully.")
                    break

                raise RuntimeError("Reauthentication completed but session remained unauthenticated.")
            except Exception as exc:
                last_error = exc
                if logger:
                    logger.warning("Fallback auth attempt %s failed: %s", attempt, exc)
        else:
            raise RuntimeError(f"Authentication recovery failed after retries: {last_error}")

    return auth_state_path


def ensure_authenticated_on_page(page: Page, base_url: str, email: str, password: str) -> None:
    """
    Conditional authentication for test-level flows:
    - Reuse active authenticated session when present.
    - Login only when page state is unauthenticated and login form is available.
    """
    page.goto(f"{base_url}/", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    if "/auth/login" not in page.url:
        return

    page.goto(f"{base_url}/auth/login", wait_until="domcontentloaded")
    if "/auth/login" not in page.url or not has_login_form(page):
        # Defensive fallback: app may redirect quickly after auth restoration.
        page.goto(f"{base_url}/", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        if "/auth/login" not in page.url:
            return
        raise RuntimeError("Unauthenticated state detected, but login form is not available.")

    page.locator('input[name="email"]').fill(email, timeout=15000)
    page.locator('input[name="password"]').fill(password, timeout=15000)
    page.locator('button:has-text("Continue")').click(timeout=15000)
    expect(page).to_have_url(re.compile(rf"^{re.escape(base_url)}/.*"), timeout=60000)
    page.wait_for_load_state("networkidle")
