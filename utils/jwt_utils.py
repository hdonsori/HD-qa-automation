import base64
import json


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * ((4 - len(segment) % 4) % 4)
    normalized = segment.replace("-", "+").replace("_", "/") + padding
    return base64.b64decode(normalized)


def decode_jwt(token):
    """
    Decode JWT payload for test diagnostics/token-expiry checks without signature verification.
    """
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload_bytes = _b64url_decode(parts[1])
    return json.loads(payload_bytes.decode("utf-8"))
