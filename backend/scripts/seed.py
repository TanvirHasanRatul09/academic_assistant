"""Idempotently seed synthetic development records; never use production data."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.models import (
    AcademicEvent,
    ClassroomItem,
    Course,
    CourseMembership,
    EventTarget,
    EventType,
    OnboardingState,
    SourceType,
    User,
    UserProfile,
    UserTask,
)
from app.db.session import SessionLocal

USER_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
COURSE_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
ITEM_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")
EVENT_ID = uuid.UUID("40000000-0000-0000-0000-000000000001")


def seed() -> None:
    now = datetime.now(UTC)
    with SessionLocal.begin() as session:
        user = session.get(User, USER_ID)
        if user is None:
            user = User(
                id=USER_ID,
                email="student@example.invalid",
                display_name="Synthetic Student",
                timezone="Asia/Dhaka",
                onboarding_state=OnboardingState.COMPLETE,
            )
            session.add(user)
            session.add(UserProfile(user_id=USER_ID, section="A", lab_group="A1"))
            session.flush()

        course = session.get(Course, COURSE_ID)
        if course is None:
            course = Course(
                id=COURSE_ID,
                classroom_course_id="synthetic-course-1",
                name="Synthetic Algorithms",
                status="ACTIVE",
            )
            session.add(course)
            session.flush()

        membership = session.scalar(
            select(CourseMembership).where(
                CourseMembership.user_id == USER_ID,
                CourseMembership.course_id == COURSE_ID,
            )
        )
        if membership is None:
            session.add(CourseMembership(user_id=USER_ID, course_id=COURSE_ID, selected=True))
            session.flush()

        item = session.get(ClassroomItem, ITEM_ID)
        if item is None:
            item = ClassroomItem(
                id=ITEM_ID,
                course_id=COURSE_ID,
                source_type=SourceType.COURSEWORK,
                source_id="synthetic-coursework-1",
                title="Synthetic graph assignment",
                body="Synthetic fixture only. No student or Classroom data.",
                source_url="https://classroom.google.com/",
                source_created_at=now,
                source_updated_at=now,
                content_hash="0" * 64,
            )
            session.add(item)
            session.flush()

        event = session.get(AcademicEvent, EVENT_ID)
        if event is None:
            event = AcademicEvent(
                id=EVENT_ID,
                classroom_item_id=ITEM_ID,
                event_type=EventType.ASSIGNMENT,
                due_at=now + timedelta(days=7),
                priority=1,
                action_required=True,
                confidence=1.0,
                extraction_version="seed-v1",
            )
            session.add(event)
            session.flush()
            session.add(EventTarget(academic_event_id=EVENT_ID, course_wide=True))
            session.add(UserTask(user_id=USER_ID, academic_event_id=EVENT_ID, relevant=True))

    print("Synthetic seed data is ready.")


if __name__ == "__main__":
    seed()
