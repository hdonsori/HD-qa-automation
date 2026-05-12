from pages.base_page import BasePage


class LoginPage(BasePage):

    EMAIL_INPUT = 'input[name="email"]'
    PASSWORD_INPUT = 'input[name="password"]'
    CONTINUE_BUTTON = 'button:has-text("Continue")'
    REMEMBER_ME = 'input[type="checkbox"]'

    def goto(self, base_url):
        self.page.goto(f"{base_url}/auth/login")

    def fill_email(self, email):
        self.page.locator(self.EMAIL_INPUT).fill(email)

    def fill_password(self, password):
        self.page.locator(self.PASSWORD_INPUT).fill(password)

    def click_continue(self):
        self.page.locator(self.CONTINUE_BUTTON).click()

    def toggle_remember_me(self):
        self.page.locator(self.REMEMBER_ME).check()

    def continue_button(self):
        return self.page.locator(self.CONTINUE_BUTTON)