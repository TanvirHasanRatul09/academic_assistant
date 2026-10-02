import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OnboardingState(enum.StrEnum):
    PENDING = "pending"
    COMPLETE = "complete"


class SourceType(enum.StrEnum):
    ANNOUNCEMENT = "announcement"
    COURSEWORK = "coursework"
    MATERIAL = "material"
    MANUAL = "manual"


class EventType(enum.StrEnum):
    ASSIGNMENT = "assignment"
    EXAM = "exam"
    NOTICE = "notice"
    MATERIAL = "material"
    OTHER = "other"


class ItemSubtype(enum.StrEnum):
    QUIZ = "quiz"
    LAB_FINAL = "lab_final"
    THEORY_FINAL = "theory_final"
    MIDTERM = "midterm"
    ASSIGNMENT = "assignment"
    LAB_TASK = "lab_task"
    ONLINE_ASSESSMENT = "online_assessment"
    ANNOUNCEMENT = "announcement"
    CLASS = "class"
    MATERIAL = "material"
    MARKS_OR_RESULT = "marks_or_result"
    OTHER = "other"


class SyncStatus(enum.StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    onboarding_state: Mapped[OnboardingState] = mapped_column(
        Enum(OnboardingState, name="onboarding_state", native_enum=False),
        nullable=False,
        default=OnboardingState.PENDING,
    )

    profile: Mapped["UserProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", single_parent=True
    )


class UserProfile(TimestampMixin, Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    section: Mapped[str | None] = mapped_column(String(64))
    lab_group: Mapped[str | None] = mapped_column(String(64))
    academic_level: Mapped[str | None] = mapped_column(String(128))
    program: Mapped[str | None] = mapped_column(String(200))
    notification_preferences: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    user: Mapped[User] = relationship(back_populates="profile")


class OAuthAccount(TimestampMixin, Base):
    __tablename__ = "oauth_accounts"
    __table_args__ = (UniqueConstraint("provider", "provider_subject"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_access_token: Mapped[bytes | None] = mapped_column(LargeBinary)
    encrypted_refresh_token: Mapped[bytes | None] = mapped_column(LargeBinary)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reauthenticated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Course(TimestampMixin, Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="google")
    classroom_course_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    __table_args__ = (UniqueConstraint("provider", "classroom_course_id"),)


class CourseMembership(TimestampMixin, Base):
    __tablename__ = "course_memberships"
    __table_args__ = (UniqueConstraint("user_id", "course_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enrollment_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE", index=True
    )
    sync_checkpoint: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    course: Mapped[Course] = relationship()


class ClassroomItem(TimestampMixin, Base):
    __tablename__ = "classroom_items"
    __table_args__ = (
        UniqueConstraint("course_id", "source_type", "source_id"),
        Index("ix_classroom_items_course_created", "course_id", "source_created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type", native_enum=False), nullable=False
    )
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class AcademicEvent(TimestampMixin, Base):
    __tablename__ = "academic_events"
    __table_args__ = (
        UniqueConstraint("classroom_item_id", "extraction_version"),
        Index("ix_academic_events_due_at", "due_at"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_event_confidence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    classroom_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classroom_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, name="event_type", native_enum=False), nullable=False
    )
    item_subtype: Mapped[ItemSubtype] = mapped_column(
        Enum(
            ItemSubtype,
            name="item_subtype",
            native_enum=False,
            values_callable=lambda values: [item.value for item in values],
        ),
        nullable=False,
        default=ItemSubtype.OTHER,
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    action_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    extraction_version: Mapped[str] = mapped_column(String(32), nullable=False)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    manually_corrected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extraction_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class EventTarget(Base):
    __tablename__ = "event_targets"
    __table_args__ = (
        UniqueConstraint("academic_event_id", "section", "lab_group"),
        CheckConstraint(
            "course_wide OR section IS NOT NULL OR lab_group IS NOT NULL",
            name="ck_event_target_present",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    academic_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_events.id", ondelete="CASCADE"), nullable=False
    )
    section: Mapped[str | None] = mapped_column(String(64))
    lab_group: Mapped[str | None] = mapped_column(String(64))
    academic_level: Mapped[str | None] = mapped_column(String(128))
    program: Mapped[str | None] = mapped_column(String(200))
    course_wide: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class UserTask(TimestampMixin, Base):
    __tablename__ = "user_tasks"
    __table_args__ = (
        UniqueConstraint("user_id", "academic_event_id"),
        Index("ix_user_tasks_relevance", "user_id", "relevant", "completed"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_events.id", ondelete="CASCADE"), nullable=False
    )
    relevant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    relevance_reason: Mapped[str] = mapped_column(String(255), nullable=False, default="legacy")
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PersonalTask(TimestampMixin, Base):
    __tablename__ = "personal_tasks"
    __table_args__ = (
        Index("ix_personal_tasks_user_due", "user_id", "due_at"),
        CheckConstraint("priority >= 0 AND priority <= 3", name="ck_personal_task_priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, name="personal_task_event_type", native_enum=False),
        nullable=False,
        default=EventType.ASSIGNMENT,
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    section: Mapped[str | None] = mapped_column(String(64))
    lab_group: Mapped[str | None] = mapped_column(String(64))
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "user_task_id", "kind"),
        Index("ix_notifications_user_unread", "user_id", "read_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    user_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_tasks.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SyncRun(Base):
    __tablename__ = "sync_runs"
    __table_args__ = (
        Index("ix_sync_runs_user_started", "user_id", "started_at"),
        Index(
            "uq_sync_runs_one_running_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
        Index(
            "ix_sync_runs_claimable",
            "status",
            "current_phase",
            "lease_expires_at",
            "started_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus, name="sync_status", native_enum=False), nullable=False
    )
    checkpoint: Mapped[str | None] = mapped_column(String(1000))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_changed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    courses_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    courses_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_phase: Mapped[str | None] = mapped_column(String(64))
    timing_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_courses: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    safe_error_code: Mapped[str | None] = mapped_column(String(64))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
