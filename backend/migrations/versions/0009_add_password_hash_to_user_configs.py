"""Add password_hash column to user_configs"""

from alembic import op
import sqlalchemy as sa

revision = "0009_add_user_password_hash"
down_revision = "0008_add_xui_db_uri"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_configs", sa.Column("password_hash", sa.String(length=256), nullable=True))


def downgrade() -> None:
    op.drop_column("user_configs", "password_hash")
