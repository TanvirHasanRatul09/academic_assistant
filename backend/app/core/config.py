from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    app_env: Literal["development", "test", "preview", "production"] = Field(
        validation_alias="APP_ENV"
    )
    database_url: str = Field(min_length=1, validation_alias="DATABASE_URL")
    migration_database_url: str | None = Field(
        default=None, validation_alias="MIGRATION_DATABASE_URL"
    )
    session_secret: str = Field(min_length=32, validation_alias="SESSION_SECRET")
    token_encryption_key: str = Field(min_length=32, validation_alias="TOKEN_ENCRYPTION_KEY")
    google_client_id: str = Field(min_length=1, validation_alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(min_length=16, validation_alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: AnyHttpUrl = Field(validation_alias="GOOGLE_REDIRECT_URI")
    allowed_origins: str = Field(validation_alias="ALLOWED_ORIGINS")
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        min_length=1,
        pattern=r"^[a-zA-Z0-9._-]+$",
        validation_alias="GEMINI_MODEL",
    )
    sync_execution_mode: Literal["in_process", "worker"] = Field(
        default="in_process", validation_alias="SYNC_EXECUTION_MODE"
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("DATABASE_URL must use PostgreSQL")
        return value

    @field_validator("migration_database_url")
    @classmethod
    def validate_migration_database_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("MIGRATION_DATABASE_URL must use PostgreSQL")
        return value

    @field_validator("session_secret", "token_encryption_key", "google_client_secret")
    @classmethod
    def reject_placeholders(cls, value: str) -> str:
        lowered = value.lower()
        if "replace-with" in lowered or "changeme" in lowered:
            raise ValueError("placeholder or weak secret is not allowed")
        return value

    @property
    def cors_origins(self) -> list[str]:
        origins = [origin.strip().rstrip("/") for origin in self.allowed_origins.split(",")]
        if not origins or any(not origin or "*" in origin for origin in origins):
            raise ValueError("ALLOWED_ORIGINS must contain exact origins without wildcards")
        if any(not origin.startswith(("http://", "https://")) for origin in origins):
            raise ValueError("ALLOWED_ORIGINS entries must be HTTP(S) origins")
        return origins


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    _ = settings.cors_origins
    return settings
