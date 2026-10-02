import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import Cookie, Depends, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_current_session, hash_secret
from app.core.rate_limit import rate_limit
from app.db.base import Base
from app.db.models.entities import (
    AcademicEvent,
    ClassroomItem,
    Course,
    CourseMembership,
        EventType,
        ItemSubtype,
    OnboardingState,
    SourceType,
    User,
    UserSession,
    UserTask,
)
from app.db.session import get_db
from app.main import app


@pytest.fixture
def database() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def authenticated_client(factory: sessionmaker[Session], user: User, token: str) -> TestClient:
    raw_session = f"session-{token}"
    raw_csrf = f"csrf-{token}"
    with factory() as db:
        db.add(
            UserSession(
                id=hash_secret(raw_session),
                user_id=user.id,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                reauthenticated_at=datetime.now(UTC),
                csrf_token_hash=hash_secret(raw_csrf),
            )
        )
        db.commit()

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db

    def override_current_session(
        request: Request,
        academic_session: str | None = Cookie(default=None),
        db: Session = Depends(get_db),
    ) -> UserSession:
        if not academic_session:
            raise HTTPException(status_code=401, detail="Authentication required")
        current = db.scalar(
            select(UserSession).where(UserSession.id == hash_secret(academic_session))
        )
        if current and current.expires_at.tzinfo is None:
            current.expires_at = current.expires_at.replace(tzinfo=UTC)
            current.reauthenticated_at = current.reauthenticated_at.replace(tzinfo=UTC)
        if not current or current.expires_at <= datetime.now(UTC):
            if current:
                db.delete(current)
                db.commit()
            raise HTTPException(status_code=401, detail="Authentication required")
        request.state.user_session = current
        return current

    app.dependency_overrides[get_current_session] = override_current_session
    client = TestClient(app)
    client.cookies.set("academic_session", raw_session)
    client.cookies.set("academic_csrf", raw_csrf)
    return client


def seed_two_users(factory: sessionmaker[Session]):
    with factory() as db:
        first = User(
            email="first@example.test",
            display_name="First",
            timezone="UTC",
            onboarding_state=OnboardingState.COMPLETE,
        )
        second = User(
            email="second@example.test",
            display_name="Second",
            timezone="UTC",
            onboarding_state=OnboardingState.COMPLETE,
        )
        first_course = Course(
            provider="google",
            classroom_course_id="first-course",
            name="First course",
            status="ACTIVE",
        )
        second_course = Course(
            provider="google",
            classroom_course_id="second-course",
            name="Second course",
            status="ACTIVE",
        )
        db.add_all([first, second, first_course, second_course])
        db.flush()
        db.add_all(
            [
                CourseMembership(user_id=first.id, course_id=first_course.id, selected=True),
                CourseMembership(user_id=second.id, course_id=second_course.id, selected=True),
            ]
        )
        now = datetime.now(UTC)
        first_item = ClassroomItem(
            course_id=first_course.id,
            source_type=SourceType.COURSEWORK,
            source_id="first-item",
            title="First private assignment",
            body="Only the first account can read this",
            source_url="https://classroom.google.com/first",
            source_created_at=now,
            source_updated_at=now,
            content_hash="a" * 64,
        )
        second_item = ClassroomItem(
            course_id=second_course.id,
            source_type=SourceType.COURSEWORK,
            source_id="second-item",
            title="Second private assignment",
            body="Only the second account can read this",
            source_url="https://classroom.google.com/second",
            source_created_at=now,
            source_updated_at=now,
            content_hash="b" * 64,
        )
        db.add_all([first_item, second_item])
        db.flush()
        first_event = AcademicEvent(
            classroom_item_id=first_item.id,
            event_type=EventType.ASSIGNMENT,
            item_subtype=ItemSubtype.ASSIGNMENT,
            due_at=now + timedelta(days=2),
            priority=2,
            action_required=True,
            confidence=0.9,
            extraction_version="test",
        )
        second_event = AcademicEvent(
            classroom_item_id=second_item.id,
            event_type=EventType.ASSIGNMENT,
            item_subtype=ItemSubtype.ASSIGNMENT,
            due_at=now + timedelta(days=3),
            priority=2,
            action_required=True,
            confidence=0.9,
            extraction_version="test",
        )
        db.add_all([first_event, second_event])
        db.flush()
        first_task = UserTask(user_id=first.id, academic_event_id=first_event.id, relevant=True)
        second_task = UserTask(user_id=second.id, academic_event_id=second_event.id, relevant=True)
        db.add_all([first_task, second_task])
        db.commit()
        return first, second, first_task, second_task


