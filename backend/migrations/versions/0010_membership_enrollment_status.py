"""Add per-user Classroom enrollment status.

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "course_memberships",
        sa.Column(
            "enrollment_status",
            sa.String(length=32),
            nullable=False,
            server_default="ACTIVE",
        ),
    )
    op.create_index(
        "ix_course_memberships_enrollment_status",
        "course_memberships",
        ["enrollment_status"],
    )
    op.alter_column("course_memberships", "enrollment_status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_course_memberships_enrollment_status", table_name="course_memberships")
    op.drop_column("course_memberships", "enrollment_status")