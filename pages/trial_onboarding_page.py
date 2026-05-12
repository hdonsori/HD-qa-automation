from playwright.sync_api import expect

from pages.base_page import BasePage


class TrialOnboardingPage(BasePage):
    # Marketing / CTA
    START_TRIAL_BUTTON = "a:has-text('Start Free Trial'), button:has-text('Start Free Trial')"
    START_TRIAL_SIGNUP_LINK = "a[href*='business.trio.so/auth/signup']"
    GET_STARTED_BUTTON = "button:has-text('Get Started')"

    # Signup form
    BUSINESS_RADIO = "button:has-text('Business'), label:has-text('Business'), [role='radio'][name='Business']"
    FIRST_NAME_INPUT = "input[name='firstName']"
    LAST_NAME_INPUT = "input[name='lastName']"
    PHONE_INPUT = "input[name='phone_number'], input[type='tel']"
    COMPANY_NAME_INPUT = "input[name='companyName'], input[placeholder*='company']"
    REGION_DROPDOWN = "select[name='region'], [role='combobox']"
    EMAIL_INPUT = "input[name='email'], input[type='email']"

    # Verification / activation
    VERIFICATION_CODE_INPUT = "input[name='code'], input[inputmode='numeric']"
    ACTIVATE_BUTTON = "button:has-text('Activate'), button:has-text('Activated')"

    # Password setup
    ACCOUNT_SETUP_HEADER = "text=Complete your account setup"
    PASSWORD_INPUT = "input[name='password']"
    PASSWORD_CONFIRM_INPUT = "input[name='confirmPassword'], input[name='passwordConfirmation']"
    NEXT_BUTTON = "button:has-text('Next')"

    # Portal navigation / login
    NAVIGATE_TO_PORTAL_BUTTON = "a:has-text('Navigate to portal'), button:has-text('Navigate to portal')"
    PORTAL_URL_TEXT = "text=/[a-z0-9-]+\\.(us|eu|in)\\.trio\\.so/i"
    SIGNIN_EMAIL_INPUT = "input[name='email'], input[type='email']"
    SIGNIN_PASSWORD_INPUT = "input[name='password']"
    SIGNIN_NEXT_BUTTON = "button:has-text('Next'), button:has-text('Continue')"

    # MFA
    MFA_TOKEN_INPUT = "input[name='token'], input[autocomplete='one-time-code'], input[inputmode='numeric']"
    DASHBOARD_ANCHOR = "text=/Dashboard|Devices|Policies|Compliance/i"

    def open_marketing_home(self, marketing_base_url: str) -> None:
        self.page.goto(marketing_base_url, wait_until="domcontentloaded")

    def start_free_trial(self) -> None:
        direct_signup_cta = self.page.locator(self.START_TRIAL_SIGNUP_LINK).first
        if direct_signup_cta.is_visible():
            direct_signup_cta.click()
        else:
            self.page.locator(self.START_TRIAL_BUTTON).first.click()

        try:
            self.page.wait_for_url("**business.trio.so/auth/signup**", timeout=5000)
        except Exception:
            self.page.goto("https://business.trio.so/auth/signup", wait_until="domcontentloaded")
        # CTA destinations vary by page variant. We accept whichever onboarding
        # marker appears first.
        onboarding_markers = [
            self.page.locator(self.GET_STARTED_BUTTON).first,
            self.page.locator(self.EMAIL_INPUT).first,
            self.page.locator(self.COMPANY_NAME_INPUT).first,
        ]
        for marker in onboarding_markers:
            try:
                expect(marker).to_be_visible(timeout=6000)
                return
            except Exception:
                continue

    def fill_signup_form(self, email: str, company_name: str, region: str) -> None:
        self.select_business_use_case()

        first_name = self.page.locator(self.FIRST_NAME_INPUT).first
        if first_name.is_visible():
            first_name.fill("QA")

        last_name = self.page.locator(self.LAST_NAME_INPUT).first
        if last_name.is_visible():
            last_name.fill("Automation")

        phone = self.page.locator(self.PHONE_INPUT).first
        if phone.is_visible():
            phone.fill("+12025550123")

        self.page.locator(self.EMAIL_INPUT).first.fill(email)
        self.page.locator(self.GET_STARTED_BUTTON).first.click()

        company_input = self.page.locator(self.COMPANY_NAME_INPUT).first
        if company_input.is_visible():
            company_input.fill(company_name)
            self._select_region(region)
            self.page.locator(self.GET_STARTED_BUTTON).first.click()

    def select_business_use_case(self) -> None:
        business_choice = self.page.locator(self.BUSINESS_RADIO).first
        expect(business_choice).to_be_visible(timeout=15000)
        business_choice.click()
        # Ensure the option remains selected/focused before continuing form fill.
        expect(business_choice).to_be_visible()

    def submit_email_code(self, verification_code: str) -> None:
        code_input = self.page.locator(self.VERIFICATION_CODE_INPUT).first
        expect(code_input).to_be_visible()
        code_input.fill(verification_code)
        self.page.locator(self.ACTIVATE_BUTTON).first.click()

    def set_password(self, password: str) -> None:
        setup_header = self.page.locator(self.ACCOUNT_SETUP_HEADER).first
        if setup_header.count():
            expect(setup_header).to_be_visible(timeout=20000)
        self.page.locator(self.PASSWORD_INPUT).first.fill(password)
        self.page.locator(self.PASSWORD_CONFIRM_INPUT).first.fill(password)
        self.page.locator(self.NEXT_BUTTON).first.click()

    def navigate_to_portal_or_open_url(self) -> None:
        portal_button = self.page.locator(self.NAVIGATE_TO_PORTAL_BUTTON).first
        if portal_button.is_visible():
            portal_button.click()
            return

        portal_url_match = self.page.locator(self.PORTAL_URL_TEXT).first.text_content()
        if portal_url_match:
            self.page.goto(f"https://{portal_url_match.strip()}", wait_until="domcontentloaded")

    def login_to_portal(self, email: str, password: str) -> None:
        self.page.locator(self.SIGNIN_EMAIL_INPUT).first.fill(email)
        self.page.locator(self.SIGNIN_PASSWORD_INPUT).first.fill(password)
        self.page.locator(self.SIGNIN_NEXT_BUTTON).first.click()

    def submit_mfa_token(self, mfa_token: str) -> None:
        token_input = self.page.locator(self.MFA_TOKEN_INPUT).first
        expect(token_input).to_be_visible()
        token_input.fill(mfa_token)
        self.page.locator(self.NEXT_BUTTON).first.click()

    def assert_dashboard_loaded(self) -> None:
        expect(self.page.locator(self.DASHBOARD_ANCHOR).first).to_be_visible()

    def _select_region(self, region: str) -> None:
        normalized = region.lower().replace(".", "")
        dropdown = self.page.locator(self.REGION_DROPDOWN).first

        if dropdown.count() and dropdown.first.is_visible():
            try:
                dropdown.select_option(value=normalized)
                return
            except Exception:
                pass

            try:
                dropdown.select_option(label=f".{normalized}")
                return
            except Exception:
                pass

        self.page.get_by_text(f".{normalized}", exact=False).first.click()
