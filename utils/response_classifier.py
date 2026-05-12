def classify_response(response):

    content_type = response.headers.get(
        "content-type",
        ""
    )

    body = response.text()

    if not body:
        return "EMPTY"

    if "cloudflare" in body.lower():
        return "CLOUDFLARE"

    if "text/html" in content_type:
        return "HTML"

    if "application/json" in content_type:
        return "JSON"

    return "UNKNOWN"