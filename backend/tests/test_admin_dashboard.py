import sys
from pathlib import Path
from http import HTTPStatus

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from flask_jwt_extended import create_access_token
from sqlalchemy.exc import OperationalError

from app import create_app
from app.extensions import db
from app.models import Tenant, User
from werkzeug.security import generate_password_hash


def test_dashboard_handles_missing_last_sync_column(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'admin_dashboard.db'}")

    app = create_app()

    with app.app_context():
        db.drop_all()
        db.create_all()

        tenant = Tenant(id="tenant-demo", name="Tenant Demo")
        user = User(
            tenant_id="tenant-demo",
            name="Admin",
            email="admin@example.com",
            password_hash=generate_password_hash("secret123"),
            role="admin",
        )
        db.session.add_all([tenant, user])
        db.session.commit()

        original_execute = db.session.execute

        def fake_execute(statement, params=None, execution_options=None):
            statement_text = str(statement)
            if (
                "max(" in statement_text
                and "user_configs" in statement_text
                and "last_sync" in statement_text
            ):
                raise OperationalError(
                    statement_text,
                    params,
                    Exception("no such column: user_configs.last_sync"),
                )
            return original_execute(
                statement, params=params, execution_options=execution_options
            )

        monkeypatch.setattr(db.session, "execute", fake_execute)

        with app.test_client() as client:
            with app.test_request_context():
                token = create_access_token(identity=f"{user.id}:{user.tenant_id}")

            response = client.get(
                "/admin/dashboard",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-ID": user.tenant_id,
                },
            )

        assert response.status_code == HTTPStatus.OK
        assert response.json["stats"]["lastSync"] is None

        db.session.remove()
