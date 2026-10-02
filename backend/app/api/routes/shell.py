from time import perf_counter

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.entities import Notification, OnboardingState, SyncRun, User
from app.db.session import get_db
from app.schemas.auth import SessionUser
from app.schemas.shell import ShellOutput

router = APIRouter(prefix="/api", tags=["application shell"])


@router.get("/shell", response_model=ShellOutput)
def shell(
    response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ShellOutput:
    started = perf_counter()
    latest = db.scalar(
        select(SyncRun)
        .where(SyncRun.user_id == user.id)
        .order_by(SyncRun.started_at.desc())
        .limit(1)
    )
    unread = (
        db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user.id,
                Notification.read_at.is_(None),
                Notification.dismissed_at.is_(None),
            )
        )
        or 0
    )
    response.headers["X-Shell-Timing-Ms"] = f"{(perf_counter() - started) * 1000:.2f}"
    session_user = SessionUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        onboarding_complete=user.onboarding_state == OnboardingState.COMPLETE,
    )
    return ShellOutput(user=session_user, unread_notification_count=unread, latest_sync=latest)
