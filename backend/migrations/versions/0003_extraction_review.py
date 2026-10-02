"""Add extraction review and correction metadata.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("academic_events", sa.Column("review_required", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("academic_events", sa.Column("manually_corrected", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("academic_events", sa.Column("extraction_metadata", sa.JSON(), server_default="{}", nullable=False))


def downgrade() -> None:
    op.drop_column("academic_events", "extraction_metadata")
    op.drop_column("academic_events", "manually_corrected")
    op.drop_column("academic_events", "review_required")
