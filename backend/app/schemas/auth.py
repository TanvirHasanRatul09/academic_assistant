from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator

ALLOWED_NOTIFICATION_KEYS = {"assignments", "exams", "notices"}


class ProfileInput(BaseModel):
    academic_level: str | None = Field(default=None, max_length=128)
    program: str | None = Field(default=None, max_length=200)
    section: str | None = Field(default=None, max_length=64)
    lab_group: str | None = Field(default=None, max_length=64)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    selected_course_ids: list[UUID] = Field(default_factory=list, max_length=100)
    notification_preferences: dict[str, bool | int] = Field(default_factory=dict)

    @field_validator("section", "lab_group", "academic_level", "program")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value

    @field_validator("selected_course_ids")
    @classmethod
    def unique_courses(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("selected courses must be unique")
        return value

    @field_validator("notification_preferences")
    @classmethod
    def validate_preferences(
        cls, value: dict[str, bool | int]
    ) -> dict[str, bool | int]:
        for key, setting in value.items():
            if key in ALLOWED_NOTIFICATION_KEYS and isinstance(setting, bool):
                continue
            if (
                key == "minimum_priority"
                and isinstance(setting, int)
                and not isinstance(setting, bool)
                and 1 <= setting <= 3
            ):
                continue
            if key.startswith("course:") and isinstance(setting, bool):
                try:
                    UUID(key.removeprefix("course:"))
                except ValueError as exc:
                    raise ValueError("invalid course notification preference") from exc
                continue
            raise ValueError("unsupported notification preference")
        return value


class ProfileOutput(ProfileInput):
    user_id: UUID
    email: str
    display_name: str
    onboarding_complete: bool
    courses: list["CourseOption"] = Field(default_factory=list)
    classroom_connected: bool
    last_successful_sync_at: datetime | None


class SessionUser(BaseModel):
    id: UUID
    email: str
    display_name: str
    onboarding_complete: bool


class AuthorizationUrl(BaseModel):
    authorization_url: str


class CsrfToken(BaseModel):
    csrf_token: str


class CourseOption(BaseModel):
    id: UUID
    name: str
    selected: bool
    enrollment_status: str = "ACTIVE"
    eligible: bool = True




