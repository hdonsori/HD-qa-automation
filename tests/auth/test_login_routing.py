from config.settings import BASE_URL



def test_trial_user_redirect(page):

    page.goto(BASE_URL)

    page.pause()

    # Validate trial routing manually first

    assert "trial" in page.url.lower() \
        or page.get_by_text("trial").count() > 0