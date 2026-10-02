"""add durable sync worker leases

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sync_runs", sa.Column("worker_id", sa.String(length=128)))
    op.add_column("sync_runs", sa.Column("lease_expires_at", sa.DateTime(timezone=True)))
    op.add_column(
        "sync_runs",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index(
        "ix_sync_runs_claimable",
        "sync_runs",
        ["status", "current_phase", "lease_expires_at", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_sync_runs_claimable", table_name="sync_runs")
    op.drop_column("sync_runs", "attempt_count")
    op.drop_column("sync_runs", "lease_expires_at")
    op.drop_column("sync_runs", "worker_id")
