from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.entities import (
    AcademicEvent,
    ClassroomItem,
    CourseMembership,
    EventType,
    Notification,
    UserProfile,
    UserTask,
)

NOTIFICATION_KIND = "new_actionable_item"
DEFAULT_MINIMUM_PRIORITY = 2
SUPPORTED_TYPES = {EventType.ASSIGNMENT, EventType.EXAM, EventType.NOTICE}


def notification_enabled(
    *,
    event_type: EventType,
    priority: int,
    course_id: UUID,
    action_required: bool,
    preferences: dict[str, object],
) -> bool:
    if not action_required or event_type not in SUPPORTED_TYPES:
        return False
    minimum = preferences.get("minimum_priority", DEFAULT_MINIMUM_PRIORITY)
    minimum_priority = (
        minimum
        if isinstance(minimum, int) and not isinstance(minimum, bool)
        else DEFAULT_MINIMUM_PRIORITY
    )
    if priority < max(1, min(3, minimum_priority)):
        return False
    type_key = {
        EventType.ASSIGNMENT: "assignments",
        EventType.EXAM: "exams",
        EventType.NOTICE: "notices",
    }[event_type]
    if preferences.get(type_key, True) is False:
        return False
    return preferences.get(f"course:{course_id}", True) is not False


def create_new_item_notifications(
    db: Session,
    user_id: UUID,
    sync_started_at: datetime,
) -> int:
    profile = db.get(UserProfile, user_id)
    preferences = profile.notification_preferences if profile else {}
    rows = db.execute(
        select(UserTask, AcademicEvent, ClassroomItem)
        .join(AcademicEvent, AcademicEvent.id == UserTask.academic_event_id)
        .join(ClassroomItem, ClassroomItem.id == AcademicEvent.classroom_item_id)
        .join(
            CourseMembership,
            (CourseMembership.course_id == ClassroomItem.course_id)
            & (CourseMembership.user_id == user_id),
        )
        .where(
            CourseMembership.selected.is_(True),
            CourseMembership.enrollment_status == "ACTIVE",
            UserTask.user_id == user_id,
            UserTask.relevant.is_(True),
            UserTask.completed.is_(False),
            ClassroomItem.created_at >= sync_started_at,
        )
    ).all()
    task_ids = [task.id for task, _, _ in rows]
    existing_task_ids = set(
        db.scalars(
            select(Notification.user_task_id).where(
                Notification.user_id == user_id,
                Notification.user_task_id.in_(task_ids),
                Notification.kind == NOTIFICATION_KIND,
            )
        )
    ) if task_ids else set()

    created = 0
    for task, event, item in rows:
        if task.id in existing_task_ids:
            continue
        if not notification_enabled(
            event_type=event.event_type,
            priority=event.priority,
            course_id=item.course_id,
            action_required=event.action_required,
            preferences=preferences,
        ):
            continue
        db.add(
            Notification(
                user_id=user_id,
                user_task_id=task.id,
                kind=NOTIFICATION_KIND,
            )
        )
        created += 1
    db.commit()
    return created

