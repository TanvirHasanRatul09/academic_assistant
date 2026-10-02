import pytest
from pydantic import ValidationError

from app.core.config import Settings


def valid_settings() -> dict[str, str]:
    return {
        "APP_ENV": "test",
        "DATABASE_URL": "postgresql+psycopg://user:pass@localhost:5432/db",
        "SESSION_SECRET": "a-secure-session-secret-with-32-characters",
        "TOKEN_ENCRYPTION_KEY": "a-separate-encryption-key-with-32-chars",
        "GOOGLE_CLIENT_ID": "client-id",
        "GOOGLE_CLIENT_SECRET": "a-google-client-secret",
        "GOOGLE_REDIRECT_URI": "http://localhost:8000/callback",
        "ALLOWED_ORIGINS": "http://localhost:5173",
    }


def test_rejects_non_postgres_database() -> None:
    values = valid_settings()
    values["DATABASE_URL"] = "sqlite:///local.db"
    with pytest.raises(ValidationError):
        Settings(**values)


def test_rejects_wildcard_cors() -> None:
    values = valid_settings()
    values["ALLOWED_ORIGINS"] = "*"
    settings = Settings(**values)
    with pytest.raises(ValueError, match="wildcards"):
        _ = settings.cors_origins
