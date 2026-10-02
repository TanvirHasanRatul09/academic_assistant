# ruff: noqa: B008
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_csrf
from app.core.config import get_settings
from app.core.rate_limit import rate_limit
from app.db.models.entities import (
    AcademicEvent,
    ClassroomItem,
    Course,
    CourseMembership,
    EventTarget,
    EventType,
    PersonalTask,
    SourceType,
    User,
    UserTask,
)
from app.db.session import get_db
from app.schemas.dashboard import (
    DashboardCourse,
    DashboardItem,
    DashboardOutput,
    DashboardTarget,
    TaskStateInput,
    TaskStateOutput,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class DashboardSource(StrEnum):
    ALL = "all"
    CLASSROOM = "classroom"
    MANUAL = "manual"


class DashboardView(StrEnum):
    ALL = "all"
    TODAY = "today"
    TOMORROW = "tomorrow"
    WEEK = "week"
    UPCOMING = "upcoming"
    DEADLINES = "deadlines"
    EXAMS = "exams"
    NOTICES = "notices"
    RECENT = "recent"


def utc_day(day: date, timezone: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, timezone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, timezone).astimezone(UTC)
    return start, end


@router.get("", response_model=DashboardOutput)
def get_dashboard(
    view: DashboardView = DashboardView.ALL,
    course_id: UUID | None = None,
    event_type: EventType | None = None,
    completed: bool | None = None,
    priority: int | None = Query(default=None, ge=0, le=3),
    source: DashboardSource = DashboardSource.ALL,
    limit: int = Query(default=100, ge=1, le=1000),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardOutput:
    now = datetime.now(UTC)
    timezone = ZoneInfo(user.timezone)
    local_today = now.astimezone(timezone).date()
    event_time = func.coalesce(AcademicEvent.due_at, AcademicEvent.starts_at)

    statement = (
        select(UserTask, AcademicEvent, ClassroomItem, Course)
        .join(AcademicEvent, AcademicEvent.id == UserTask.academic_event_id)
        .join(ClassroomItem, ClassroomItem.id == AcademicEvent.classroom_item_id)
        .join(Course, Course.id == ClassroomItem.course_id)
        .join(
            CourseMembership,
            (CourseMembership.course_id == Course.id)
            & (CourseMembership.user_id == user.id)
            & CourseMembership.selected.is_(True)
            & (CourseMembership.enrollment_status == "ACTIVE"),
        )
        .where(UserTask.user_id == user.id, UserTask.relevant.is_(True))
    )
    if course_id:
        statement = statement.where(Course.id == course_id)
    if event_type:
        statement = statement.where(AcademicEvent.event_type == event_type)
    if completed is not None:
        statement = statement.where(UserTask.completed.is_(completed))
    if priority is not None:
        statement = statement.where(AcademicEvent.priority == priority)

    if view in {DashboardView.TODAY, DashboardView.TOMORROW}:
        day = local_today + timedelta(days=1 if view == DashboardView.TOMORROW else 0)
        start, end = utc_day(day, timezone)
        statement = statement.where(event_time >= start, event_time < end)
    elif view == DashboardView.WEEK:
        start, _ = utc_day(local_today, timezone)
        _, end = utc_day(local_today + timedelta(days=6), timezone)
        statement = statement.where(event_time >= start, event_time < end)
    elif view in {DashboardView.UPCOMING, DashboardView.DEADLINES}:
        statement = statement.where(AcademicEvent.due_at >= now)
    elif view == DashboardView.EXAMS:
        statement = statement.where(AcademicEvent.event_type == EventType.EXAM)
    elif view == DashboardView.NOTICES:
        statement = statement.where(AcademicEvent.event_type == EventType.NOTICE)
    elif view == DashboardView.RECENT:
        statement = statement.where(ClassroomItem.source_updated_at >= now - timedelta(days=7))

    rows = (
        []
        if source == DashboardSource.MANUAL
        else db.execute(
            statement.order_by(
                UserTask.completed.asc(),
                AcademicEvent.priority.desc(),
                event_time.asc().nulls_last(),
                ClassroomItem.source_updated_at.desc(),
            ).limit(limit)
        ).all()
    )
    event_ids = [event.id for _, event, _, _ in rows]
    targets_by_event: dict[UUID, list[DashboardTarget]] = {event_id: [] for event_id in event_ids}
    if event_ids:
        target_query = select(EventTarget).where(EventTarget.academic_event_id.in_(event_ids))
        for target in db.scalars(target_query):
            targets_by_event[target.academic_event_id].append(
                DashboardTarget(
                    section=target.section,
                    lab_group=target.lab_group,
                    academic_level=target.academic_level,
                    program=target.program,
                    course_wide=target.course_wide,
                )
            )

    courses = [
        DashboardCourse(id=course.id, name=course.name)
        for course in db.scalars(
            select(Course)
            .join(CourseMembership, CourseMembership.course_id == Course.id)
            .where(
                CourseMembership.user_id == user.id,
                CourseMembership.selected.is_(True),
                CourseMembership.enrollment_status == "ACTIVE",
            )
            .order_by(Course.name)
        )
    ]
    items = [
        DashboardItem(
            task_id=task.id,
            event_id=event.id,
            course_id=course.id,
            course_name=course.name,
            title=item.title,
            body=item.body,
            source_type=item.source_type,
            source_url=item.source_url,
            source_created_at=item.source_created_at,
            source_updated_at=item.source_updated_at,
            event_type=event.event_type,
            starts_at=event.starts_at,
            due_at=event.due_at,
            priority=event.priority,
            action_required=event.action_required,
            confidence=event.confidence,
            review_required=event.review_required,
            manually_corrected=event.manually_corrected,
            relevant=task.relevant,
            relevance_reason=task.relevance_reason,
            completed=task.completed,
            acknowledged=task.acknowledged,
            read=task.read,
            task_updated_at=task.updated_at,
            targets=targets_by_event[event.id],
        )
        for task, event, item, course in rows
    ]

    if source != DashboardSource.CLASSROOM:
        personal_time = func.coalesce(PersonalTask.due_at, PersonalTask.starts_at)
        personal_statement = (
            select(PersonalTask, Course)
            .outerjoin(Course, Course.id == PersonalTask.course_id)
            .outerjoin(
                CourseMembership,
                (CourseMembership.course_id == PersonalTask.course_id)
                & (CourseMembership.user_id == user.id)
                & CourseMembership.selected.is_(True)
                & (CourseMembership.enrollment_status == "ACTIVE"),
            )
            .where(
                PersonalTask.user_id == user.id,
                (PersonalTask.course_id.is_(None)) | (CourseMembership.id.is_not(None)),
            )
        )
        if course_id:
            personal_statement = personal_statement.where(PersonalTask.course_id == course_id)
        if event_type:
            personal_statement = personal_statement.where(PersonalTask.event_type == event_type)
        if completed is not None:
            personal_statement = personal_statement.where(PersonalTask.completed.is_(completed))
        if priority is not None:
            personal_statement = personal_statement.where(PersonalTask.priority == priority)
        if view in {DashboardView.TODAY, DashboardView.TOMORROW}:
            day = local_today + timedelta(days=1 if view == DashboardView.TOMORROW else 0)
            start, end = utc_day(day, timezone)
            personal_statement = personal_statement.where(
                personal_time >= start, personal_time < end
            )
        elif view == DashboardView.WEEK:
            start, _ = utc_day(local_today, timezone)
            _, end = utc_day(local_today + timedelta(days=6), timezone)
            personal_statement = personal_statement.where(
                personal_time >= start, personal_time < end
            )
        elif view in {DashboardView.UPCOMING, DashboardView.DEADLINES}:
            personal_statement = personal_statement.where(PersonalTask.due_at >= now)
        elif view == DashboardView.EXAMS:
            personal_statement = personal_statement.where(PersonalTask.event_type == EventType.EXAM)
        elif view == DashboardView.NOTICES:
            personal_statement = personal_statement.where(
                PersonalTask.event_type == EventType.NOTICE
            )
        elif view == DashboardView.RECENT:
            personal_statement = personal_statement.where(
                PersonalTask.updated_at >= now - timedelta(days=7)
            )
        personal_rows = db.execute(personal_statement.limit(limit)).all()
        items.extend(
            DashboardItem(
                task_id=task.id,
                event_id=task.id,
                course_id=task.course_id,
                course_name=course.name if course else "Personal",
                title=task.title,
                body=task.details,
                source_type=SourceType.MANUAL,
                source_url=None,
                source_created_at=task.created_at,
                source_updated_at=task.updated_at,
                event_type=task.event_type,
                starts_at=task.starts_at,
                due_at=task.due_at,
                priority=task.priority,
                action_required=not task.completed,
                confidence=1.0,
                review_required=False,
                manually_corrected=True,
                relevant=True,
                relevance_reason="added by user",
                completed=task.completed,
                acknowledged=True,
                read=True,
                task_updated_at=task.updated_at,
                targets=[
                    DashboardTarget(
                        section=task.section,
                        lab_group=task.lab_group,
                        academic_level=None,
                        program=None,
                        course_wide=not (task.section or task.lab_group),
                    )
                ],
                source_kind="manual",
            )
            for task, course in personal_rows
        )
    items.sort(
        key=lambda item: (
            item.completed,
            -item.priority,
            item.due_at or item.starts_at or datetime.max.replace(tzinfo=UTC),
            item.source_updated_at,
        )
    )
    items = items[:limit]
    return DashboardOutput(
        generated_at=now,
        timezone=user.timezone,
        items=items,
        courses=courses,
    )


@router.get("/relevance-debug")
def relevance_debug(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    if get_settings().app_env == "production":
        raise HTTPException(status_code=404, detail="Not found")
    rows = db.execute(
        select(UserTask, AcademicEvent, ClassroomItem, Course)
        .join(AcademicEvent, AcademicEvent.id == UserTask.academic_event_id)
        .join(ClassroomItem, ClassroomItem.id == AcademicEvent.classroom_item_id)
        .join(Course, Course.id == ClassroomItem.course_id)
        .join(CourseMembership, CourseMembership.course_id == Course.id)
        .where(
            UserTask.user_id == user.id,
            CourseMembership.user_id == user.id,
            CourseMembership.selected.is_(True),
            CourseMembership.enrollment_status == "ACTIVE",
        )
        .order_by(ClassroomItem.source_updated_at.desc())
        .limit(200)
    ).all()
    return [
        {
            "event_id": str(event.id),
            "course": course.name,
            "title": item.title,
            "relevant": task.relevant,
            "reason": task.relevance_reason,
            "review_required": event.review_required,
            "targeting": event.extraction_metadata.get("targeting", {}),
        }
        for task, event, item, course in rows
    ]


@router.patch(
    "/tasks/{task_id}",
    response_model=TaskStateOutput,
    dependencies=[Depends(require_csrf), Depends(rate_limit("task-state", 60, 60))],
)
def update_task_state(
    task_id: UUID,
    payload: TaskStateInput,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserTask | TaskStateOutput:
    state_fields = payload.model_fields_set - {"expected_updated_at"}
    if not state_fields:
        raise HTTPException(status_code=422, detail="At least one task state is required")
    task = db.scalar(
        select(UserTask)
        .where(UserTask.id == task_id, UserTask.user_id == user.id)
        .with_for_update()
    )
    if not task:
        personal = db.scalar(
            select(PersonalTask)
            .where(PersonalTask.id == task_id, PersonalTask.user_id == user.id)
            .with_for_update()
        )
        if not personal:
            raise HTTPException(status_code=404, detail="Task not found")
        if payload.expected_updated_at and personal.updated_at != payload.expected_updated_at:
            raise HTTPException(status_code=409, detail="Task state changed on another device")
        if payload.completed is not None:
            personal.completed = payload.completed
        db.commit()
        db.refresh(personal)
        return TaskStateOutput(
            id=personal.id,
            completed=personal.completed,
            acknowledged=True,
            read=True,
            updated_at=personal.updated_at,
        )
    if payload.expected_updated_at and task.updated_at != payload.expected_updated_at:
        raise HTTPException(status_code=409, detail="Task state changed on another device")
    for field in state_fields:
        value = getattr(payload, field)
        if value is not None:
            setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task
