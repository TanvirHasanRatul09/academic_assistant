from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.db.models.entities import EventType


class PersonalTaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    details: str | None = Field(default=None, max_length=30000)
    course_id: UUID | None = None
    event_type: EventType = EventType.ASSIGNMENT
    starts_at: datetime | None = None
    due_at: datetime | None = None
    priority: int = Field(default=1, ge=0, le=3)
    section: str | None = Field(default=None, max_length=64)
    lab_group: str | None = Field(default=None, max_length=64)
    completed: bool = False

    @model_validator(mode="after")
    def validate_times(self) -> "PersonalTaskInput":
        for value in (self.starts_at, self.due_at):
            if value is not None and value.tzinfo is None:
                raise ValueError("task date/time must include a timezone")
        if self.starts_at and self.due_at and self.due_at < self.starts_at:
            raise ValueError("due_at must not be before starts_at")
        return self


class PersonalTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    details: str | None = Field(default=None, max_length=30000)
    course_id: UUID | None = None
    event_type: EventType | None = None
    starts_at: datetime | None = None
    due_at: datetime | None = None
    priority: int | None = Field(default=None, ge=0, le=3)
    section: str | None = Field(default=None, max_length=64)
    lab_group: str | None = Field(default=None, max_length=64)
    completed: bool | None = None

    @model_validator(mode="after")
    def validate_times(self) -> "PersonalTaskUpdate":
        for value in (self.starts_at, self.due_at):
            if value is not None and value.tzinfo is None:
                raise ValueError("task date/time must include a timezone")
        if self.starts_at and self.due_at and self.due_at < self.starts_at:
            raise ValueError("due_at must not be before starts_at")
        return self


class PersonalTaskOutput(BaseModel):
    id: UUID
    user_id: UUID
    course_id: UUID | None
    course_name: str | None = None
    title: str
    details: str | None
    event_type: EventType
    starts_at: datetime | None
    due_at: datetime | None
    priority: int
    section: str | None
    lab_group: str | None
    completed: bool
    created_at: datetime
    updated_at: datetime
    source_kind: str = "manual"