def test_two_account_resources_are_isolated(database) -> None:
    first, _second, _first_task, second_task = seed_two_users(database)
    client = authenticated_client(database, first, "first")
    try:
        dashboard = client.get("/api/dashboard").json()
        assert [item["title"] for item in dashboard["items"]] == ["First private assignment"]
        forbidden = client.patch(
            f"/api/dashboard/tasks/{second_task.id}",
            json={"completed": True},
            headers={"X-CSRF-Token": "csrf-first"},
        )
        assert forbidden.status_code == 404
        answer = client.post(
            "/api/assistant/query",
            json={"message": "Find private assignment"},
            headers={"X-CSRF-Token": "csrf-first"},
        )
        assert answer.status_code == 200
        assert [source["title"] for source in answer.json()["sources"]] == [
            "First private assignment"
        ]
    finally:
        app.dependency_overrides.clear()


def test_inactive_membership_is_historical_and_excluded_everywhere(database) -> None:
    first, *_ = seed_two_users(database)
    with database() as db:
        membership = db.scalar(
            select(CourseMembership).where(CourseMembership.user_id == first.id)
        )
        assert membership is not None
        membership.enrollment_status = "INACTIVE"
        membership.selected = False
        db.commit()

    client = authenticated_client(database, first, "inactive-course")
    try:
        dashboard = client.get("/api/dashboard").json()
        assert dashboard["items"] == []
        assert dashboard["courses"] == []

        courses = client.get("/api/auth/courses").json()
        assert courses == [
            {
                "id": str(membership.course_id),
                "name": "First course",
                "selected": False,
                "enrollment_status": "INACTIVE",
                "eligible": False,
            }
        ]

        rejected = client.put(
            "/api/auth/profile",
            json={
                "timezone": "UTC",
                "selected_course_ids": [str(membership.course_id)],
                "notification_preferences": {},
            },
            headers={"X-CSRF-Token": "csrf-inactive-course"},
        )
        assert rejected.status_code == 403
    finally:
        app.dependency_overrides.clear()

def test_csrf_session_logout_cors_and_headers(database) -> None:
    first, *_ = seed_two_users(database)
    client = authenticated_client(database, first, "security")
    try:
        missing_csrf = client.patch(
            f"/api/dashboard/tasks/{uuid.uuid4()}", json={"completed": True}
        )
        assert missing_csrf.status_code == 403
        response = client.get("/api/dashboard", headers={"Origin": "http://localhost:5173"})
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        logout = client.post("/api/auth/logout", headers={"X-CSRF-Token": "csrf-security"})
        assert logout.status_code == 204
        assert client.get("/api/auth/me").status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_expired_session_and_account_deletion(database) -> None:
    first, *_ = seed_two_users(database)
    client = authenticated_client(database, first, "delete")
    try:
        deleted = client.delete("/api/auth/account", headers={"X-CSRF-Token": "csrf-delete"})
        assert deleted.status_code == 204
        with database() as db:
            assert db.get(User, first.id) is None
            assert (
                db.scalar(select(func.count(UserTask.id)).where(UserTask.user_id == first.id)) == 0
            )
        assert client.get("/api/auth/me").status_code == 401
    finally:
        app.dependency_overrides.clear()

    with database() as db:
        remaining = db.scalar(select(User))
    expired = authenticated_client(database, remaining, "expired")
    try:
        with database() as db:
            session = db.scalar(select(UserSession).where(UserSession.user_id == remaining.id))
            session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()
        assert expired.get("/api/auth/me").status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_rate_limit_rejects_excess_requests() -> None:
    check = rate_limit(f"verification-{uuid.uuid4()}", 2, 60)
    request = Request({"type": "http", "client": ("203.0.113.10", 1234), "headers": []})
    check(request)
    check(request)
    with pytest.raises(HTTPException) as error:
        check(request)
    assert error.value.status_code == 429
