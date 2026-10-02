from types import SimpleNamespace
from uuid import UUID

from app.services.synchronization import worker


class FakeSession:
    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_claim_and_execute_dispatches_the_claimed_run(monkeypatch) -> None:
    run_id = UUID("53b9fe75-e65c-4a64-88c4-eec997d3d55d")
    user_id = UUID("ac741a98-0e46-448f-a8c3-f9f59d94aa32")
    claimed = SimpleNamespace(id=run_id, user_id=user_id)
    calls: list[tuple[UUID, UUID, str]] = []

    monkeypatch.setattr(worker, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(
        worker.ClassroomSynchronizer,
        "claim_run",
        staticmethod(lambda _db, _worker_id, _run_id=None: claimed),
    )
    monkeypatch.setattr(
        worker,
        "execute_claimed_run",
        lambda claimed_id, claimed_user, worker_id: calls.append(
            (claimed_id, claimed_user, worker_id)
        ),
    )

    assert worker.claim_and_execute("worker:test", run_id)
    assert calls == [(run_id, user_id, "worker:test")]


def test_claim_and_execute_returns_false_when_queue_is_empty(monkeypatch) -> None:
    monkeypatch.setattr(worker, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(
        worker.ClassroomSynchronizer,
        "claim_run",
        staticmethod(lambda _db, _worker_id, _run_id=None: None),
    )

    assert not worker.claim_and_execute("worker:test")
