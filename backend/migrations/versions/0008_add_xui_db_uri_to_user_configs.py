"""Add xui_db_uri column to user_configs"""

from alembic import op
import sqlalchemy as sa


revision = "0008_add_xui_db_uri_to_user_configs"
down_revision = "0007_user_configs_and_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("user_configs")}

    if "xui_db_uri" not in columns:
        op.add_column("user_configs", sa.Column("xui_db_uri", sa.String(length=512), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("user_configs")}

    if "xui_db_uri" in columns:
        op.drop_column("user_configs", "xui_db_uri")
