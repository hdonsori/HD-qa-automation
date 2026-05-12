from playwright.sync_api import Page
import json

from config.settings import BASE_URL


visited_routes = set()
api_calls = []



def test_route_discovery(page: Page):

    def handle_navigation(frame):

        url = frame.url

        if "trio-dev" in url:

            visited_routes.add(url)

            print(f"\n[ROUTE] {url}")

    def handle_response(response):

        url = response.url

        if "/v2/" in url:

            api_info = {
                "status": response.status,
                "url": url,
            }

            api_calls.append(api_info)

            print(f"\n[API] {api_info}")

    page.on("framenavigated", handle_navigation)

    page.on("response", handle_response)

    page.goto(BASE_URL)

    if "/auth/login" in page.url:
        raise Exception(
            "Stored auth session invalid"
        )

    page.pause()

    with open("artifacts/routes.json", "w") as f:
        json.dump(list(visited_routes), f, indent=2)

    with open("artifacts/apis.json", "w") as f:
        json.dump(api_calls, f, indent=2)