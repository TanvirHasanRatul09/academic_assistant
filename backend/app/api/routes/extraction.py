import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, delete, exists, func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_csrf
from app.core.rate_limit import rate_limit
from app.db.models.entities import (
    AcademicEvent,
    ClassroomItem,
    Course,
    CourseMembership,
    EventTarget,
    User,
    UserTask,
)
from app.db.session import get_db
from app.schemas.extraction import (
    EventCorrection,
    EventOutput,
    ReprocessResult,
    ReviewItem,
    ReviewPage,
    ReviewTarget,
)
from app.services.extraction.pipeline import process_user
from app.services.extraction.rules import (
    normalize_lab_group,
    normalize_level,
    normalize_program,
    normalize_section,
)

router = APIRouter(prefix="/api/extraction", tags=["extraction"])


@router.post(
    "/reprocess",
    response_model=ReprocessResult,
    dependencies=[Depends(require_csrf), Depends(rate_limit("reprocess", 4, 300))],
)
def reprocess(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ReprocessResult:
    return ReprocessResult(**process_user(db, user.id))


@router.get("/review", response_model=ReviewPage)
def review_queue(
    offset: int = 0,
    limit: int = 25,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewPage:
    limit = min(max(limit, 1), 100)
    profile = user.profile
    profile_section = normalize_section(profile.section if profile else None)
    profile_group = normalize_lab_group(profile.lab_group if profile else None)
    profile_level = normalize_level(profile.academic_level if profile else None)
    profile_program = normalize_program(profile.program if profile else None)

    def matches_profile(column, value: str | None):
        return (
            column.is_(None)
            if value is None
            else or_(column.is_(None), func.lower(column) == value)
        )

    relevant_target = exists(
        select(EventTarget.id).where(
            EventTarget.academic_event_id == AcademicEvent.id,
            or_(
                EventTarget.course_wide.is_(True),
                and_(
                    matches_profile(EventTarget.section, profile_section),
                    matches_profile(EventTarget.lab_group, profile_group),
                    matches_profile(EventTarget.academic_level, profile_level),
                    matches_profile(EventTarget.program, profile_program),
                ),
            ),
        )
    )
    base = (
        select(AcademicEvent, ClassroomItem, Course)
        .join(ClassroomItem, ClassroomItem.id == AcademicEvent.classroom_item_id)
        .join(Course, Course.id == ClassroomItem.course_id)
        .join(CourseMembership, CourseMembership.course_id == ClassroomItem.course_id)
        .where(
            CourseMembership.user_id == user.id,
            CourseMembership.selected.is_(True),
            CourseMembership.enrollment_status == "ACTIVE",
            AcademicEvent.review_required.is_(True),
            relevant_target,
        )
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(
        base.order_by(AcademicEvent.due_at.asc().nulls_last()).offset(offset).limit(limit)
    ).all()
    ids = [event.id for event, _, _ in rows]
    targets = {}
    if ids:
        targets = {event_id: [] for event_id in ids}
        for target in db.scalars(select(EventTarget).where(EventTarget.academic_event_id.in_(ids))):
            targets[target.academic_event_id].append(
                ReviewTarget(
                    section=target.section,
                    lab_group=target.lab_group,
                    course_wide=target.course_wide,
                )
            )
    items = []
    for event, source, course in rows:
        metadata = event.extraction_metadata or {}
        reason = metadata.get("review_reason") or (
            "Missing date"
            if not event.due_at and not event.starts_at
            else "Low confidence"
            if event.confidence < 0.75
            else "Unknown event type"
        )
        items.append(
            ReviewItem(
                event=event,
                title=source.title,
                body=source.body,
                course_id=course.id,
                course_name=course.name,
                source_url=source.source_url,
                targets=targets[event.id],
                review_reason=reason,
            )
        )
    return ReviewPage(
        items=items, offset=offset, limit=limit, total=total, has_more=offset + len(items) < total
    )


@router.patch(
    "/events/{event_id}",
    response_model=EventOutput,
    dependencies=[Depends(require_csrf), Depends(rate_limit("event-correction", 20, 60))],
)
def correct_event(
    event_id: UUID,
    payload: EventCorrection,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AcademicEvent:
    event = db.scalar(
        select(AcademicEvent)
        .join(ClassroomItem, ClassroomItem.id == AcademicEvent.classroom_item_id)
        .join(CourseMembership, CourseMembership.course_id == ClassroomItem.course_id)
        .where(AcademicEvent.id == event_id, CourseMembership.user_id == user.id)
    )
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    section = re.sub(r"\\s+", " ", payload.section or "").strip() or None
    lab_group = re.sub(r"\\s+", " ", payload.lab_group or "").strip() or None
    event.event_type = payload.event_type
    event.starts_at = payload.starts_at
    event.due_at = payload.due_at
    event.priority = payload.priority
    event.action_required = payload.action_required
    event.confidence = 1.0
    event.review_required = False
    event.manually_corrected = True
    event.extraction_metadata = {**event.extraction_metadata, "corrected_by_user": True}
    db.execute(delete(EventTarget).where(EventTarget.academic_event_id == event.id))
    db.add(
        EventTarget(
            academic_event_id=event.id,
            section=section,
            lab_group=lab_group,
            course_wide=not section and not lab_group,
        )
    )
    task = db.scalar(
        select(UserTask).where(UserTask.user_id == user.id, UserTask.academic_event_id == event.id)
    )
    if task:
        task.relevant = True
        task.relevance_reason = "manually corrected for this user"
    db.commit()
    db.refresh(event)
    return event
