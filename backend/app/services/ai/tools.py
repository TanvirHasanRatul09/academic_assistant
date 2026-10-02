from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.db.models.entities import (
    AcademicEvent,
    ClassroomItem,
    Course,
    CourseMembership,
    EventType,
    ItemSubtype,
    SyncRun,
    SyncStatus,
    UserTask,
)

MAX_RESULTS = 50


class DateRangeArgs(BaseModel):
    start_date: date
    end_date: date
    limit: int = Field(default=25, ge=1, le=MAX_RESULTS)
    terms: list[str] = Field(default_factory=list, max_length=4)
    item_subtype: ItemSubtype | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "DateRangeArgs":
        if self.end_date < self.start_date or (self.end_date - self.start_date).days > 31:
            raise ValueError("date range must be between 0 and 31 days")
        return self


class UpcomingArgs(BaseModel):
    days: int = Field(default=30, ge=1, le=60)
    limit: int = Field(default=25, ge=1, le=MAX_RESULTS)
    terms: list[str] = Field(default_factory=list, max_length=4)
    item_subtype: ItemSubtype | None = None


class ExamArgs(BaseModel):
    days: int = Field(default=120, ge=1, le=180)
    limit: int = Field(default=25, ge=1, le=MAX_RESULTS)
    terms: list[str] = Field(default_factory=list, max_length=4)
    item_subtype: ItemSubtype | None = None
    include_past: bool = False


class SearchArgs(BaseModel):
    query: str = Field(min_length=2, max_length=120)
    course_terms: list[str] = Field(default_factory=list, max_length=4)
    item_subtype: ItemSubtype | None = None
    limit: int = Field(default=25, ge=1, le=25)


@dataclass(frozen=True)
class AcademicAttachment:
    title: str
    url: str
    kind: str
    is_pdf: bool


@dataclass(frozen=True)
class AcademicRecord:
    title: str
    body: str | None
    course_name: str
    source_url: str | None
    event_type: str
    starts_at: datetime | None
    due_at: datetime | None
    priority: int
    completed: bool
    item_subtype: str = "other"
    attachments: list[AcademicAttachment] = field(default_factory=list)
    personal: bool = False
    task_id: UUID | None = None
    personal_task_id: UUID | None = None


def _base_statement(user_id: UUID):
    return (
        select(UserTask, AcademicEvent, ClassroomItem, Course)
        .join(AcademicEvent, AcademicEvent.id == UserTask.academic_event_id)
        .join(ClassroomItem, ClassroomItem.id == AcademicEvent.classroom_item_id)
        .join(Course, Course.id == ClassroomItem.course_id)
        .join(
            CourseMembership,
            (CourseMembership.course_id == Course.id)
            & (CourseMembership.user_id == user_id)
            & CourseMembership.selected.is_(True)
            & (CourseMembership.enrollment_status == "ACTIVE"),
        )
        .where(
            UserTask.user_id == user_id,
            UserTask.relevant.is_(True),
            Course.status == "ACTIVE",
        )
    )


def _with_terms(statement, terms: list[str]):
    for term in terms:
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        statement = statement.where(
            or_(
                ClassroomItem.title.ilike(pattern, escape="\\"),
                ClassroomItem.body.ilike(pattern, escape="\\"),
                Course.name.ilike(pattern, escape="\\"),
            )
        )
    return statement


def _records(
    db: Session, statement, limit: int, *, recent_source_first: bool = False
) -> list[AcademicRecord]:
    event_time = func.coalesce(AcademicEvent.due_at, AcademicEvent.starts_at)
    ordering = [UserTask.completed.asc()]
    if recent_source_first:
        ordering.append(ClassroomItem.source_updated_at.desc())
    ordering.extend([AcademicEvent.priority.desc(), event_time.asc().nulls_last()])
    rows = db.execute(statement.order_by(*ordering).limit(limit)).all()
    return [
        AcademicRecord(
            title=item.title,
            body=item.body,
            course_name=course.name,
            source_url=item.source_url,
            event_type=event.event_type.value,
            item_subtype=event.item_subtype.value,
            starts_at=event.starts_at,
            due_at=event.due_at,
            priority=event.priority,
            completed=task.completed,
            task_id=task.id,
            attachments=[
                AcademicAttachment(
                    title=str(attachment.get("title") or "Attachment")[:500],
                    url=str(attachment.get("url") or "")[:2048],
                    kind=str(attachment.get("kind") or "attachment")[:32],
                    is_pdf=bool(attachment.get("is_pdf")),
                )
                for attachment in (item.provider_metadata or {}).get("attachments", [])[:25]
                if isinstance(attachment, dict)
                and str(attachment.get("url") or "").startswith("https://")
            ],
        )
        for task, event, item, course in rows
    ]


