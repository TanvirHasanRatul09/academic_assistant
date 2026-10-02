from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_csrf
from app.core.rate_limit import rate_limit
from app.db.models.entities import (
    AcademicEvent,
    ClassroomItem,
    Course,
    CourseMembership,
    Notification,
    User,
    UserProfile,
    UserTask,
)
from app.db.session import get_db
from app.schemas.notifications import (
    NotificationCoursePreference,
    NotificationItem,
    NotificationList,
    NotificationPreferencesInput,
    NotificationPreferencesOutput,
    UnreadCount,
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _owned_notification(db: Session, user_id: UUID, notification_id: UUID) -> Notification:
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


def _unread_count(db: Session, user_id: UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .join(UserTask, UserTask.id == Notification.user_task_id)
            .join(AcademicEvent, AcademicEvent.id == UserTask.academic_event_id)
            .join(ClassroomItem, ClassroomItem.id == AcademicEvent.classroom_item_id)
            .join(
                CourseMembership,
                (CourseMembership.course_id == ClassroomItem.course_id)
                & (CourseMembership.user_id == user_id),
            )
            .where(
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
                Notification.dismissed_at.is_(None),
                CourseMembership.selected.is_(True),
                CourseMembership.enrollment_status == "ACTIVE",
            )
        )
        or 0
    )


@router.get("", response_model=NotificationList)
def list_notifications(
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationList:
    rows = db.execute(
        select(Notification, UserTask, AcademicEvent, ClassroomItem, Course)
        .join(UserTask, UserTask.id == Notification.user_task_id)
        .join(AcademicEvent, AcademicEvent.id == UserTask.academic_event_id)
        .join(ClassroomItem, ClassroomItem.id == AcademicEvent.classroom_item_id)
        .join(Course, Course.id == ClassroomItem.course_id)
        .join(
            CourseMembership,
            (CourseMembership.course_id == Course.id)
            & (CourseMembership.user_id == user.id),
        )
        .where(
            Notification.user_id == user.id,
            CourseMembership.selected.is_(True),
            CourseMembership.enrollment_status == "ACTIVE",
            UserTask.user_id == user.id,
            Notification.dismissed_at.is_(None),
        )
        .order_by(Notification.created_at.desc())
        .limit(limit)
    ).all()
    return NotificationList(
        items=[
            NotificationItem(
                id=notification.id,
                kind=notification.kind,
                created_at=notification.created_at,
                read_at=notification.read_at,
                dismissed_at=notification.dismissed_at,
                task_id=task.id,
                title=item.title,
                course_name=course.name,
                event_type=event.event_type,
                priority=event.priority,
                due_at=event.due_at,
                source_url=item.source_url,
            )
            for notification, task, event, item, course in rows
        ],
        unread_count=_unread_count(db, user.id),
    )


@router.get("/unread-count", response_model=UnreadCount)
def unread_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UnreadCount:
    return UnreadCount(unread_count=_unread_count(db, user.id))


@router.post(
    "/{notification_id}/read",
    status_code=204,
    dependencies=[Depends(require_csrf), Depends(rate_limit("notification-state", 120, 60))],
)
def mark_read(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    notification = _owned_notification(db, user.id, notification_id)
    notification.read_at = notification.read_at or datetime.now(UTC)
    db.commit()
    return Response(status_code=204)


@router.post(
    "/actions/read-all",
    status_code=204,
    dependencies=[Depends(require_csrf), Depends(rate_limit("notification-read-all", 10, 60))],
)
def mark_all_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    now = datetime.now(UTC)
    notifications = db.scalars(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.read_at.is_(None),
            Notification.dismissed_at.is_(None),
        )
    )
    for notification in notifications:
        notification.read_at = now
    db.commit()
    return Response(status_code=204)


@router.delete(
    "/{notification_id}",
    status_code=204,
    dependencies=[Depends(require_csrf), Depends(rate_limit("notification-state", 120, 60))],
)
def dismiss(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    notification = _owned_notification(db, user.id, notification_id)
    notification.dismissed_at = datetime.now(UTC)
    db.commit()
    return Response(status_code=204)


@router.get("/preferences", response_model=NotificationPreferencesOutput)
def get_preferences(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationPreferencesOutput:
    profile = db.get(UserProfile, user.id)
    preferences = profile.notification_preferences if profile else {}
    courses = list(
        db.scalars(
            select(Course)
            .join(CourseMembership, CourseMembership.course_id == Course.id)
            .where(
                CourseMembership.user_id == user.id,
                CourseMembership.selected.is_(True),
                CourseMembership.enrollment_status == "ACTIVE",
            )
            .order_by(Course.name)
        )
    )
    minimum = preferences.get("minimum_priority", 2)
    return NotificationPreferencesOutput(
        assignments=preferences.get("assignments", True) is not False,
        exams=preferences.get("exams", True) is not False,
        notices=preferences.get("notices", True) is not False,
        minimum_priority=(
            minimum
            if isinstance(minimum, int) and not isinstance(minimum, bool)
            else 2
        ),
        courses=[
            NotificationCoursePreference(
                id=course.id,
                name=course.name,
                enabled=preferences.get(f"course:{course.id}", True) is not False,
            )
            for course in courses
        ],
    )


@router.put(
    "/preferences",
    response_model=NotificationPreferencesOutput,
    dependencies=[Depends(require_csrf), Depends(rate_limit("notification-preferences", 20, 60))],
)
def update_preferences(
    payload: NotificationPreferencesInput,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationPreferencesOutput:
    profile = db.get(UserProfile, user.id)
    if not profile:
        raise HTTPException(status_code=409, detail="Complete onboarding first")
    owned_courses = set(
        db.scalars(
            select(CourseMembership.course_id).where(
                CourseMembership.user_id == user.id,
                CourseMembership.selected.is_(True),
                CourseMembership.enrollment_status == "ACTIVE",
            )
        )
    )
    if not set(payload.course_preferences).issubset(owned_courses):
        raise HTTPException(status_code=403, detail="A course preference is not available")
    preferences: dict[str, object] = {
        "assignments": payload.assignments,
        "exams": payload.exams,
        "notices": payload.notices,
        "minimum_priority": payload.minimum_priority,
    }
    preferences.update(
        {
            f"course:{course_id}": enabled
            for course_id, enabled in payload.course_preferences.items()
        }
    )
    profile.notification_preferences = preferences
    db.commit()
    return get_preferences(user=user, db=db)


