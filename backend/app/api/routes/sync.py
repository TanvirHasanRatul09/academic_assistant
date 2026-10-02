import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_csrf
from app.core.config import get_settings
from app.core.rate_limit import rate_limit
from app.db.models.entities import SyncRun, User
from app.db.session import get_db
from app.schemas.sync import SyncRunOutput, SyncStatusOutput
from app.services.classroom.client import ClassroomError
from app.services.synchronization.classroom_sync import ClassroomSynchronizer
from app.services.synchronization.worker import claim_and_execute, worker_identity

router = APIRouter(prefix="/api/sync", tags=["synchronization"])
logger = logging.getLogger(__name__)


def _execute_sync(run_id: UUID) -> None:
    worker_id = worker_identity("api-worker")
    if not claim_and_execute(worker_id, run_id):
        logger.warning("sync_job_not_claimed run_id=%s worker_id=%s", run_id, worker_id)


@router.post(
    "",
    response_model=SyncRunOutput,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_csrf), Depends(rate_limit("manual-sync", 6, 300))],
)
def synchronize(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> SyncRun:
    try:
        run = ClassroomSynchronizer(db, user.id).start()
    except ClassroomError as exc:
        status_code = 409 if exc.code in {"sync_already_running", "sync_cooldown"} else 502
        raise HTTPException(status_code=status_code, detail=exc.code) from exc
    if get_settings().sync_execution_mode == "in_process":
        background_tasks.add_task(_execute_sync, run.id)
    return run


@router.get("/status", response_model=SyncStatusOutput)
def synchronization_status(
    user: User = Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> SyncStatusOutput:
    latest = db.scalar(
        select(SyncRun)
        .where(SyncRun.user_id == user.id)
        .order_by(SyncRun.started_at.desc())
        .limit(1)
    )
    if latest:
        ClassroomSynchronizer.recover_stalled(db, latest)
    return SyncStatusOutput(latest=latest)
