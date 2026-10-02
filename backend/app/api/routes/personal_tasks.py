# ruff: noqa: B008
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_csrf
from app.core.rate_limit import rate_limit
from app.db.models.entities import Course, CourseMembership, PersonalTask, User
from app.db.session import get_db
from app.schemas.personal_tasks import PersonalTaskInput, PersonalTaskOutput, PersonalTaskUpdate

router = APIRouter(prefix="/api/personal-tasks", tags=["personal-tasks"])


def _course(db: Session, user_id: UUID, course_id: UUID | None) -> Course | None:
    if course_id is None:
        return None
    course = db.scalar(
        select(Course)
        .join(CourseMembership, CourseMembership.course_id == Course.id)
        .where(
            Course.id == course_id,
            Course.status == "ACTIVE",
            CourseMembership.user_id == user_id,
            CourseMembership.selected.is_(True),
            CourseMembership.enrollment_status == "ACTIVE",
        )
    )
    if not course:
        raise HTTPException(status_code=422, detail="Course is not active and selected")
    return course


def _output(task: PersonalTask, course: Course | None = None) -> PersonalTaskOutput:
    return PersonalTaskOutput.model_validate(
        {**task.__dict__, "course_name": course.name if course else None}, from_attributes=True
    )


@router.get("", response_model=list[PersonalTaskOutput])
def list_personal_tasks(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[PersonalTaskOutput]:
    rows = db.execute(
        select(PersonalTask, Course)
        .outerjoin(Course, Course.id == PersonalTask.course_id)
        .where(PersonalTask.user_id == user.id)
        .order_by(
            PersonalTask.completed,
            PersonalTask.due_at.asc().nulls_last(),
            PersonalTask.created_at.desc(),
        )
        .limit(200)
    ).all()
    return [_output(task, course) for task, course in rows]


@router.post(
    "",
    response_model=PersonalTaskOutput,
    status_code=201,
    dependencies=[Depends(require_csrf), Depends(rate_limit("personal-task-create", 30, 60))],
)
def create_personal_task(
    payload: PersonalTaskInput,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PersonalTaskOutput:
    course = _course(db, user.id, payload.course_id)
    task = PersonalTask(user_id=user.id, **payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return _output(task, course)


@router.patch(
    "/{task_id}",
    response_model=PersonalTaskOutput,
    dependencies=[Depends(require_csrf), Depends(rate_limit("personal-task-update", 60, 60))],
)
def update_personal_task(
    task_id: UUID,
    payload: PersonalTaskUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PersonalTaskOutput:
    task = db.scalar(
        select(PersonalTask)
        .where(PersonalTask.id == task_id, PersonalTask.user_id == user.id)
        .with_for_update()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Personal task not found")
    values = payload.model_dump(exclude_unset=True)
    resulting_start = values.get("starts_at", task.starts_at)
    resulting_due = values.get("due_at", task.due_at)
    if resulting_start and resulting_due and resulting_due < resulting_start:
        raise HTTPException(status_code=422, detail="due_at must not be before starts_at")
    course = _course(db, user.id, values.get("course_id", task.course_id))
    for key, value in values.items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return _output(task, course)


@router.delete(
    "/{task_id}",
    status_code=204,
    dependencies=[Depends(require_csrf), Depends(rate_limit("personal-task-delete", 30, 60))],
)
def delete_personal_task(
    task_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    task = db.scalar(
        select(PersonalTask)
        .where(PersonalTask.id == task_id, PersonalTask.user_id == user.id)
        .with_for_update()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Personal task not found")
    db.delete(task)
    db.commit()
    return Response(status_code=204)
