import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT_ENV_PATH = PROJECT_ROOT / ".env"

if ROOT_ENV_PATH.is_file():
    load_dotenv(ROOT_ENV_PATH)
elif ROOT_ENV_PATH.is_dir():
    load_dotenv(ROOT_ENV_PATH / "trio.env")
else:
    load_dotenv()

BASE_URL = os.getenv("BASE_URL", "https://a99.trio-dev.us.bcpapers.ca").rstrip("/")
MARKETING_BASE_URL = os.getenv("MARKETING_BASE_URL", "https://www.trio.so").rstrip("/")

AUTH_FILE = os.getenv("AUTH_FILE", "playwright/.auth/user.json")
TOKEN_STORE_FILE = os.getenv("TOKEN_STORE_FILE", "auth/token_bundle.json")
TOKEN_REFRESH_PATH = os.getenv("TOKEN_REFRESH_PATH", "/auth/refresh")
TOKEN_EXPIRY_LEEWAY_SECONDS = int(os.getenv("TOKEN_EXPIRY_LEEWAY_SECONDS", "60"))

HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
SLOW_MO = int(os.getenv("SLOW_MO", "0"))

DEFAULT_TIMEOUT_MS = int(os.getenv("DEFAULT_TIMEOUT_MS", "20000"))
BROWSER_CHANNEL = os.getenv("BROWSER_CHANNEL", "chrome")
