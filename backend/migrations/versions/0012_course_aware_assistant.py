# ruff: noqa: E501
"""Add deterministic academic item subtypes.

Revision ID: 0012
Revises: 0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "academic_events",
        sa.Column("item_subtype", sa.String(length=32), nullable=False, server_default="other"),
    )
    op.execute(
        """
        UPDATE academic_events AS event
        SET item_subtype = CASE
            WHEN lower(item.title || ' ' || coalesce(item.body, '')) LIKE '%lab final%' THEN 'lab_final'
            WHEN lower(item.title || ' ' || coalesce(item.body, '')) LIKE '%quiz%' THEN 'quiz'
            WHEN lower(item.title || ' ' || coalesce(item.body, '')) LIKE '%midterm%'
              OR lower(item.title || ' ' || coalesce(item.body, '')) LIKE '%mid-term%'
              OR lower(item.title || ' ' || coalesce(item.body, '')) LIKE '%mid exam%' THEN 'midterm'
            WHEN lower(item.title || ' ' || coalesce(item.body, '')) LIKE '%theory final%'
              OR lower(item.title || ' ' || coalesce(item.body, '')) LIKE '%final exam%'
              OR lower(item.title || ' ' || coalesce(item.body, '')) LIKE '%final test%' THEN 'theory_final'
            WHEN lower(item.title || ' ' || coalesce(item.body, '')) ~ '(mark|result|grade|score)' THEN 'marks_or_result'
            WHEN lower(item.title || ' ' || coalesce(item.body, '')) ~ '(online|assessment)[[:space:]]*[0-9]+' THEN 'online_assessment'
            WHEN lower(item.title || ' ' || coalesce(item.body, '')) ~ 'lab[[:space:]]+(task|assignment|work|[0-9]+)' THEN 'lab_task'
            WHEN lower(event.event_type) = 'assignment' THEN 'assignment'
            WHEN lower(event.event_type) = 'material' THEN 'material'
            WHEN lower(event.event_type) = 'notice' THEN 'announcement'
            ELSE 'other'
        END
        FROM classroom_items AS item
        WHERE item.id = event.classroom_item_id
        """
    )
    op.create_index("ix_academic_events_item_subtype", "academic_events", ["item_subtype"])


def downgrade() -> None:
    op.drop_index("ix_academic_events_item_subtype", table_name="academic_events")
    op.drop_column("academic_events", "item_subtype")
