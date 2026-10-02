from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class NotificationItem(BaseModel):
    id: UUID
    kind: str
    created_at: datetime
    read_at: datetime | None
    dismissed_at: datetime | None
    task_id: UUID
    title: str
    course_name: str
    event_type: str
    priority: int
    due_at: datetime | None
    source_url: str


class NotificationList(BaseModel):
    items: list[NotificationItem]
    unread_count: int


class UnreadCount(BaseModel):
    unread_count: int


class NotificationCoursePreference(BaseModel):
    id: UUID
    name: str
    enabled: bool


class NotificationPreferencesOutput(BaseModel):
    assignments: bool
    exams: bool
    notices: bool
    minimum_priority: int
    courses: list[NotificationCoursePreference]


class NotificationPreferencesInput(BaseModel):
    assignments: bool = True
    exams: bool = True
    notices: bool = True
    minimum_priority: int = Field(default=2, ge=1, le=3)
    course_preferences: dict[UUID, bool] = Field(default_factory=dict)

    @field_validator("course_preferences")
    @classmethod
    def bound_courses(cls, value: dict[UUID, bool]) -> dict[UUID, bool]:
        if len(value) > 100:
            raise ValueError("too many course preferences")
        return value
