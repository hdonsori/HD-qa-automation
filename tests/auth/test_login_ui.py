from pages.login_page import LoginPage
from config.settings import BASE_URL



def test_login_ui_states(page):

    login = LoginPage(page)

    login.goto(BASE_URL)

    continue_button = login.continue_button()

    # Empty state
    assert continue_button.is_disabled()

    # Email only
    login.fill_email("a+99@sternx.de")

    assert continue_button.is_disabled()

    # Password only state
    page.reload()

    login.fill_password("Password123!")

    assert continue_button.is_disabled()



def test_remember_me_checkbox(page):

    login = LoginPage(page)

    login.goto(BASE_URL)

    login.toggle_remember_me()

    checkbox = page.locator(login.REMEMBER_ME)

    assert checkbox.is_checked()



def test_password_visibility_toggle(page):

    login = LoginPage(page)

    login.goto(BASE_URL)

    password_input = page.locator(login.PASSWORD_INPUT)

    assert password_input.get_attribute("type") == "password"

    # Adjust selector if needed
    page.locator("svg").click()

    assert password_input.get_attribute("type") == "text"