from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models.entities import (
    Course,
    CourseMembership,
    EventType,
    PersonalTask,
    SourceType,
    User,
)
from app.services.ai.planner import QueryPlan
from app.services.ai.tools import AcademicRecord, DateRangeArgs, ExamArgs, SearchArgs, UpcomingArgs
from app.services.extraction.rules import classify_item_subtype


def _bounds(day, timezone_name: str):
    timezone = ZoneInfo(timezone_name)
    start = datetime.combine(day, time.min, timezone).astimezone(UTC)
    return start, datetime.combine(day + timedelta(days=1), time.min, timezone).astimezone(UTC)


def personal_task_records(db: Session, user: User, plan: QueryPlan) -> list[AcademicRecord]:
    event_time = func.coalesce(PersonalTask.due_at, PersonalTask.starts_at)
    statement = (
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
            or_(PersonalTask.course_id.is_(None), CourseMembership.id.is_not(None)),
        )
    )
    limit = 25
    if plan.tool == "get_tasks_by_date":
        args = plan.args
        assert isinstance(args, DateRangeArgs)
        start, _ = _bounds(args.start_date, user.timezone)
        _, end = _bounds(args.end_date, user.timezone)
        statement = statement.where(event_time >= start, event_time < end)
        limit = args.limit
    elif plan.tool == "get_upcoming_deadlines":
        args = plan.args
        assert isinstance(args, UpcomingArgs)
        now = datetime.now(UTC)
        statement = statement.where(
            PersonalTask.due_at >= now, PersonalTask.due_at <= now + timedelta(days=args.days)
        )
        limit = args.limit
    elif plan.tool == "get_exams":
        args = plan.args
        assert isinstance(args, ExamArgs)
        now = datetime.now(UTC)
        statement = statement.where(
            PersonalTask.event_type == EventType.EXAM,
            event_time >= now,
            event_time <= now + timedelta(days=args.days),
        )
        limit = args.limit
    else:
        args = plan.args
        assert isinstance(args, SearchArgs)
        for token in [token for token in args.query.casefold().split() if len(token) >= 3][:8]:
            pattern = f"%{token.replace('%', '').replace('_', '')}%"
            statement = statement.where(
                or_(
                    PersonalTask.title.ilike(pattern),
                    PersonalTask.details.ilike(pattern),
                    Course.name.ilike(pattern),
                )
            )
        for course_term in args.course_terms:
            statement = statement.where(
                Course.name.ilike(f"%{course_term.replace('%', '').replace('_', '')}%")
            )
        limit = args.limit
    rows = db.execute(
        statement.order_by(
            PersonalTask.completed, event_time.asc().nulls_last(), PersonalTask.priority.desc()
        ).limit(limit)
    ).all()
    return [
        AcademicRecord(
            title=task.title,
            body=task.details,
            course_name=course.name if course else "Personal",
            source_url=None,
            event_type=task.event_type.value,
            item_subtype=classify_item_subtype(
                f"{task.title}\n{task.details or ''}", SourceType.MANUAL
            ).value,
            starts_at=task.starts_at,
            due_at=task.due_at,
            priority=task.priority,
            completed=task.completed,
            personal=True,
            personal_task_id=task.id,
        )
        for task, course in rows
    ]
