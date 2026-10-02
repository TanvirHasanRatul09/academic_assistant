from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes.personal_tasks import (
    create_personal_task,
    delete_personal_task,
    list_personal_tasks,
    update_personal_task,
)
from app.db.base import Base
from app.db.models.entities import Course, CourseMembership, OnboardingState, PersonalTask, User
from app.schemas.personal_tasks import PersonalTaskInput, PersonalTaskUpdate
from app.services.ai.personal_tasks import personal_task_records
from app.services.ai.planner import plan_query


def database():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def users_and_course(db: Session):
    first = User(
        email="first@example.test",
        display_name="First",
        timezone="Asia/Dhaka",
        onboarding_state=OnboardingState.COMPLETE,
    )
    second = User(
        email="second@example.test",
        display_name="Second",
        timezone="Asia/Dhaka",
        onboarding_state=OnboardingState.COMPLETE,
    )
    course = Course(
        provider="google",
        classroom_course_id="personal-course",
        name="CSE 3213 OS Theory",
        status="ACTIVE",
        provider_metadata={},
    )
    db.add_all([first, second, course])
    db.flush()
    db.add(
        CourseMembership(
            user_id=first.id, course_id=course.id, selected=True, enrollment_status="ACTIVE"
        )
    )
    db.commit()
    return first, second, course


def test_personal_task_crud_is_owner_scoped() -> None:
    with database() as db:
        owner, other, course = users_and_course(db)
        created = create_personal_task(
            PersonalTaskInput(
                title="Physical OS assignment",
                details="Submit report",
                course_id=course.id,
                due_at=datetime.now(UTC) + timedelta(days=2),
                priority=2,
            ),
            owner,
            db,
        )
        assert created.source_kind == "manual"
        assert created.course_name == course.name
        assert [task.id for task in list_personal_tasks(owner, db)] == [created.id]
        assert list_personal_tasks(other, db) == []
        with pytest.raises(HTTPException) as update_error:
            update_personal_task(created.id, PersonalTaskUpdate(completed=True), other, db)
        assert update_error.value.status_code == 404
        updated = update_personal_task(
            created.id, PersonalTaskUpdate(completed=True, title="Updated OS assignment"), owner, db
        )
        assert updated.completed is True
        assert updated.title == "Updated OS assignment"
        with pytest.raises(HTTPException) as delete_error:
            delete_personal_task(created.id, other, db)
        assert delete_error.value.status_code == 404
        assert delete_personal_task(created.id, owner, db).status_code == 204
        assert db.get(PersonalTask, created.id) is None


def test_personal_task_requires_timezone_and_active_selected_course() -> None:
    with pytest.raises(ValidationError):
        PersonalTaskInput(title="No timezone", due_at=datetime(2026, 10, 1, 12, 0))
    with database() as db:
        _owner, other, course = users_and_course(db)
        with pytest.raises(HTTPException) as error:
            create_personal_task(
                PersonalTaskInput(title="Not my course", course_id=course.id), other, db
            )
        assert error.value.status_code == 422


def test_personal_task_rejects_due_before_start() -> None:
    start = datetime.now(UTC) + timedelta(days=2)
    with pytest.raises(ValidationError):
        PersonalTaskInput(
            title="Invalid schedule",
            starts_at=start,
            due_at=start - timedelta(hours=1),
        )


def test_weekly_assistant_query_includes_personal_tasks_chronologically() -> None:
    with database() as db:
        owner, _other, course = users_and_course(db)
        today = datetime.now(UTC).date()
        later = PersonalTask(
            user_id=owner.id,
            course_id=course.id,
            title="Later physical task",
            due_at=datetime.now(UTC) + timedelta(days=4),
            priority=1,
        )
        sooner = PersonalTask(
            user_id=owner.id,
            course_id=course.id,
            title="Sooner physical task",
            due_at=datetime.now(UTC) + timedelta(days=1),
            priority=2,
        )
        db.add_all([later, sooner])
        db.commit()
        records = personal_task_records(db, owner, plan_query("tasks this week", today))
        assert [record.title for record in records] == [
            "Sooner physical task",
            "Later physical task",
        ]
        assert all(record.personal for record in records)
        assert all(record.course_name == course.name for record in records)


def test_assistant_merges_classroom_and_personal_records(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.services.ai import service
    from app.services.ai.tools import AcademicRecord

    now = datetime.now(UTC)
    classroom = AcademicRecord(
        title="Classroom task",
        body=None,
        course_name="CSE 3213",
        source_url="https://classroom.google.com/c/1",
        event_type="assignment",
        starts_at=None,
        due_at=now + timedelta(days=2),
        priority=1,
        completed=False,
    )
    personal = AcademicRecord(
        title="Physical task",
        body="Announced in class",
        course_name="CSE 3213",
        source_url=None,
        event_type="assignment",
        starts_at=None,
        due_at=now + timedelta(days=1),
        priority=2,
        completed=False,
        personal=True,
    )
    monkeypatch.setattr(
        service,
        "resolve_course_intent",
        lambda *_args: SimpleNamespace(course_names=[], ambiguous=False),
    )
    monkeypatch.setattr(service, "last_successful_sync", lambda *_args: now)
    monkeypatch.setattr(service, "_execute", lambda *_args: [classroom])
    monkeypatch.setattr(service, "personal_task_records", lambda *_args: [personal])
    output = service.answer_question(
        object(),
        SimpleNamespace(id="user", timezone="UTC"),
        "tasks this week",
        SimpleNamespace(gemini_api_key=None, gemini_model="unused"),
    )
    assert [source.title for source in output.sources] == ["Physical task", "Classroom task"]
    assert "Source: Added by you" in output.answer
