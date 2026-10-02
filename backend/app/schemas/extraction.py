from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models.entities import EventType


class ReprocessResult(BaseModel):
    processed: int
    created: int
    review_required: int


class EventCorrection(BaseModel):
    event_type: EventType
    starts_at: datetime | None = None
    due_at: datetime | None = None
    priority: int = Field(ge=0, le=3)
    action_required: bool
    section: str | None = Field(default=None, max_length=64)
    lab_group: str | None = Field(default=None, max_length=64)


class EventOutput(BaseModel):
    id: UUID
    event_type: EventType
    starts_at: datetime | None
    due_at: datetime | None
    priority: int
    action_required: bool
    confidence: float
    extraction_version: str
    review_required: bool
    manually_corrected: bool

    model_config = {"from_attributes": True}

class ReviewTarget(BaseModel):
    section: str | None
    lab_group: str | None
    course_wide: bool

class ReviewItem(BaseModel):
    event: EventOutput
    title: str
    body: str | None
    course_id: UUID
    course_name: str
    source_url: str
    targets: list[ReviewTarget]
    review_reason: str

class ReviewPage(BaseModel):
    items: list[ReviewItem]
    offset: int
    limit: int
    total: int
    has_more: bool
