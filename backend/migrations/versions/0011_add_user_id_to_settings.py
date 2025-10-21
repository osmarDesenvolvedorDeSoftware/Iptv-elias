"""Add user_id to settings"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


revision = "0011_add_user_id_to_settings"
down_revision = "0010_create_settings_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_settings_user_id",
        "settings",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    bind = op.get_bind()
    settings_rows = bind.execute(text("SELECT id, tenant_id FROM settings")).fetchall()
    for row in settings_rows:
        user_id = bind.execute(
            text(
                """
                SELECT id
                FROM users
                WHERE tenant_id = :tenant_id
                ORDER BY CASE WHEN role = 'admin' THEN 0 ELSE 1 END, id
                LIMIT 1
                """
            ),
            {"tenant_id": row.tenant_id},
        ).scalar()
        if user_id is None:
            raise RuntimeError(
                "Não foi possível atribuir user_id ao registro de configuração existente para o tenant %s" % row.tenant_id
            )
        bind.execute(
            text("UPDATE settings SET user_id = :user_id WHERE id = :id"),
            {"user_id": user_id, "id": row.id},
        )

    op.alter_column("settings", "user_id", existing_type=sa.Integer(), nullable=False)
    op.drop_constraint("uq_settings_tenant_key", "settings", type_="unique")
    op.create_unique_constraint("uq_settings_tenant_user_key", "settings", ["tenant_id", "user_id", "key"])


def downgrade() -> None:
    op.drop_constraint("uq_settings_tenant_user_key", "settings", type_="unique")
    op.create_unique_constraint("uq_settings_tenant_key", "settings", ["tenant_id", "key"])
    op.drop_constraint("fk_settings_user_id", "settings", type_="foreignkey")
    op.drop_column("settings", "user_id")
