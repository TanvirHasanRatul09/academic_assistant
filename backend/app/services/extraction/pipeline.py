import uuid
from collections import defaultdict
from itertools import product
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models.entities import (
    AcademicEvent,
    ClassroomItem,
    CourseMembership,
    EventTarget,
    User,
    UserProfile,
    UserTask,
)
from app.services.extraction.rules import (
    RULE_VERSION,
    Extraction,
    extract,
    normalize_lab_group,
    normalize_level,
    normalize_program,
    normalize_section,
)

STALE_REPROCESS_LIMIT = 50


def relevance_decision(profile: UserProfile | None, result: Extraction) -> tuple[bool, str]:
    if result.review_required:
        return False, "ambiguous targeting; queued for review"
    dimensions = (
        ("section", normalize_section(getattr(profile, "section", None)), result.sections),
        ("lab group", normalize_lab_group(getattr(profile, "lab_group", None)), result.lab_groups),
        (
            "academic level",
            normalize_level(getattr(profile, "academic_level", None)),
            result.academic_levels,
        ),
        ("program", normalize_program(getattr(profile, "program", None)), result.programs),
    )
    targeted = [(name, value, targets) for name, value, targets in dimensions if targets]
    if not targeted:
        return True, "general course-wide content"
    for name, value, targets in targeted:
        if value is None:
            return False, f"profile has no {name}; item targets {', '.join(targets)}"
        if value not in targets:
            return False, f"{name} {value} does not match {', '.join(targets)}"
    matched = ", ".join(f"{name} {value}" for name, value, _targets in targeted)
    return True, f"matched {matched}"


def relevance(profile: UserProfile | None, result: Extraction) -> bool:
    return relevance_decision(profile, result)[0]


def process_user(
    db: Session,
    user_id: UUID,
    *,
    item_ids: set[UUID] | None = None,
    include_stale: bool = True,
) -> dict[str, int]:
    user = db.get(User, user_id)
    if not user:
        return {"processed": 0, "created": 0, "review_required": 0}
    memberships = list(
        db.scalars(
            select(CourseMembership).where(
                CourseMembership.user_id == user_id,
                CourseMembership.selected.is_(True),
                CourseMembership.enrollment_status == "ACTIVE"
            )
        )
    )
    course_ids = {membership.course_id for membership in memberships}
    if not course_ids:
        return {"processed": 0, "created": 0, "review_required": 0}
    item_query = select(ClassroomItem).where(ClassroomItem.course_id.in_(course_ids))
    if item_ids is not None:
        stale_item_ids = set(
            db.scalars(
                select(ClassroomItem.id)
                .join(AcademicEvent, AcademicEvent.classroom_item_id == ClassroomItem.id)
                .where(
                    ClassroomItem.course_id.in_(course_ids),
                    AcademicEvent.extraction_version != RULE_VERSION,
                    AcademicEvent.manually_corrected.is_(False),
                )
                .limit(STALE_REPROCESS_LIMIT)
            )
        )
        target_ids = item_ids | stale_item_ids if include_stale else item_ids
        if not target_ids:
            return {"processed": 0, "created": 0, "review_required": 0}
        item_query = item_query.where(ClassroomItem.id.in_(target_ids))
    items = list(db.scalars(item_query))
    item_ids = {item.id for item in items}
    events = (
        list(
            db.scalars(
                select(AcademicEvent).where(
                    AcademicEvent.classroom_item_id.in_(item_ids),
                )
            )
        )
        if item_ids
        else []
    )
    events_by_item = {event.classroom_item_id: event for event in events}
    extracted: list[tuple[ClassroomItem, AcademicEvent, Extraction]] = []
    created = review_count = 0
    for item in items:
        result = extract(
            title=item.title,
            body=item.body,
            source_type=item.source_type,
            source_created_at=item.source_created_at,
            provider_metadata=item.provider_metadata,
            timezone_name=user.timezone,
        )
        event = events_by_item.get(item.id)
        if event and event.manually_corrected:
            continue
        if not event:
            event = AcademicEvent(
                id=uuid.uuid4(), classroom_item_id=item.id, extraction_version=RULE_VERSION
            )
            db.add(event)
            events_by_item[item.id] = event
            created += 1
        event.extraction_version = RULE_VERSION
        event.event_type = result.event_type
        event.item_subtype = result.item_subtype
        event.starts_at = result.starts_at
        event.due_at = result.due_at
        event.priority = result.priority
        event.action_required = result.action_required
        event.confidence = result.confidence
        event.review_required = result.review_required
        event.extraction_metadata = result.metadata
        extracted.append((item, event, result))
        review_count += int(result.review_required)
    event_ids = [event.id for _, event, _ in extracted]
    if event_ids:
        db.execute(delete(EventTarget).where(EventTarget.academic_event_id.in_(event_ids)))
    all_memberships = list(
        db.scalars(
            select(CourseMembership).where(
                CourseMembership.course_id.in_(course_ids),
                CourseMembership.selected.is_(True),
                CourseMembership.enrollment_status == "ACTIVE"
            )
        )
    )
    memberships_by_course: dict[UUID, list[CourseMembership]] = defaultdict(list)
    for membership in all_memberships:
        memberships_by_course[membership.course_id].append(membership)
    member_ids = {membership.user_id for membership in all_memberships}
    profiles = (
        {
            profile.user_id: profile
            for profile in db.scalars(
                select(UserProfile).where(UserProfile.user_id.in_(member_ids))
            )
        }
        if member_ids
        else {}
    )
    tasks = (
        list(db.scalars(select(UserTask).where(UserTask.academic_event_id.in_(event_ids))))
        if event_ids
        else []
    )
    tasks_by_key = {(task.user_id, task.academic_event_id): task for task in tasks}
    for item, event, result in extracted:
        dimensions = (result.sections, result.lab_groups, result.academic_levels, result.programs)
        if not any(dimensions):
            db.add(EventTarget(academic_event_id=event.id, course_wide=True))
        else:
            for section, group, level, program_name in product(
                result.sections or (None,),
                result.lab_groups or (None,),
                result.academic_levels or (None,),
                result.programs or (None,),
            ):
                db.add(
                    EventTarget(
                        academic_event_id=event.id,
                        section=section,
                        lab_group=group,
                        academic_level=level,
                        program=program_name,
                    )
                )
        for membership in memberships_by_course[item.course_id]:
            key = (membership.user_id, event.id)
            task = tasks_by_key.get(key)
            if not task:
                task = UserTask(
                    user_id=membership.user_id, academic_event_id=event.id, relevant=True
                )
                db.add(task)
                tasks_by_key[key] = task
            task.relevant, task.relevance_reason = relevance_decision(
                profiles.get(membership.user_id), result
            )
    db.commit()
    return {"processed": len(items), "created": created, "review_required": review_count}
