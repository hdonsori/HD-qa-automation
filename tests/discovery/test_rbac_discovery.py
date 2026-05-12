from config.settings import BASE_URL



def test_rbac_discovery(page):

    page.goto(BASE_URL)

    page.pause()

    # During pause:
    # - compare sidebars
    # - inspect hidden buttons
    # - inspect access denied states
    # - inspect API 403 responses