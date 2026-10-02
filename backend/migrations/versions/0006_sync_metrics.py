"""add synchronization progress and timing metrics

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sync_runs",
        sa.Column("courses_processed", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "sync_runs", sa.Column("courses_total", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("sync_runs", sa.Column("current_phase", sa.String(length=64), nullable=True))
    op.add_column(
        "sync_runs",
        sa.Column(
            "timing_metrics", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("sync_runs", "timing_metrics")
    op.drop_column("sync_runs", "current_phase")
    op.drop_column("sync_runs", "courses_total")
    op.drop_column("sync_runs", "courses_processed")
