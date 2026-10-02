from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.db.models.entities import EventType, SourceType


class DashboardCourse(BaseModel):
    id: UUID
    name: str


class DashboardTarget(BaseModel):
    section: str | None
    lab_group: str | None
    academic_level: str | None
    program: str | None
    course_wide: bool


class DashboardItem(BaseModel):
    task_id: UUID
    event_id: UUID
    course_id: UUID | None
    course_name: str
    title: str
    body: str | None
    source_type: SourceType
    source_url: str | None
    source_created_at: datetime
    source_updated_at: datetime
    event_type: EventType
    starts_at: datetime | None
    due_at: datetime | None
    priority: int
    action_required: bool
    confidence: float
    review_required: bool
    manually_corrected: bool
    relevant: bool
    relevance_reason: str
    completed: bool
    acknowledged: bool
    read: bool
    task_updated_at: datetime
    targets: list[DashboardTarget]
    source_kind: str = "classroom"


class DashboardOutput(BaseModel):
    generated_at: datetime
    timezone: str
    items: list[DashboardItem]
    courses: list[DashboardCourse]


class TaskStateInput(BaseModel):
    completed: bool | None = None
    acknowledged: bool | None = None
    read: bool | None = None
    expected_updated_at: datetime | None = None


class TaskStateOutput(BaseModel):
    id: UUID
    completed: bool
    acknowledged: bool
    read: bool
    updated_at: datetime

    model_config = {"from_attributes": True}
