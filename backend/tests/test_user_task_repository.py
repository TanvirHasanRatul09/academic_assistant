import uuid
from unittest.mock import MagicMock

from app.repositories.user_tasks import UserTaskRepository


def test_get_scopes_query_to_authenticated_user() -> None:
    session = MagicMock()
    repository = UserTaskRepository(session)
    user_id = uuid.uuid4()
    task_id = uuid.uuid4()

    repository.get(user_id, task_id)

    statement = session.scalar.call_args.args[0]
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert user_id.hex in compiled
    assert task_id.hex in compiled


def test_unknown_task_cannot_be_updated() -> None:
    session = MagicMock()
    session.scalar.return_value = None
    repository = UserTaskRepository(session)

    assert repository.set_completed(uuid.uuid4(), uuid.uuid4(), completed=True) is None
    session.flush.assert_not_called()
