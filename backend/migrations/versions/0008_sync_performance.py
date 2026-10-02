"""add incremental sync checkpoints and job heartbeat

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "course_memberships",
        sa.Column(
            "sync_checkpoint", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False
        ),
    )
    op.add_column("sync_runs", sa.Column("heartbeat_at", sa.DateTime(timezone=True)))
    op.add_column(
        "sync_runs",
        sa.Column(
            "failed_courses", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False
        ),
    )
    op.create_index(
        "uq_sync_runs_one_running_per_user",
        "sync_runs",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    op.drop_index("uq_sync_runs_one_running_per_user", table_name="sync_runs")
    op.drop_column("sync_runs", "failed_courses")
    op.drop_column("sync_runs", "heartbeat_at")
    op.drop_column("course_memberships", "sync_checkpoint")
