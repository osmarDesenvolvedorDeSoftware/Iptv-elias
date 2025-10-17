"""Add job metrics columns and index"""

from alembic import op
import sqlalchemy as sa


revision = "0002_job_metrics"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("inserted", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "jobs",
        sa.Column("updated", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "jobs",
        sa.Column("ignored", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "jobs",
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "jobs",
        sa.Column("duration_sec", sa.Integer(), nullable=True),
    )

    op.create_index("ix_jobs_tenant_type_started", "jobs", ["tenant_id", "type", "started_at"])

    with op.batch_alter_table("jobs") as batch_op:
        batch_op.alter_column("inserted", server_default=None)
        batch_op.alter_column("updated", server_default=None)
        batch_op.alter_column("ignored", server_default=None)
        batch_op.alter_column("errors", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_jobs_tenant_type_started", table_name="jobs")
    op.drop_column("jobs", "duration_sec")
    op.drop_column("jobs", "errors")
    op.drop_column("jobs", "ignored")
    op.drop_column("jobs", "updated")
    op.drop_column("jobs", "inserted")
