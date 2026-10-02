from uuid import UUID

from fastapi.testclient import TestClient

from app.db.models.entities import EventType
from app.main import app
from app.schemas.notifications import NotificationPreferencesInput
from app.services.notifications.generator import notification_enabled

client = TestClient(app)
COURSE_ID = UUID("f825f23b-d461-4de7-a9a3-c904ca69f6a4")


def test_notification_rule_requires_actionable_supported_priority() -> None:
    assert notification_enabled(
        event_type=EventType.ASSIGNMENT,
        priority=2,
        course_id=COURSE_ID,
        action_required=True,
        preferences={},
    )
    assert not notification_enabled(
        event_type=EventType.MATERIAL,
        priority=3,
        course_id=COURSE_ID,
        action_required=True,
        preferences={},
    )
    assert not notification_enabled(
        event_type=EventType.EXAM,
        priority=3,
        course_id=COURSE_ID,
        action_required=False,
        preferences={},
    )


def test_notification_preferences_suppress_type_course_and_low_priority() -> None:
    assert not notification_enabled(
        event_type=EventType.ASSIGNMENT,
        priority=3,
        course_id=COURSE_ID,
        action_required=True,
        preferences={"assignments": False},
    )
    assert not notification_enabled(
        event_type=EventType.EXAM,
        priority=3,
        course_id=COURSE_ID,
        action_required=True,
        preferences={f"course:{COURSE_ID}": False},
    )
    assert not notification_enabled(
        event_type=EventType.NOTICE,
        priority=2,
        course_id=COURSE_ID,
        action_required=True,
        preferences={"minimum_priority": 3},
    )


def test_notification_preferences_are_bounded() -> None:
    settings = NotificationPreferencesInput(minimum_priority=3)
    assert settings.minimum_priority == 3


def test_notification_endpoints_require_authentication() -> None:
    assert client.get("/api/notifications").status_code == 401
    assert client.get("/api/notifications/unread-count").status_code == 401
    assert client.get("/api/notifications/preferences").status_code == 401

