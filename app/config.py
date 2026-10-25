import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _need(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f".env 缺少 {name}")
    return value


DEEPSEEK_API_KEY = _need("DEEPSEEK_API_KEY")
TAVILY_API_KEY = _need("TAVILY_API_KEY")

OSS_ACCESS_KEY_ID = _need("OSS_ACCESS_KEY_ID")
OSS_ACCESS_KEY_SECRET = _need("OSS_ACCESS_KEY_SECRET")
OSS_BUCKET = _need("OSS_BUCKET")
OSS_ENDPOINT = (
    _need("OSS_ENDPOINT").replace("https://", "").replace("http://", "").strip("/")
)


def _derive_region(endpoint: str) -> str:
    host = endpoint.split(".")[0]
    return host.removeprefix("oss-").removesuffix("-internal")


OSS_REGION = os.getenv("OSS_REGION") or _derive_region(OSS_ENDPOINT)

DB_PATH = BASE_DIR / "data" / "personal_chief.db"
