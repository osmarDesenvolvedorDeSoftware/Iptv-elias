"""Initial database schema"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="admin"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
        sa.Column("eta_sec", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "job_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    tenants_table = sa.Table(
        "tenants",
        sa.MetaData(),
        sa.Column("id", sa.String(length=64)),
        sa.Column("name", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime()),
    )
    users_table = sa.Table(
        "users",
        sa.MetaData(),
        sa.Column("id", sa.Integer()),
        sa.Column("tenant_id", sa.String(length=64)),
        sa.Column("name", sa.String(length=255)),
        sa.Column("email", sa.String(length=255)),
        sa.Column("password_hash", sa.String(length=255)),
        sa.Column("role", sa.String(length=50)),
        sa.Column("created_at", sa.DateTime()),
    )

    now = datetime.utcnow()
    op.bulk_insert(
        tenants_table,
        [
            {"id": "tenant-demo", "name": "Tenant Demo", "created_at": now},
        ],
    )
    op.bulk_insert(
        users_table,
        [
            {
                "tenant_id": "tenant-demo",
                "name": "Admin",
                "email": "admin@tenant.com",
                "password_hash": "$2b$12$JTQqi3ZjF0pUha2MW.i9eeGpEG.tDLFdwstz0cpHhMI7LpmwHbAMS",
                "role": "admin",
                "created_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("job_logs")
    op.drop_table("jobs")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_table("tenants")
