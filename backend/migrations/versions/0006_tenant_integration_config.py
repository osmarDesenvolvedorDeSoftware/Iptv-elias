"""Tenant integration configuration table"""

from alembic import op
import sqlalchemy as sa


revision = "0006_tenant_integration_config"
down_revision = "0005_streams_and_series"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_integration_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), sa.ForeignKey("tenants.id"), nullable=False, unique=True),
        sa.Column("xui_db_uri", sa.String(length=512), nullable=True),
        sa.Column("xtream_base_url", sa.String(length=512), nullable=True),
        sa.Column("xui_api_user", sa.String(length=128), nullable=True),
        sa.Column("xui_api_pass", sa.String(length=256), nullable=True),
        sa.Column("tmdb_key", sa.String(length=128), nullable=True),
        sa.Column("ignore_prefixes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("ignore_categories", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("tenant_integration_configs")
