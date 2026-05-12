import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests

from config.settings import (
    BASE_URL,
    TOKEN_EXPIRY_LEEWAY_SECONDS,
    TOKEN_REFRESH_PATH,
    TOKEN_STORE_FILE,
)
from utils.jwt_utils import decode_jwt


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def load_token_bundle(path: str = TOKEN_STORE_FILE) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_token_bundle(bundle: Dict[str, Any], path: str = TOKEN_STORE_FILE) -> None:
    _ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2)


def extract_auth_bundle(login_payload: Dict[str, Any]) -> Dict[str, Any]:
    access_token = login_payload.get("accessToken") or login_payload.get("access_token")
    refresh_token = login_payload.get("refreshToken") or login_payload.get("refresh_token")
    user = login_payload.get("user") or {}
    employee_id = (
        user.get("employeeId")
        or user.get("employee_id")
        or user.get("id")
        or user.get("_id")
        or user.get("userId")
    )

    if not access_token:
        raise ValueError("Access token missing in login payload")
    if not refresh_token:
        raise ValueError("Refresh token missing in login payload")
    if not employee_id:
        raise ValueError("Employee ID missing in login payload")

    access_claims = decode_jwt(access_token)
    exp = access_claims.get("exp")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "employee_id": str(employee_id),
        "access_token_exp": exp,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def is_access_token_valid(bundle: Optional[Dict[str, Any]], leeway_seconds: int = TOKEN_EXPIRY_LEEWAY_SECONDS) -> bool:
    if not bundle:
        return False
    exp = bundle.get("access_token_exp")
    if not exp:
        return False
    try:
        exp_int = int(exp)
    except (TypeError, ValueError):
        return False
    now = int(datetime.now(timezone.utc).timestamp())
    return (exp_int - now) > leeway_seconds


def try_refresh_token_bundle(
    bundle: Dict[str, Any],
    refresh_url: Optional[str] = None,
    timeout_seconds: int = 20,
) -> Optional[Dict[str, Any]]:
    refresh_token = bundle.get("refresh_token")
    if not refresh_token:
        return None

    target_url = refresh_url or f"{BASE_URL}{TOKEN_REFRESH_PATH}"
    headers = {"Content-Type": "application/json"}
    payload = {"refreshToken": refresh_token}

    response = requests.post(target_url, json=payload, headers=headers, timeout=timeout_seconds)
    if response.status_code < 200 or response.status_code >= 300:
        return None

    response_data = response.json()
    refreshed_bundle = extract_auth_bundle(
        {
            "accessToken": response_data.get("accessToken") or response_data.get("access_token"),
            "refreshToken": response_data.get("refreshToken") or response_data.get("refresh_token") or refresh_token,
            "user": response_data.get("user") or {"employeeId": bundle.get("employee_id")},
        }
    )
    return refreshed_bundle
