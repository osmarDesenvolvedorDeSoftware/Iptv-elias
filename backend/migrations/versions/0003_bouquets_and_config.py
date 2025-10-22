"""Bouquets and configuration tables"""

from alembic import op
import sqlalchemy as sa


revision = "0003_bouquets_and_config"
down_revision = "0002_job_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bouquets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_bouquets_tenant_name"),
    )

    op.create_table(
        "bouquet_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bouquet_id", sa.Integer(), sa.ForeignKey("bouquets.id"), nullable=False),
        sa.Column("content_id", sa.String(length=128), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("bouquet_id", "content_id", name="uq_bouquet_items_unique"),
    )
    op.create_index(
        "ix_bouquet_items_bouquet_id_created",
        "bouquet_items",
        ["bouquet_id", "created_at"],
    )

    op.create_table(
        "configurations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), sa.ForeignKey("tenants.id"), nullable=False, unique=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_table("configurations")
    op.drop_index("ix_bouquet_items_bouquet_id_created", table_name="bouquet_items")
    op.drop_table("bouquet_items")
    op.drop_table("bouquets")
