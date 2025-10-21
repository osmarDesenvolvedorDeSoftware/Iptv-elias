"""Add user config table and status flags"""

from alembic import op
import sqlalchemy as sa


revision = "0007_user_configs_and_status"
down_revision = "0006_tenant_integration_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("users", sa.Column("last_login", sa.DateTime(), nullable=True))
    op.alter_column("users", "role", server_default="user", existing_type=sa.String(length=50))

    op.create_table(
        "user_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("dominio", sa.String(length=255), nullable=True),
        sa.Column("porta", sa.Integer(), nullable=True),
        sa.Column("usuario_api", sa.String(length=255), nullable=True),
        sa.Column("senha_api", sa.String(length=512), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_sync", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.execute("UPDATE users SET is_active = 1")


def downgrade() -> None:
    op.drop_table("user_configs")
    op.drop_column("users", "last_login")
    op.drop_column("users", "is_active")
    op.alter_column("users", "role", server_default="admin", existing_type=sa.String(length=50))
