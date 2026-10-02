from datetime import date

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.db.models.entities import ItemSubtype
from app.main import app
from app.schemas.assistant import AssistantQuery
from app.services.ai.planner import plan_query
from app.services.ai.tools import DateRangeArgs, ExamArgs, SearchArgs


def test_planner_selects_bounded_read_only_tools() -> None:
    today = date(2026, 9, 26)
    assert plan_query("What do I have tomorrow?", today).tool == "get_tasks_by_date"
    assert plan_query("Show upcoming exams", today).tool == "get_exams"
    assert plan_query("What is due soon?", today).tool == "get_upcoming_deadlines"
    assert plan_query("Find database normalization", today).tool == "search_academic_content"


def test_tool_arguments_are_bounded() -> None:
    with pytest.raises(ValidationError):
        DateRangeArgs(start_date=date(2026, 1, 1), end_date=date(2026, 3, 1))
    with pytest.raises(ValidationError):
        SearchArgs(query="x")


def test_assistant_limits_prompt_and_history() -> None:
    with pytest.raises(ValidationError):
        AssistantQuery(message="x" * 501)
    with pytest.raises(ValidationError):
        AssistantQuery(message="valid", history=[{"role": "user", "content": "ok"}] * 7)


def test_assistant_requires_authentication() -> None:
    response = TestClient(app).post("/api/assistant/query", json={"message": "What is due?"})
    assert response.status_code == 401


def test_planner_resolves_tuesday_and_keeps_course_event_terms() -> None:
    plan = plan_query("There is a CSE 3208 lab final on Tuesday", date(2026, 9, 27))
    assert plan.tool == "get_tasks_by_date"
    assert isinstance(plan.args, DateRangeArgs)
    assert plan.args.start_date == date(2026, 9, 29)
    assert plan.args.terms == ["CSE 3208", "lab final"]


def test_planner_understands_natural_mark_completed_commands() -> None:
    quiz = plan_query("mark the CN lab quiz as completed", date(2026, 9, 30))
    assert quiz.intent == "mark_as_completed"
    assert quiz.item_subtype == ItemSubtype.QUIZ

    exam = plan_query("mark the OS exam completed", date(2026, 9, 30))
    assert exam.intent == "mark_as_completed"
    assert exam.tool == "get_exams"
    assert isinstance(exam.args, ExamArgs)
    assert exam.args.include_past
    incomplete = plan_query(
        "mark it as incompleted",
        date(2026, 9, 30),
        context="is there a CN lab quiz in this week?",
        resolved_course_terms=["Fall 2025 CSE 3202"],
    )
    assert incomplete.intent == "mark_as_incomplete"
    assert incomplete.tool == "get_tasks_by_date"

def test_mark_it_follow_up_reuses_course_assessment_and_time_window() -> None:
    plan = plan_query(
        "mark it as completed",
        date(2026, 9, 30),
        context="is there an OS final in this week?",
        resolved_course_terms=["Fall 2025 CSE 3213 OS Theory"],
    )

    assert plan.intent == "mark_as_completed"
    assert plan.tool == "get_tasks_by_date"
    assert isinstance(plan.args, DateRangeArgs)
    assert plan.args.start_date == date(2026, 9, 30)
    assert plan.args.end_date == date(2026, 10, 7)
    assert plan.args.terms == ["Fall 2025 CSE 3213 OS Theory", "final"]

def test_question_pattern_follow_up_uses_content_search_and_course_context() -> None:
    plan = plan_query(
        "what is the question pattern of this exam",
        date(2026, 9, 28),
        context="CSE 3208 lab final is on Tuesday",
    )

    assert plan.tool == "search_academic_content"
    assert isinstance(plan.args, SearchArgs)
    assert plan.args.query == "question pattern"
    assert plan.args.course_terms == ["CSE 3208"]


