import os
import uuid

import pytest
from sqlalchemy import func, select

from app.db.models import UserTask
from app.db.session import SessionLocal
from app.repositories.user_tasks import UserTaskRepository

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1", reason="requires migrated PostgreSQL"
)


def test_seeded_database_and_cross_user_isolation() -> None:
    seeded_user_id = uuid.UUID("10000000-0000-0000-0000-000000000001")
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(UserTask)) == 1
        repository = UserTaskRepository(session)
        assert len(repository.list_relevant(seeded_user_id)) == 1
        assert repository.list_relevant(uuid.uuid4()) == []
