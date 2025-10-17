"""Streams and series tables ported from legacy"""

from alembic import op
import sqlalchemy as sa


revision = "0005_streams_and_series"
down_revision = "0004_compatibility_source_tags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "streams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("type", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column("group_title", sa.String(length=255), nullable=True),
        sa.Column("is_adult", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("stream_source", sa.JSON(), nullable=False),
        sa.Column("primary_url", sa.String(length=1024), nullable=False),
        sa.Column("target_container", sa.String(length=16), nullable=True),
        sa.Column("source_tag", sa.String(length=255), nullable=True),
        sa.Column("source_tag_filmes", sa.String(length=255), nullable=True),
        sa.Column("tmdb_id", sa.Integer(), nullable=True),
        sa.Column("movie_properties", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "primary_url", name="uq_streams_tenant_url"),
    )
    op.create_index("ix_streams_tenant_type", "streams", ["tenant_id", "type"])
    op.create_index("ix_streams_source_tag", "streams", ["source_tag"])
    op.create_index("ix_streams_source_tag_filmes", "streams", ["source_tag_filmes"])

    op.create_table(
        "streams_series",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("title_base", sa.String(length=255), nullable=False),
        sa.Column("source_tag", sa.String(length=255), nullable=True),
        sa.Column("tmdb_id", sa.Integer(), nullable=True),
        sa.Column("overview", sa.Text(), nullable=True),
        sa.Column("poster", sa.String(length=512), nullable=True),
        sa.Column("backdrop", sa.String(length=512), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("genres", sa.JSON(), nullable=True),
        sa.Column("seasons", sa.Integer(), nullable=True),
        sa.Column("is_adult", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "title_base", "source_tag", name="uq_series_identity"),
    )
    op.create_index("ix_streams_series_source_tag", "streams_series", ["source_tag"])

    op.create_table(
        "streams_episodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("stream_id", sa.Integer(), sa.ForeignKey("streams.id"), nullable=False, unique=True),
        sa.Column("series_id", sa.Integer(), sa.ForeignKey("streams_series.id"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("episode", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_streams_episodes_series", "streams_episodes", ["series_id"])



def downgrade() -> None:
    op.drop_index("ix_streams_episodes_series", table_name="streams_episodes")
    op.drop_table("streams_episodes")
    op.drop_index("ix_streams_series_source_tag", table_name="streams_series")
    op.drop_table("streams_series")
    op.drop_index("ix_streams_source_tag_filmes", table_name="streams")
    op.drop_index("ix_streams_source_tag", table_name="streams")
    op.drop_index("ix_streams_tenant_type", table_name="streams")
    op.drop_table("streams")
