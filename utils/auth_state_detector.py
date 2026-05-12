def detect_auth_state(page):

    url = page.url.lower()

    if "/auth/login" in url:
        return "LOGIN"

    if "cloudflare" in url:
        return "CLOUDFLARE"

    if "/mfa" in url:
        return "MFA"

    if "/trial" in url:
        return "TRIAL"

    if "/dashboard" in url:
        return "AUTHENTICATED"

    return "UNKNOWN"