def test_cse_3208_tuesday_lab_final_is_answered_from_synchronized_records() -> None:
    from datetime import UTC, datetime, time, timedelta
    from types import SimpleNamespace
    from zoneinfo import ZoneInfo

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

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
        SyncRun,
        SyncStatus,
        User,
        UserTask,
    )
    from app.services.ai.service import answer_question

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    local_today = datetime.now(UTC).astimezone(ZoneInfo("Asia/Dhaka")).date()
    tuesday = local_today + timedelta(days=(1 - local_today.weekday()) % 7)
    due_at = datetime.combine(tuesday, time(10, 0), ZoneInfo("Asia/Dhaka")).astimezone(UTC)
    with Session(engine) as db:
        user = User(
            email="student@example.com",
            display_name="Student",
            timezone="Asia/Dhaka",
            onboarding_state=OnboardingState.COMPLETE,
        )
        course = Course(
            provider="google",
            classroom_course_id="3208",
            name="CSE 3208",
            status="ACTIVE",
            provider_metadata={},
        )
        db.add_all([user, course])
        db.flush()
        db.add(CourseMembership(user_id=user.id, course_id=course.id, selected=True))
        item = ClassroomItem(
            course_id=course.id,
            source_type=SourceType.ANNOUNCEMENT,
            source_id="lab-final",
            title="CSE 3208 lab final",
            body="The lab final is on Tuesday.",
            source_url="https://classroom.google.com/c/example",
            source_created_at=datetime.now(UTC),
            source_updated_at=datetime.now(UTC),
            content_hash="a" * 64,
            provider_metadata={},
        )
        db.add(item)
        db.flush()
        event = AcademicEvent(
            classroom_item_id=item.id,
            event_type=EventType.EXAM,
            item_subtype=ItemSubtype.LAB_FINAL,
            starts_at=due_at,
            due_at=due_at,
            priority=3,
            action_required=True,
            confidence=1.0,
            extraction_version="test",
            review_required=False,
            manually_corrected=False,
            extraction_metadata={},
        )
        db.add(event)
        db.flush()
        db.add(
            UserTask(
                user_id=user.id,
                academic_event_id=event.id,
                relevant=True,
                relevance_reason="matched course and date",
            )
        )
        db.add(
            SyncRun(
                user_id=user.id,
                status=SyncStatus.SUCCEEDED,
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                items_seen=1,
                items_changed=1,
                courses_processed=1,
                courses_total=1,
                current_phase="complete",
                timing_metrics={},
            )
        )
        db.commit()
        output = answer_question(
            db,
            user,
            "There is a CSE 3208 lab final on Tuesday",
            SimpleNamespace(gemini_api_key=None, gemini_model="unused"),
        )
    assert output.mode == "local"
    assert output.tool == "get_tasks_by_date"
    assert output.data_available
    assert output.sources[0].course_name == "CSE 3208"
    assert output.sources[0].event_type == "exam"
    assert output.sources[0].source_url.startswith("https://classroom.google.com/")
    assert "CSE 3208 lab final" in output.answer


def test_planner_understands_imperfect_day_of_month_exam_question() -> None:
    plan = plan_query("i have exams sure on 29 of cse 3208 course", date(2026, 9, 28))

    assert plan.tool == "get_tasks_by_date"
    assert isinstance(plan.args, DateRangeArgs)
    assert plan.args.start_date == date(2026, 9, 29)
    assert plan.args.end_date == date(2026, 9, 29)
    assert plan.args.terms == ["CSE 3208"]


def test_assistant_explains_outside_lab_group_and_section() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from app.db.base import Base
    from app.db.models.entities import OnboardingState, User, UserProfile
    from app.services.ai.service import _outside_profile_target

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(
            email="a1@example.test",
            display_name="A1 Student",
            timezone="Asia/Dhaka",
            onboarding_state=OnboardingState.COMPLETE,
        )
        db.add(user)
        db.flush()
        db.add(UserProfile(user_id=user.id, section="A", lab_group="A1"))
        db.commit()

        group_answer = _outside_profile_target(db, user, "What is the Final Report task for B2?")
        assert group_answer is not None
        assert "lab group B2" in group_answer
        assert "profile lab group is A1" in group_answer

        section_answer = _outside_profile_target(db, user, "What is the notice for Section C?")
        assert section_answer is not None
        assert "section C" in section_answer
        assert "profile section is A" in section_answer

        assert _outside_profile_target(db, user, "What is my A1 report task?") is None
        assert _outside_profile_target(db, user, "What is the notice for all groups?") is None


