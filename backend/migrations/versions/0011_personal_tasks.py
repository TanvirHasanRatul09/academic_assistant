"""Add owner-scoped personal academic tasks.

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "personal_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("course_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("event_type", sa.String(length=10), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("section", sa.String(length=64), nullable=True),
        sa.Column("lab_group", sa.String(length=64), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("priority >= 0 AND priority <= 3", name="ck_personal_task_priority"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_personal_tasks_user_id", "personal_tasks", ["user_id"])
    op.create_index("ix_personal_tasks_course_id", "personal_tasks", ["course_id"])
    op.create_index("ix_personal_tasks_user_due", "personal_tasks", ["user_id", "due_at"])


def downgrade() -> None:
    op.drop_index("ix_personal_tasks_user_due", table_name="personal_tasks")
    op.drop_index("ix_personal_tasks_course_id", table_name="personal_tasks")
    op.drop_index("ix_personal_tasks_user_id", table_name="personal_tasks")
    op.drop_table("personal_tasks")
