from uuid import UUID

import pytest

from app.services.classroom.client import ClassroomError
from app.services.synchronization.classroom_sync import ClassroomSynchronizer, _lock_for


def test_duplicate_sync_is_rejected_before_work_starts() -> None:
    user_id = UUID("f825f23b-d461-4de7-a9a3-c904ca69f6a4")
    lock = _lock_for(user_id)
    lock.acquire()
    try:
        with pytest.raises(ClassroomError, match="sync_already_running"):
            ClassroomSynchronizer(object(), user_id).run(cooldown_seconds=0)  # type: ignore[arg-type]
    finally:
        lock.release()