def test_course_resolver_understands_aliases_context_and_ambiguity() -> None:
    from app.services.ai.course_resolver import resolve_course_names

    courses = ["Fall 2025 OS Theory", "CSE 3208 Artificial Intelligence"]
    direct = resolve_course_names(courses, "show mid marks of OS")
    assert direct.course_names == ["Fall 2025 OS Theory"]
    assert not direct.ambiguous

    follow_up = resolve_course_names(
        courses, "what about its question pattern?", "Tell me about CSE 3208"
    )
    assert follow_up.course_names == ["CSE 3208 Artificial Intelligence"]
    assert follow_up.matched_from_context

    ambiguous = resolve_course_names(
        ["CSE 3213 OS Theory", "CSE 4213 OS Advanced"], "show OS marks"
    )
    assert ambiguous.ambiguous_names == ["CSE 3213 OS Theory", "CSE 4213 OS Advanced"]


def test_planner_applies_resolved_course_as_required_filter() -> None:
    plan = plan_query(
        "mid marks of OS",
        date(2026, 9, 29),
        resolved_course_terms=["Fall 2025 OS Theory"],
    )
    assert plan.tool == "search_academic_content"
    assert isinstance(plan.args, SearchArgs)
    assert plan.args.course_terms == ["Fall 2025 OS Theory"]
    assert "marks" in plan.args.query


def test_course_resolver_does_not_treat_code_prefix_as_alias() -> None:
    from app.services.ai.course_resolver import resolve_course_names

    courses = ["CSE 3208 Artificial Intelligence", "CSE 3213 Operating Systems"]
    result = resolve_course_names(courses, "show CSE 3208 details")
    assert result.course_names == ["CSE 3208 Artificial Intelligence"]
    assert not result.ambiguous


def test_course_resolver_maps_ai_alias_to_cse_3208() -> None:
    from app.services.ai.course_resolver import resolve_course_names

    result = resolve_course_names(
        ["Fall 2025 CSE 3208", "Fall 2025 CSE 3214"],
        "is ai lab final marked completed?",
    )
    assert result.course_names == ["Fall 2025 CSE 3208"]
    assert not result.ambiguous


def test_course_resolver_maps_cn_lab_alias_to_cse_3202() -> None:
    from app.services.ai.course_resolver import resolve_course_names

    result = resolve_course_names(
        ["Fall 2025 CSE 3202", "Fall 2025 CSE 3214"],
        "is the CN lab final marked completed?",
    )
    assert result.course_names == ["Fall 2025 CSE 3202"]
    assert not result.ambiguous

def test_course_resolver_ignores_trailing_semester_as_course_code() -> None:
    from app.services.ai.course_resolver import resolve_course_names

    courses = [
        "CSE 11 Spring 2023",
        "CSE 3200 Software Development V - Fall 2025",
        "CSE 3208 - Fall 2025",
        "CSE 3223 Fall 2025",
        "CSE 3224 - Fall2025",
    ]
    result = resolve_course_names(courses, "cse 3208")
    assert result.course_names == ["CSE 3208 - Fall 2025"]
    assert not result.ambiguous


def test_course_resolver_maps_os_lab_alias_to_cse_3214() -> None:
    from app.services.ai.course_resolver import resolve_course_names

    result = resolve_course_names(
        ["Fall 2025 CSE 3208", "Fall 2025 CSE 3214"],
        "is my OS lab final completed?",
    )
    assert result.course_names == ["Fall 2025 CSE 3214"]
    assert not result.ambiguous


def test_completion_question_searches_past_content_in_resolved_course() -> None:
    plan = plan_query(
        "is ai lab final marked completed?",
        date(2026, 9, 30),
        resolved_course_terms=["Fall 2025 CSE 3208"],
    )
    assert plan.tool == "search_academic_content"
    assert isinstance(plan.args, SearchArgs)
    assert plan.args.query == "lab final"
    assert plan.args.course_terms == ["Fall 2025 CSE 3208"]


def test_short_course_reply_continues_previous_completion_question() -> None:
    plan = plan_query(
        "cse 3208",
        date(2026, 10, 1),
        context="is ai lab final marked completed?",
        resolved_course_terms=["CSE 3208 - Fall 2025"],
    )
    assert plan.intent == "completion_status"
    assert plan.item_subtype == ItemSubtype.LAB_FINAL
    assert isinstance(plan.args, SearchArgs)
    assert plan.args.query == "lab final"
    assert plan.args.course_terms == ["CSE 3208 - Fall 2025"]


