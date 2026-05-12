from playwright.sync_api import Page
import json


from utils.response_classifier import (
    classify_response
)

from utils.auth_state_detector import (
    detect_auth_state
)

from config.settings import BASE_URL
from utils.artifact_manager import save_json
from utils.jwt_utils import decode_jwt
from utils.auth_token_manager import extract_auth_bundle, save_token_bundle


login_response_data = {}


def test_bootstrap_auth(page: Page):

    def handle_response(response):

        global login_response_data

        if "/auth/login" in response.url:

            print(f"\n[LOGIN API] {response.url}")
            print(f"[STATUS] {response.status}")

            assert 200 <= response.status < 300, \
                f"Login failed with status {response.status}"

            body = ""

            try:

                response_type = classify_response(
                    response
                )

                print(
                    f"\n[RESPONSE TYPE] {response_type}"
                )

                body = response.text()

                assert body, \
                    "Empty response body"

                assert response_type != "CLOUDFLARE", \
                    "Cloudflare challenge detected"

                assert response_type != "HTML", \
                    "HTML returned instead of JSON"

                assert response_type == "JSON", \
                    f"Unexpected response type: {response_type}"

                data = response.json()

                login_response_data = data

                save_json(
                    "artifacts/login_response.json",
                    data
                )

                access_token = (
                    data.get("accessToken")
                    or data.get("access_token")
                )

                refresh_token = (
                    data.get("refreshToken")
                    or data.get("refresh_token")
                )

                assert access_token, \
                    "Access token missing"

                assert refresh_token, \
                    "Refresh token missing"

                user = data.get("user")

                assert user, \
                    "User object missing"

                user_id = (
                    user.get("id")
                    or user.get("_id")
                    or user.get("userId")
                )

                assert user_id, \
                    "User ID missing"

                token_bundle = extract_auth_bundle(data)
                save_token_bundle(token_bundle)

                claims = decode_jwt(
                    access_token
                )

                save_json(
                    "artifacts/jwt_claims.json",
                    claims
                )

                print("\n[JWT CLAIMS]")
                print(
                    json.dumps(
                        claims,
                        indent=2
                    )
                )

            except Exception as e:

                print("\n[RAW RESPONSE BODY]")
                print(body[:1000])

                raise Exception(
                    f"Login response validation failed: {e}"
                )

    page.on("response", handle_response)

    page.goto(f"{BASE_URL}/auth/login")

    page.pause()

    page.wait_for_load_state(
        "networkidle",
        timeout=30000
    )

    page.wait_for_timeout(5000)

    current_url = page.url

    print(f"\n[FINAL URL] {current_url}")

    cookies = page.context.cookies()

    assert len(cookies) > 0, \
        "No auth cookies found"

    save_json(
        "auth/cookies.json",
        cookies
    )

    page.context.storage_state(
        path="auth/auth.json"
    )

    print("\n[SUCCESS] Auth bootstrap completed")

    auth_state = detect_auth_state(page)

    print(f"\n[AUTH STATE] {auth_state}")

    assert auth_state != "LOGIN", \
        "Authentication failed"
