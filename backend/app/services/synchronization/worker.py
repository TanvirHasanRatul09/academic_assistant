import logging
import os
import socket
from uuid import UUID, uuid4

from app.db.session import SessionLocal
from app.services.synchronization.classroom_sync import ClassroomSynchronizer

logger = logging.getLogger(__name__)


def worker_identity(prefix: str = "sync-worker") -> str:
    return f"{prefix}:{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"


def execute_claimed_run(run_id: UUID, user_id: UUID, worker_id: str) -> None:
    with SessionLocal() as db:
        try:
            ClassroomSynchronizer(db, user_id, worker_id).run_existing(run_id)
        except Exception:
            logger.exception(
                "sync_job_crashed run_id=%s user_id=%s worker_id=%s",
                run_id,
                user_id,
                worker_id,
            )
            ClassroomSynchronizer.release_crashed_run(db, run_id, worker_id)


def claim_and_execute(worker_id: str, run_id: UUID | None = None) -> bool:
    with SessionLocal() as db:
        run = ClassroomSynchronizer.claim_run(db, worker_id, run_id)
        if not run:
            return False
        claimed_run_id = run.id
        user_id = run.user_id
    execute_claimed_run(claimed_run_id, user_id, worker_id)
    return True