def test_assistant_marks_one_exact_item_completed(monkeypatch) -> None:
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from uuid import uuid4

    from app.services.ai import service
    from app.services.ai.tools import AcademicRecord

    user = SimpleNamespace(id=uuid4(), timezone="Asia/Dhaka")
    task = SimpleNamespace(id=uuid4(), user_id=user.id, completed=False)
    record = AcademicRecord(
        title="CN Lab Quiz 2\nGroup A1: Wednesday at 1:00 PM",
        body=None,
        course_name="Fall 2025 CSE 3202",
        source_url=None,
        event_type="exam",
        item_subtype="quiz",
        starts_at=datetime(2026, 9, 29, 7, 0, tzinfo=UTC),
        due_at=None,
        priority=2,
        completed=False,
        task_id=task.id,
    )

    class FakeDb:
        committed = False

        def get(self, _model, item_id):
            return task if item_id == task.id else None

        def commit(self):
            self.committed = True

    db = FakeDb()
    monkeypatch.setattr(service, "_execute", lambda *_args: [record])
    monkeypatch.setattr(service, "personal_task_records", lambda *_args: [])
    monkeypatch.setattr(service, "last_successful_sync", lambda *_args: None)
    monkeypatch.setattr(
        service,
        "resolve_course_intent",
        lambda *_args: SimpleNamespace(course_names=[record.course_name], ambiguous=False),
    )

    output = service.answer_question(
        db,
        user,
        "mark it as completed",
        SimpleNamespace(gemini_api_key=None, gemini_model="unused"),
        history=[
            SimpleNamespace(role="user", content="is there a CN lab quiz in this week?"),
            SimpleNamespace(role="assistant", content="Yes — CN Lab Quiz 2 is this week."),
        ],
    )

    assert task.completed
    assert db.committed
    assert output.item is not None and output.item.completed
    assert output.item.title == "CN Lab Quiz 2"
    assert output.answer == "I marked CN Lab Quiz 2 in Fall 2025 CSE 3202 as completed."
    from dataclasses import replace

    task.completed = True
    db.committed = False
    monkeypatch.setattr(service, "_execute", lambda *_args: [replace(record, completed=True)])
    reopened = service.answer_question(
        db,
        user,
        "mark it as incompleted",
        SimpleNamespace(gemini_api_key=None, gemini_model="unused"),
        history=[
            SimpleNamespace(role="user", content="is there a CN lab quiz in this week?"),
            SimpleNamespace(role="assistant", content="Yes — CN Lab Quiz 2 is this week."),
            SimpleNamespace(role="user", content="mark it as incompleted"),
            SimpleNamespace(role="assistant", content="No matching synchronized data was available."),
        ],
    )

    assert not task.completed
    assert db.committed
    assert reopened.answer == "I marked CN Lab Quiz 2 in Fall 2025 CSE 3202 as incomplete."

def test_completion_question_answers_status_directly(monkeypatch) -> None:
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from app.services.ai import service
    from app.services.ai.tools import AcademicRecord

    record = AcademicRecord(
        title="AI Lab Final",
        body="Held on September 29.",
        course_name="Fall 2025 CSE 3208",
        source_url="https://classroom.google.com/c/3208",
        event_type="exam",
        starts_at=datetime(2026, 9, 29, 7, 0, tzinfo=UTC),
        due_at=None,
        priority=3,
        completed=True,
    )
    monkeypatch.setattr(service, "_execute", lambda *_args: [record])
    monkeypatch.setattr(service, "personal_task_records", lambda *_args: [])
    monkeypatch.setattr(service, "last_successful_sync", lambda *_args: None)
    monkeypatch.setattr(
        service,
        "resolve_course_intent",
        lambda *_args: SimpleNamespace(course_names=[record.course_name], ambiguous=False),
    )
    output = service.answer_question(
        None,
        SimpleNamespace(id="user", timezone="Asia/Dhaka"),
        "is ai lab final marked completed?",
        SimpleNamespace(gemini_api_key=None, gemini_model="unused"),
    )
    assert output.tool == "search_academic_content"
    assert output.answer.startswith("Yes — AI Lab Final")
    assert "CSE 3208" in output.answer
    assert "is completed" in output.answer


