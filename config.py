import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-this-secret-key")
    DATABASE = os.environ.get("DATABASE_PATH", str(BASE_DIR / "instance" / "expense_claims.sqlite3"))
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=15)
    SESSION_REFRESH_EACH_REQUEST = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    WTF_CSRF_TIME_LIMIT = None
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    SEED_DATA = os.environ.get("SEED_DATA", "1") == "1"
    APPROVAL_LIMIT = 5_000_000
    MAX_CLAIM_AMOUNT = 100_000_000
    CATEGORIES = [
        "Travel", "Meals", "Accommodation", "Office Supplies", "Training", "Other"
    ]
