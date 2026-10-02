import uuid

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.models import AcademicEvent, ClassroomItem, CourseMembership, UserTask


class UserTaskRepository:
    """Private task queries always scope access through the authenticated user ID."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, user_id: uuid.UUID, task_id: uuid.UUID) -> UserTask | None:
        return self.session.scalar(
            select(UserTask).where(UserTask.id == task_id, UserTask.user_id == user_id)
        )

    def list_relevant(self, user_id: uuid.UUID) -> list[UserTask]:
        statement: Select[tuple[UserTask]] = (
            select(UserTask)
            .join(AcademicEvent, AcademicEvent.id == UserTask.academic_event_id)
            .join(ClassroomItem, ClassroomItem.id == AcademicEvent.classroom_item_id)
            .join(
                CourseMembership,
                (CourseMembership.course_id == ClassroomItem.course_id)
                & (CourseMembership.user_id == user_id),
            )
            .where(UserTask.user_id == user_id, UserTask.relevant.is_(True))
            .order_by(AcademicEvent.due_at.asc().nulls_last())
        )
        return list(self.session.scalars(statement))

    def set_completed(
        self, user_id: uuid.UUID, task_id: uuid.UUID, *, completed: bool
    ) -> UserTask | None:
        task = self.get(user_id, task_id)
        if task is None:
            return None
        task.completed = completed
        self.session.flush()
        return task