def test_completion_question_ignores_question_pattern_post(monkeypatch) -> None:
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from app.services.ai import service
    from app.services.ai.tools import AcademicRecord

    pattern = AcademicRecord(
        title="Lab Final Question Pattern",
        body="Theoretical and coding questions.",
        course_name="Fall 2025 CSE 3208",
        source_url="https://classroom.google.com/c/3208/pattern",
        event_type="exam",
        item_subtype="lab_final",
        starts_at=None,
        due_at=None,
        priority=1,
        completed=False,
    )
    assessment = AcademicRecord(
        title="AI Lab Final",
        body="Held on September 29.",
        course_name="Fall 2025 CSE 3208",
        source_url="https://classroom.google.com/c/3208/final",
        event_type="exam",
        item_subtype="lab_final",
        starts_at=datetime(2026, 9, 29, 7, 0, tzinfo=UTC),
        due_at=None,
        priority=3,
        completed=True,
    )
    monkeypatch.setattr(service, "_execute", lambda *_args: [pattern, assessment])
    monkeypatch.setattr(service, "personal_task_records", lambda *_args: [])
    monkeypatch.setattr(service, "last_successful_sync", lambda *_args: None)
    monkeypatch.setattr(
        service,
        "resolve_course_intent",
        lambda *_args: SimpleNamespace(
            course_names=[assessment.course_name],
            ambiguous=False,
        ),
    )

    output = service.answer_question(
        None,
        SimpleNamespace(id="user", timezone="Asia/Dhaka"),
        "is ai lab final marked completed?",
        SimpleNamespace(gemini_api_key=None, gemini_model="unused"),
    )

    assert output.answer.startswith("Yes — AI Lab Final")
    assert [source.title for source in output.sources] == ["AI Lab Final"]


def test_course_resolver_uses_only_active_selected_memberships() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from app.db.base import Base
    from app.db.models.entities import Course, CourseMembership, OnboardingState, User
    from app.services.ai.course_resolver import resolve_course_intent

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(
            email="resolver@example.test",
            display_name="Resolver",
            timezone="UTC",
            onboarding_state=OnboardingState.COMPLETE,
        )
        selected = Course(
            provider="google",
            classroom_course_id="1",
            name="CSE 3213 OS Theory",
            status="ACTIVE",
            provider_metadata={},
        )
        unselected = Course(
            provider="google",
            classroom_course_id="2",
            name="CSE 4213 OS Advanced",
            status="ACTIVE",
            provider_metadata={},
        )
        inactive = Course(
            provider="google",
            classroom_course_id="3",
            name="CSE 5213 OS Research",
            status="ACTIVE",
            provider_metadata={},
        )
        db.add_all([user, selected, unselected, inactive])
        db.flush()
        db.add_all(
            [
                CourseMembership(
                    user_id=user.id,
                    course_id=selected.id,
                    selected=True,
                    enrollment_status="ACTIVE",
                ),
                CourseMembership(
                    user_id=user.id,
                    course_id=unselected.id,
                    selected=False,
                    enrollment_status="ACTIVE",
                ),
                CourseMembership(
                    user_id=user.id,
                    course_id=inactive.id,
                    selected=True,
                    enrollment_status="INACTIVE",
                ),
            ]
        )
        db.commit()
        result = resolve_course_intent(db, user.id, "show OS marks")
    assert result.course_names == ["CSE 3213 OS Theory"]
    assert not result.ambiguous


