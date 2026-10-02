from pydantic import BaseModel

from app.schemas.auth import SessionUser
from app.schemas.sync import SyncRunOutput


class ShellOutput(BaseModel):
    user: SessionUser
    unread_notification_count: int
    latest_sync: SyncRunOutput | None
