"""Add user_id to settings"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.sql import text


revision = "0011_add_user_id_to_settings"
down_revision = "0010_create_settings_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    columns = [col["name"] for col in inspector.get_columns("settings")]
    fks = [fk["name"] for fk in inspector.get_foreign_keys("settings")]
    indexes = [idx["name"] for idx in inspector.get_indexes("settings")]
    unique_constraints = [uc["name"] for uc in inspector.get_unique_constraints("settings")]

    needs_column = "user_id" not in columns
    needs_fk = "fk_settings_user_id_users" not in fks and "fk_settings_user_id" not in fks
    has_old_unique = "uq_settings_tenant_key" in indexes or "uq_settings_tenant_key" in unique_constraints
    needs_new_unique = "uq_settings_tenant_user_key" not in unique_constraints

    if bind.dialect.name == "sqlite":
        if needs_column or needs_fk:
            with op.batch_alter_table("settings", recreate="always") as batch_op:
                if needs_column:
                    batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
                if needs_fk:
                    batch_op.create_foreign_key(
                        "fk_settings_user_id_users",
                        "users",
                        ["user_id"],
                        ["id"],
                        ondelete="CASCADE",
                    )
    else:
        if needs_column:
            op.add_column("settings", sa.Column("user_id", sa.Integer(), nullable=True))
        if needs_fk:
            op.create_foreign_key(
                "fk_settings_user_id_users",
                "settings",
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )

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

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("settings", recreate="always") as batch_op:
            batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)

            dropped_old_unique = False
            if has_old_unique:
                try:
                    batch_op.drop_constraint("uq_settings_tenant_key", type_="unique")
                    dropped_old_unique = True
                except Exception:
                    print("⚠️  Índice uq_settings_tenant_key está vinculado, mantendo.")

            if needs_new_unique and (dropped_old_unique or not has_old_unique):
                batch_op.create_unique_constraint(
                    "uq_settings_tenant_user_key", ["tenant_id", "user_id", "key"]
                )
    else:
        op.alter_column("settings", "user_id", existing_type=sa.Integer(), nullable=False)

        dropped_old_unique = False
        if "uq_settings_tenant_key" in indexes:
            try:
                op.drop_constraint("uq_settings_tenant_key", "settings", type_="unique")
                dropped_old_unique = True
            except Exception:
                print("⚠️  Índice uq_settings_tenant_key está vinculado, mantendo.")

        if needs_new_unique and (dropped_old_unique or "uq_settings_tenant_key" not in indexes):
            op.create_unique_constraint(
                "uq_settings_tenant_user_key", "settings", ["tenant_id", "user_id", "key"]
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    unique_constraints = [uc["name"] for uc in inspector.get_unique_constraints("settings")]
    fks = [fk["name"] for fk in inspector.get_foreign_keys("settings")]
    columns = [col["name"] for col in inspector.get_columns("settings")]

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("settings", recreate="always") as batch_op:
            if "uq_settings_tenant_user_key" in unique_constraints:
                batch_op.drop_constraint("uq_settings_tenant_user_key", type_="unique")

            if "uq_settings_tenant_key" not in unique_constraints:
                batch_op.create_unique_constraint("uq_settings_tenant_key", ["tenant_id", "key"])

            if "fk_settings_user_id_users" in fks:
                batch_op.drop_constraint("fk_settings_user_id_users", type_="foreignkey")
            elif "fk_settings_user_id" in fks:
                batch_op.drop_constraint("fk_settings_user_id", type_="foreignkey")

            if "user_id" in columns:
                batch_op.drop_column("user_id")
    else:
        if "uq_settings_tenant_user_key" in unique_constraints:
            op.drop_constraint("uq_settings_tenant_user_key", "settings", type_="unique")

        if "uq_settings_tenant_key" not in unique_constraints:
            op.create_unique_constraint("uq_settings_tenant_key", "settings", ["tenant_id", "key"])

        if "fk_settings_user_id_users" in fks:
            op.drop_constraint("fk_settings_user_id_users", "settings", type_="foreignkey")
        elif "fk_settings_user_id" in fks:
            op.drop_constraint("fk_settings_user_id", "settings", type_="foreignkey")

        if "user_id" in columns:
            op.drop_column("settings", "user_id")
