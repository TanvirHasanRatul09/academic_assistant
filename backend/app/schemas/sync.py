from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.db.models.entities import SyncStatus


class SyncRunOutput(BaseModel):
    id: UUID
    status: SyncStatus
    started_at: datetime
    finished_at: datetime | None
    items_seen: int
    items_changed: int
    courses_processed: int
    courses_total: int
    current_phase: str | None
    timing_metrics: dict[str, float | int]
    heartbeat_at: datetime | None
    worker_id: str | None
    lease_expires_at: datetime | None
    attempt_count: int
    failed_courses: list[dict[str, str]]
    safe_error_code: str | None

    model_config = {"from_attributes": True}


class SyncStatusOutput(BaseModel):
    latest: SyncRunOutput | None
