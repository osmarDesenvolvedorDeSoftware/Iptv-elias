"""Compatibilidade com source_tag legacy"""

from alembic import op
import sqlalchemy as sa


revision = "0004_compatibility_source_tags"
down_revision = "0003_bouquets_and_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("source_tag", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("source_tag_filmes", sa.String(length=255), nullable=True))

    with op.batch_alter_table("bouquet_items") as batch_op:
        batch_op.add_column(sa.Column("source_tag", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("source_tag_filmes", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("bouquet_items") as batch_op:
        batch_op.drop_column("source_tag_filmes")
        batch_op.drop_column("source_tag")

    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_column("source_tag_filmes")
        batch_op.drop_column("source_tag")
