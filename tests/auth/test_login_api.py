from playwright.sync_api import Page
from config.settings import BASE_URL



def test_login_api_status(page: Page):

    responses = []

    def handle_response(response):

        if "/auth/login" in response.url:
            responses.append(response)

    page.on("response", handle_response)

    page.goto(f"{BASE_URL}/auth/login")

    page.pause()

    assert len(responses) > 0, \
        "No login API detected"

    login_response = responses[-1]

    assert 200 <= login_response.status < 300