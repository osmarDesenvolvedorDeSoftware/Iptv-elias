"""Add xui_db_uri column to user_configs"""

from alembic import op
import sqlalchemy as sa


revision = "0008_add_xui_db_uri_to_user_configs"
down_revision = "0007_user_configs_and_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_configs", sa.Column("xui_db_uri", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("user_configs", "xui_db_uri")
