import os
import random
import string
import time

import pytest

from config.settings import MARKETING_BASE_URL
from pages.trial_onboarding_page import TrialOnboardingPage


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        pytest.skip(f"Missing required env var: {name}")
    return value


def _build_email_from_template() -> str:
    template = os.getenv("TRIO_TRIAL_EMAIL_TEMPLATE", "").strip()
    if not template:
        return _required_env("TRIO_TRIAL_EMAIL")
    digits = "".join(random.choices(string.digits, k=6))
    return template.replace("{digits}", digits)


@pytest.mark.onboarding
@pytest.mark.parametrize("region", ["us", "eu", "in"])
def test_trial_signup_to_dashboard_happy_path(fresh_page, region):
    """
    Full flow:
    1) trio.so start trial
    2) signup as Business
    3) verify email code
    4) set password
    5) navigate to company portal
    6) login and complete MFA
    7) dashboard is visible
    """
    email = _build_email_from_template()
    password = os.getenv("TRIO_ACCOUNT_SETUP_PASSWORD", "").strip() or _required_env("TRIO_TRIAL_PASSWORD")
    company_prefix = os.getenv("TRIO_COMPANY_PREFIX", "qaauto")
    verification_code = _required_env("TRIO_EMAIL_VERIFICATION_CODE")
    mfa_token = _required_env("TRIO_MFA_TOKEN")

    page = TrialOnboardingPage(fresh_page)

    # Keep company unique per run/worker to avoid domain-collision flakiness.
    worker_id = os.getenv("PYTEST_XDIST_WORKER", "gw0")
    company_name = f"{company_prefix}-{region}-{worker_id}-{int(time.time())}"

    page.open_marketing_home(MARKETING_BASE_URL)
    page.start_free_trial()
    page.fill_signup_form(email=email, company_name=company_name, region=region)
    page.submit_email_code(verification_code=verification_code)
    page.set_password(password=password)
    page.navigate_to_portal_or_open_url()
    page.login_to_portal(email=email, password=password)
    page.submit_mfa_token(mfa_token=mfa_token)
    page.assert_dashboard_loaded()
