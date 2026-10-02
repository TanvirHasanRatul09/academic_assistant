"""add targeting dimensions and relevance reason

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "event_targets", sa.Column("academic_level", sa.String(length=128), nullable=True)
    )
    op.add_column("event_targets", sa.Column("program", sa.String(length=200), nullable=True))
    op.add_column(
        "user_tasks",
        sa.Column(
            "relevance_reason", sa.String(length=255), server_default="legacy", nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("user_tasks", "relevance_reason")
    op.drop_column("event_targets", "program")
    op.drop_column("event_targets", "academic_level")
