from config.settings import BASE_URL



def test_session_persistence(page):

    page.goto(BASE_URL)

    assert "/auth/login" not in page.url, \
        "Session persistence failed"