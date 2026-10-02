"""add profile academic fields"""
from alembic import op
import sqlalchemy as sa
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None
def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("academic_level", sa.String(length=128), nullable=True))
    op.add_column("user_profiles", sa.Column("program", sa.String(length=200), nullable=True))
def downgrade() -> None:
    op.drop_column("user_profiles", "program")
    op.drop_column("user_profiles", "academic_level")