def _utc_bounds(day: date, timezone_name: str) -> tuple[datetime, datetime]:
    timezone = ZoneInfo(timezone_name)
    start = datetime.combine(day, time.min, timezone).astimezone(UTC)
    return start, datetime.combine(day + timedelta(days=1), time.min, timezone).astimezone(UTC)


def get_tasks_by_date(
    db: Session, user_id: UUID, timezone_name: str, args: DateRangeArgs
) -> list[AcademicRecord]:
    start, _ = _utc_bounds(args.start_date, timezone_name)
    _, end = _utc_bounds(args.end_date, timezone_name)
    event_time = func.coalesce(AcademicEvent.due_at, AcademicEvent.starts_at)
    statement = _base_statement(user_id).where(event_time >= start, event_time < end)
    if args.item_subtype:
        statement = statement.where(AcademicEvent.item_subtype == args.item_subtype)
    return _records(
        db,
        _with_terms(statement, args.terms),
        args.limit,
    )


def get_upcoming_deadlines(db: Session, user_id: UUID, args: UpcomingArgs) -> list[AcademicRecord]:
    now = datetime.now(UTC)
    statement = _base_statement(user_id).where(
        AcademicEvent.due_at >= now, AcademicEvent.due_at <= now + timedelta(days=args.days)
    )
    if args.item_subtype:
        statement = statement.where(AcademicEvent.item_subtype == args.item_subtype)
    return _records(
        db,
        _with_terms(statement, args.terms),
        args.limit,
    )


def get_exams(db: Session, user_id: UUID, args: ExamArgs) -> list[AcademicRecord]:
    now = datetime.now(UTC)
    event_time = func.coalesce(AcademicEvent.starts_at, AcademicEvent.due_at)
    statement = _base_statement(user_id).where(AcademicEvent.event_type == EventType.EXAM)
    if not args.include_past:
        statement = statement.where(
            event_time >= now, event_time <= now + timedelta(days=args.days)
        )
    if args.item_subtype:
        statement = statement.where(AcademicEvent.item_subtype == args.item_subtype)
    return _records(
        db,
        _with_terms(statement, args.terms),
        args.limit,
    )


def search_academic_content(db: Session, user_id: UUID, args: SearchArgs) -> list[AcademicRecord]:
    statement = _base_statement(user_id)
    if args.item_subtype:
        statement = statement.where(AcademicEvent.item_subtype == args.item_subtype)
    tokens = [token for token in args.query.casefold().split() if len(token) >= 3][:8]
    for token in tokens:
        escaped = token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        statement = statement.where(
            or_(
                ClassroomItem.title.ilike(pattern, escape="\\"),
                ClassroomItem.body.ilike(pattern, escape="\\"),
                Course.name.ilike(pattern, escape="\\"),
            )
        )
    for course_term in args.course_terms:
        escaped = course_term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = statement.where(Course.name.ilike(f"%{escaped}%", escape="\\"))
    escaped_query = args.query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    statement = statement.order_by(
        case(
            (func.lower(ClassroomItem.title) == args.query.casefold(), 0),
            (ClassroomItem.title.ilike(f"%{escaped_query}%", escape="\\"), 1),
            else_=2,
        )
    )
    return _records(db, statement, args.limit, recent_source_first=True)


def last_successful_sync(db: Session, user_id: UUID) -> datetime | None:
    return db.scalar(
        select(SyncRun.finished_at)
        .where(SyncRun.user_id == user_id, SyncRun.status == SyncStatus.SUCCEEDED)
        .order_by(SyncRun.finished_at.desc())
        .limit(1)
    )