def test_assistant_asks_for_clarification_when_course_alias_is_ambiguous(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.services.ai import service

    monkeypatch.setattr(
        service,
        "resolve_course_intent",
        lambda *_args: SimpleNamespace(
            course_names=[],
            ambiguous=True,
            ambiguous_names=["CSE 3213 OS Theory", "CSE 4213 OS Advanced"],
        ),
    )
    monkeypatch.setattr(service, "last_successful_sync", lambda *_args: None)
    output = service.answer_question(
        None,
        SimpleNamespace(id="user", timezone="UTC"),
        "show OS marks",
        SimpleNamespace(gemini_api_key=None, gemini_model="unused"),
    )
    assert output.mode == "local"
    assert output.sources == []
    assert "Which course do you mean" in output.answer
    assert "CSE 3213 OS Theory" in output.answer
    assert "CSE 4213 OS Advanced" in output.answer


def test_classroom_attachment_metadata_is_normalized_and_safe() -> None:
    from datetime import UTC, datetime

    from app.services.synchronization.classroom_sync import _attachment_metadata

    synchronized_at = datetime(2026, 9, 29, tzinfo=UTC)
    materials = [
        {
            "driveFile": {
                "driveFile": {
                    "id": "pdf-1",
                    "title": "OS Mid Marks.pdf",
                    "alternateLink": "https://drive.google.com/file/d/pdf-1/view",
                }
            }
        },
        {"link": {"title": "Marks sheet", "url": "https://example.edu/marks"}},
        {"link": {"title": "Unsafe", "url": "javascript:alert(1)"}},
    ]
    attachments = _attachment_metadata(materials, synchronized_at)
    assert len(attachments) == 2
    assert attachments[0]["provider_id"] == "pdf-1"
    assert attachments[0]["is_pdf"] is True
    assert attachments[0]["url"].startswith("https://")
    assert attachments[0]["synchronized_at"] == synchronized_at.isoformat()
    assert attachments[1]["kind"] == "link"


@pytest.mark.parametrize(
    ("attachments", "expected_label", "expected_kind"),
    [
        (
            [
                {
                    "title": "OS Marks.pdf",
                    "url": "https://drive.google.com/marks",
                    "kind": "drive_file",
                    "is_pdf": True,
                }
            ],
            "Open marks PDF",
            "pdf",
        ),
        (
            [
                {
                    "title": "OS Marks",
                    "url": "https://drive.google.com/sheet",
                    "kind": "drive_file",
                    "is_pdf": False,
                }
            ],
            "Open OS Marks",
            "attachment",
        ),
        ([], "Open Classroom post", "classroom"),
    ],
)
def test_marks_answers_expose_only_contextual_document_actions(
    monkeypatch, attachments, expected_label, expected_kind
) -> None:
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from app.services.ai import service
    from app.services.ai.tools import AcademicAttachment, AcademicRecord

    record = AcademicRecord(
        title="Midterm marks",
        body="Marks are available.",
        course_name="CSE 3213 OS Theory",
        source_url="https://classroom.google.com/c/1/p/1",
        event_type="notice",
        starts_at=datetime(2026, 9, 29, tzinfo=UTC),
        due_at=None,
        priority=1,
        completed=False,
        attachments=[AcademicAttachment(**item) for item in attachments],
    )
    monkeypatch.setattr(service, "_execute", lambda *_args: [record])
    monkeypatch.setattr(service, "last_successful_sync", lambda *_args: None)
    monkeypatch.setattr(
        service,
        "resolve_course_intent",
        lambda *_args: SimpleNamespace(course_names=[record.course_name], ambiguous=False),
    )
    output = service.answer_question(
        None,
        SimpleNamespace(id="user", timezone="UTC"),
        "show mid marks of OS",
        SimpleNamespace(gemini_api_key=None, gemini_model="unused"),
    )
    assert len(output.sources) == 1
    assert len(output.sources[0].actions) == 1
    assert output.sources[0].actions[0].label == expected_label
    assert output.sources[0].actions[0].kind == expected_kind
    if expected_kind == "attachment":
        assert "No PDF was attached" in output.answer
    if expected_kind == "classroom":
        assert "No marks document was attached" in output.answer


def test_non_marks_answer_does_not_expose_generic_source_actions(monkeypatch) -> None:
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from app.services.ai import service
    from app.services.ai.tools import AcademicAttachment, AcademicRecord

    record = AcademicRecord(
        title="OS notice",
        body="Read this notice.",
        course_name="CSE 3213 OS Theory",
        source_url="https://classroom.google.com/c/1/p/1",
        event_type="notice",
        starts_at=datetime(2026, 9, 29, tzinfo=UTC),
        due_at=None,
        priority=1,
        completed=False,
        attachments=[
            AcademicAttachment(
                title="Notice.pdf",
                url="https://drive.google.com/notice",
                kind="drive_file",
                is_pdf=True,
            )
        ],
    )
    monkeypatch.setattr(service, "_execute", lambda *_args: [record])
    monkeypatch.setattr(service, "last_successful_sync", lambda *_args: None)
    monkeypatch.setattr(
        service,
        "resolve_course_intent",
        lambda *_args: SimpleNamespace(course_names=[record.course_name], ambiguous=False),
    )
    output = service.answer_question(
        None,
        SimpleNamespace(id="user", timezone="UTC"),
        "show OS notice",
        SimpleNamespace(gemini_api_key=None, gemini_model="unused"),
    )
    assert output.sources[0].actions == []
