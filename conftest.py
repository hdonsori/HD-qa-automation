import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from config.settings import (
    AUTH_FILE,
    BASE_URL,
    BROWSER_CHANNEL,
    DEFAULT_TIMEOUT_MS,
    HEADLESS,
    SLOW_MO,
)
from fixtures.auth_fixtures import AUTH_STATE_PATH, validate_or_refresh_storage_state
from utils.auth_token_manager import (
    is_access_token_valid,
    load_token_bundle,
    save_token_bundle,
    try_refresh_token_bundle,
)


ARTIFACTS_DIR = Path("artifacts")
SCREENSHOTS_DIR = ARTIFACTS_DIR / "screenshots"
LOGS_DIR = ARTIFACTS_DIR / "logs"


def _build_logger() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("qa-automation")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.FileHandler(LOGS_DIR / "test-run.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
    return logger


@pytest.fixture(scope="session", autouse=True)
def ensure_artifacts():
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session")
def test_logger() -> logging.Logger:
    return _build_logger()


@pytest.fixture(scope="session")
def base_url() -> str:
    if not BASE_URL:
        pytest.fail("BASE_URL is not configured.")
    return BASE_URL


@pytest.fixture(scope="session")
def prod_email() -> str:
    value = os.getenv("TRIO_PROD_EMAIL", "").strip()
    if not value:
        pytest.fail("TRIO_PROD_EMAIL is not configured.")
    return value


@pytest.fixture(scope="session")
def prod_password() -> str:
    value = os.getenv("TRIO_PROD_PASSWORD", "").strip()
    if not value:
        pytest.fail("TRIO_PROD_PASSWORD is not configured.")
    return value


@pytest.fixture(scope="session")
def auth_bundle():
    bundle = load_token_bundle()
    if is_access_token_valid(bundle):
        return bundle

    if bundle:
        refreshed = try_refresh_token_bundle(bundle)
        if refreshed:
            save_token_bundle(refreshed)
            return refreshed

    return bundle


@pytest.fixture(scope="session")
def auth_headers(auth_bundle):
    if not auth_bundle or not auth_bundle.get("access_token"):
        return {}
    return {"Authorization": f"Bearer {auth_bundle['access_token']}"}


@pytest.fixture(scope="session")
def playwright_instance() -> Playwright:
    with sync_playwright() as playwright:
        yield playwright


@pytest.fixture(scope="session")
def browser(playwright_instance: Playwright) -> Browser:
    browser = playwright_instance.chromium.launch(
        channel=BROWSER_CHANNEL,
        headless=HEADLESS,
        slow_mo=SLOW_MO,
        args=["--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage", "--no-sandbox"],
    )
    yield browser
    browser.close()


@pytest.fixture(scope="session")
def authenticated_storage_state(browser: Browser, base_url: str, prod_email: str, prod_password: str, test_logger: logging.Logger) -> str:
    auth_path = Path(os.getenv("AUTH_FILE", AUTH_FILE) or AUTH_STATE_PATH)
    resolved = validate_or_refresh_storage_state(
        browser=browser,
        base_url=base_url,
        email=prod_email,
        password=prod_password,
        auth_state_path=auth_path,
        logger=test_logger,
    )
    test_logger.info("Using auth storage state: %s", resolved)
    return str(resolved)


@pytest.fixture(scope="function")
def context(
    browser: Browser,
    authenticated_storage_state: str,
    base_url: str,
    prod_email: str,
    prod_password: str,
    test_logger: logging.Logger,
) -> BrowserContext:
    # Per-test auth lifecycle check for stale/expired production sessions.
    # This keeps authenticated UI flows self-healing across long runs.
    validate_or_refresh_storage_state(
        browser=browser,
        base_url=base_url,
        email=prod_email,
        password=prod_password,
        auth_state_path=Path(authenticated_storage_state),
        logger=test_logger,
    )

    context = browser.new_context(
        storage_state=authenticated_storage_state,
        viewport={"width": 1600, "height": 900},
        ignore_https_errors=True,
    )
    context.set_default_timeout(DEFAULT_TIMEOUT_MS)
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    try:
        yield context
    finally:
        trace_dir = ARTIFACTS_DIR / "traces"
        trace_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        trace_path = trace_dir / f"trace_{timestamp}.zip"
        try:
            context.tracing.stop(path=str(trace_path))
        except Exception:
            pass
        context.close()


@pytest.fixture(scope="function")
def page(context: BrowserContext) -> Page:
    pg = context.new_page()
    yield pg


@pytest.fixture(scope="function")
def fresh_page(browser: Browser) -> Page:
    context = browser.new_context(viewport={"width": 1600, "height": 900}, ignore_https_errors=True)
    context.set_default_timeout(DEFAULT_TIMEOUT_MS)
    pg = context.new_page()
    yield pg
    context.close()


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


@pytest.fixture(autouse=True)
def screenshot_on_failure(request: pytest.FixtureRequest):
    yield
    rep = getattr(request.node, "rep_call", None)
    context_obj = request.node.funcargs.get("context")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = request.node.nodeid.replace("/", "_").replace("::", "__")

    if rep and rep.failed:
        page_obj = request.node.funcargs.get("page")
        if page_obj and isinstance(page_obj, Page):
            path = SCREENSHOTS_DIR / f"{safe_name}_{timestamp}.png"
            try:
                if not page_obj.is_closed():
                    page_obj.screenshot(path=str(path), full_page=True)
            except Exception:
                # Never mask the original test failure with artifact errors.
                pass

    _ = context_obj
