from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes.extraction import review_queue
from app.db.base import Base
from app.db.models.entities import (
    AcademicEvent,
    ClassroomItem,
    Course,
    CourseMembership,
    EventTarget,
    EventType,
    ItemSubtype,
    OnboardingState,
    SourceType,
    User,
    UserProfile,
)


def test_review_queue_hides_items_for_other_lab_groups() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(
            email="review@example.test",
            display_name="Student",
            timezone="Asia/Dhaka",
            onboarding_state=OnboardingState.COMPLETE,
        )
        course = Course(
            provider="google",
            classroom_course_id="review-course",
            name="AI Lab",
            status="ACTIVE",
            provider_metadata={},
        )
        db.add_all([user, course])
        db.flush()
        db.add_all([
            UserProfile(
                user_id=user.id,
                section="A",
                lab_group="A1",
                notification_preferences={},
            ),
            CourseMembership(
                user_id=user.id,
                course_id=course.id,
                selected=True,
                enrollment_status="ACTIVE",
            ),
        ])
        now = datetime.now(UTC)
        events = []
        for index, group in enumerate(("a1", "b2")):
            item = ClassroomItem(
                course_id=course.id,
                source_type=SourceType.ANNOUNCEMENT,
                source_id=f"review-{index}",
                title=f"{group.upper()} lab notice",
                body=None,
                source_url=f"https://classroom.google.com/review-{index}",
                source_created_at=now,
                source_updated_at=now,
                content_hash=str(index) * 64,
                provider_metadata={},
            )
            db.add(item)
            db.flush()
            event = AcademicEvent(
                classroom_item_id=item.id,
                event_type=EventType.NOTICE,
                item_subtype=ItemSubtype.ANNOUNCEMENT,
                priority=1,
                action_required=False,
                confidence=.5,
                extraction_version=f"test-{index}",
                review_required=True,
                extraction_metadata={},
            )
            db.add(event)
            db.flush()
            db.add(EventTarget(academic_event_id=event.id, lab_group=group, course_wide=False))
            events.append(event)
        db.commit()

        result = review_queue(0, 25, user, db)

        assert result.total == 1
        assert [item.title for item in result.items] == ["A1 lab notice"]
