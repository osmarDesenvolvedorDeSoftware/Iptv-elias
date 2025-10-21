"""Add database fields to settings"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0012_add_db_fields_to_settings"
down_revision = "0011_add_user_id_to_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("settings")}

    if "db_host" not in existing_columns:
        op.add_column("settings", sa.Column("db_host", sa.String(length=255), nullable=True))
    if "db_port" not in existing_columns:
        op.add_column("settings", sa.Column("db_port", sa.Integer(), nullable=True))
    if "db_user" not in existing_columns:
        op.add_column("settings", sa.Column("db_user", sa.String(length=255), nullable=True))
    if "db_password" not in existing_columns:
        op.add_column("settings", sa.Column("db_password", sa.String(length=512), nullable=True))
    if "db_name" not in existing_columns:
        op.add_column("settings", sa.Column("db_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("settings")}

    if "db_name" in existing_columns:
        op.drop_column("settings", "db_name")
    if "db_password" in existing_columns:
        op.drop_column("settings", "db_password")
    if "db_user" in existing_columns:
        op.drop_column("settings", "db_user")
    if "db_port" in existing_columns:
        op.drop_column("settings", "db_port")
    if "db_host" in existing_columns:
        op.drop_column("settings", "db_host")
