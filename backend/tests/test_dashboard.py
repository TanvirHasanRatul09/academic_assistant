from datetime import date
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.api.routes.dashboard import utc_day
from app.main import app

client = TestClient(app)


def test_dashboard_requires_authentication_and_disables_caching() -> None:
    response = client.get("/api/dashboard")
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-security-policy"] == (
        "default-src 'none'; frame-ancestors 'none'"
    )


def test_task_state_requires_authentication() -> None:
    response = client.patch(
        "/api/dashboard/tasks/f825f23b-d461-4de7-a9a3-c904ca69f6a4",
        json={"completed": True},
    )
    assert response.status_code == 401


def test_day_boundaries_use_user_timezone() -> None:
    start, end = utc_day(date(2026, 9, 26), ZoneInfo("Asia/Dhaka"))
    assert start.isoformat() == "2026-09-25T18:00:00+00:00"
    assert end.isoformat() == "2026-09-26T18:00:00+00:00"


def test_dashboard_projects_and_filters_personal_tasks() -> None:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from app.api.routes.dashboard import DashboardSource, DashboardView, get_dashboard
    from app.db.base import Base
    from app.db.models.entities import (
        Course,
        CourseMembership,
        EventType,
        OnboardingState,
        PersonalTask,
        User,
    )

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(
            email="dashboard-personal@example.test",
            display_name="Student",
            timezone="UTC",
            onboarding_state=OnboardingState.COMPLETE,
        )
        course = Course(
            provider="google",
            classroom_course_id="dashboard-personal",
            name="OS Theory",
            status="ACTIVE",
            provider_metadata={},
        )
        db.add_all([user, course])
        db.flush()
        db.add(
            CourseMembership(
                user_id=user.id, course_id=course.id, selected=True, enrollment_status="ACTIVE"
            )
        )
        db.add_all(
            [
                PersonalTask(
                    user_id=user.id,
                    course_id=course.id,
                    title="Physical OS task",
                    event_type=EventType.ASSIGNMENT,
                    due_at=datetime.now(UTC) + timedelta(days=1),
                    priority=2,
                ),
                PersonalTask(
                    user_id=user.id,
                    title="Personal reminder",
                    event_type=EventType.OTHER,
                    due_at=datetime.now(UTC) + timedelta(days=2),
                    priority=1,
                ),
            ]
        )
        db.commit()
        output = get_dashboard(
            DashboardView.ALL, None, None, None, None, DashboardSource.MANUAL, 100, user, db
        )
        assert [item.title for item in output.items] == ["Physical OS task", "Personal reminder"]
        assert all(item.source_kind == "manual" for item in output.items)
        assert output.items[1].course_name == "Personal"
        course_only = get_dashboard(
            DashboardView.ALL, course.id, None, None, None, DashboardSource.MANUAL, 100, user, db
        )
        assert [item.title for item in course_only.items] == ["Physical OS task"]


def test_dashboard_personal_completion_is_owner_scoped() -> None:
    from datetime import UTC, datetime

    import pytest
    from fastapi import HTTPException
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from app.api.routes.dashboard import update_task_state
    from app.db.base import Base
    from app.db.models.entities import OnboardingState, PersonalTask, User
    from app.schemas.dashboard import TaskStateInput

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        owner = User(
            email="dashboard-owner@example.test",
            display_name="Owner",
            timezone="UTC",
            onboarding_state=OnboardingState.COMPLETE,
        )
        other = User(
            email="dashboard-other@example.test",
            display_name="Other",
            timezone="UTC",
            onboarding_state=OnboardingState.COMPLETE,
        )
        db.add_all([owner, other])
        db.flush()
        task = PersonalTask(user_id=owner.id, title="Owner task", due_at=datetime.now(UTC))
        db.add(task)
        db.commit()
        db.refresh(task)
        with pytest.raises(HTTPException) as error:
            update_task_state(task.id, TaskStateInput(completed=True), other, db)
        assert error.value.status_code == 404
        result = update_task_state(task.id, TaskStateInput(completed=True), owner, db)
        assert result.completed is True
